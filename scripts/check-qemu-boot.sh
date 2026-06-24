#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-boot}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"
mkdir -p "$BUILD_DIR"
echo "[1/3] Building compiler..."
cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
echo "[2/3] Assembling trampoline and compiling kernel..."
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
[ $(wc -c < "$BUILD_DIR/trampoline.bin") -eq 4096 ] || { echo "trampoline size error" >&2; exit 1; }
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel.bin"
echo "[3/3] Booting and checking output..."
rm -f "$SERIAL" "$FIFO"
mkfifo "$FIFO"
# Start QEMU with serial input from the FIFO and output to the log file.
# Keep fd 3 open for writing to the FIFO so QEMU's stdin does not see EOF.
qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 512M \
  -vga std -serial stdio -display none -no-reboot <"$FIFO" >"$SERIAL" 2>/dev/null &
QPID=$!
exec 3>"$FIFO"
# Wait for the interactive shell prompt to appear.
for _ in $(seq 1 150); do
  grep -qF "interactive shell" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
# Send the 'linux' command to run the Linux personality demo.
echo "linux" >&3
# Wait for the demo to complete.
for _ in $(seq 1 100); do
  grep -qF "linux: personality demo complete" "$SERIAL" 2>/dev/null && break
  kill -0 "$QPID" 2>/dev/null || break
  sleep 0.1
done
# Send 'fb' command to show framebuffer info.
echo "fb" >&3
sleep 0.5
# Send 'halt' to cleanly stop the shell.
echo "halt" >&3
exec 3>&-
sleep 0.5
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true
rm -f "$FIFO"
# --- assertions ---
for m in "kernel root entered" "available RAM bytes" "interrupts enabled" \
         "domain subsystem init, 1 domains (kernel + 63 available)" "timer ticks" \
         "heartbeat -> ACTIVATING" "DENIED undeclared cap" "scheduler running" \
         "channel demo complete" "preemptive scheduler" "preemption ended" \
         "filesystem initialized" "Linux personality initialized" \
         "framebuffer initialized" "compositor initialized" \
         "interactive shell" \
         "linux: personality demo starting" \
         "linux: write(1, msg" \
         "linux: getpid()" \
         "linux: open(hello.txt" \
         "linux: personality demo complete"; do
  if grep -qF "$m" "$SERIAL" 2>/dev/null; then echo "  ok: $m"
  else echo "  MISSING: $m" >&2; fail=1; fi
done
[ -z "${fail:-}" ] && { echo "PASS"; exit 0; } || { echo "FAIL" >&2; exit 1; }
