#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-qemu-smoke}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"
mkdir -p "$BUILD_DIR"

if [ -n "${KERNEL_BIN:-}" ]; then
  KERNEL="$KERNEL_BIN"
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

echo "[2/2] QEMU smoke (kernel root + interactive shell)..."
command -v qemu-system-x86_64 >/dev/null || { echo "qemu-system-x86_64 not found" >&2; exit 1; }
rm -f "$SERIAL" "$FIFO"
mkfifo "$FIFO"
qemu-system-x86_64 -kernel "$KERNEL" -m 256M \
  -device isa-debug-exit,iobase=0xf4 \
  -vga std -serial stdio -display none -no-reboot <"$FIFO" >"$SERIAL" 2>"$BUILD_DIR/qemu.err" &
QPID=$!
exec 3>"$FIFO"
for _ in $(seq 1 300); do
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

fail=
for m in "kernel root entered" "interactive shell" "space>"; do
  if grep -qF "$m" "$SERIAL" 2>/dev/null; then echo "  ok: $m"
  else echo "  MISSING: $m" >&2; fail=1; fi
done
if [ -n "$fail" ]; then
  echo "---- serial ----" >&2
  tail -n 80 "$SERIAL" >&2 || true
  echo "---- qemu.err ----" >&2
  tail -n 40 "$BUILD_DIR/qemu.err" >&2 || true
  echo "FAIL" >&2
  exit 1
fi
echo "PASS"
exit 0
