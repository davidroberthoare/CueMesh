# CueMesh Media Encoding Presets

CueMesh v1 recommends **WebM (VP9 video + Opus audio)** as the default video format.
This is royalty-free, open-source, and well-supported by mpv on Raspberry Pi.

---

## Recommended format

| Spec | Value |
|------|-------|
| Container | WebM |
| Video codec | VP9 |
| Audio codec | Opus |
| Max resolution | 1920×1080 |
| Max framerate | 30 fps |
| Bitrate | 2–8 Mbps (video) |

---

## ffmpeg examples

### Convert MP4 to WebM (VP9 + Opus) — standard quality
```bash
ffmpeg -i input.mp4 \
  -c:v libvpx-vp9 -crf 28 -b:v 4M \
  -c:a libopus -b:a 128k \
  -vf "scale=-2:1080,fps=30" \
  output.webm
```

### Fast encode for testing (lower quality)
```bash
ffmpeg -i input.mp4 \
  -c:v libvpx-vp9 -crf 35 -b:v 2M -speed 4 \
  -c:a libopus -b:a 96k \
  -vf "scale=-2:720,fps=25" \
  output_fast.webm
```

### Raspberry Pi 4 — recommended preset
```bash
ffmpeg -i input.mp4 \
  -c:v libvpx-vp9 -crf 30 -b:v 3M -deadline good -cpu-used 2 \
  -c:a libopus -b:a 128k \
  -vf "scale=-2:1080,fps=25" \
  -threads 4 \
  output_pi4.webm
```

### Convert image to PNG
```bash
ffmpeg -i input.jpg output.png
# or simply:
convert input.jpg output.png
```

---

## Two-pass encoding (best quality)

```bash
# Pass 1
ffmpeg -i input.mp4 \
  -c:v libvpx-vp9 -b:v 4M -pass 1 -an -f null /dev/null

# Pass 2
ffmpeg -i input.mp4 \
  -c:v libvpx-vp9 -b:v 4M -pass 2 \
  -c:a libopus -b:a 128k \
  output_2pass.webm
```

---

## Verify file plays on Pi 4

```bash
mpv --no-config output.webm
```

Check for dropped frames in mpv output. If frames are dropping, reduce resolution or bitrate.

---

## Images

Use PNG or JPEG:
- PNG for images with transparency or text
- JPEG for photographs
- Recommended max size: 1920×1080

---

## Folder structure

Place all media files in `~/cuemesh_media/` on each client machine:

```
~/cuemesh_media/
├── intro.webm
├── scene1.webm
├── credits.webm
├── title_card.png
└── intermission.png
```

All file references in `.cuemesh.toml` use filenames only:
```toml
[show]
media_root = "~/cuemesh_media"   # Standard location

[[cues]]
file = "intro.webm"   # Just the filename
```
