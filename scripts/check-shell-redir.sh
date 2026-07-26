#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-shell-redir}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"

mkdir -p "$BUILD_DIR"
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
nasm -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

rm -f "$SERIAL" "$FIFO"
mkfifo "$FIFO"
qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 512M -rtc base=utc \
  -device isa-debug-exit,iobase=0xf4 -serial stdio -display none -no-reboot \
  <"$FIFO" >"$SERIAL" 2>/dev/null &
QPID=$!
cleanup() {
  exec 3>&- 2>/dev/null || true
  kill "$QPID" 2>/dev/null || true
  wait "$QPID" 2>/dev/null || true
  rm -f "$FIFO"
}
trap cleanup EXIT
exec 3>"$FIFO"

wait_marker() {
  local marker="$1" tries="${2:-150}"
  for _ in $(seq 1 "$tries"); do
    grep -qF "$marker" "$SERIAL" 2>/dev/null && return 0
    kill -0 "$QPID" 2>/dev/null || return 1
    sleep 0.1
  done
  return 1
}

wait_marker "interactive shell" || { echo "shell did not start" >&2; exit 1; }

printf 'format\r' >&3
wait_marker "disk formatted" 100 || { echo "format failed" >&2; exit 1; }

printf 'write a hi\r' >&3
wait_marker "written" 100 || { echo "write a failed" >&2; exit 1; }

OFFSET=$(wc -c < "$SERIAL")
printf 'ls > listing\r' >&3
wait_marker "redirected to listing" 100 || { echo "ls redirect failed" >&2; exit 1; }

printf 'cat listing\r' >&3
for _ in $(seq 1 100); do
  tail -c +$((OFFSET + 1)) "$SERIAL" 2>/dev/null | grep -qF "  a" && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
tail -c +$((OFFSET + 1)) "$SERIAL" | grep -qF "  a" || { echo "cat listing missing a" >&2; exit 1; }

OFFSET=$(wc -c < "$SERIAL")
printf 'echo zz > b\r' >&3
wait_marker "redirected to b" 100 || { echo "echo redirect failed" >&2; exit 1; }

printf 'cat b\r' >&3
for _ in $(seq 1 100); do
  tail -c +$((OFFSET + 1)) "$SERIAL" 2>/dev/null | grep -qF "zz" && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
tail -c +$((OFFSET + 1)) "$SERIAL" | grep -qF "zz" || { echo "cat b missing zz" >&2; exit 1; }

printf 'halt\r' >&3
echo PASS
