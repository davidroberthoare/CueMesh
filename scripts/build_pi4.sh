#!/usr/bin/env bash
# Build CueMesh Client release folder for Raspberry Pi 4 (ARM64/ARMv7)
# Run this script ON the Pi 4 (or in a Pi 4 chroot/Docker).
# Usage: ./scripts/build_pi4.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"

echo "=== CueMesh Pi 4 Client Build ==="
echo "Project: $PROJECT_DIR"

# Check for mpv
if ! command -v mpv &>/dev/null; then
  echo ""
  echo "NOTE: mpv is not installed. Install with:"
  echo "  sudo apt install mpv"
  echo ""
fi

cd "$PROJECT_DIR"

echo "[1/3] Installing dependencies..."
pip install pyinstaller PySide6 websockets zeroconf

echo "[2/3] Building Client..."
pyinstaller --onedir --name CueMesh-Client-Pi4 \
  --add-data "shared:shared" \
  --add-data "assets:assets" \
  --distpath "$DIST_DIR" \
  client/__main__.py

echo "[3/3] Copying support files..."
cp -r docs "$DIST_DIR/CueMesh-Client-Pi4/"
cp README.md "$DIST_DIR/CueMesh-Client-Pi4/"

echo ""
echo "=== Build complete ==="
echo "Client: $DIST_DIR/CueMesh-Client-Pi4/"
echo ""
echo "IMPORTANT: mpv must be installed on each Pi separately:"
echo "  sudo apt install mpv"
