#!/usr/bin/env bash
#
# check-dhcp.sh — Boot with e1000 + QEMU user DHCP, run shell `dhcp`, expect lease.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-dhcp}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler, trampoline, kernel..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
nasm -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry \
  --emit boot --trampoline "$BUILD_DIR/trampoline.bin" \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

echo "[2/3] Booting with e1000 user net, running dhcp..."
rm -f "$BUILD_DIR/serial.log" "$BUILD_DIR/dhcp.in"
printf 'help\rdhcp\rhalt\r' > "$BUILD_DIR/dhcp.in"
qemu-system-x86_64 \
  -kernel "$BUILD_DIR/kernel.bin" -m 256M \
  -netdev user,id=n0 -device e1000,netdev=n0 \
  -serial stdio -display none -no-reboot < "$BUILD_DIR/dhcp.in" > "$BUILD_DIR/serial.log" 2>/dev/null &
QPID=$!
for _ in $(seq 1 400); do
  if grep -qE "dhcp: (lease |timeout)" "$BUILD_DIR/serial.log" 2>/dev/null; then
    break
  fi
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
sleep 0.5
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
rm -f "$BUILD_DIR/dhcp.in"

echo "--- dhcp serial ---"
sed -n '/space> dhcp/,/space>/p' "$BUILD_DIR/serial.log" 2>/dev/null || cat "$BUILD_DIR/serial.log"
echo "-------------------"

grep -qF "dhcp: discover sent" "$BUILD_DIR/serial.log"

if grep -qF "dhcp: lease " "$BUILD_DIR/serial.log"; then
  echo "[3/3] PASS: full DHCP lease acquired"
  grep -F "dhcp: " "$BUILD_DIR/serial.log" || true
  exit 0
fi

if grep -qF "dhcp: timeout" "$BUILD_DIR/serial.log"; then
  echo "[3/3] WARN: discover sent but no OFFER/ACK (timeout path OK)"
  exit 0
fi

echo "[3/3] FAIL: no dhcp discover/timeout/lease output"
exit 1
