#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${BUILD_DIR:-/tmp/space-volume-nvme}"
SERIAL_A="$BUILD_DIR/serial-a.log"
SERIAL_B="$BUILD_DIR/serial-b.log"
FIFO_A="$BUILD_DIR/serial_in_a"
FIFO_B="$BUILD_DIR/serial_in_b"
NVME_IMG="$BUILD_DIR/nvme.img"
mkdir -p "$BUILD_DIR"
BUILD_DIR="$BUILD_DIR" "$SCRIPT_DIR/build-runtime-components.sh" >/dev/null
rm -f "$SERIAL_A" "$SERIAL_B" "$FIFO_A" "$FIFO_B" "$NVME_IMG"
truncate -s 64M "$NVME_IMG"

boot_until() {
  local serial="$1"
  local fifo="$2"
  local marker="$3"
  rm -f "$serial" "$fifo"
  mkfifo "$fifo"
  qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 512M -rtc base=utc \
    -vga std -serial stdio -display none -no-reboot \
    -drive file="$NVME_IMG",format=raw,if=none,id=nvme0 \
    -device nvme,drive=nvme0,serial=volume \
    <"$fifo" >"$serial" 2>/dev/null &
  local qpid=$!
  exec 3>"$fifo"
  local i
  for i in $(seq 1 600); do
    if grep -qF "$marker" "$serial" 2>/dev/null; then
      echo "halt" >&3
      exec 3>&-
      sleep 0.5
      kill "$qpid" 2>/dev/null || true
      wait "$qpid" 2>/dev/null || true
      rm -f "$fifo"
      return 0
    fi
    if ! kill -0 "$qpid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  echo "halt" >&3 2>/dev/null || true
  exec 3>&- 2>/dev/null || true
  kill "$qpid" 2>/dev/null || true
  wait "$qpid" 2>/dev/null || true
  rm -f "$fifo"
  return 1
}

echo "[1/2] Boot A: format Volume + write via SCI RPC onto NVMe..."
if ! boot_until "$SERIAL_A" "$FIFO_A" "volume: component init/write/read passed"; then
  echo "FAIL: boot A missing volume: component init/write/read passed" >&2
  exit 1
fi
grep -qF "volume: loading NVMe backing" "$SERIAL_A" || { echo "FAIL: boot A missing NVMe backing load" >&2; exit 1; }

echo "[2/2] Boot B: remount same NVMe image, prove persistence..."
if ! boot_until "$SERIAL_B" "$FIFO_B" "volume: component init/write/read passed"; then
  echo "FAIL: boot B missing volume: component init/write/read passed" >&2
  tail -40 "$SERIAL_B" >&2 || true
  exit 1
fi
grep -qF "volume: persistent mount passed" "$SERIAL_B" || {
  echo "FAIL: boot B missing volume: persistent mount passed" >&2
  exit 1
}
echo "PASS"
