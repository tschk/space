#!/usr/bin/env bash
#
# check-qemu-boot.sh — Build the Space nanokernel from `.in` and boot it in QEMU.
#
# Pipeline:
#   1. build the Inauguration `.in` compiler (../inauguration)
#   2. assemble the long-mode boot trampoline (nasm -f bin)
#   3. compile kernel/kernel-root.in to a flat Multiboot1 boot image
#   4. boot it under qemu-system-x86_64 and verify the serial marker
#
# Requirements: clang, make, nasm, qemu-system-x86_64.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-boot}"
MARKER="space: kernel root entered"

IN="$INAUG_DIR/in-cli/in"
KERNEL_IN="$SPACE_DIR/kernel/kernel-root.in"
TRAMPOLINE_ASM="$SPACE_DIR/boot/multiboot.asm"

mkdir -p "$BUILD_DIR"

echo "[1/4] Building the Inauguration .in compiler..."
make -C "$INAUG_DIR/in-cli" >/dev/null

echo "[2/4] Assembling the boot trampoline..."
nasm -f bin "$TRAMPOLINE_ASM" -o "$BUILD_DIR/trampoline.bin"
tramp_size=$(stat -f%z "$BUILD_DIR/trampoline.bin" 2>/dev/null || stat -c%s "$BUILD_DIR/trampoline.bin")
if [ "$tramp_size" -ne 8192 ]; then
  echo "  error: trampoline is $tramp_size bytes, expected 8192" >&2
  exit 1
fi

echo "[3/4] Compiling kernel-root.in to a boot image..."
"$IN" compile \
  --path "$KERNEL_IN" \
  --entry kernel_entry \
  --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --out "$BUILD_DIR/kernel.bin" \
  --metadata "$BUILD_DIR/kernel.component-metadata.json" \
  --json

echo "[4/4] Booting in QEMU..."
rm -f "$BUILD_DIR/serial.log"
perl -e 'alarm 6; exec @ARGV' qemu-system-x86_64 \
  -kernel "$BUILD_DIR/kernel.bin" \
  -serial "file:$BUILD_DIR/serial.log" \
  -display none -no-reboot >/dev/null 2>&1 || true

echo "--- serial output ---"
cat "$BUILD_DIR/serial.log" 2>/dev/null || true
echo "---------------------"

if grep -q "$MARKER" "$BUILD_DIR/serial.log" 2>/dev/null; then
  echo "PASS: '$MARKER' observed on serial."
  exit 0
fi
echo "FAIL: boot marker not found on serial." >&2
exit 1
