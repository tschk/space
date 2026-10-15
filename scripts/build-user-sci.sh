#!/usr/bin/env bash
set -euo pipefail

# build-user-sci.sh — Compile the shared library and user SCIs, then embed:
#   kind 7  libspace SCI   — shared library, exports lib-* symbols
#   kind 5  user-hello SCI — shell: hello  (imports lib-*)
#   kind 6  user-echo  SCI — shell: uecho  (imports lib-*)
# --base values are page-aligned SCI image bases (SCI v2, 64-byte manifest);
# the manifest entry becomes base+64 (the linked code start).
# The library image is compiled at page-aligned LIB-VIRT-BASE (0x3F000000)
# used by the loader.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-user-sci}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"

LIB_BASE=0x3F000000
HELLO_BASE=0x70000000
ECHO_BASE=0x71000000

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler and trampoline..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"

echo "[2/3] Compiling kernel, shared library, and user SCIs..."
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

"$IN" compile --path "$SPACE_DIR/components/libspace.in" --entry lib-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$LIB_BASE" --out "$BUILD_DIR/libspace.sci"

"$IN" compile --path "$SPACE_DIR/components/user-hello.in" --entry hello-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$HELLO_BASE" --out "$BUILD_DIR/user-hello.sci"

"$IN" compile --path "$SPACE_DIR/components/user-echo.in" --entry echo-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$ECHO_BASE" --out "$BUILD_DIR/user-echo.sci"

echo "[3/3] Assembling combined boot image..."
python3 "$SCRIPT_DIR/pack-sci-image.py" "$BUILD_DIR/kernel.bin" "$BUILD_DIR/combined.bin" \
  "7:$BUILD_DIR/libspace.sci" "5:$BUILD_DIR/user-hello.sci" "6:$BUILD_DIR/user-echo.sci"

echo "Done. Boot with:"
echo "  qemu-system-x86_64 -kernel $BUILD_DIR/combined.bin -m 256M -nographic -no-reboot -serial stdio"
