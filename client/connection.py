"""CueMesh client WebSocket connection to controller."""
from __future__ import annotations
import asyncio
import json
import logging
import platform
import socket
import time
import uuid
from pathlib import Path
from typing import Optional

import websockets
from websockets.client import WebSocketClientProtocol

from shared.protocol import (
    make_envelope, parse_envelope,
    MSG_HELLO, MSG_AUTH, MSG_STATUS, MSG_HEARTBEAT,
    MSG_HELLO_ACK, MSG_ACCEPT, MSG_REJECT,
    MSG_LOAD_CUE, MSG_PLAY_AT, MSG_PAUSE, MSG_STOP,
    MSG_SEEK_TO, MSG_SET_RATE, MSG_SET_VOLUME,
    MSG_BLACKOUT, MSG_SHOW_TESTSCREEN, MSG_REQUEST_STATUS,
    MSG_SYNC,
    STATE_IDLE, STATE_LOADING, STATE_READY, STATE_PLAYING,
    STATE_PAUSED, STATE_ERROR, STATE_BLACK,
)
from client.clock_client import ClockClient
from client.mpv_controller import MpvController

logger = logging.getLogger("cuemesh.client.connection")

TOKEN_FILE = Path("cuemesh_client_token.json")


def _load_token() -> tuple[str, Optional[str]]:
    """Load client_id and token from local file."""
    if TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text())
            return data.get("client_id", str(uuid.uuid4())), data.get("token")
        except Exception:
            pass
    cid = str(uuid.uuid4())
    _save_token(cid, None)
    return cid, None


def _save_token(client_id: str, token: Optional[str]) -> None:
    TOKEN_FILE.write_text(json.dumps({"client_id": client_id, "token": token}))


class ClientConnection:
    """Manages connection to the controller and drives mpv."""

    def __init__(self, mpv: MpvController, on_state_change=None, on_error=None, on_testscreen=None):
        self.mpv = mpv
        self.on_state_change = on_state_change  # callback(state_str)
        self.on_error = on_error
        self.on_testscreen = on_testscreen  # callback(on: bool)
        self.client_id, self.token = _load_token()
        self.hostname = socket.gethostname()
        self.platform_str = f"{platform.system()} {platform.machine()}"
        self.state = STATE_IDLE
        self._ws: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._dropout_policy = "continue"
        self._clock = ClockClient(self._send, mpv)
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._current_cue_id: Optional[str] = None

    async def _send(self, msg_type: str, payload: dict) -> None:
        if self._ws:
            try:
                await self._ws.send(make_envelope(msg_type, payload))
            except Exception as e:
                logger.warning("Send error: %s", e)

    async def connect(self, host: str, port: int = 9420) -> None:
        """Connect to controller and process messages until disconnected."""
        self._running = True
        uri = f"ws://{host}:{port}"
        logger.info("Connecting to %s", uri)
        try:
            async with websockets.connect(uri, ping_interval=10, ping_timeout=30) as ws:
                self._ws = ws
                await self._do_hello()
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                async for raw in ws:
                    try:
                        await self._handle_message(raw)
                    except Exception as e:
                        logger.error("Message handling error: %s", e)
        except Exception as e:
            logger.warning("Connection lost: %s", e)
            await self._handle_dropout()
        finally:
            self._ws = None
            if self._heartbeat_task:
                self._heartbeat_task.cancel()

    async def disconnect(self) -> None:
        """Disconnect from controller."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
                logger.info("Disconnected from controller")
            except Exception as e:
                logger.warning("Error during disconnect: %s", e)
        self._set_state(STATE_IDLE)

    async def _do_hello(self) -> None:
        await self._send(MSG_HELLO, {
            "client_id": self.client_id,
            "hostname": self.hostname,
            "platform": self.platform_str,
            "capabilities": {"mpv": True},
            "token": self.token,
        })

    async def _heartbeat_loop(self) -> None:
        while self._running and self._ws:
            await asyncio.sleep(5.0)
            await self._send(MSG_HEARTBEAT, {"local_utc_ms": int(time.time() * 1000)})
            await self._send_status()

    async def _send_status(self) -> None:
        pos = await self.mpv.get_position_ms() if self.mpv.is_connected else None
        await self._send(MSG_STATUS, {
            "state": self.state,
            "cue_id": self._current_cue_id,
            "position_ms": pos or 0,
            "rate": 1.0,
            "volume": 100,
            "fullscreen": True,
        })

    async def _handle_message(self, raw: str) -> None:
        msg_type, ts, payload = parse_envelope(raw)
        logger.debug("Recv: %s", msg_type)

        if msg_type == MSG_HELLO_ACK:
            logger.info("Accepted by controller session: %s", payload.get("session_id"))

        elif msg_type == MSG_ACCEPT:
            self.token = payload.get("token")
            _save_token(self.client_id, self.token)
            logger.info("Accepted! Token saved.")

        elif msg_type == MSG_REJECT:
            logger.warning("Rejected: %s", payload.get("reason"))
            self._running = False

        elif msg_type == MSG_LOAD_CUE:
            await self._handle_load_cue(payload)

        elif msg_type == MSG_PLAY_AT:
            await self._handle_play_at(payload)

        elif msg_type == MSG_PAUSE:
            await self.mpv.pause()
            self._set_state(STATE_PAUSED)
            self._clock.set_stopped()

        elif msg_type == MSG_STOP:
            await self.mpv.stop()
            self._set_state(STATE_IDLE)
            self._clock.set_stopped()

        elif msg_type == MSG_SEEK_TO:
            pos = payload.get("position_ms", 0)
            await self.mpv.seek(pos)

        elif msg_type == MSG_SET_RATE:
            rate = payload.get("rate", 1.0)
            await self.mpv.set_speed(rate)

        elif msg_type == MSG_SET_VOLUME:
            vol = payload.get("volume", 100)
            await self.mpv.set_volume(vol)

        elif msg_type == MSG_BLACKOUT:
            on = payload.get("on", True)
            if on:
                await self.mpv.blackout()
                self._set_state(STATE_BLACK)
                self._clock.set_stopped()
            else:
                # Restore: load last cue or idle
                self._set_state(STATE_IDLE)

        elif msg_type == MSG_SHOW_TESTSCREEN:
            on = payload.get("on", True)
            if self.on_testscreen:
                self.on_testscreen(on)

        elif msg_type == MSG_REQUEST_STATUS:
            await self._send_status()

        elif msg_type == MSG_SYNC:
            await self._clock.handle_sync(payload)

    async def _handle_load_cue(self, payload: dict) -> None:
        self._set_state(STATE_LOADING)
        cue_id = payload.get("cue_id")
        rel_path = payload.get("asset_relpath", "")
        volume = payload.get("volume", 100)
        loop = payload.get("loop", False)
        fullscreen = payload.get("fullscreen", True)  # Use setting from show, default to True
        fade_in_ms = payload.get("fade_in_ms", 0)
        fade_out_ms = payload.get("fade_out_ms", 0)
        end_time_ms = payload.get("end_time_ms")
        self._current_cue_id = cue_id
        
        # Show full path for debugging
        full_path = (self.mpv.media_root / rel_path).resolve()
        logger.info("Loading cue %s: %s", cue_id, rel_path)
        logger.info("  Full system path: %s", full_path)
        logger.info("  Media root: %s", self.mpv.media_root)
        logger.info("  Fade: in=%dms, out=%dms", fade_in_ms, fade_out_ms)
        
        ok = await self.mpv.load_file(rel_path, fade_in_ms, fade_out_ms, end_time_ms)
        if ok:
            await self.mpv.set_volume(volume)
            await self.mpv.set_loop(loop)
            await self.mpv.set_fullscreen(fullscreen)
            self._set_state(STATE_READY)
            logger.info("Cue %s ready", cue_id)
            await self._send("READY", {"cue_id": cue_id})
        else:
            self._set_state(STATE_ERROR)
            logger.error("Failed to load cue %s (file: %s)", cue_id, full_path)
            await self._send("ERROR", {"cue_id": cue_id, "reason": f"Failed to load file: {full_path}"})

    async def _handle_play_at(self, payload: dict) -> None:
        cue_id = payload.get("cue_id")
        master_start_utc_ms = payload.get("master_start_utc_ms", 0)

        # Compute local scheduled time
        now_local_ms = int(time.time() * 1000)
        master_now = self._clock.local_to_master(now_local_ms)
        delay_ms = master_start_utc_ms - master_now
        delay_s = max(0.0, delay_ms / 1000.0)

        logger.info("Scheduled play for cue %s in %.0fms", cue_id, delay_ms)

        if delay_s > 0:
            await asyncio.sleep(delay_s)

        await self.mpv.play()
        self._set_state(STATE_PLAYING)

        # Start drift correction
        cue_start_ms = 0  # TODO: get from cue payload
        self._clock.set_playing(master_start_utc_ms, cue_start_ms)

    async def _handle_dropout(self) -> None:
        """Handle controller disconnect."""
        logger.warning("Controller disconnected; policy=%s", self._dropout_policy)
        if self._dropout_policy == "freeze":
            await self.mpv.pause()
            self._set_state(STATE_PAUSED)
        elif self._dropout_policy == "black":
            await self.mpv.blackout()
            self._set_state(STATE_BLACK)
        # "continue": keep playing
        self._clock.set_stopped()

    def _set_state(self, state: str) -> None:
        self.state = state
        if self.on_state_change:
            self.on_state_change(state)

    def set_dropout_policy(self, policy: str) -> None:
        self._dropout_policy = policy
