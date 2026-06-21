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
# ponytail: use release binary, not in-tree build
IN="$INAUG_DIR/in-cli/target/release/in"

GUEST_LOAD=$((0x140000))     # manifest address
GUEST_BASE=$((0x140020))     # guest code base (after the 32-byte manifest)
SCI_MAGIC=$((0x5343490000000001))
GUEST_REQUIRED_CAPS=1        # serial; must match the guest's declared capability
GUEST_DENIED_CAPS=4

mkdir -p "$BUILD_DIR"

echo "[1/5] Building the compiler and trampoline..."
cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"

echo "[2/5] Compiling the nanokernel boot image..."
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry \
  --emit boot --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

echo "[3/5] Compiling the guest SCI component at base $(printf 0x%x "$GUEST_BASE")..."
"$IN" compile --path "$SPACE_DIR/kernel/guest-service.in" --entry guest_entry \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/guest.o" >/dev/null

OBJCOPY="${OBJCOPY:-llvm-objcopy}"
if ! command -v "$OBJCOPY" >/dev/null 2>&1; then
  OBJCOPY="objcopy"
fi
"$OBJCOPY" --change-section-address ".text=$(printf 0x%x "$GUEST_BASE")" \
  -O binary "$BUILD_DIR/guest.o" "$BUILD_DIR/guest.bin"

python3 - "$BUILD_DIR/guest.component-metadata.json" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f:
    meta = json.load(f)
target = meta.get("target")
if target != "x86_64-unknown-none":
    print(f"FAIL: guest metadata target {target!r}, expected 'x86_64-unknown-none'", file=sys.stderr)
    sys.exit(1)
PY

assemble_image() {
  python3 - "$BUILD_DIR" "$GUEST_LOAD" "$GUEST_BASE" "$SCI_MAGIC" "$1" "$2" <<'PY'
import sys, struct, os
build, gload, gbase, magic, caps, out_name = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
kernel = open(os.path.join(build, "kernel.bin"), "rb").read()
guest  = open(os.path.join(build, "guest.bin"), "rb").read()
img_base = 0x100000
manifest_off = gload - img_base       # file offset of the manifest
assert len(kernel) <= manifest_off, "kernel image overlaps the guest load address"
out = bytearray(kernel)
out += b"\x00" * (manifest_off - len(out))          # pad to the manifest offset
out += struct.pack("<QQQQ", magic, caps, gbase, 0)  # 32-byte SCI manifest
out += guest                                        # component code at gbase
open(os.path.join(build, out_name), "wb").write(out)
print(f"  {out_name}: {len(out)} bytes, manifest at 0x{gload:x}, guest at 0x{gbase:x}")
PY
}

echo "[4/5] Assembling the combined image with the SCI manifest..."
assemble_image "$GUEST_DENIED_CAPS" "combined-denied.bin"
assemble_image "$GUEST_REQUIRED_CAPS" "combined.bin"

echo "[5/5] Booting and running the SCI loader..."
EXPECT="${EXPECT:-expect}"
if ! command -v "$EXPECT" >/dev/null 2>&1; then
  echo "FAIL: expect is required to drive QEMU serial input" >&2
  exit 1
fi

rm -f "$BUILD_DIR/serial-denied.log"
"$EXPECT" <<EOF >/dev/null 2>&1 || true
set timeout 20
log_file -noappend "$BUILD_DIR/serial-denied.log"
spawn qemu-system-x86_64 -kernel "$BUILD_DIR/combined-denied.bin" -m 256M -nographic -no-reboot
expect "SCI: DENIED undeclared cap"
expect "space> "
send "halt\r"
after 500
close
wait
EOF

echo "--- SCI denial output ---"
sed -n '/SCI: manifest ok/,/SCI: DENIED undeclared cap/p' "$BUILD_DIR/serial-denied.log" 2>/dev/null || true
echo "-------------------------"

if ! grep -q "SCI: DENIED undeclared cap 0x0000000000000004" "$BUILD_DIR/serial-denied.log" 2>/dev/null \
   || grep -q "SCI: component returned status 0x" "$BUILD_DIR/serial-denied.log" 2>/dev/null; then
  echo "FAIL: SCI loader did not reject the missing required cap as expected." >&2
  exit 1
fi

rm -f "$BUILD_DIR/serial.log"
"$EXPECT" <<EOF >/dev/null 2>&1 || true
set timeout 20
log_file -noappend "$BUILD_DIR/serial.log"
spawn qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 256M -nographic -no-reboot
expect "space interactive shell"
expect "space> "
send "sci\r"
expect "SCI: component returned status"
send "halt\r"
after 500
close
wait
EOF

echo "--- SCI loader output ---"
sed -n '/SCI: manifest ok/,/SCI: component returned status/p' "$BUILD_DIR/serial.log" 2>/dev/null || true
echo "-------------------------"

if grep -q "SCI: manifest ok, caps 0x0000000000000001 entry 0x0000000000140020" "$BUILD_DIR/serial.log" 2>/dev/null \
   && grep -q "cap check passed" "$BUILD_DIR/serial.log" 2>/dev/null \
   && grep -q "SCI: component returned status 0x" "$BUILD_DIR/serial.log" 2>/dev/null \
   && ! grep -q "SCI: component returned status 0x000000000000dead" "$BUILD_DIR/serial.log" 2>/dev/null; then
  echo "PASS: SCI component loaded, validated, executed, and returned the expected status."
  exit 0
fi
echo "FAIL: SCI loader did not run the component as expected." >&2
exit 1
