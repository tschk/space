#!/usr/bin/env bash
#
# build-multicomponent.sh — Build a boot image containing the nanokernel plus a
# separately-compiled SCI component, then boot it and exercise the SCI loader.
#
# Memory layout of the combined image (loaded at 0x100000 by QEMU multiboot):
#   0x100000  boot trampoline + nanokernel (the normal boot image)
#   0x140000  16-byte SCI manifest: [magic][required_caps][entry][reserved]
#   0x140020  guest-service component code (compiled with --base 0x140020)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-multi}"
IN="$INAUG_DIR/in-cli/in"

GUEST_LOAD=$((0x140000))     # manifest address
GUEST_BASE=$((0x140020))     # guest code base (after the 32-byte manifest)
SCI_MAGIC=$((0x5343490000000001))
GUEST_REQUIRED_CAPS=1        # serial; must match the guest's declared capability

mkdir -p "$BUILD_DIR"

echo "[1/5] Building the compiler and trampoline..."
make -C "$INAUG_DIR/in-cli" >/dev/null
nasm -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"

echo "[2/5] Compiling the nanokernel boot image..."
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry \
  --emit boot --trampoline "$BUILD_DIR/trampoline.bin" \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

echo "[3/5] Compiling the guest SCI component at base $(printf 0x%x "$GUEST_BASE")..."
"$IN" compile --path "$SPACE_DIR/kernel/guest-service.in" --entry guest_entry \
  --emit flat --base "$(printf 0x%x "$GUEST_BASE")" \
  --out "$BUILD_DIR/guest.bin" \
  --metadata "$BUILD_DIR/guest.component-metadata.json" >/dev/null

echo "[4/5] Assembling the combined image with the SCI manifest..."
python3 - "$BUILD_DIR" "$GUEST_LOAD" "$GUEST_BASE" "$SCI_MAGIC" "$GUEST_REQUIRED_CAPS" <<'PY'
import sys, struct, os
build, gload, gbase, magic, caps = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
kernel = open(os.path.join(build, "kernel.bin"), "rb").read()
guest  = open(os.path.join(build, "guest.bin"), "rb").read()
img_base = 0x100000
manifest_off = gload - img_base       # file offset of the manifest
assert len(kernel) <= manifest_off, "kernel image overlaps the guest load address"
out = bytearray(kernel)
out += b"\x00" * (manifest_off - len(out))          # pad to the manifest offset
out += struct.pack("<QQQQ", magic, caps, gbase, 0)  # 32-byte SCI manifest
out += guest                                        # component code at gbase
open(os.path.join(build, "combined.bin"), "wb").write(out)
print(f"  combined image: {len(out)} bytes, manifest at 0x{gload:x}, guest at 0x{gbase:x}")
PY

echo "[5/5] Booting and running the SCI loader..."
rm -f "$BUILD_DIR/serial.log"
printf 'help\rsci\rhalt\r' | perl -e 'alarm 10; exec @ARGV' qemu-system-x86_64 \
  -kernel "$BUILD_DIR/combined.bin" -m 256M \
  -serial stdio -display none -no-reboot >"$BUILD_DIR/serial.log" 2>/dev/null || true

echo "--- SCI loader output ---"
sed -n '/space> sci/,/space>/p' "$BUILD_DIR/serial.log" 2>/dev/null || true
echo "-------------------------"

if grep -q "guest-service] separately-compiled SCI component running" "$BUILD_DIR/serial.log" 2>/dev/null \
   && grep -q "SCI: component returned status 0x0000000000001042" "$BUILD_DIR/serial.log" 2>/dev/null; then
  echo "PASS: SCI component loaded, validated, executed, and returned the expected status."
  exit 0
fi
echo "FAIL: SCI loader did not run the component as expected." >&2
exit 1
