# CueMesh User Guide

CueMesh is a portable, offline, LAN-only synchronized video/image playback system for small theatres. A technician runs cues on the Controller; multiple Client nodes (typically Raspberry Pi 4) play the same cue in near-sync.

---

## System Requirements

### Controller
- Linux x86_64 (primary) or Windows x86_64
- Python 3.11+
- PySide6
- mpv (optional, for local preview)

### Client
- Linux ARM64/ARMv7 (Raspberry Pi 4 baseline) or Linux x86_64
- Python 3.11+
- PySide6
- mpv (required for playback)

---

## Installation

### From release folder (recommended)
1. Download the release zip for your platform.
2. Extract to a folder (USB key or local drive).
3. Run `./CueMesh-Controller/cuemesh-controller` or `./CueMesh-Client/cuemesh-client`.

### From source
```bash
git clone https://github.com/davidroberthoare/CueMesh.git
cd CueMesh
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Prepare media files
Place all media files in a folder named `cuemesh_media/` next to your show file:
```
my_show/
├── my_show.cuemesh.toml
└── cuemesh_media/
    ├── videos/
    │   └── intro.webm
    └── images/
        └── title_card.png
```

All clients must have identical `cuemesh_media/` folders.

### 2. Start the Controller
```bash
cuemesh-controller
# or from source:
python -m controller
```

### 3. Start Clients
On each client (e.g., Raspberry Pi):
```bash
cuemesh-client
# or from source:
python -m client
```

### 4. Create or open a show
- Click **New Show** or **Open Show...** in the Show Manager tab.
- Edit cues in the **Show Editor** tab.
- Save with **File → Save Show** (`.cuemesh.toml`).

### 5. Connect clients
- Open the **Clients** tab on the controller.
- Clients appear in **Pending Clients** when they connect.
- Click **Accept Selected** to approve clients.
- Optionally rename clients.

### 6. Run the show
- Switch to the **Run Show** tab.
- Press **GO** to play the first cue on all accepted clients simultaneously.
- Use **NEXT / PREV** to advance cues.
- Use **BLACKOUT** to black all client screens.
- Use **Jump to Cue** to skip to a specific cue.

### 7. Diagnostics
- Use **Diagnostics** tab to toggle the alignment/test screen on clients.
- Export a support bundle (ZIP) for troubleshooting.

---

## Show File Format

Show files use TOML format with the `.cuemesh.toml` extension. See `examples/example_show.cuemesh.toml` for a complete example.

Key sections:
- `[show]` — title, version, media_root, dropout_policy, sync settings
- `[[clients]]` — optional named client entries
- `[[cues]]` — list of cues with type, file, timing, volume, etc.

---

## Cue Types

| Type | Description |
|------|-------------|
| `video` | Plays a video file via mpv |
| `image` | Displays a static image via mpv |

---

## Sync Modes

CueMesh targets **medium sync** (~50–150ms starts on a typical LAN). This is sufficient for theatrical A/V and is not frame-accurate SMPTE timecode.

Clients self-correct drift using:
1. **Rate adjustment** — slight speed-up or slow-down
2. **Hard seek** — jump to expected position when drift exceeds threshold

---

## Dropout Behavior

Configure `dropout_policy` in your show file:

| Policy | Behavior when controller disconnects |
|--------|-------------------------------------|
| `continue` | Keep playing current cue (default) |
| `freeze` | Pause immediately |
| `black` | Black screen immediately |

---

## Jog Controls

- **Forward jog**: Rate slider adjusts playback speed (0.5x–2.0x)
- **Backward jog**: Hold JOG button to seek backward in 200ms steps at ~2x speed (not true reverse decode)

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open show |
| `Ctrl+S` | Save show |
| `Ctrl+I` (client) | Toggle status overlay |

---

## Troubleshooting

See `docs/troubleshooting.md` for common issues.
