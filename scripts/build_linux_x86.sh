#!/usr/bin/env bash
# Build CueMesh release folder for Linux x86_64
# Usage: ./scripts/build_linux_x86.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"

echo "=== CueMesh Linux x86_64 Build ==="
echo "Project: $PROJECT_DIR"

cd "$PROJECT_DIR"

# Install dependencies
echo "[1/4] Installing dependencies..."
pip install pyinstaller PySide6 websockets zeroconf

# Build Controller
echo "[2/4] Building Controller..."
pyinstaller --onedir --name CueMesh-Controller \
  --add-data "shared:shared" \
  --add-data "assets:assets" \
  --distpath "$DIST_DIR" \
  controller/__main__.py

# Build Client
echo "[3/4] Building Client..."
pyinstaller --onedir --name CueMesh-Client \
  --add-data "shared:shared" \
  --add-data "assets:assets" \
  --distpath "$DIST_DIR" \
  client/__main__.py

# Copy examples and docs
echo "[4/4] Copying support files..."
cp -r examples "$DIST_DIR/CueMesh-Controller/"
cp -r docs "$DIST_DIR/CueMesh-Controller/"
cp README.md "$DIST_DIR/CueMesh-Controller/"

echo ""
echo "=== Build complete ==="
echo "Controller: $DIST_DIR/CueMesh-Controller/"
echo "Client:     $DIST_DIR/CueMesh-Client/"
