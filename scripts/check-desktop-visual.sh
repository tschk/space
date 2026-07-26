#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-desktop-visual}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_IN="$SERIAL_BASE.in"
SERIAL_OUT="$SERIAL_BASE.out"
SERIAL_LOG="$BUILD_DIR/serial.log"
MONITOR="$BUILD_DIR/qemu-monitor.sock"
PPM="$BUILD_DIR/desktop.ppm"
PNG="$BUILD_DIR/desktop.png"

mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$SERIAL_LOG" "$MONITOR" "$PPM" "$PNG"

echo "[1/4] Building compiler..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"

echo "[2/4] Compiling kernel..."
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
[ "$(wc -c < "$BUILD_DIR/trampoline.bin")" -eq 4096 ] || { echo "trampoline size error" >&2; exit 1; }
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

echo "[3/4] Capturing desktop..."
mkfifo "$SERIAL_IN" "$SERIAL_OUT"
qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 256M -no-reboot \
  -vga std -display none -serial "pipe:$SERIAL_BASE" \
  -monitor "unix:$MONITOR,server,nowait" -daemonize

timeout 30 cat "$SERIAL_OUT" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 200); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo "shell did not start" >&2; exit 1; }

printf 'desktop\n' > "$SERIAL_IN"
for _ in $(seq 1 100); do
  grep -qF "space: compositor running" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space: compositor running" "$SERIAL_LOG" || { echo "desktop did not start" >&2; exit 1; }

for _ in $(seq 1 200); do
  grep -qF "space: compositor frame ready" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space: compositor frame ready" "$SERIAL_LOG" || { echo "desktop did not paint" >&2; exit 1; }

for key in f e t c h ret; do
  printf 'sendkey %s\n' "$key" | nc -U "$MONITOR" >/dev/null
  sleep 0.5
done
sleep 5
printf 'screendump %s\n' "$PPM" | nc -U "$MONITOR" >/dev/null
sleep 1
printf '\033' > "$SERIAL_IN"
for _ in $(seq 1 100); do
  grep -qF "space: compositor exited" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space: compositor exited" "$SERIAL_LOG" || { echo "desktop did not exit" >&2; exit 1; }
printf 'halt\n' > "$SERIAL_IN"
printf 'quit\n' | nc -U "$MONITOR" >/dev/null || true
kill "$CATPID" 2>/dev/null || true
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$MONITOR"

echo "[4/4] Checking pixels..."
python3 - "$PPM" <<'PY'
from collections import Counter
from pathlib import Path
import sys

data = Path(sys.argv[1]).read_bytes()
parts = []
i = 0
while len(parts) < 4:
    j = data.find(b"\n", i)
    line = data[i:j].strip()
    i = j + 1
    if line and not line.startswith(b"#"):
        parts.extend(line.split())

if parts[0] != b"P6" or int(parts[1]) != 1920 or int(parts[2]) != 1080:
    raise SystemExit("unexpected screendump format")

pixels = data[i:]
counts = Counter(tuple(pixels[n:n + 3]) for n in range(0, len(pixels), 3))
width = int(parts[1])
height = int(parts[2])
area = width * height

# Palette from current display.in:
#   COMP-COLOR-DESKTOP  0x0B0909 = (11,9,9)
#   COMP-COLOR-PANEL    0x1B1818 = (27,24,24)
#   FB-COLOR-GREEN      0x00FF00 = (0,255,0)
#   COMP-COLOR-TERM-TEXT 0xF5F4F4 = (245,244,244)
#   COMP-COLOR-TERM-BG  0x1E1E2E = (30,30,46)
desktop_rgb = (11, 9, 9)
panel_rgb = (27, 24, 24)
term_rgb = (245, 244, 244)
term_bg_rgb = (30, 30, 46)

required = {
    "desktop bg": (desktop_rgb, area // 12),
    "panel (top/taskbar)": (panel_rgb, width * 16),
    "prompt green": ((0, 255, 0), 100),
    "term bg": (term_bg_rgb, width * 40),
}
for label, (rgb, minimum) in required.items():
    found = counts[rgb]
    if found < minimum:
        raise SystemExit(f"{label} color missing: {found} < {minimum}")

# Verify fetch glyphs: count text-colored pixels in left terminal content area.
# Terminal 1 spans approx x=32..960 y=48..1032. History/output appears below
# the title strip (y > ~80). After typing 'fetch' + Enter, the info banner
# and prompt should produce many text pixels.
text_px = 0
for y in range(80, 900):
    row = y * width * 3
    for x in range(48, 900):
        c = tuple(pixels[row + x * 3:row + x * 3 + 3])
        if c in (term_rgb, (255, 255, 255), (0, 255, 0), (0, 255, 255), (248, 189, 56)):
            text_px += 1
if text_px < 1000:
    raise SystemExit(f"terminal content missing: {text_px} < 1000 pixels")
print(f"PASS: desktop visual pixels present (text_px={text_px})")
PY

if command -v sips >/dev/null 2>&1; then
  sips -s format png "$PPM" --out "$PNG" >/dev/null
  echo "  screenshot: $PNG"
else
  echo "  screenshot: $PPM"
fi
