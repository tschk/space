#!/usr/bin/env bash
#
# boot.sh — Build and boot Space interactively in QEMU.
#
# Drops you into the serial shell where you can type commands:
#   help        list all commands
#   status      realm/object/capability info
#   mem         RAM and heap state
#   ticks       timer tick count
#   ps          scheduler thread count
#   test        array self-test (sum of squares)
#   det         deterministic execution demo
#   domain      create a new memory domain
#   chan        cross-domain channel demo
#   pci         scan PCI bus for devices
#   net         e1000 NIC driver: ARP + UDP transmit
#   snapshot    checkpoint the object graph
#   spawn       allocate a new object
#   restore     restore from last checkpoint
#   map         map a virtual page and read it back
#   sci         load the SCI guest component (if present in image)
#   linux       run the Linux personality demo (POSIX syscall layer)
#   desktop     launch the graphical desktop environment (Wayland-style compositor)
#   fb          show framebuffer info
#   fault       trigger a page fault (tests exception handler)
#   divzero     trigger divide-by-zero (tests exception handler)
#   echo <x>    echo a string
#   peek <addr> read 8 bytes at a hex address
#   poke <addr> <val>  write 8 bytes at a hex address
#   uptime      ticks since boot
#   halt        stop the kernel
#
# Usage:
#   ./scripts/boot.sh              # boot with NVMe disk, VGA display, serial on stdio
#   ./scripts/boot.sh --net        # boot with e1000 NIC (for `net` command)
#   ./scripts/boot.sh --sci        # boot with SCI guest component loaded
#   ./scripts/boot.sh --usb        # boot with USB xHCI + HID keyboard
#   ./scripts/boot.sh --disk       # boot with NVMe disk (default, can be omitted)
#   ./scripts/boot.sh --no-gui     # boot without VGA display (serial only, no desktop)
#   ./scripts/boot.sh --net --usb  # both USB and network
#
# Requirements: nasm, qemu-system-x86_64, ../inauguration checked out
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-boot}"
IN="${IN:-$(which in 2>/dev/null || echo /Users/undivisible/projects/inauguration/in-cli/target/release/in)}"

USE_NET=0
USE_SCI=0
USE_USB=0
USE_DISK=1
USE_GUI=1
for arg in "$@"; do
  case "$arg" in
    --net) USE_NET=1 ;;
    --sci) USE_SCI=1 ;;
    --usb) USE_USB=1 ;;
    --disk) USE_DISK=1 ;;
    --no-disk) USE_DISK=0 ;;
    --no-gui) USE_GUI=0 ;;
    --help|-h)
      head -40 "$0" | tail -36
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

mkdir -p "$BUILD_DIR"

echo "[1/2] Assembling trampoline and compiling kernel..."
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"

"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

KERNEL_IMAGE="$BUILD_DIR/kernel.bin"

if [ "$USE_SCI" = "1" ]; then
  echo "  compiling SCI guest component..."
  GUEST_LOAD=$((0x140000))
  GUEST_VIRT_LOAD=$((0x40000000))
  GUEST_BASE=$((GUEST_VIRT_LOAD + 0x20))
  SCI_MAGIC=$((0x5343490000000001))
  GUEST_CAPS=1

  "$IN" compile --path "$SPACE_DIR/kernel/guest-service.in" --entry guest_entry \
    --target native --target-triple x86_64-unknown-none --linkage static-lib \
    --out "$BUILD_DIR/guest.o" >/dev/null

  OBJCOPY="${OBJCOPY:-llvm-objcopy}"
  command -v "$OBJCOPY" >/dev/null 2>&1 || OBJCOPY="objcopy"
  "$OBJCOPY" --change-section-address ".text=$(printf 0x%x "$GUEST_BASE")" \
    -O binary "$BUILD_DIR/guest.o" "$BUILD_DIR/guest.bin"

  python3 - "$BUILD_DIR" "$GUEST_LOAD" "$GUEST_BASE" "$SCI_MAGIC" "$GUEST_CAPS" <<'PY'
import sys, struct, os
build, gload, gbase, magic, caps = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
kernel = open(os.path.join(build, "kernel.bin"), "rb").read()
guest  = open(os.path.join(build, "guest.bin"), "rb").read()
img_base = 0x100000
manifest_off = gload - img_base
out = bytearray(kernel)
out += b"\x00" * (manifest_off - len(out))
out += struct.pack("<QQQQ", magic, caps, gbase, 32 + len(guest))
out += guest
open(os.path.join(build, "combined.bin"), "wb").write(out)
print(f"  combined image: {len(out)} bytes, SCI manifest at 0x{gload:x}")
PY
  KERNEL_IMAGE="$BUILD_DIR/combined.bin"
fi

BOOT_SIZE=$(wc -c < "$KERNEL_IMAGE")
echo "  boot image: $BOOT_SIZE bytes"

# Create the NVMe disk image if it does not exist yet.
DISK_IMG="${DISK_IMG:-/tmp/space-nvme.img}"
if [ "$USE_DISK" = "1" ]; then
  if [ ! -f "$DISK_IMG" ]; then
    echo "  creating NVMe disk image (16 MB)..."
    dd if=/dev/zero of="$DISK_IMG" bs=1M count=16 status=none
  fi
fi

echo "[2/2] Booting in QEMU (Ctrl-A X to quit)..."
echo

QEMU_ARGS=(
  -kernel "$KERNEL_IMAGE"
  -m 256M
  -no-reboot
  -serial stdio
)

if [ "$USE_GUI" = "1" ]; then
  QEMU_ARGS+=(-vga std)
  echo "  VGA: standard display enabled (try 'desktop' command for graphical environment)"
else
  QEMU_ARGS+=(-display none)
fi

if [ "$USE_DISK" = "1" ]; then
  QEMU_ARGS+=(-drive file="$DISK_IMG",if=none,id=nvme0,format=raw)
  QEMU_ARGS+=(-device nvme,drive=nvme0,serial=space_nvme)
  echo "  Disk: NVMe attached (try 'nvme', 'format', 'ls', 'write', 'read' commands)"
fi

if [ "$USE_NET" = "1" ]; then
  QEMU_ARGS+=(-netdev user,id=net0 -device e1000,netdev=net0)
  echo "  NIC: e1000 attached (try 'net' command)"
fi

if [ "$USE_SCI" = "1" ]; then
  echo "  SCI: guest component loaded (try 'sci' command)"
fi

if [ "$USE_USB" = "1" ]; then
  QEMU_ARGS+=(-device qemu-xhci,id=xhci -device usb-kbd)
  echo "  USB: xHCI controller + HID keyboard attached (try 'key', 'desktop' commands)"
fi

echo
exec qemu-system-x86_64 "${QEMU_ARGS[@]}"
