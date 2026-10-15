#!/usr/bin/env bash
# Fast QEMU smoke: boot to the serial shell and halt.
# Reuses KERNEL_BIN when CI already compiled the image.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-qemu-smoke}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"

mkdir -p "$BUILD_DIR"

if [ -n "${KERNEL_BIN:-}" ]; then
  KERNEL="$KERNEL_BIN"
  echo "[1/2] Reusing KERNEL_BIN=$KERNEL"
else
  echo "[1/2] Building kernel..."
  [ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
  NASM="${NASM:-nasm}"
  "$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
  "$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
    --trampoline "$BUILD_DIR/trampoline.bin" \
    --target native --target-triple x86_64-unknown-none --linkage static-lib \
    --out "$BUILD_DIR/kernel.bin"
  KERNEL="$BUILD_DIR/kernel.bin"
fi

[ -f "$KERNEL" ] || { echo "missing kernel image" >&2; exit 1; }

echo "[2/2] Booting..."
rm -f "$SERIAL" "$FIFO"
mkfifo "$FIFO"
qemu-system-x86_64 -kernel "$KERNEL" -m 256M \
  -device isa-debug-exit,iobase=0xf4 \
  -vga std -serial stdio -display none -no-reboot <"$FIFO" >"$SERIAL" 2>/dev/null &
QPID=$!
exec 3>"$FIFO"
for _ in $(seq 1 200); do
  grep -qF "space>" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
echo "hardening" >&3
for _ in $(seq 1 80); do
  grep -qE "hardening (PASS|FAIL)" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
echo "halt" >&3
exec 3>&-
sleep 0.5
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
rm -f "$FIFO"

fail=0
for m in "kernel root entered" "interactive shell" "space>" "hardening PASS"; do
  if grep -qF "$m" "$SERIAL" 2>/dev/null; then
    echo "  ok: $m"
  else
    echo "  MISSING: $m" >&2
    fail=1
  fi
done
if [ "$fail" -eq 0 ]; then
  echo "PASS: QEMU smoke"
  exit 0
fi
echo "FAIL: QEMU smoke" >&2
tail -40 "$SERIAL" >&2 || true
exit 1
