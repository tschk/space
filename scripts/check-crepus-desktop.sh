#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-crepus-desktop}"
mkdir -p "$BUILD_DIR"
crepus embedded check "$SPACE_DIR/ui/desktop.crepus"
crepus embedded snapshot "$SPACE_DIR/ui/desktop.crepus" --width 1280 --height 800 --out "$BUILD_DIR/desktop.ppm"
echo "PASS: crepus desktop snapshot: $BUILD_DIR/desktop.ppm"
