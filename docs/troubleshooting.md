# CueMesh Troubleshooting Guide

---

## Clients not appearing in Controller

1. **Check network**: Ensure controller and clients are on the same LAN/subnet.
2. **Firewall**: Allow port 9420 (TCP) on the controller.
3. **mDNS**: Some networks block multicast. Use manual IP entry on the client if needed.
4. **Manual connection**: On the client Connect screen, enter the controller's IP directly.

---

## Clients connecting but sync is poor

1. **Wired > Wi-Fi**: Use Ethernet when possible, especially for the controller.
2. **Network load**: Avoid heavy downloads during show run.
3. **Tune sync**: Reduce `sync_interval_ms` or increase `start_lead_ms` in show config.
4. **Check drift logs**: Use Diagnostics → Log Viewer to review drift reports.

---

## mpv not found (client)

Install mpv:
```bash
# Raspberry Pi OS / Debian
sudo apt install mpv

# Arch Linux
sudo pacman -S mpv
```

---

## Video stutters on Raspberry Pi 4

1. Use the recommended VP9/WebM format (see `docs/encoding_presets.md`).
2. Keep resolution ≤ 1080p and framerate ≤ 30fps.
3. Check CPU usage: `htop`
4. Check dropped frames in the client log.

---

## Show file fails to load

- Ensure the file ends in `.cuemesh.toml`
- Validate TOML syntax: `python -c "import tomllib; tomllib.load(open('yourshow.cuemesh.toml','rb'))"`
- Check for duplicate cue IDs.

---

## Export support bundle

Controller → Diagnostics tab → **Export Support Bundle (ZIP)**.
Include this ZIP when reporting issues.
