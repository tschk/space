#!/usr/bin/env bash
#
# check-dns.sh — Boot with e1000, run shell `dns` (optional name), accept any
# non-crash dns: line (a / no answer / timeout). Query TX path is enough.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-dns}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler, trampoline, kernel..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
nasm -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry \
  --emit boot --trampoline "$BUILD_DIR/trampoline.bin" \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

echo "[2/3] Booting with e1000 user net, dhcp then dns example.com..."
rm -f "$BUILD_DIR/serial.log" "$BUILD_DIR/dns.in"
# dhcp first (lease optional); then A query — any dns: outcome is PASS if line prints
printf 'help\rdhcp\rdns example.com\rhalt\r' > "$BUILD_DIR/dns.in"
qemu-system-x86_64 \
  -kernel "$BUILD_DIR/kernel.bin" -m 256M \
  -netdev user,id=n0 -device e1000,netdev=n0 \
  -serial stdio -display none -no-reboot < "$BUILD_DIR/dns.in" > "$BUILD_DIR/serial.log" 2>/dev/null &
QPID=$!
for _ in $(seq 1 500); do
  if grep -qE "dns: (a |no answer|timeout)" "$BUILD_DIR/serial.log" 2>/dev/null; then
    break
  fi
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
sleep 0.5
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
rm -f "$BUILD_DIR/dns.in"

echo "--- dns serial ---"
sed -n '/space> dns/,/space>/p' "$BUILD_DIR/serial.log" 2>/dev/null || cat "$BUILD_DIR/serial.log"
echo "------------------"

if grep -qE "dns: (a |no answer|timeout)" "$BUILD_DIR/serial.log"; then
  echo "[3/3] PASS: dns query path produced a dns: line (answer/no-answer/timeout OK)"
  grep -E "dns: " "$BUILD_DIR/serial.log" || true
  exit 0
fi

echo "[3/3] FAIL: no dns: a / no answer / timeout line (crash or no TX path)"
exit 1
