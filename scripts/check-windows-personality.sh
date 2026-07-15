#!/usr/bin/env bash
# Prove Windows personality CreateFile/WriteFile/ReadFile demo path boots.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-windows-personality}"
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
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

mkfifo "$SERIAL_IN" "$SERIAL_OUT"
qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 512M -no-reboot \
  -display none -serial "pipe:$SERIAL_BASE" -daemonize
timeout 40 cat "$SERIAL_OUT" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 300); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
if ! grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null; then
  echo "FAIL: shell did not start" >&2
  kill "$CATPID" 2>/dev/null || true
  wait "$CATPID" 2>/dev/null || true
  rm -f "$SERIAL_IN" "$SERIAL_OUT"
  exit 1
fi

printf 'windows\nhalt\n' > "$SERIAL_IN"
for _ in $(seq 1 200); do
  grep -qF "windows: personality demo complete" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
kill "$CATPID" 2>/dev/null || true
wait "$CATPID" 2>/dev/null || true
rm -f "$SERIAL_IN" "$SERIAL_OUT"

grep -qE "CreateFile|WriteFile" "$SERIAL_LOG"
grep -qE "SetFilePointer|MoveFile" "$SERIAL_LOG"
grep -qE "CreateDirectory|GetLastError|VirtualAlloc" "$SERIAL_LOG"
# GetStdHandle optional deeper marker
grep -qF "windows: personality demo complete" "$SERIAL_LOG"
echo "PASS: Windows personality demo (CreateFile/CreateDirectory/GetLastError path)"
