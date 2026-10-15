#!/usr/bin/env bash
set -euo pipefail
trap '' PIPE

# check-dynamic-modules.sh — Prove the dynamic nanokernel contract:
#   1. The kernel boot image publishes its own export table.
#   2. A dynamic module imports kernel serial services + one libspace symbol;
#      the loader binds all call sites before the module's entry runs.
#   3. A module importing an unprovided symbol is denied before entry and
#      boot continues.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${BUILD_DIR:-/tmp/space-dynmod-check}"
SERIAL="$BUILD_DIR/serial.log"
DENY="$BUILD_DIR/deny.log"

BUILD_DIR="$BUILD_DIR" "$SCRIPT_DIR/build-dynamic-modules.sh" >/dev/null

boot_image() {
  local kernel="$1" log="$2"
  local fifo="$BUILD_DIR/fifo-$3"
  rm -f "$log" "$fifo"
  mkfifo "$fifo"
  qemu-system-x86_64 -kernel "$kernel" -m 256M \
    -device isa-debug-exit,iobase=0xf4 -display none -serial stdio -no-reboot \
    <"$fifo" >"$log" 2>/dev/null &
  local qpid=$!
  exec 3>"$fifo"
  for _ in $(seq 1 400); do
    grep -qF "interactive shell" "$log" 2>/dev/null && break
    kill -0 "$qpid" 2>/dev/null || break
    sleep 0.1
  done
  { echo "halt" >&3; } 2>/dev/null || true
  exec 3>&-
  sleep 0.5
  kill "$qpid" 2>/dev/null || true
  wait "$qpid" 2>/dev/null || true
  rm -f "$fifo"
}

boot_image "$BUILD_DIR/combined.bin" "$SERIAL" good
boot_image "$BUILD_DIR/deny.bin" "$DENY" deny

for marker in \
  "SCI: library registered at 0x000000003f000040" \
  "SCI: bound 7 imports" \
  "dynmod: kernel services bound, marker 0x00000000000000d9" \
  "lib"; do
  grep -qF "$marker" "$SERIAL" || { echo "MISSING: $marker" >&2; exit 1; }
done

grep -qE "SCI: kernel exports registered: [0-9]+" "$SERIAL" \
  || { echo "MISSING: kernel exports registered" >&2; exit 1; }

grep -qF "SCI: DENIED unresolved import no-such-service" "$DENY" \
  || { echo "MISSING: unresolved-import deny" >&2; exit 1; }
grep -qF "interactive shell" "$DENY" \
  || { echo "MISSING: shell after deny" >&2; exit 1; }

echo "PASS: dynamic nanokernel binds kernel exports, chained modules, and denies unresolved imports"
