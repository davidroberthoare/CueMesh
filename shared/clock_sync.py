"""CueMesh clock sync math (lightweight NTP-like over WebSocket)."""
from __future__ import annotations
import statistics
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SyncSample:
    t1: int  # controller send time (utc ms)
    t2: int  # client recv time (local ms)
    t3: int  # client send time (local ms)
    t4: int  # controller recv time (utc ms)

    @property
    def rtt_ms(self) -> int:
        return (self.t4 - self.t1) - (self.t3 - self.t2)

    @property
    def offset_ms(self) -> float:
        """Estimated offset: client_time - controller_time. Positive means client is ahead."""
        return ((self.t2 - self.t1) + (self.t3 - self.t4)) / 2.0


class ClockSyncState:
    """Maintains rolling window of sync samples and computes offset estimate."""

    WINDOW = 8
    OUTLIER_FACTOR = 2.0

    def __init__(self) -> None:
        self._samples: list[SyncSample] = []
        self._offset_ms: float = 0.0

    def add_sample(self, sample: SyncSample) -> None:
        self._samples.append(sample)
        if len(self._samples) > self.WINDOW:
            self._samples.pop(0)
        self._recompute()

    def _recompute(self) -> None:
        if not self._samples:
            return
        offsets = [s.offset_ms for s in self._samples]
        rtts = [s.rtt_ms for s in self._samples]
        # Reject high-RTT outliers
        if len(rtts) >= 3:
            median_rtt = statistics.median(rtts)
            good = [s for s in self._samples if s.rtt_ms <= median_rtt * self.OUTLIER_FACTOR]
        else:
            good = self._samples
        if good:
            self._offset_ms = statistics.median([s.offset_ms for s in good])

    @property
    def offset_ms(self) -> float:
        """Current estimated offset: client_local_time - master_time."""
        return self._offset_ms

    def master_now_ms(self, local_utc_ms: Optional[int] = None) -> int:
        """Convert local UTC ms to estimated master time ms."""
        if local_utc_ms is None:
            local_utc_ms = int(time.time() * 1000)
        return int(local_utc_ms - self._offset_ms)

    @property
    def sample_count(self) -> int:
        return len(self._samples)


def compute_drift_correction(
    drift_ms: float,
    max_drift_ms: int,
    hard_seek_threshold_ms: int,
    rate_min: float,
    rate_max: float,
) -> tuple[str, float]:
    """
    Returns (action, rate_or_seek_position).
    action: "none" | "rate_adjust" | "hard_seek"
    For rate_adjust: second value is the new playback rate.
    For hard_seek: second value is meaningless (caller uses expected_pos).
    For none: second value is 1.0.
    """
    abs_drift = abs(drift_ms)
    if abs_drift > hard_seek_threshold_ms:
        return "hard_seek", 1.0
    if abs_drift <= max_drift_ms:
        # Proportional rate correction
        # drift > 0 means playing ahead: slow down (rate < 1)
        # drift < 0 means playing behind: speed up (rate > 1)
        scale = abs_drift / max_drift_ms
        if drift_ms > 0:
            rate = 1.0 - scale * (1.0 - rate_min)
            rate = max(rate_min, rate)
        else:
            rate = 1.0 + scale * (rate_max - 1.0)
            rate = min(rate_max, rate)
        return "rate_adjust", round(rate, 4)
    return "none", 1.0
