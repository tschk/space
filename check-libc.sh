#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$SCRIPT_DIR"
# shellcheck source=scripts/inauguration-dir.sh
source "$SCRIPT_DIR/scripts/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-boot}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"
mkdir -p "$BUILD_DIR"
echo "[1/3] Building compiler..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
echo "[2/3] Assembling trampoline and compiling kernel..."
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"
echo "[3/3] Booting and checking output..."
rm -f "$SERIAL" "$FIFO"
mkfifo "$FIFO"
qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 512M \
  -vga std -serial stdio -display none -no-reboot <"$FIFO" >"$SERIAL" 2>/dev/null &
QPID=$!
exec 3>"$FIFO"
for _ in $(seq 1 150); do
  grep -qF "interactive shell" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
echo "libc" >&3
for _ in $(seq 1 100); do
  grep -qF "libc self-test" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
echo "halt" >&3
exec 3>&-
sleep 0.5
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
rm -f "$FIFO"

cat "$SERIAL"

if grep -qF "libc self-test passed" "$SERIAL" 2>/dev/null; then echo "PASS"; else echo "FAIL" >&2; fi
