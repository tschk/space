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

SCI_MAGIC=0x5343490000000001
DISPLAY_PHYS=0x1a0000
INPUT_PHYS=0x1e0000

OBJCOPY="${OBJCOPY:-llvm-objcopy}"
command -v "$OBJCOPY" >/dev/null 2>&1 || OBJCOPY="objcopy"

mkdir -p "$BUILD_DIR"

build_component() {
  local name=$1
  local src=$2
  local entry=$3
  local base=$4
  local out=$5
  echo "[component] building $name at virtual 0x$(printf '%x' "$base")..."
  "$IN" compile --path "$src" --entry "$entry" \
    --target native --target-triple x86_64-unknown-none --linkage static-lib \
    --base "$base" --out "$BUILD_DIR/$name.o" >/dev/null
  "$OBJCOPY" --change-section-address ".text=$(printf '0x%x' "$base")" \
    -O binary "$BUILD_DIR/$name.o" "$BUILD_DIR/$name.bin"
  python3 - "$BUILD_DIR/$name.bin" "$base" "$out" "$SCI_MAGIC" <<'PY'
import sys, struct, os
body_path, base_str, out_path, magic_str = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
base = int(base_str, 0)
magic = int(magic_str, 0)
body = open(body_path, "rb").read()
pages = (len(body) + 4095) // 4096
image_size = pages * 4096
body = body + b"\x00" * (image_size - len(body))
manifest = struct.pack("<QQQQ", magic, 1, base, 32 + len(body))
open(out_path, "wb").write(manifest + body)
PY
}

echo "[1/3] Building compiler..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"

echo "[2/3] Compiling nanokernel and runtime components..."
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

build_component "display" "$SPACE_DIR/components/display.in" display_entry 0x40000020 "$BUILD_DIR/display.sci"
build_component "input" "$SPACE_DIR/components/input.in" input_entry 0x50000020 "$BUILD_DIR/input.sci"

echo "[3/3] Assembling combined boot image..."
python3 - "$BUILD_DIR" "$DISPLAY_PHYS" "$INPUT_PHYS" <<'PY'
import sys, os, struct
bd, display_phys, input_phys = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
kernel = open(os.path.join(bd, "kernel.bin"), "rb").read()
display = open(os.path.join(bd, "display.sci"), "rb").read()
input_ = open(os.path.join(bd, "input.sci"), "rb").read()

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

out_path = os.path.join(bd, "combined.bin")
open(out_path, "wb").write(out)
print(f"  {out_path}: {len(out)} bytes")
print(f"  display SCI at physical 0x{display_phys:x}")
print(f"  input SCI at physical 0x{input_phys:x}")
PY

echo "Done. Boot with:"
echo "  qemu-system-x86_64 -kernel $BUILD_DIR/combined.bin -m 512M -vga std -serial stdio -display none"
