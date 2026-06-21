#!/usr/bin/env bash
# check-qemu-boot.sh — Build the kernel, boot it in QEMU, verify markers.
# ponytail: single-file check, no redundant marker lists.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-boot}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL="$BUILD_DIR/serial.log"
mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler..."
cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"

echo "[2/3] Assembling trampoline and compiling kernel..."
NASM="${NASM:-nasm}"
[ -f /tmp/trampoline.bin ] && cp /tmp/trampoline.bin "$BUILD_DIR/trampoline.bin" \
  || "$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
[ $(wc -c < "$BUILD_DIR/trampoline.bin") -eq 8192 ] || { echo "trampoline size error" >&2; exit 1; }

"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"

echo "[3/3] Booting and checking output..."
rm -f "$SERIAL"
qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 256M \
  -serial stdio -display none -no-reboot >"$SERIAL" 2>/dev/null &
QPID=$!
for _ in $(seq 1 150); do
  grep -qF "interactive shell" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true

# Core markers that must appear in normal boot
for m in "kernel root entered" "available RAM bytes" "interrupts enabled" \
         "domain_create test -> id" "domain isolation test -> PASS" \
         "heartbeat -> ACTIVATING" "DENIED undeclared cap" "scheduler running" \
         "channel demo complete" "interactive shell"; do
  if grep -qF "$m" "$SERIAL" 2>/dev/null; then echo "  ok: $m"
  else echo "  MISSING: $m" >&2; fail=1; fi
done
[ -z "${fail:-}" ] && { echo "PASS"; exit 0; } || { echo "FAIL" >&2; exit 1; }
