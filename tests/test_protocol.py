"""Tests for protocol message parsing."""
import json
import pytest
from shared.protocol import make_envelope, parse_envelope, VALID_STATES


def test_make_envelope_basic():
    msg = make_envelope("HELLO", {"client_id": "abc123"})
    data = json.loads(msg)
    assert data["type"] == "HELLO"
    assert "ts_utc_ms" in data
    assert data["payload"]["client_id"] == "abc123"


def test_parse_envelope():
    raw = json.dumps({"type": "STATUS", "ts_utc_ms": 1234567890, "payload": {"state": "playing"}})
    msg_type, ts, payload = parse_envelope(raw)
    assert msg_type == "STATUS"
    assert ts == 1234567890
    assert payload["state"] == "playing"


def test_valid_states():
    assert "idle" in VALID_STATES
    assert "playing" in VALID_STATES
    assert "error" in VALID_STATES
    assert "black" in VALID_STATES
    assert "invalid_state" not in VALID_STATES


def test_round_trip():
    payload = {"cue_id": "q1", "master_start_utc_ms": 9999999999}
    raw = make_envelope("PLAY_AT", payload)
    msg_type, _, parsed = parse_envelope(raw)
    assert msg_type == "PLAY_AT"
    assert parsed["cue_id"] == "q1"
    assert parsed["master_start_utc_ms"] == 9999999999
