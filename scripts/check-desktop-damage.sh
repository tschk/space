#!/usr/bin/env bash
# Moving-window stress benchmark for the desktop compositor (damage-rect gate).
#
# Runs the self-contained `bench` shell command: the compositor animates a
# window for 100 frames and the kernel times it against the PIT tick counter,
# reporting frames/sec. Damage-rect compositing must beat the eager full-screen
# recompose path (measured: 19 fps eager -> 38 fps damage-rect on M3 TCG).
#
# Usage:
#   bash scripts/check-desktop-damage.sh               # build kernel, benchmark
#   KERNEL_BIN=/path/kernel.bin bash scripts/check-desktop-damage.sh
#   MIN_FPS=25 bash scripts/check-desktop-damage.sh    # tune threshold
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-desktop-damage}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_IN="$SERIAL_BASE.in"
SERIAL_OUT="$SERIAL_BASE.out"
SERIAL_LOG="$BUILD_DIR/serial.log"
MONITOR="$BUILD_DIR/qemu-monitor.sock"
MIN_FPS="${MIN_FPS:-30}"

mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$SERIAL_LOG" "$MONITOR"

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

timeout 120 cat "$SERIAL_OUT" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 200); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo "shell did not start" >&2; exit 1; }

echo "[3/4] Running moving-window bench (100 frames)..."
printf 'bench\n' > "$SERIAL_IN"
for _ in $(seq 1 400); do
  grep -qF "bench elapsed" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.5
done
grep -qF "bench elapsed" "$SERIAL_LOG" || { echo "bench did not finish" >&2; exit 1; }

# Visual sanity: capture the desktop after the animation.
printf 'screendump %s\n' "$BUILD_DIR/damage.ppm" | nc -U "$MONITOR" >/dev/null 2>&1 || true
sleep 0.3

echo "[4/4] Checking frame rate..."
python3 - "$SERIAL_LOG" "$MIN_FPS" <<'PY'
import re
import sys

lines = open(sys.argv[1]).read().splitlines()
fps = None
ticks = None
for ln in lines:
    m = re.search(r"bench elapsed ticks (\d+) fps (\d+)", ln)
    if m:
        ticks = int(m.group(1))
        fps = int(m.group(2))
if fps is None:
    raise SystemExit("no bench result found")
min_fps = int(sys.argv[2])
print(f"bench: 100 moving-window frames in {ticks} ticks => {fps} fps")
if fps < min_fps:
    raise SystemExit(f"FAIL: frame rate {fps} fps < {min_fps} minimum")
print(f"PASS: moving-window stress {fps} fps (min {min_fps})")
PY
PASS=$?

printf 'halt\n' > "$SERIAL_IN"
printf 'quit\n' | nc -U "$MONITOR" >/dev/null 2>&1 || true
kill "$CATPID" 2>/dev/null || true
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$MONITOR"
exit "$PASS"
