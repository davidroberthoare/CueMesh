"""CueMesh client-side clock sync."""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional

from shared.clock_sync import ClockSyncState, SyncSample, compute_drift_correction
from shared.protocol import make_envelope, MSG_SYNC_REPLY, MSG_DRIFT

logger = logging.getLogger("cuemesh.client.clock")


class ClockClient:
    """
    Manages clock sync with the controller and drift correction during playback.
    """

    def __init__(self, send_func, mpv=None):
        """
        send_func: async callable(msg_type, payload) to send WS messages
        mpv: MpvController instance for drift correction
        """
        self.send = send_func
        self.mpv = mpv
        self.sync_state = ClockSyncState()
        self._cue_start_master_ms: Optional[int] = None
        self._cue_start_time_ms: int = 0
        self._max_drift_ms: int = 150
        self._hard_seek_threshold_ms: int = 300
        self._rate_min: float = 0.98
        self._rate_max: float = 1.02
        self._sync_interval_ms: int = 1000
        self._drift_task: Optional[asyncio.Task] = None
        self._playing: bool = False

    def configure(self, sync_config) -> None:
        """Configure from SyncConfig dataclass."""
        self._max_drift_ms = sync_config.max_drift_ms
        self._hard_seek_threshold_ms = sync_config.correction.hard_seek_threshold_ms
        self._rate_min = sync_config.correction.rate_min
        self._rate_max = sync_config.correction.rate_max
        self._sync_interval_ms = sync_config.correction.sync_interval_ms

    async def handle_sync(self, payload: dict) -> None:
        """Called when SYNC message received from controller."""
        t1 = payload.get("t1_utc_ms", 0)
        t2 = int(time.time() * 1000)
        t3 = int(time.time() * 1000)
        await self.send(MSG_SYNC_REPLY, {
            "t1_utc_ms": t1,
            "t2_client_recv_utc_ms": t2,
            "t3_client_send_utc_ms": t3,
        })

    def set_playing(self, master_start_utc_ms: int, cue_start_time_ms: int = 0) -> None:
        self._cue_start_master_ms = master_start_utc_ms
        self._cue_start_time_ms = cue_start_time_ms
        self._playing = True
        if self._drift_task:
            self._drift_task.cancel()
        self._drift_task = asyncio.create_task(self._drift_loop())

    def set_stopped(self) -> None:
        self._playing = False
        self._cue_start_master_ms = None
        if self._drift_task:
            self._drift_task.cancel()
            self._drift_task = None

    def local_to_master(self, local_ms: Optional[int] = None) -> int:
        """Convert local time to estimated master time."""
        return self.sync_state.master_now_ms(local_ms)

    async def _drift_loop(self) -> None:
        """Periodically compute drift and apply correction."""
        interval = self._sync_interval_ms / 1000.0
        while self._playing and self._cue_start_master_ms is not None:
            await asyncio.sleep(interval)
            if not self._playing or self.mpv is None:
                continue
            try:
                await self._correct_drift()
            except Exception as e:
                logger.error("Drift correction error: %s", e)

    async def _correct_drift(self) -> None:
        master_now = self.local_to_master()
        elapsed = master_now - self._cue_start_master_ms
        expected_pos_ms = elapsed + self._cue_start_time_ms
        actual_pos_ms = await self.mpv.get_position_ms()
        if actual_pos_ms is None:
            return

        drift_ms = actual_pos_ms - expected_pos_ms
        action, rate = compute_drift_correction(
            drift_ms=float(drift_ms),
            max_drift_ms=self._max_drift_ms,
            hard_seek_threshold_ms=self._hard_seek_threshold_ms,
            rate_min=self._rate_min,
            rate_max=self._rate_max,
        )

        if action == "rate_adjust":
            await self.mpv.set_speed(rate)
        elif action == "hard_seek":
            await self.mpv.seek(max(0, expected_pos_ms))
            await self.mpv.set_speed(1.0)
            rate = 1.0

        # Report drift to controller
        await self.send(MSG_DRIFT, {
            "offset_ms": self.sync_state.offset_ms,
            "drift_ms": float(drift_ms),
            "action": action,
        })

        logger.debug("Drift: %.1fms -> action=%s rate=%.3f", drift_ms, action, rate)
