#!/usr/bin/env bash
set -euo pipefail

# check-fs-dirs.sh — Full coverage for mkdir / rmdir / mv / rm (happy + errors).
# Boot mem FS (USE_NVME=1 optional), format, exercise dir tree ops over serial.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-fs-dirs}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"
NVME_IMG="$BUILD_DIR/nvme.img"
USE_NVME="${USE_NVME:-0}"

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
    -device nvme,drive=nvme0,serial=fsdirs
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

wait_new() {
  # Wait for marker only in bytes appended after OFFSET.
  local marker="$1" tries="${2:-120}" off="${3:-0}"
  local i=0
  while [ "$i" -lt "$tries" ]; do
    if tail -c +"$((off + 1))" "$SERIAL" 2>/dev/null | grep -qF "$marker"; then
      return 0
    fi
    kill -0 "$QPID" 2>/dev/null || return 1
    sleep 0.1
    i=$((i + 1))
  done
  return 1
}

run() {
  # Send cmd; require marker in fresh output. Prints step label.
  local label="$1" cmd="$2" want="$3" tries="${4:-120}"
  local off
  off=$(wc -c < "$SERIAL")
  printf '%s\r' "$cmd" >&3
  if wait_new "$want" "$tries" "$off"; then
    echo "  ok: $label"
    return 0
  fi
  echo "  FAIL: $label (want '$want' after '$cmd')" >&2
  tail -c +"$((off + 1))" "$SERIAL" 2>/dev/null | tail -20 >&2 || true
  return 1
}

wait_new "interactive shell" 200 0 || { echo "shell did not start" >&2; exit 1; }

fail=0
step() { run "$@" || fail=1; }

step "format" "format" "  disk formatted"

# --- happy: nested mkdir ---
step "mkdir root dir" "mkdir tree" "  created"
step "mkdir child" "mkdir tree/left" "  created"
step "mkdir grandchild" "mkdir tree/left/deep" "  created"
step "mkdir sibling" "mkdir tree/right" "  created"

# --- happy: files + rename file same dir ---
step "write leaf file" "write tree/left/deep/f alpha" "  written"
step "mv file same-dir" "mv tree/left/deep/f tree/left/deep/g" "  renamed"
step "cat renamed file" "cat tree/left/deep/g" "alpha"

# --- happy: mv file across directories ---
step "mv file cross-dir" "mv tree/left/deep/g tree/right/g" "  renamed"
step "cat cross-dir dest" "cat tree/right/g" "alpha"

# --- happy: mv directory ---
step "mv directory" "mv tree/left tree/left2" "  renamed"
step "mkdir under moved dir" "mkdir tree/left2/deep/x" "  created"
step "write under moved dir" "write tree/left2/deep/x/n nest" "  written"
step "cat under moved dir" "cat tree/left2/deep/x/n" "nest"

# --- happy: cd / pwd through tree ---
step "cd moved path" "cd tree/left2/deep" "  /tree/left2/deep"
step "pwd deep" "pwd" "  /tree/left2/deep"
step "ls deep has x" "ls" "  x"
step "cd root" "cd /" "  /"

# --- errors: mkdir ---
step "mkdir duplicate fails" "mkdir tree" "  mkdir: no such parent or already exists"
step "mkdir missing parent fails" "mkdir nope/child" "  mkdir: no such parent or already exists"

# --- errors: rmdir ---
step "rmdir non-empty fails" "rmdir tree/right" "  rmdir: not found or not empty"
step "rmdir missing fails" "rmdir missing-dir" "  rmdir: not found or not empty"
step "rmdir file fails" "rmdir tree/right/g" "  rmdir: not found or not empty"

# --- errors: rm ---
step "rm directory fails" "rm tree/right" "  rm: not found or is directory"
step "rm missing fails" "rm missing-file" "  rm: not found or is directory"

# --- errors: mv ---
step "mv missing fails" "mv missing-a missing-b" "  mv: not found or destination exists"
step "mv onto existing fails" "mv tree/right/g tree/left2/deep/x/n" "  mv: not found or destination exists"

# --- happy: delete file then empty dirs bottom-up ---
step "rm file" "rm tree/right/g" "  deleted"
step "rm nested file" "rm tree/left2/deep/x/n" "  deleted"
step "rmdir empty x" "rmdir tree/left2/deep/x" "  removed"
step "rmdir empty deep" "rmdir tree/left2/deep" "  removed"
step "rmdir empty left2" "rmdir tree/left2" "  removed"
step "rmdir empty right" "rmdir tree/right" "  removed"
step "rmdir empty tree" "rmdir tree" "  removed"

# --- post-delete: ls root should not list tree ---
off=$(wc -c < "$SERIAL")
printf 'ls\r' >&3
wait_new "space>" 80 "$off" || true
if tail -c +"$((off + 1))" "$SERIAL" 2>/dev/null | grep -qE '(^| )tree( |$)'; then
  echo "  FAIL: tree still listed after rmdir cascade" >&2
  fail=1
else
  echo "  ok: tree gone from root ls"
fi

# recreate shallow + wipe again (idempotent path)
step "recreate dir" "mkdir z" "  created"
step "recreate file" "write z/f ok" "  written"
step "rm recreate file" "rm z/f" "  deleted"
step "rmdir recreate dir" "rmdir z" "  removed"

printf 'halt\r' >&3
sleep 0.3

if [ "$fail" -eq 0 ]; then
  echo "PASS: mkdir/rmdir/mv/rm full coverage"
  exit 0
fi
echo "FAIL: fs dir coverage" >&2
exit 1
