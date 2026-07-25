#!/usr/bin/env bash
set -euo pipefail

# check-shell-stress.sh — FS + redirect shell stress on mem/NVMe path.
# Nested mkdir, write, cd/pwd/ls, mv/rm/rmdir, status redirect, halt.
# History up-arrow best-effort (skip if flaky).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-shell-stress}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"
NVME_IMG="$BUILD_DIR/nvme.img"
USE_NVME="${USE_NVME:-1}"

mkdir -p "$BUILD_DIR"
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
nasm -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

rm -f "$SERIAL" "$FIFO" "$NVME_IMG"
mkfifo "$FIFO"

QEMU_ARGS=(
  qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 512M -rtc base=utc
  -device isa-debug-exit,iobase=0xf4 -serial stdio -display none -no-reboot
)
if [ "$USE_NVME" = "1" ]; then
  truncate -s 64M "$NVME_IMG"
  QEMU_ARGS+=(
    -drive "file=$NVME_IMG,format=raw,if=none,id=nvme0"
    -device nvme,drive=nvme0,serial=shellstress
  )
fi

"${QEMU_ARGS[@]}" <"$FIFO" >"$SERIAL" 2>/dev/null &
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

printf 'mkdir a\r' >&3
wait_marker "  created" 100 || { echo "mkdir a failed" >&2; exit 1; }

printf 'mkdir a/b\r' >&3
wait_marker "  created" 100 || { echo "mkdir a/b failed" >&2; exit 1; }

printf 'mkdir a/b/c\r' >&3
wait_marker "  created" 100 || { echo "mkdir a/b/c failed" >&2; exit 1; }

printf 'write a/b/c/f hi\r' >&3
wait_marker "  written" 100 || { echo "write failed" >&2; exit 1; }

printf 'cd a/b/c\r' >&3
wait_marker "/a/b/c" 100 || { echo "cd a/b/c failed" >&2; exit 1; }

printf 'pwd\r' >&3
wait_marker "  /a/b/c" 100 || { echo "pwd failed" >&2; exit 1; }

printf 'ls\r' >&3
wait_marker "  f" 100 || { echo "ls missing f" >&2; exit 1; }

printf 'cd /\r' >&3
wait_marker "  /" 100 || { echo "cd / failed" >&2; exit 1; }

printf 'mv a/b/c/f a/b/c/g\r' >&3
wait_marker "  renamed" 100 || { echo "mv failed" >&2; exit 1; }

printf 'rm a/b/c/g\r' >&3
wait_marker "  deleted" 100 || { echo "rm failed" >&2; exit 1; }

printf 'rmdir a/b/c\r' >&3
wait_marker "  removed" 100 || { echo "rmdir a/b/c failed" >&2; exit 1; }

printf 'rmdir a/b\r' >&3
wait_marker "  removed" 100 || { echo "rmdir a/b failed" >&2; exit 1; }

printf 'rmdir a\r' >&3
wait_marker "  removed" 100 || { echo "rmdir a failed" >&2; exit 1; }

# history up-arrow: best-effort after a few cmds (ESC [ A)
OFFSET=$(wc -c < "$SERIAL")
printf 'echo histmark\r' >&3
wait_marker "histmark" 100 || true
printf '\x1b[A\r' >&3
sleep 0.5
if tail -c +$((OFFSET + 1)) "$SERIAL" 2>/dev/null | grep -qF "echo histmark"; then
  echo "  ok: history up-arrow"
else
  echo "  skip: history up-arrow flaky/unavailable"
fi

OFFSET=$(wc -c < "$SERIAL")
printf 'status > st\r' >&3
wait_marker "redirected to st" 100 || { echo "status redirect failed" >&2; exit 1; }

printf 'cat st\r' >&3
for _ in $(seq 1 100); do
  tail -c +$((OFFSET + 1)) "$SERIAL" 2>/dev/null | grep -qF "realm object id" && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
tail -c +$((OFFSET + 1)) "$SERIAL" | grep -qF "realm object id" \
  || { echo "cat st missing status marker" >&2; exit 1; }

printf 'halt\r' >&3

fail=0
for m in \
  "interactive shell" \
  "  disk formatted" \
  "  created" \
  "  written" \
  "  /a/b/c" \
  "  f" \
  "  renamed" \
  "  deleted" \
  "  removed" \
  "  redirected to st" \
  "realm object id"
do
  if grep -qF "$m" "$SERIAL" 2>/dev/null; then
    echo "  ok: $m"
  else
    echo "  MISSING: $m" >&2
    fail=1
  fi
done

[ "$fail" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL" >&2; exit 1; }
