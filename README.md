# CueMesh

**Open-source portable offline LAN-only synchronized video/image playback for small theatres.**

A technician runs cues on a **Controller** app; multiple **Client** nodes (typically Raspberry Pi 4) play the same cue in near-sync (~50–150ms on a typical LAN). Clients periodically sync to a master clock and self-correct drift.

---

## Features

- **Portable**: Runs from a folder; no installer required; USB-key friendly
- **Offline**: No internet connection needed
- **LAN-only**: Works on a consumer router; wired or Wi-Fi; tested with up to 10 clients
- **Synchronized**: Medium sync target (~50–150ms), with drift correction during playback
- **Show files**: Hand-editable TOML format (`.cuemesh.toml`)
- **Playback**: Single display per client, always fullscreen; video and image cues
- **Discovery**: Automatic mDNS/zeroconf; manual IP fallback
- **Logging**: Rotating local logs + controller aggregation; support bundle export

---

## Quick Start

### Requirements
- Python 3.11+
- [mpv](https://mpv.io/) (client playback)
- PySide6, websockets, zeroconf

### Install from source
```bash
git clone https://github.com/davidroberthoare/CueMesh.git
cd CueMesh
pip install -e ".[dev]"
```

### Run Controller
```bash
python -m controller
```

### Run Client (e.g., on a Raspberry Pi)
```bash
python -m client
```

---

## Repository Layout

```
controller/          Controller app (PySide6)
client/              Client app (PySide6 + mpv IPC)
shared/              Protocol, show parsing, clock sync, hashing, logging
assets/              Icons, test patterns
examples/            Example show files
scripts/             Build/packaging scripts (PyInstaller)
docs/                User guide, encoding presets, troubleshooting
tests/               Unit tests (pytest)
```

---

## Show File Format

Show files are hand-editable TOML (`.cuemesh.toml`):

```toml
[show]
title = "My Show"
version = 1
media_root = "./cuemesh_media"
dropout_policy = "continue"   # "continue" | "freeze" | "black"

[show.sync]
mode = "medium"
max_drift_ms = 150
start_lead_ms = 250

[[cues]]
id = "cue-001"
name = "Opening Video"
type = "video"
file = "videos/opening.webm"
volume = 85
loop = false
fade_in_ms = 1000
fade_out_ms = 1000
```

See `examples/example_show.cuemesh.toml` for a complete example.

---

## Media

- **Video**: WebM (VP9 + Opus) recommended — royalty-free, Pi 4 friendly
- **Images**: PNG / JPEG
- Max 1080p @ 30fps
- See `docs/encoding_presets.md` for ffmpeg commands

---

## Packaging

Build portable release folders:
```bash
# Linux x86_64 (Controller + Client)
bash scripts/build_linux_x86.sh

# Raspberry Pi 4 (Client only)
bash scripts/build_pi4.sh

# Windows (Controller only)
scripts\build_windows.bat
```

---

## Documentation

- [User Guide](docs/user_guide.md)
- [Encoding Presets](docs/encoding_presets.md)
- [Troubleshooting](docs/troubleshooting.md)

---

## License

See [LICENSE](LICENSE).
