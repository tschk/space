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

IN="$INAUG_DIR/in-cli/target/release/in"
KERNEL_IN="$SPACE_DIR/kernel/kernel-root.in"
TRAMPOLINE_ASM="$SPACE_DIR/boot/multiboot.asm"
SERIAL="$BUILD_DIR/serial.log"

mkdir -p "$BUILD_DIR"

echo "[1/4] Building the Inauguration .in compiler..."
cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml" 2>&1 | grep -E "error|warning" || true

echo "[2/4] Checking boot trampoline..."
if [ -f /tmp/trampoline.bin ]; then
  cp /tmp/trampoline.bin "$BUILD_DIR/trampoline.bin"
else
  if command -v nasm &>/dev/null; then
    nasm -f bin "$TRAMPOLINE_ASM" -o "$BUILD_DIR/trampoline.bin"
  else
    echo "  error: no trampoline found at /tmp/trampoline.bin and nasm not available" >&2
    exit 1
  fi
fi
tramp_size=$(stat -f%z "$BUILD_DIR/trampoline.bin" 2>/dev/null || stat -c%s "$BUILD_DIR/trampoline.bin")
[ "$tramp_size" -eq 8192 ] || { echo "  error: trampoline is $tramp_size bytes, expected 8192" >&2; exit 1; }

echo "[3/4] Compiling kernel-root.in to a boot image..."
"$IN" compile \
  --path "$KERNEL_IN" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

echo "[4/4] Booting in QEMU and driving the shell..."
rm -f "$SERIAL"
printf '\r' | perl -e 'alarm 6; exec @ARGV' qemu-system-x86_64 \
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
  "CR2"
  "halting"
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
