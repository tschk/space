#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-terminal-editor}"
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
for _ in $(seq 1 150); do
  grep -qF "interactive shell" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
grep -qF "interactive shell" "$SERIAL" || { echo "shell did not start" >&2; exit 1; }

printf 'write editor-check.txt seed\r' >&3
for _ in $(seq 1 100); do
  grep -qF "written" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
grep -qF "written" "$SERIAL" || { echo "seed file was not written" >&2; exit 1; }

printf 'edit editor-check.txt\r' >&3
for _ in $(seq 1 100); do
  grep -qF "Ctrl-S save  Ctrl-F find  Ctrl-Q quit" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
grep -qF "Ctrl-S save  Ctrl-F find  Ctrl-Q quit" "$SERIAL" || { echo "editor did not open" >&2; exit 1; }

printf 'X\023\021' >&3
for _ in $(seq 1 100); do
  grep -qF $'\033[?1049l' "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
grep -qF $'\033[?1049l' "$SERIAL" || { echo "editor did not exit" >&2; exit 1; }

OFFSET=$(wc -c < "$SERIAL")
printf 'cat editor-check.txt\r' >&3
for _ in $(seq 1 100); do
  tail -c +$((OFFSET + 1)) "$SERIAL" 2>/dev/null | grep -qF "Xseed" && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
tail -c +$((OFFSET + 1)) "$SERIAL" | grep -qF "Xseed" || { echo "editor did not save" >&2; exit 1; }
printf 'halt\r' >&3
echo PASS
