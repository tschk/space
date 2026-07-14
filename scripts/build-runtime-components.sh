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
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
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
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

"$IN" compile --path "$SPACE_DIR/components/display.in" --entry display_entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$DISPLAY_ENTRY" --out "$BUILD_DIR/display.sci"

"$IN" compile --path "$SPACE_DIR/components/input.in" --entry input_entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$INPUT_ENTRY" --out "$BUILD_DIR/input.sci"
"$IN" compile --path "$SPACE_DIR/components/volume.in" --entry volume_entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$VOLUME_ENTRY" --out "$BUILD_DIR/volume.sci"

echo "[3/3] Assembling combined boot image..."
python3 - "$BUILD_DIR" "$DISPLAY_PHYS" "$INPUT_PHYS" "$VOLUME_PHYS" <<'PY'
import sys, os
bd, display_phys, input_phys, volume_phys = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), int(sys.argv[4], 0)
kernel = open(os.path.join(bd, "kernel.bin"), "rb").read()
display = open(os.path.join(bd, "display.sci"), "rb").read()
input_ = open(os.path.join(bd, "input.sci"), "rb").read()
volume = open(os.path.join(bd, "volume.sci"), "rb").read()

out = bytearray(kernel)
display_off = display_phys - 0x100000
input_off = input_phys - 0x100000

out += b"\x00" * (display_off - len(out))
out += display

if len(out) > input_off:
    input_off = (len(out) + 4095) & -4096
    print(f"warning: input component moved to file offset 0x{input_off:x}")
out += b"\x00" * (input_off - len(out))
out += input_

volume_off = volume_phys - 0x100000
if len(out) > volume_off:
    raise SystemExit("volume SCI overlaps prior image")
out += b"\x00" * (volume_off - len(out))
out += volume

out_path = os.path.join(bd, "combined.bin")
open(out_path, "wb").write(out)
print(f"  {out_path}: {len(out)} bytes")
print(f"  display SCI at physical 0x{display_phys:x}")
print(f"  input SCI at physical 0x{input_phys:x}")
print(f"  volume SCI at physical 0x{volume_phys:x}")
PY

echo "Done. Boot with:"
echo "  qemu-system-x86_64 -kernel $BUILD_DIR/combined.bin -m 512M -rtc base=utc -vga std -serial stdio -display none"
