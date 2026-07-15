#!/usr/bin/env bash
set -euo pipefail

# check-volume-soak.sh — sole-FS soak on volume-ready path.
#
# Builds kernel + Volume SCI only (no display/input: those preempt and starve
# the serial shell). Embeds Volume at 0x220000 like build-runtime-components.
#
# Boot A: wait volume bind, shell multi-file write/read
# Boot B: remount same NVMe, cat both files
# Path: shell write/cat → filesystem.in volume-ready → Volume RPC → NVMe LBA

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-volume-soak}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
SERIAL_A="$BUILD_DIR/serial-a.log"
SERIAL_B="$BUILD_DIR/serial-b.log"
FIFO_A="$BUILD_DIR/serial_in_a"
FIFO_B="$BUILD_DIR/serial_in_b"
NVME_IMG="$BUILD_DIR/nvme.img"
VOLUME_PHYS=0x220000
VOLUME_ENTRY=0x60000020

mkdir -p "$BUILD_DIR"
echo "[0/2] Building volume-only image (kernel + Volume SCI)..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null
"$IN" compile --path "$SPACE_DIR/components/volume.in" --entry volume-entry \
  --target native --target-triple x86_64-unknown-none --emit sci \
  --base "$VOLUME_ENTRY" --out "$BUILD_DIR/volume.sci"
python3 - "$BUILD_DIR" "$VOLUME_PHYS" <<'PY'
import sys, os
bd, volume_phys = sys.argv[1], int(sys.argv[2], 0)
kernel = open(os.path.join(bd, "kernel.bin"), "rb").read()
volume = open(os.path.join(bd, "volume.sci"), "rb").read()
out = bytearray(kernel)
off = volume_phys - 0x100000
if len(out) > off:
    raise SystemExit(f"kernel overlaps volume slot ({len(out)} > {off})")
out += b"\x00" * (off - len(out))
out += volume
open(os.path.join(bd, "combined.bin"), "wb").write(out)
print(f"  combined.bin: {len(out)} bytes (volume @ 0x{volume_phys:x})")
PY

rm -f "$SERIAL_A" "$SERIAL_B" "$FIFO_A" "$FIFO_B" "$NVME_IMG"
truncate -s 64M "$NVME_IMG"

wait_marker() {
  local serial="$1" qpid="$2" marker="$3" tries="${4:-600}"
  local i
  for i in $(seq 1 "$tries"); do
    if grep -qF "$marker" "$serial" 2>/dev/null; then
      return 0
    fi
    if ! kill -0 "$qpid" 2>/dev/null; then
      return 1
    fi
    sleep 0.1
  done
  return 1
}

stop_qemu() {
  local qpid="$1" fifo="$2"
  printf 'halt\r' >&3 2>/dev/null || true
  exec 3>&- 2>/dev/null || true
  sleep 0.5
  kill "$qpid" 2>/dev/null || true
  wait "$qpid" 2>/dev/null || true
  rm -f "$fifo"
}

echo "[1/2] Boot A: volume bind + multi-file shell write/read..."
rm -f "$SERIAL_A" "$FIFO_A"
mkfifo "$FIFO_A"
qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 512M -rtc base=utc \
  -vga std -serial stdio -display none -no-reboot \
  -drive file="$NVME_IMG",format=raw,if=none,id=nvme0 \
  -device nvme,drive=nvme0,serial=volume \
  <"$FIFO_A" >"$SERIAL_A" 2>/dev/null &
QPID=$!
exec 3>"$FIFO_A"
if ! wait_marker "$SERIAL_A" "$QPID" "interactive shell"; then
  echo "FAIL: boot A shell missing" >&2
  stop_qemu "$QPID" "$FIFO_A"
  exit 1
fi
if ! wait_marker "$SERIAL_A" "$QPID" "volume: client bound"; then
  echo "FAIL: boot A missing volume: client bound" >&2
  stop_qemu "$QPID" "$FIFO_A"
  exit 1
fi
printf 'write a alpha\r' >&3
printf 'write b bravo\r' >&3
printf 'cat a\r' >&3
printf 'cat b\r' >&3
for m in "  written" "alpha" "bravo" "volume: filesystem op via Volume RPC"; do
  if ! wait_marker "$SERIAL_A" "$QPID" "$m" 200; then
    echo "FAIL: boot A missing marker: $m" >&2
    tail -60 "$SERIAL_A" >&2 || true
    stop_qemu "$QPID" "$FIFO_A"
    exit 1
  fi
done
stop_qemu "$QPID" "$FIFO_A"

for m in "volume: loading NVMe backing" "volume: component init/write/read passed" \
         "volume: client bound" "volume: filesystem op via Volume RPC" \
         "  written" "alpha" "bravo"; do
  grep -qF "$m" "$SERIAL_A" || { echo "FAIL: boot A missing $m" >&2; exit 1; }
done

echo "[2/2] Boot B: remount NVMe, cat both files..."
rm -f "$SERIAL_B" "$FIFO_B"
mkfifo "$FIFO_B"
qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 512M -rtc base=utc \
  -vga std -serial stdio -display none -no-reboot \
  -drive file="$NVME_IMG",format=raw,if=none,id=nvme0 \
  -device nvme,drive=nvme0,serial=volume \
  <"$FIFO_B" >"$SERIAL_B" 2>/dev/null &
QPID=$!
exec 3>"$FIFO_B"
if ! wait_marker "$SERIAL_B" "$QPID" "interactive shell"; then
  echo "FAIL: boot B shell missing" >&2
  stop_qemu "$QPID" "$FIFO_B"
  exit 1
fi
if ! wait_marker "$SERIAL_B" "$QPID" "volume: persistent mount passed"; then
  echo "FAIL: boot B missing volume: persistent mount passed" >&2
  tail -40 "$SERIAL_B" >&2 || true
  stop_qemu "$QPID" "$FIFO_B"
  exit 1
fi
printf 'cat a\r' >&3
printf 'cat b\r' >&3
for m in "alpha" "bravo"; do
  if ! wait_marker "$SERIAL_B" "$QPID" "$m" 200; then
    echo "FAIL: boot B missing persisted file content: $m" >&2
    tail -60 "$SERIAL_B" >&2 || true
    stop_qemu "$QPID" "$FIFO_B"
    exit 1
  fi
done
stop_qemu "$QPID" "$FIFO_B"

for m in "volume: persistent mount passed" "alpha" "bravo"; do
  grep -qF "$m" "$SERIAL_B" || { echo "FAIL: boot B missing $m" >&2; exit 1; }
done

echo "PASS: volume-ready multi-file shell soak (write a/b, reboot, cat both)"
echo "  path: shell write/cat → filesystem.in volume-ready → Volume RPC → NVMe LBA backing"
echo "  note: volume-only image (no display/input SCI; those starve serial shell)"
