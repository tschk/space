#!/usr/bin/env bash
# Kernel-audit hardening regression gate.
#
# Boots the kernel and runs the `hardening` shell command, which asserts the
# fixes from docs/kernel-audit.md: chan cap=0 rejection, chan handle sanity,
# sys_write buffer guard, and the bounded DNS parser.
#
# Usage:
#   bash scripts/check-audit-fixes.sh
#   KERNEL_BIN=/path/kernel.bin bash scripts/check-audit-fixes.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-audit-fixes}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_IN="$SERIAL_BASE.in"
SERIAL_OUT="$SERIAL_BASE.out"
SERIAL_LOG="$BUILD_DIR/serial.log"
MONITOR="$BUILD_DIR/qemu-monitor.sock"

mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$SERIAL_LOG" "$MONITOR"

echo "[1/4] Building kernel..."
if [ -n "${KERNEL_BIN:-}" ]; then
  KERNEL="$KERNEL_BIN"
else
  [ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
  NASM="${NASM:-nasm}"
  "$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
  "$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
    --trampoline "$BUILD_DIR/trampoline.bin" \
    --target native --target-triple x86_64-unknown-none --linkage static-lib \
    --out "$BUILD_DIR/kernel.bin"
  KERNEL="$BUILD_DIR/kernel.bin"
fi

echo "[2/4] Booting to shell..."
mkfifo "$SERIAL_IN" "$SERIAL_OUT"
qemu-system-x86_64 -kernel "$KERNEL" -m 256M -no-reboot \
  -vga std -display none -serial "pipe:$SERIAL_BASE" \
  -monitor "unix:$MONITOR,server,nowait" -daemonize

timeout 30 cat "$SERIAL_OUT" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 200); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo "shell did not start" >&2; exit 1; }

echo "[3/4] Running hardening assertions..."
printf 'hardening\n' > "$SERIAL_IN"
for _ in $(seq 1 50); do
  grep -qE "hardening (PASS|FAIL)" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done

echo "[4/4] Checking result..."
if grep -qF "hardening PASS" "$SERIAL_LOG"; then
  echo "PASS: kernel audit fixes hold (chan/syscall/dns hardening)"
  rc=0
else
  echo "FAIL: hardening assertions failed" >&2
  grep -E "hardening" "$SERIAL_LOG" | tail -5 >&2
  rc=1
fi

printf 'halt\n' > "$SERIAL_IN"
printf 'quit\n' | nc -U "$MONITOR" >/dev/null 2>&1 || true
kill "$CATPID" 2>/dev/null || true
rm -f "$SERIAL_IN" "$SERIAL_OUT" "$MONITOR"
exit "$rc"
