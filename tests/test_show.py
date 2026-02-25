"""Tests for show file parsing and validation."""
import pytest
from pathlib import Path
import tempfile
import os
from shared.show import load_show, save_show, Show, Cue, SyncConfig, SyncCorrection


EXAMPLE_TOML = """\
[show]
title = "Test Show"
version = 1
created_utc = "2026-01-01T00:00:00+00:00"
modified_utc = "2026-01-01T00:00:00+00:00"
media_root = "./cuemesh_media"
dropout_policy = "continue"

[show.sync]
mode = "medium"
max_drift_ms = 150
start_lead_ms = 250

[show.sync.correction]
rate_min = 0.98
rate_max = 1.02
hard_seek_threshold_ms = 300
sync_interval_ms = 1000

[[cues]]
id = "cue-001"
name = "Test Image"
type = "image"
file = "images/test.png"
volume = 100
loop = false
fade_in_ms = 0
fade_out_ms = 0

[[cues]]
id = "cue-002"
name = "Test Video"
type = "video"
file = "videos/test.webm"
start_time_ms = 0
end_time_ms = 10000
volume = 85
loop = false
fade_in_ms = 500
fade_out_ms = 500
auto_follow_ms = 200
notes = "Test video cue"
"""


def test_load_show_basic():
    with tempfile.NamedTemporaryFile(suffix=".cuemesh.toml", mode="wb", delete=False) as f:
        f.write(EXAMPLE_TOML.encode())
        path = Path(f.name)
    try:
        show = load_show(path)
        assert show.title == "Test Show"
        assert show.version == 1
        assert show.media_root == "./cuemesh_media"
        assert show.dropout_policy == "continue"
        assert len(show.cues) == 2
    finally:
        os.unlink(path)


def test_load_show_sync_config():
    with tempfile.NamedTemporaryFile(suffix=".cuemesh.toml", mode="wb", delete=False) as f:
        f.write(EXAMPLE_TOML.encode())
        path = Path(f.name)
    try:
        show = load_show(path)
        assert show.sync.mode == "medium"
        assert show.sync.max_drift_ms == 150
        assert show.sync.start_lead_ms == 250
        assert show.sync.correction.rate_min == 0.98
        assert show.sync.correction.rate_max == 1.02
        assert show.sync.correction.hard_seek_threshold_ms == 300
        assert show.sync.correction.sync_interval_ms == 1000
    finally:
        os.unlink(path)


def test_load_show_cue_fields():
    with tempfile.NamedTemporaryFile(suffix=".cuemesh.toml", mode="wb", delete=False) as f:
        f.write(EXAMPLE_TOML.encode())
        path = Path(f.name)
    try:
        show = load_show(path)
        cue1 = show.cues[0]
        assert cue1.id == "cue-001"
        assert cue1.type == "image"
        assert cue1.file == "images/test.png"
        assert cue1.volume == 100
        assert cue1.loop is False

        cue2 = show.cues[1]
        assert cue2.id == "cue-002"
        assert cue2.type == "video"
        assert cue2.end_time_ms == 10000
        assert cue2.auto_follow_ms == 200
        assert cue2.notes == "Test video cue"
    finally:
        os.unlink(path)


def test_cue_validation_valid():
    cue = Cue(id="cue-001", type="video", file="test.webm", volume=100)
    errors = cue.validate()
    assert errors == []


def test_cue_validation_missing_id():
    cue = Cue(id="", type="video", file="test.webm")
    errors = cue.validate()
    assert any("missing" in e.lower() or "id" in e.lower() for e in errors)


def test_cue_validation_invalid_type():
    cue = Cue(id="cue-001", type="gif", file="test.gif")
    errors = cue.validate()
    assert any("type" in e.lower() for e in errors)


def test_cue_validation_invalid_volume():
    cue = Cue(id="cue-001", type="video", file="test.webm", volume=200)
    errors = cue.validate()
    assert any("volume" in e.lower() for e in errors)


def test_show_validation_duplicate_cue_ids():
    show = Show(cues=[
        Cue(id="dup", type="video", file="a.webm"),
        Cue(id="dup", type="image", file="b.png"),
    ])
    errors = show.validate()
    assert any("duplicate" in e.lower() for e in errors)


def test_show_validation_invalid_dropout():
    show = Show(dropout_policy="invalid")
    errors = show.validate()
    assert any("dropout" in e.lower() for e in errors)


def test_save_and_reload():
    show = Show(
        title="Round-trip Test",
        dropout_policy="freeze",
        cues=[
            Cue(id="q1", name="First", type="image", file="img.png"),
            Cue(id="q2", name="Second", type="video", file="vid.webm", end_time_ms=5000),
        ],
    )
    with tempfile.NamedTemporaryFile(suffix=".cuemesh.toml", delete=False) as f:
        path = Path(f.name)
    try:
        save_show(show, path)
        loaded = load_show(path)
        assert loaded.title == "Round-trip Test"
        assert loaded.dropout_policy == "freeze"
        assert len(loaded.cues) == 2
        assert loaded.cues[0].id == "q1"
        assert loaded.cues[1].end_time_ms == 5000
    finally:
        os.unlink(path)


def test_load_example_show():
    """Ensure example show file parses cleanly."""
    example = Path(__file__).parent.parent / "examples" / "example_show.cuemesh.toml"
    if not example.exists():
        pytest.skip("Example show file not found")
    show = load_show(example)
    assert show.title
    assert len(show.cues) > 0
    errors = show.validate()
    assert errors == [], f"Example show has validation errors: {errors}"
