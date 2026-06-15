#!/usr/bin/env bash
#
# check-qemu-boot.sh — Build the Space nanokernel from `.in`, boot it in QEMU,
# drive its serial shell, and verify every subsystem's marker on the console.
#
# Pipeline:
#   1. build the Inauguration `.in` compiler (../inauguration)
#   2. assemble the long-mode boot trampoline (nasm -f bin)
#   3. compile kernel/kernel-root.in to a flat Multiboot1 boot image
#   4. boot under qemu-system-x86_64, feed shell commands, check the output
#
# Requirements: clang, make, nasm, qemu-system-x86_64, perl.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-boot}"

IN="$INAUG_DIR/in-cli/in"
KERNEL_IN="$SPACE_DIR/kernel/kernel-root.in"
TRAMPOLINE_ASM="$SPACE_DIR/boot/multiboot.asm"
SERIAL="$BUILD_DIR/serial.log"

mkdir -p "$BUILD_DIR"

echo "[1/4] Building the Inauguration .in compiler..."
make -C "$INAUG_DIR/in-cli" >/dev/null

echo "[2/4] Assembling the boot trampoline..."
nasm -f bin "$TRAMPOLINE_ASM" -o "$BUILD_DIR/trampoline.bin"
tramp_size=$(stat -f%z "$BUILD_DIR/trampoline.bin" 2>/dev/null || stat -c%s "$BUILD_DIR/trampoline.bin")
[ "$tramp_size" -eq 8192 ] || { echo "  error: trampoline is $tramp_size bytes, expected 8192" >&2; exit 1; }

echo "[3/4] Compiling kernel-root.in to a boot image..."
"$IN" compile \
  --path "$KERNEL_IN" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --out "$BUILD_DIR/kernel.bin" \
  --metadata "$BUILD_DIR/kernel.component-metadata.json" --json

echo "[4/4] Booting in QEMU and driving the shell..."
rm -f "$SERIAL"
# The leading 'help' absorbs the one byte the UART drops during early init.
printf 'help\rtest\rsnapshot\rspawn\rrestore\rmap\rstatus\rhalt\r' \
  | perl -e 'alarm 12; exec @ARGV' qemu-system-x86_64 \
      -kernel "$BUILD_DIR/kernel.bin" -m 256M \
      -serial stdio -display none -no-reboot >"$SERIAL" 2>/dev/null || true

echo "--- serial output ---"
cat "$SERIAL" 2>/dev/null || true
echo "---------------------"

# Required markers, one per subsystem.
declare -a MARKERS=(
  "space: kernel root entered"
  "available RAM bytes"
  "interrupts enabled"
  "supervisor evaluating heartbeat -> ACTIVATING"
  "DENIED undeclared cap"
  "scheduler quiesced"
  "channel drained"
  "preemption ended"
  "array selftest sum 0x000000000000008c"
  "restored to checkpoint"
  "readback 0x00000000cafebabe"
  "halting on request"
)

fail=0
for m in "${MARKERS[@]}"; do
  if grep -qF "$m" "$SERIAL" 2>/dev/null; then
    echo "  ok: $m"
  else
    echo "  MISSING: $m"
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "PASS: all subsystem markers observed on serial."
  exit 0
fi
echo "FAIL: one or more subsystem markers missing." >&2
exit 1
