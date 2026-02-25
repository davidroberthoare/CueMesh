"""CueMesh Controller WebSocket server."""
from __future__ import annotations
import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional, Callable
import websockets
from websockets.server import WebSocketServerProtocol

from shared.protocol import (
    make_envelope, parse_envelope,
    MSG_HELLO, MSG_AUTH, MSG_READY, MSG_STATUS, MSG_DRIFT,
    MSG_HEARTBEAT, MSG_LOG, MSG_SYNC_REPLY,
    MSG_HELLO_ACK, MSG_ACCEPT, MSG_REJECT, MSG_LOAD_CUE,
    MSG_READY_CHECK, MSG_PLAY_AT, MSG_PAUSE, MSG_STOP,
    MSG_SEEK_TO, MSG_SET_RATE, MSG_SET_VOLUME, MSG_BLACKOUT,
    MSG_SHOW_TESTSCREEN, MSG_REQUEST_STATUS, MSG_SYNC,
    STATE_IDLE,
)
from shared.clock_sync import ClockSyncState, SyncSample

logger = logging.getLogger("cuemesh.controller.server")

DEFAULT_PORT = 9420


class ClientSession:
    """Represents a connected client."""

    def __init__(self, ws: WebSocketServerProtocol, client_id: str, hostname: str,
                 platform: str, capabilities: dict):
        self.ws = ws
        self.client_id = client_id
        self.hostname = hostname
        self.platform = platform
        self.capabilities = capabilities
        self.token: Optional[str] = None
        self.name: str = hostname
        self.status: str = "pending"  # pending | accepted | rejected
        self.state: str = STATE_IDLE
        self.cue_id: Optional[str] = None
        self.position_ms: int = 0
        self.rate: float = 1.0
        self.volume: int = 100
        self.drift_ms: float = 0.0
        self.last_heartbeat: float = time.time()
        self.last_error: Optional[str] = None
        self.clock_sync = ClockSyncState()
        self._sync_t1: Optional[int] = None

    @property
    def is_accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def heartbeat_age(self) -> float:
        return time.time() - self.last_heartbeat

    async def send(self, msg_type: str, payload: dict) -> None:
        try:
            await self.ws.send(make_envelope(msg_type, payload))
        except Exception as e:
            logger.warning("Failed to send to %s: %s", self.client_id, e)


class ControllerServer:
    """
    Manages WebSocket connections from clients.
    Emits events via callbacks for the UI layer.
    """

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.controller_id = str(uuid.uuid4())
        self.session_id = str(uuid.uuid4())
        self._clients: dict[str, ClientSession] = {}  # client_id -> session
        self._trusted: dict[str, str] = {}  # client_id -> token
        self._ws_server = None
        self._running = False

        # Callbacks (set by UI)
        self.on_client_hello: Optional[Callable] = None
        self.on_client_status: Optional[Callable] = None
        self.on_client_log: Optional[Callable] = None
        self.on_client_drift: Optional[Callable] = None
        self.on_client_disconnected: Optional[Callable] = None

    @property
    def clients(self) -> dict[str, ClientSession]:
        return self._clients

    def load_trusted(self, trusted: dict[str, str]) -> None:
        """Load persisted trusted client tokens."""
        self._trusted = dict(trusted)

    async def start(self) -> None:
        self._running = True
        self._ws_server = await websockets.serve(
            self._handle_client, "0.0.0.0", self.port
        )
        logger.info("Controller server listening on port %d", self.port)
        asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        self._running = False
        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()

    async def _handle_client(self, ws: WebSocketServerProtocol) -> None:
        session: Optional[ClientSession] = None
        try:
            async for raw in ws:
                msg_type, ts, payload = parse_envelope(raw)
                if msg_type == MSG_HELLO:
                    session = await self._on_hello(ws, payload)
                elif session and msg_type == MSG_AUTH:
                    await self._on_auth(session, payload)
                elif session and msg_type == MSG_STATUS:
                    await self._on_status(session, payload)
                elif session and msg_type == MSG_DRIFT:
                    await self._on_drift(session, payload)
                elif session and msg_type == MSG_HEARTBEAT:
                    session.last_heartbeat = time.time()
                elif session and msg_type == MSG_LOG:
                    await self._on_log(session, payload)
                elif session and msg_type == MSG_SYNC_REPLY:
                    await self._on_sync_reply(session, ts, payload)
                elif session and msg_type == MSG_READY:
                    if self.on_client_status:
                        self.on_client_status(session)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if session:
                del self._clients[session.client_id]
                logger.info("Client disconnected: %s", session.client_id)
                if self.on_client_disconnected:
                    self.on_client_disconnected(session)

    async def _on_hello(self, ws: WebSocketServerProtocol, payload: dict) -> ClientSession:
        client_id = payload.get("client_id", str(uuid.uuid4()))
        hostname = payload.get("hostname", "unknown")
        platform = payload.get("platform", "unknown")
        capabilities = payload.get("capabilities", {})
        token = payload.get("token")

        session = ClientSession(ws, client_id, hostname, platform, capabilities)
        self._clients[client_id] = session

        await session.send(MSG_HELLO_ACK, {
            "controller_id": self.controller_id,
            "session_id": self.session_id,
        })

        # Check if already trusted
        if token and self._trusted.get(client_id) == token:
            session.token = token
            session.status = "accepted"
            logger.info("Client auto-accepted (trusted): %s", client_id)
        else:
            logger.info("Client pending: %s (%s)", client_id, hostname)

        if self.on_client_hello:
            self.on_client_hello(session)
        return session

    async def _on_auth(self, session: ClientSession, payload: dict) -> None:
        token = payload.get("token")
        if token and self._trusted.get(session.client_id) == token:
            session.token = token
            session.status = "accepted"
            if self.on_client_status:
                self.on_client_status(session)

    async def _on_status(self, session: ClientSession, payload: dict) -> None:
        session.state = payload.get("state", session.state)
        session.cue_id = payload.get("cue_id")
        session.position_ms = payload.get("position_ms", 0)
        session.rate = payload.get("rate", 1.0)
        session.volume = payload.get("volume", 100)
        session.last_error = payload.get("last_error")
        session.last_heartbeat = time.time()
        if self.on_client_status:
            self.on_client_status(session)

    async def _on_drift(self, session: ClientSession, payload: dict) -> None:
        session.drift_ms = payload.get("drift_ms", 0.0)
        if self.on_client_drift:
            self.on_client_drift(session, payload)

    async def _on_log(self, session: ClientSession, payload: dict) -> None:
        if self.on_client_log:
            self.on_client_log(session, payload)

    async def _on_sync_reply(self, session: ClientSession, ts: int, payload: dict) -> None:
        t4 = int(time.time() * 1000)
        t1 = payload.get("t1_utc_ms", 0)
        t2 = payload.get("t2_client_recv_utc_ms", 0)
        t3 = payload.get("t3_client_send_utc_ms", 0)
        sample = SyncSample(t1=t1, t2=t2, t3=t3, t4=t4)
        session.clock_sync.add_sample(sample)

    async def _sync_loop(self) -> None:
        """Periodically send SYNC to all accepted clients."""
        while self._running:
            await asyncio.sleep(5.0)
            t1 = int(time.time() * 1000)
            for session in list(self._clients.values()):
                if session.is_accepted:
                    await session.send(MSG_SYNC, {"t1_utc_ms": t1})

    # ---- Command methods called by UI ----

    async def accept_client(self, client_id: str, name: str = "") -> None:
        session = self._clients.get(client_id)
        if not session:
            return
        token = str(uuid.uuid4())
        session.token = token
        session.status = "accepted"
        if name:
            session.name = name
        self._trusted[client_id] = token
        await session.send(MSG_ACCEPT, {"token": token, "assigned_name": session.name})
        logger.info("Accepted client: %s as '%s'", client_id, session.name)

    async def reject_client(self, client_id: str, reason: str = "Rejected by operator") -> None:
        session = self._clients.get(client_id)
        if not session:
            return
        session.status = "rejected"
        await session.send(MSG_REJECT, {"reason": reason})

    async def broadcast_accepted(self, msg_type: str, payload: dict) -> None:
        """Send a message to all accepted clients."""
        for session in list(self._clients.values()):
            if session.is_accepted:
                await session.send(msg_type, payload)

    async def send_load_cue(self, cue) -> None:
        payload = {
            "cue_id": cue.id,
            "type": cue.type,
            "asset_relpath": cue.file,
            "start_time_ms": cue.start_time_ms,
            "volume": cue.volume,
            "loop": cue.loop,
            "fade_in_ms": cue.fade_in_ms,
            "fade_out_ms": cue.fade_out_ms,
        }
        if cue.end_time_ms is not None:
            payload["end_time_ms"] = cue.end_time_ms
        await self.broadcast_accepted(MSG_LOAD_CUE, payload)

    async def send_play_at(self, cue_id: str, start_lead_ms: int = 250) -> None:
        master_start = int(time.time() * 1000) + start_lead_ms
        await self.broadcast_accepted(MSG_PLAY_AT, {
            "cue_id": cue_id,
            "master_start_utc_ms": master_start,
        })
        return master_start

    async def send_pause(self) -> None:
        await self.broadcast_accepted(MSG_PAUSE, {})

    async def send_stop(self) -> None:
        await self.broadcast_accepted(MSG_STOP, {})

    async def send_blackout(self, on: bool) -> None:
        await self.broadcast_accepted(MSG_BLACKOUT, {"on": on})

    async def send_testscreen(self, on: bool) -> None:
        await self.broadcast_accepted(MSG_SHOW_TESTSCREEN, {"on": on})

    async def send_seek(self, position_ms: int) -> None:
        await self.broadcast_accepted(MSG_SEEK_TO, {"position_ms": position_ms})

    async def send_set_rate(self, rate: float) -> None:
        await self.broadcast_accepted(MSG_SET_RATE, {"rate": rate})

    async def send_set_volume(self, volume: int) -> None:
        await self.broadcast_accepted(MSG_SET_VOLUME, {"volume": volume})

    async def request_status_all(self) -> None:
        await self.broadcast_accepted(MSG_REQUEST_STATUS, {})

    def get_trusted_dict(self) -> dict[str, str]:
        return dict(self._trusted)
