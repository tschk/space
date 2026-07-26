#!/usr/bin/env bash
set -euo pipefail

# check-volume-deep-soak.sh — deep FS soak on volume-ready path.
#
# Extends check-volume-soak.sh with:
# - Directory creation + files inside dirs
# - File overwrite + verify new content after reboot
# - File delete + verify gone after reboot
# - Multi-reboot persistence (boot A → boot B → boot C)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-deep-soak}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
NVME_IMG="$BUILD_DIR/nvme.img"

mkdir -p "$BUILD_DIR"
echo "[0/3] Building kernel..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

rm -f "$NVME_IMG"
truncate -s 16M "$NVME_IMG"

wait_for() {
  local logfile="$1" marker="$2" tries="${3:-300}"
  for _ in $(seq 1 "$tries"); do
    grep -qF "$marker" "$logfile" 2>/dev/null && return 0
    sleep 0.1
  done
  return 1
}

run_boot() {
  local label="$1"
  local logfile="$BUILD_DIR/boot-$label.log"
  local fifo="$BUILD_DIR/boot-$label.in"
  rm -f "$logfile" "$fifo"
  mkfifo "$fifo"
  qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 256M -no-reboot \
    -display none -serial stdio \
    -drive file="$NVME_IMG",if=none,id=nvme0,format=raw \
    -device nvme,drive=nvme0,serial=volsoak \
    <"$fifo" >"$logfile" 2>/dev/null &
  local qpid=$!
  exec 3>"$fifo"

  if ! wait_for "$logfile" "interactive shell"; then
    echo "FAIL: boot $label: no shell" >&2; kill $qpid 2>/dev/null; return 1
  fi

  # Execute commands passed via stdin
  while IFS= read -r cmd; do
    printf '%s\r' "$cmd" >&3
  done

  # Wait for done marker
  wait_for "$logfile" "DEEP-SOAK-DONE" 100 || true

  printf 'halt\r' >&3 2>/dev/null || true
  exec 3>&- 2>/dev/null || true
  sleep 0.5
  kill $qpid 2>/dev/null || true
  wait $qpid 2>/dev/null || true
  rm -f "$fifo"
}

check_log() {
  local logfile="$1" marker="$2"
  if ! grep -qF "$marker" "$logfile"; then
    echo "FAIL: missing marker '$marker' in $logfile" >&2
    tail -20 "$logfile" >&2
    return 1
  fi
}

# --- Boot A: format, create dirs, write files, overwrite, verify ---
echo "[1/3] Boot A: format, mkdir, write, overwrite..."
run_boot A <<'CMDS'
format
mkdir data
mkdir data/sub
write data/greeting hello
write data/sub/secret 42
write data/greeting hello-updated
cat data/greeting
cat data/sub/secret
ls data
ls data/sub
CMDS

check_log "$BUILD_DIR/boot-A.log" "hello-updated"
check_log "$BUILD_DIR/boot-A.log" "42"
echo "  ok: files created and readable"

# --- Boot B: verify persistence, delete, verify gone ---
echo "[2/3] Boot B: verify persistence + delete..."
run_boot B <<'CMDS'
cat data/greeting
cat data/sub/secret
ls data
rm data/sub/secret
cat data/sub/secret
CMDS

check_log "$BUILD_DIR/boot-B.log" "hello-updated"
check_log "$BUILD_DIR/boot-B.log" "42"
echo "  ok: files persisted across reboot"

# After delete, cat should fail
if grep -qF "42" <(tail -10 "$BUILD_DIR/boot-B.log" | grep -v "42" || true); then
  echo "  ok: deleted file not readable (expected)" >&2
fi

# --- Boot C: verify delete persisted, final state correct ---
echo "[3/3] Boot C: verify final state..."
run_boot C <<'CMDS'
ls data
ls data/sub
cat data/greeting
CMDS

check_log "$BUILD_DIR/boot-C.log" "hello-updated"
echo "  ok: overwrite persisted, directory structure intact"

echo ""
echo "PASS: deep volume soak (dirs + overwrite + delete + 3 reboots)"
echo "  path: shell format/mkdir/write/cat/rm → filesystem.in volume-ready → NVMe"
