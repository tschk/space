#!/usr/bin/env bash
set -euo pipefail

# build-runtime-components.sh — Compile Space display/input components into
# SCI binaries and assemble them into a combined boot image after the nanokernel.
#
# The kernel probes fixed physical addresses for SCI manifests:
#   display component at 0x1a0000
#   input component   at 0x1e0000
#
# These are embedded in the boot image file at file offsets physical-0x100000
# because the multiboot loader loads the image at physical 0x100000.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-runtime}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"

DISPLAY_PHYS=0x1a0000
INPUT_PHYS=0x1e0000
VOLUME_PHYS=0x220000
DISPLAY_ENTRY=0x40000020
INPUT_ENTRY=0x50000020
VOLUME_ENTRY=0x60000020

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler..."
cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"

echo "[2/3] Compiling nanokernel and runtime components..."
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

"$IN" compile --path "$SPACE_DIR/components/display-standalone.in" --entry display-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$DISPLAY_ENTRY" --out "$BUILD_DIR/display.sci"

"$IN" compile --path "$SPACE_DIR/components/input.in" --entry input-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$INPUT_ENTRY" --out "$BUILD_DIR/input.sci"
"$IN" compile --path "$SPACE_DIR/components/volume.in" --entry volume-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$VOLUME_ENTRY" --out "$BUILD_DIR/volume.sci"

echo "[3/3] Assembling combined boot image..."
python3 "$SCRIPT_DIR/pack-sci-image.py" "$BUILD_DIR/kernel.bin" "$BUILD_DIR/combined.bin" \
  "2:$BUILD_DIR/display.sci" "3:$BUILD_DIR/input.sci" "4:$BUILD_DIR/volume.sci"

echo "Done. Boot with:"
echo "  qemu-system-x86_64 -kernel $BUILD_DIR/combined.bin -m 512M -rtc base=utc -vga std -serial stdio -display none"
