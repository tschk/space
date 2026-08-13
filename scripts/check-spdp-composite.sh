#!/usr/bin/env bash
# SPDP surface-pipeline proof (compositor/client split groundwork).
#
# Runs the `dsp demo` shell command: a client-owned pool buffer is filled with
# a red/green checker pattern, attached + committed to a surface via the SPDP
# surface API, and composited once onto the framebuffer. The screenshot is
# checked for the checker colors (red/green) and the dark-blue composite
# background.
#
# Usage:
#   bash scripts/check-spdp-composite.sh
#   KERNEL_BIN=/path/kernel.bin bash scripts/check-spdp-composite.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-spdp-composite}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_IN="$SERIAL_BASE.in"
SERIAL_OUT="$SERIAL_BASE.out"
SERIAL_LOG="$BUILD_DIR/serial.log"
MONITOR="$BUILD_DIR/qemu-monitor.sock"
PPM="$BUILD_DIR/composite.ppm"

mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$SERIAL_LOG" "$MONITOR" "$PPM"

echo "[1/4] Building kernel..."
if [ -n "${KERNEL_BIN:-}" ]; then
  KERNEL="$KERNEL_BIN"
else
  [ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
  NASM="${NASM:-nasm}"
  "$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
  [ "$(wc -c < "$BUILD_DIR/trampoline.bin")" -eq 4096 ] || { echo "trampoline size error" >&2; exit 1; }
  "$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
    --trampoline "$BUILD_DIR/trampoline.bin" \
    --target native --target-triple x86_64-unknown-none --linkage static-lib \
    --out "$BUILD_DIR/kernel.bin"
  KERNEL="$BUILD_DIR/kernel.bin"
fi

echo "[2/4] Booting to shell..."
mkfifo "$SERIAL_IN" "$SERIAL_OUT"
qemu-system-x86_64 -kernel "$KERNEL" -m 256M -no-reboot \
  -vga std -display none -serial "pipe:$SERIAL_BASE" \
  -monitor "unix:$MONITOR,server,nowait" -daemonize

timeout 30 cat "$SERIAL_OUT" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 200); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo "shell did not start" >&2; exit 1; }

echo "[3/4] Running dsp demo..."
printf 'dsp demo\n' > "$SERIAL_IN"
for _ in $(seq 1 50); do
  grep -qF "dsp: demo composited" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "dsp: demo composited" "$SERIAL_LOG" || { echo "dsp demo did not composite" >&2; exit 1; }

printf 'screendump %s\n' "$PPM" | nc -U "$MONITOR" >/dev/null 2>&1
sleep 0.5

echo "[4/4] Checking composite pixels..."
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
width = int(parts[1])
height = int(parts[2])

# Surface is placed at (100,100), 64x64, red/green 8px checker. The composite
# fills the screen with dark blue (0x00000080 -> RGB (0,0,128)) first.
def c(x, y):
    row = y * width * 3 + x * 3
    return tuple(pixels[row:row + 3])

red = green = blue = 0
for y in range(100, 164):
    for x in range(100, 164):
        col = c(x, y)
        if col == (255, 0, 0):
            red += 1
        elif col == (0, 255, 0):
            green += 1
        elif col == (0, 0, 128):
            blue += 1
# Dark-blue background outside the surface.
bg = 0
for n in range(0, width * height, 7):
    col = c(n % width, n // width)
    if col == (0, 0, 128):
        bg += 1

print(f"checker: red={red} green={green} blue={blue}; bg samples={bg}")
if red < 500 or green < 500:
    raise SystemExit(f"checker pattern missing: red={red} green={green}")
if bg < 5000:
    raise SystemExit(f"composite background missing: {bg} < 5000")
print("PASS: spdp surface composited (red/green checker on dark-blue bg)")
PY
PASS=$?

printf 'halt\n' > "$SERIAL_IN"
printf 'quit\n' | nc -U "$MONITOR" >/dev/null 2>&1 || true
kill "$CATPID" 2>/dev/null || true
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$MONITOR"
exit "$PASS"
