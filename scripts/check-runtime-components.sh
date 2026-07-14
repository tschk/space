#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${BUILD_DIR:-/tmp/space-runtime-check}"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"

BUILD_DIR="$BUILD_DIR" "$SCRIPT_DIR/build-runtime-components.sh" >/dev/null
rm -f "$SERIAL" "$FIFO"
mkfifo "$FIFO"
qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 512M -rtc base=utc \
  -device isa-debug-exit,iobase=0xf4 -vga std -serial stdio -display none -no-reboot \
  <"$FIFO" >"$SERIAL" 2>/dev/null &
QPID=$!
exec 3>"$FIFO"
for _ in $(seq 1 400); do
  grep -qF "interactive shell" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
echo "halt" >&3
exec 3>&-
sleep 0.5
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
rm -f "$FIFO"

for marker in "interactive shell" "display: component entered" \
  "display: framebuffer initialized" "display: server running" \
  "input: component entered" "input: channel bound" "input: PS/2 mouse ready" \
  "volume: component init/write/read passed" "volume: client bound" \
  "volume: filesystem op via Volume RPC" \
  "test_sci_loader: PASS" \
  "linux: personality demo complete" \
  "linux: open(hello.txt"; do
  grep -qF "$marker" "$SERIAL" || { echo "MISSING: $marker" >&2; exit 1; }
done
echo "PASS"
