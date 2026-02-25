"""CueMesh network protocol definitions."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def make_envelope(msg_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": msg_type, "ts_utc_ms": _now_ms(), "payload": payload})


def parse_envelope(raw: str) -> tuple[str, int, dict[str, Any]]:
    data = json.loads(raw)
    return data["type"], data.get("ts_utc_ms", 0), data.get("payload", {})


# ---- Controller → Client message types ----
MSG_HELLO_ACK = "HELLO_ACK"
MSG_ACCEPT = "ACCEPT"
MSG_REJECT = "REJECT"
MSG_LOAD_CUE = "LOAD_CUE"
MSG_READY_CHECK = "READY_CHECK"
MSG_PLAY_AT = "PLAY_AT"
MSG_PAUSE = "PAUSE"
MSG_STOP = "STOP"
MSG_SEEK_TO = "SEEK_TO"
MSG_SET_RATE = "SET_RATE"
MSG_SET_VOLUME = "SET_VOLUME"
MSG_BLACKOUT = "BLACKOUT"
MSG_SHOW_TESTSCREEN = "SHOW_TESTSCREEN"
MSG_REQUEST_STATUS = "REQUEST_STATUS"
MSG_SYNC = "SYNC"

# ---- Client → Controller message types ----
MSG_HELLO = "HELLO"
MSG_AUTH = "AUTH"
MSG_READY = "READY"
MSG_STATUS = "STATUS"
MSG_DRIFT = "DRIFT"
MSG_HEARTBEAT = "HEARTBEAT"
MSG_LOG = "LOG"
MSG_SYNC_REPLY = "SYNC_REPLY"

# ---- Client states ----
STATE_IDLE = "idle"
STATE_LOADING = "loading"
STATE_READY = "ready"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_ERROR = "error"
STATE_BLACK = "black"

VALID_STATES = {STATE_IDLE, STATE_LOADING, STATE_READY, STATE_PLAYING, STATE_PAUSED, STATE_ERROR, STATE_BLACK}
