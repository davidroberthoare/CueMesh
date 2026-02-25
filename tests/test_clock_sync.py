"""Tests for clock sync math and drift correction."""
import pytest
from shared.clock_sync import SyncSample, ClockSyncState, compute_drift_correction


def test_sync_sample_rtt():
    s = SyncSample(t1=1000, t2=1010, t3=1020, t4=1035)
    # RTT = (1035 - 1000) - (1020 - 1010) = 35 - 10 = 25
    assert s.rtt_ms == 25


def test_sync_sample_offset():
    # Symmetric: t1=1000, t2=1012, t3=1012, t4=1024 -> offset = ((12-0)+(12-24))/2 = 0/2 = 0...
    # Actually: offset = ((t2-t1) + (t3-t4))/2 = ((1012-1000) + (1012-1024))/2 = (12 + (-12))/2 = 0
    s = SyncSample(t1=1000, t2=1012, t3=1012, t4=1024)
    assert s.offset_ms == 0.0


def test_sync_sample_positive_offset():
    # Client is 5ms ahead of controller
    # t1=1000 (ctrl sends), t2=1005+5=1010 (client sees: 1010 if 5ms ahead),
    # t3=1015 (client sends back), t4=1020 (ctrl receives)
    # offset = ((1010-1000) + (1015-1020))/2 = (10 + -5)/2 = 2.5
    s = SyncSample(t1=1000, t2=1010, t3=1015, t4=1020)
    assert s.offset_ms == 2.5


def test_clock_sync_state_empty():
    state = ClockSyncState()
    assert state.offset_ms == 0.0
    assert state.sample_count == 0


def test_clock_sync_state_single_sample():
    state = ClockSyncState()
    state.add_sample(SyncSample(t1=1000, t2=1012, t3=1012, t4=1024))
    assert state.offset_ms == 0.0


def test_clock_sync_state_multiple_samples():
    state = ClockSyncState()
    # Add several samples with consistent 10ms offset (client 10ms ahead)
    for i in range(5):
        state.add_sample(SyncSample(
            t1=i * 1000,
            t2=i * 1000 + 15,  # client 10ms ahead + 5ms half-RTT
            t3=i * 1000 + 20,
            t4=i * 1000 + 30,  # 10ms RTT
        ))
    # offset = ((15) + (20-30))/2 = (15-10)/2 = 2.5
    # With consistent samples, median should be 2.5
    assert state.sample_count == 5
    assert abs(state.offset_ms - 2.5) < 1.0


def test_clock_sync_state_outlier_rejection():
    state = ClockSyncState()
    # Add good samples
    for i in range(6):
        state.add_sample(SyncSample(t1=1000 * i, t2=1000 * i + 10, t3=1000 * i + 10, t4=1000 * i + 20))
    # Add outlier with huge RTT
    state.add_sample(SyncSample(t1=9000, t2=9500, t3=9500, t4=10000))
    # Offset should still be close to 0 (the good samples)
    assert abs(state.offset_ms) < 5.0


def test_drift_correction_none():
    action, rate = compute_drift_correction(
        drift_ms=50.0, max_drift_ms=150, hard_seek_threshold_ms=300,
        rate_min=0.98, rate_max=1.02
    )
    assert action == "rate_adjust"
    assert 0.98 <= rate <= 1.02


def test_drift_correction_hard_seek():
    action, rate = compute_drift_correction(
        drift_ms=400.0, max_drift_ms=150, hard_seek_threshold_ms=300,
        rate_min=0.98, rate_max=1.02
    )
    assert action == "hard_seek"


def test_drift_correction_slow_down_when_ahead():
    # drift > 0 means ahead, should slow down (rate < 1)
    action, rate = compute_drift_correction(
        drift_ms=100.0, max_drift_ms=150, hard_seek_threshold_ms=300,
        rate_min=0.98, rate_max=1.02
    )
    assert action == "rate_adjust"
    assert rate < 1.0


def test_drift_correction_speed_up_when_behind():
    # drift < 0 means behind, should speed up (rate > 1)
    action, rate = compute_drift_correction(
        drift_ms=-100.0, max_drift_ms=150, hard_seek_threshold_ms=300,
        rate_min=0.98, rate_max=1.02
    )
    assert action == "rate_adjust"
    assert rate > 1.0


def test_drift_correction_rate_clamped():
    action, rate = compute_drift_correction(
        drift_ms=1000.0, max_drift_ms=150, hard_seek_threshold_ms=300,
        rate_min=0.98, rate_max=1.02
    )
    # Over threshold: hard seek
    assert action == "hard_seek"
