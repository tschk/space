#!/usr/bin/env bash
# Benchmark SpaceOS boot time and kernel image size.
# Measures: compile time, kernel image size, boot-to-shell time, boot-to-halt time.
# Runs multiple iterations and reports median/min/max.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-bench}"
IN="$INAUG_DIR/in-cli/target/release/in"
SERIAL="$BUILD_DIR/serial.log"
FIFO="$BUILD_DIR/serial_in"
ITERATIONS="${ITERATIONS:-5}"
mkdir -p "$BUILD_DIR"

echo "SpaceOS Boot Benchmark — $ITERATIONS iterations"
echo "================================================"

# Ensure compiler is built
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"

NASM="${NASM:-nasm}"

# --- Compile benchmark ---
echo ""
echo "[1] Compile time (kernel + trampoline)"
compile_times=()
for i in $(seq 1 "$ITERATIONS"); do
  "$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin" 2>/dev/null
  t0=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
  "$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry --emit boot \
    --trampoline "$BUILD_DIR/trampoline.bin" \
    --target native --target-triple x86_64-unknown-none --linkage static-lib \
    --out "$BUILD_DIR/kernel.bin" 2>/dev/null
  t1=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
  elapsed_ms=$(( (t1 - t0) / 1000000 ))
  compile_times+=("$elapsed_ms")
  printf "  iter %d: %d ms\n" "$i" "$elapsed_ms"
done

# Kernel image size
kernel_size=$(wc -c < "$BUILD_DIR/kernel.bin")
trampoline_size=$(wc -c < "$BUILD_DIR/trampoline.bin")
echo ""
echo "  kernel image: $kernel_size bytes"
echo "  trampoline:   $trampoline_size bytes"
echo "  total boot:   $((kernel_size + trampoline_size)) bytes"

# --- Boot time benchmark ---
echo ""
echo "[2] Boot time (QEMU launch -> shell prompt)"
boot_times=()
for i in $(seq 1 "$ITERATIONS"); do
  rm -f "$SERIAL" "$FIFO"
  mkfifo "$FIFO"
  t0=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
  qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 512M \
    -rtc base=utc \
    -vga std -serial stdio -display none -no-reboot <"$FIFO" >"$SERIAL" 2>/dev/null &
  QPID=$!
  exec 3>"$FIFO"
  # Wait for shell prompt
  for _ in $(seq 1 300); do
    grep -qF "interactive shell" "$SERIAL" 2>/dev/null && break
    kill -0 "$QPID" 2>/dev/null || break
    sleep 0.01
  done
  t1=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
  elapsed_ms=$(( (t1 - t0) / 1000000 ))
  boot_times+=("$elapsed_ms")
  printf "  iter %d: %d ms\n" "$i" "$elapsed_ms"
  # Clean up
  echo "halt" >&3 2>/dev/null || true
  exec 3>&- 2>/dev/null || true
  kill "$QPID" 2>/dev/null || true
  wait "$QPID" 2>/dev/null || true
  rm -f "$FIFO"
  sleep 0.2
done

# --- Full boot-to-halt benchmark ---
echo ""
echo "[3] Full boot-to-halt time (shell commands + halt)"
halt_times=()
for i in $(seq 1 "$ITERATIONS"); do
  rm -f "$SERIAL" "$FIFO"
  mkfifo "$FIFO"
  t0=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
  qemu-system-x86_64 -kernel "$BUILD_DIR/kernel.bin" -m 512M \
    -rtc base=utc \
    -vga std -serial stdio -display none -no-reboot <"$FIFO" >"$SERIAL" 2>/dev/null &
  QPID=$!
  exec 3>"$FIFO"
  # Wait for shell
  for _ in $(seq 1 300); do
    grep -qF "interactive shell" "$SERIAL" 2>/dev/null && break
    kill -0 "$QPID" 2>/dev/null || break
    sleep 0.01
  done
  # Run commands
  echo "linux" >&3
  sleep 0.3
  echo "vfs" >&3
  sleep 0.2
  echo "libc" >&3
  sleep 0.5
  echo "time" >&3
  sleep 0.2
  echo "halt" >&3
  exec 3>&-
  # Wait for QEMU to exit (with timeout — halt returns from shell but
  # doesn't power off QEMU, so we kill it after a grace period)
  for _ in $(seq 1 50); do
    kill -0 "$QPID" 2>/dev/null || break
    sleep 0.1
  done
  kill "$QPID" 2>/dev/null || true
  wait "$QPID" 2>/dev/null || true
  t1=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
  elapsed_ms=$(( (t1 - t0) / 1000000 ))
  halt_times+=("$elapsed_ms")
  printf "  iter %d: %d ms\n" "$i" "$elapsed_ms"
  rm -f "$FIFO"
  sleep 0.2
done

# --- Summary ---
echo ""
echo "================================================"
echo "Summary (median / min / max)"
echo "================================================"

# Compute median
median() {
  local arr=("$@")
  local n=${#arr[@]}
  local sorted=($(printf '%s\n' "${arr[@]}" | sort -n))
  local mid=$(( n / 2 ))
  if (( n % 2 == 0 )); then
    echo $(( (sorted[mid-1] + sorted[mid]) / 2 ))
  else
    echo "${sorted[mid]}"
  fi
}

min_val() {
  local arr=("$@")
  local sorted=($(printf '%s\n' "${arr[@]}" | sort -n))
  echo "${sorted[0]}"
}

max_val() {
  local arr=("$@")
  local sorted=($(printf '%s\n' "${arr[@]}" | sort -n))
  echo "${sorted[${#sorted[@]}-1]}"
}

c_med=$(median "${compile_times[@]}")
c_min=$(min_val "${compile_times[@]}")
c_max=$(max_val "${compile_times[@]}")
echo "Compile:     ${c_med} ms (min ${c_min}, max ${c_max})"

b_med=$(median "${boot_times[@]}")
b_min=$(min_val "${boot_times[@]}")
b_max=$(max_val "${boot_times[@]}")
echo "Boot-to-shell: ${b_med} ms (min ${b_min}, max ${b_max})"

h_med=$(median "${halt_times[@]}")
h_min=$(min_val "${halt_times[@]}")
h_max=$(max_val "${halt_times[@]}")
echo "Boot-to-halt:  ${h_med} ms (min ${h_min}, max ${h_max})"

echo ""
echo "Kernel image: ${kernel_size} bytes"
echo "Boot image:   $((kernel_size + trampoline_size)) bytes"
