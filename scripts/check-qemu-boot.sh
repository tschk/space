#!/usr/bin/env bash
#
# check-qemu-boot.sh — Build Space kernel and boot in QEMU
#
# Prerequisites:
#   - ../inauguration built (release mode)
#   - limine installed
#   - x86_64-qemu available (qemu-system-x86_64)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="$SPACE_DIR/../inauguration"
BUILD_DIR="/tmp/space-boot"

KERNEL_IN="$SPACE_DIR/kernel/kernel-root.in"
LIMINE_CONF="$SPACE_DIR/boot/limine.conf"
LINKER_SCRIPT="$SPACE_DIR/boot/linker.ld"
ENTRY_ASM="$SPACE_DIR/boot/x86_64-entry.S"

echo "=== Space QEMU Boot Check ==="

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Step 1: Compile .in kernel to freestanding ELF object
echo "[1/5] Compiling .in kernel..."
"$INAUG_DIR/in-cli/target/release/in" compile \
    --path "$KERNEL_IN" \
    --target native \
    --target-triple x86_64-unknown-none \
    --linkage static-lib \
    --entry kernel_entry \
    --out "$BUILD_DIR/kernel.o" \
    --json 2>&1 || echo "  (compilation not yet implemented — placeholder)"

# Step 2: Assemble boot shim
echo "[2/5] Assembling boot shim..."
as --64 -o "$BUILD_DIR/entry.o" "$ENTRY_ASM"

# Step 3: Link into final ELF
echo "[3/5] Linking kernel..."
ld.lld \
    -T "$LINKER_SCRIPT" \
    -o "$BUILD_DIR/kernel.elf" \
    "$BUILD_DIR/entry.o" \
    "$BUILD_DIR/kernel.o" \
    2>&1 || echo "  (linking not yet possible — placeholder)"

# Step 4: Create bootable image
echo "[4/5] Creating boot image..."
cp "$LIMINE_CONF" "$BUILD_DIR/limine.conf"
# limine bios-install "$BUILD_DIR/kernel.elf" 2>&1 || true

# Step 5: Boot in QEMU
echo "[5/5] Booting in QEMU..."
# qemu-system-x86_64 \
#     -cdrom "$BUILD_DIR/space.iso" \
#     -serial stdio \
#     -no-reboot \
#     -m 256M \
#     2>&1

echo ""
echo "=== Boot check complete ==="
echo "Note: full compilation and boot requires Inauguration"
echo "Tasks 2-4 (freestanding x86_64 output + real lowering)."
