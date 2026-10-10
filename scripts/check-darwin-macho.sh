#!/usr/bin/env bash
# Validate malformed Mach-O rejection and execute a trusted fixed-address fixture.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-darwin-macho}"
IN="$INAUG_DIR/in-cli/target/release/in"
NASM="${NASM:-nasm}"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_LOG="$BUILD_DIR/serial.log"
PIDFILE="$BUILD_DIR/qemu.pid"
CATPID=""
mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_BASE.in" "$SERIAL_BASE.out" "$SERIAL_LOG" "$PIDFILE"
cleanup() {
  if [ -n "$CATPID" ]; then
    kill "$CATPID" 2>/dev/null || true
    wait "$CATPID" 2>/dev/null || true
  fi
  if [ -f "$PIDFILE" ]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
  fi
  rm -f "$SERIAL_BASE.in" "$SERIAL_BASE.out" "$PIDFILE"
}
trap cleanup EXIT
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" --target native \
  --target-triple x86_64-unknown-none --linkage static-lib --out "$BUILD_DIR/kernel.bin"
"$NASM" -f bin "$SPACE_DIR/fixtures/darwin-minimal-macho.asm" -o "$BUILD_DIR/fixture.macho"
python3 - "$BUILD_DIR" <<'PY'
from pathlib import Path
import struct
import sys
build = Path(sys.argv[1])
image = (build / 'fixture.macho').read_bytes()
assert len(image) == 4096
assert struct.unpack_from('<8I', image) == (0xfeedfacf, 0x1000007, 3, 2, 2, 96, 1, 0)
assert struct.unpack_from('<II16s4Q4I', image, 32) == (
    0x19, 72, b'__TEXT' + bytes(10), 0x280000, 4096, 0, 4096, 5, 5, 0, 0)
assert struct.unpack_from('<IIQQ', image, 104) == (0x80000028, 24, 128, 0)
assert image[128:134] == bytes.fromhex('b82a000000c3')
kernel = (build / 'kernel.bin').read_bytes()
assert len(kernel) <= 0x180000, 'kernel overlaps Mach-O fixture'
(build / 'combined.bin').write_bytes(kernel + bytes(0x180000-len(kernel)) + image)
PY
mkfifo "$SERIAL_BASE.in" "$SERIAL_BASE.out"
qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 512M -no-reboot \
  -display none -serial "pipe:$SERIAL_BASE" -pidfile "$PIDFILE" -daemonize
timeout 40 cat "$SERIAL_BASE.out" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 300); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo 'FAIL: shell did not start' >&2; exit 1; }
printf 'darwinmacho\nhalt\n' > "$SERIAL_BASE.in"
for _ in $(seq 1 100); do
  grep -qF 'halting on request' "$SERIAL_LOG" 2>/dev/null && break
  grep -qF 'validation FAILED' "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
if grep -qE 'FAILED|CPU EXCEPTION|nanokernel fault' "$SERIAL_LOG"; then
  cat "$SERIAL_LOG" >&2
  exit 1
fi
grep -qxF 'darwin: Mach-O validation scenarios 22/22' "$SERIAL_LOG"
grep -qxF 'darwin: Mach-O exec returned 42' "$SERIAL_LOG"
grep -qF 'halting on request' "$SERIAL_LOG"
echo 'PASS: Darwin trusted Mach-O fixture (22 validation scenarios, return 42)'
