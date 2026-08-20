#!/usr/bin/env bash
set -euo pipefail

# build-user-sci.sh — Compile user SCIs and embed:
#   0x190000  user-hello SCI — shell: hello
#   0x1b0000  user-echo  SCI — shell: uecho
# Virtual entry bases map SCI header at entry-32.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-user-sci}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"

HELLO_PHYS=0x190000
ECHO_PHYS=0x1b0000
HELLO_ENTRY=0x70000020
ECHO_ENTRY=0x71000020

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler and trampoline..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"

echo "[2/3] Compiling kernel and user SCIs..."
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

"$IN" compile --path "$SPACE_DIR/components/user-hello.in" --entry hello-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$HELLO_ENTRY" --out "$BUILD_DIR/user-hello.sci"

"$IN" compile --path "$SPACE_DIR/components/user-echo.in" --entry echo-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$ECHO_ENTRY" --out "$BUILD_DIR/user-echo.sci"

echo "[3/3] Assembling combined boot image..."
python3 "$SCRIPT_DIR/pack-sci-image.py" "$BUILD_DIR/kernel.bin" "$BUILD_DIR/combined.bin" \
  "5:$BUILD_DIR/user-hello.sci" "6:$BUILD_DIR/user-echo.sci"

echo "Done. Boot with:"
echo "  qemu-system-x86_64 -kernel $BUILD_DIR/combined.bin -m 256M -nographic -no-reboot -serial stdio"
