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
python3 - "$BUILD_DIR" "$HELLO_PHYS" "$ECHO_PHYS" <<'PY'
import sys, os, struct
bd, hello_phys, echo_phys = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
kernel = open(os.path.join(bd, "kernel.bin"), "rb").read()
hello = open(os.path.join(bd, "user-hello.sci"), "rb").read()
echo = open(os.path.join(bd, "user-echo.sci"), "rb").read()
for name, blob in (("user-hello.sci", hello), ("user-echo.sci", echo)):
    if len(blob) < 32:
        raise SystemExit(f"{name} too small")
    magic = struct.unpack_from("<Q", blob, 0)[0]
    if magic != 0x5343490000000001:
        raise SystemExit(f"bad SCI magic in {name}: 0x{magic:x}")
out = bytearray(kernel)
for phys, blob, label in (
    (hello_phys, hello, "user-hello"),
    (echo_phys, echo, "user-echo"),
):
    off = phys - 0x100000
    if len(out) > off:
        raise SystemExit(f"overlap before {label} slot (len={len(out)} off={off})")
    out += b"\x00" * (off - len(out))
    out += blob
    print(f"  {label} SCI at physical 0x{phys:x} ({len(blob)} bytes)")
out_path = os.path.join(bd, "combined.bin")
open(out_path, "wb").write(out)
print(f"  {out_path}: {len(out)} bytes")
print(f"  shell: hello / uecho")
PY

echo "Done. Boot with:"
echo "  qemu-system-x86_64 -kernel $BUILD_DIR/combined.bin -m 256M -nographic -no-reboot -serial stdio"
