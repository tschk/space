#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
OUT="${BUILD_DIR:-/tmp/space-time-component}/time.sci"

mkdir -p "$(dirname "$OUT")"
"$IN" compile --path "$SPACE_DIR/components/time.in" --entry time-component-entry \
  --target native --target-triple x86_64-unknown-none --emit sci --base 0x60000020 --out "$OUT"
test -s "$OUT"
echo PASS
