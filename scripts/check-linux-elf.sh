#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-linux-elf}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_IN="$SERIAL_BASE.in"
SERIAL_OUT="$SERIAL_BASE.out"
SERIAL_LOG="$BUILD_DIR/serial.log"

mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$SERIAL_LOG"

[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

python3 - "$BUILD_DIR" <<'PY'
from pathlib import Path
import struct
build = Path(__import__("sys").argv[1])
base = 0x140000
load_off = base - 0x100000
code = bytes([0xB8, 0x2A, 0x00, 0x00, 0x00, 0xC3])
entry = base + 64 + 56
elf = bytearray()
elf += b"\x7FELF" + bytes([2, 1, 1, 0]) + bytes(8)
elf += struct.pack("<HHIQQQIHHHHHH", 2, 0x3E, 1, entry, 64, 0, 0, 64, 56, 1, 0, 0, 0)
elf += struct.pack("<IIQQQQQQ", 1, 5, 0, base, base, 64 + 56 + len(code), 64 + 56 + len(code), 0x1000)
elf += code
kernel = bytearray((build / "kernel.bin").read_bytes())
kernel += b"\0" * (load_off - len(kernel))
kernel += elf
(build / "combined.bin").write_bytes(kernel)
PY

mkfifo "$SERIAL_IN" "$SERIAL_OUT"
qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 512M -no-reboot \
  -display none -serial "pipe:$SERIAL_BASE" -daemonize
timeout 30 cat "$SERIAL_OUT" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 200); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo "shell did not start" >&2; exit 1; }
printf 'linuxelf\nhalt\n' > "$SERIAL_IN"
for _ in $(seq 1 100); do
  grep -qF "linux: ELF exec returned 42" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
kill "$CATPID" 2>/dev/null || true
wait "$CATPID" 2>/dev/null || true
rm -f "$SERIAL_IN" "$SERIAL_OUT"
grep -qF "linux: execve loading ELF from space-minimal-elf" "$SERIAL_LOG"
grep -qF "linux: ELF exec returned 42" "$SERIAL_LOG"
echo "PASS: Linux personality executed minimal ELF"
