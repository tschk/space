#!/usr/bin/env bash
set -euo pipefail

# build-user-sci.sh — Compile HelloUser as SCI and embed at physical 0x190000.
#
# Layout (multiboot image base 0x100000):
#   0x100000  kernel boot image
#   0x190000  user-hello SCI (manifest + code), shell: hello / sci-load
# Virtual entry base: 0x70000020 (maps SCI header at 0x70000000)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-user-sci}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"

USER_PHYS=0x190000
USER_ENTRY=0x70000020

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler and trampoline..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"

echo "[2/3] Compiling kernel and user-hello SCI..."
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

"$IN" compile --path "$SPACE_DIR/components/user-hello.in" --entry hello-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$USER_ENTRY" --out "$BUILD_DIR/user-hello.sci"

echo "[3/3] Assembling combined boot image..."
python3 - "$BUILD_DIR" "$USER_PHYS" <<'PY'
import sys, os, struct
bd, user_phys = sys.argv[1], int(sys.argv[2], 0)
kernel = open(os.path.join(bd, "kernel.bin"), "rb").read()
user = open(os.path.join(bd, "user-hello.sci"), "rb").read()
if len(user) < 32:
    raise SystemExit("user-hello.sci too small")
magic = struct.unpack_from("<Q", user, 0)[0]
if magic != 0x5343490000000001:
    raise SystemExit(f"bad SCI magic 0x{magic:x}")
off = user_phys - 0x100000
if len(kernel) > off:
    raise SystemExit(f"kernel overlaps user SCI slot (kernel={len(kernel)} off={off})")
out = bytearray(kernel)
out += b"\x00" * (off - len(out))
out += user
out_path = os.path.join(bd, "combined.bin")
open(out_path, "wb").write(out)
print(f"  {out_path}: {len(out)} bytes")
print(f"  user-hello SCI at physical 0x{user_phys:x}")
print(f"  shell: hello  (sci-load 0x{user_phys:x})")
PY

echo "Done. Boot with:"
echo "  qemu-system-x86_64 -kernel $BUILD_DIR/combined.bin -m 256M -nographic -no-reboot -serial stdio"
