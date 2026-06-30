#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-desktop-visual}"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
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
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
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
  sleep 0.2
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
printf 'quit\n' | nc -U "$MONITOR" >/dev/null
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
text_rgb = (28, 33, 40)
muted_rgb = (92, 106, 122)
term_rgb = (200, 212, 224)
required = {
    "desktop": ((25, 28, 32), area // 7),
    "top bar": ((36, 39, 46), width * 16),
    "terminal surface": ((18, 16, 21), 450000),
    "terminal text": (term_rgb, 500),
    "prompt": ((0, 255, 0), 180),
}
for label, (rgb, minimum) in required.items():
    found = counts[rgb]
    if found < minimum:
        raise SystemExit(f"{label} color missing: {found} < {minimum}")
regions = {
    "terminal text": (80, 80, 900, 390, 1400),
    "terminal fetch": (80, 80, 700, 360, 1600),
}
for label, (x0, y0, x1, y1, minimum) in regions.items():
    found = 0
    for y in range(y0, y1):
        row = y * width * 3
        for x in range(x0, x1):
            offset = row + x * 3
            if tuple(pixels[offset:offset + 3]) in (text_rgb, muted_rgb, term_rgb, (0, 255, 0), (0, 255, 255), (255, 255, 255)):
                found += 1
    if found < minimum:
        raise SystemExit(f"{label} missing: {found} < {minimum}")
fetch_value = 0
for y in range(95, 340):
    row = y * width * 3
    for x in range(160, 520):
        offset = row + x * 3
        if tuple(pixels[offset:offset + 3]) in (term_rgb, (255, 255, 255)):
            fetch_value += 1
if fetch_value < 100:
    raise SystemExit(f"terminal fetch value glyphs missing: {fetch_value} < 100")
print("PASS: desktop visual pixels present")
PY

if command -v sips >/dev/null 2>&1; then
  sips -s format png "$PPM" --out "$PNG" >/dev/null
  echo "  screenshot: $PNG"
else
  echo "  screenshot: $PPM"
fi
