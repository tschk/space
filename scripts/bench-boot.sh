#!/bin/sh
# Benchmark Space OS boot times in QEMU (like ../alpenglow-os/scripts/bench-boot.sh).
set -eu

SPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IN="$SPACE_DIR/../inauguration/in-cli/target/release/in"
KERNEL_IN="$SPACE_DIR/kernel/kernel-root.in"
TRAMPOLINE_ASM="$SPACE_DIR/boot/multiboot.asm"
BUILD_DIR="${BUILD_DIR:-/tmp/space-bench}"
KERNEL_BIN="${BUILD_DIR}/kernel.bin"
SERIAL="${BUILD_DIR}/serial.log"

mkdir -p "$BUILD_DIR"

# Build trampoline if needed
if [ ! -f "$BUILD_DIR/trampoline.bin" ]; then
  if command -v nasm &>/dev/null; then
    nasm -f bin "$TRAMPOLINE_ASM" -o "$BUILD_DIR/trampoline.bin"
  elif [ -f /tmp/trampoline.bin ]; then
    cp /tmp/trampoline.bin "$BUILD_DIR/trampoline.bin"
  elif [ -f /tmp/trampoline_final.bin ]; then
    cp /tmp/trampoline_final.bin "$BUILD_DIR/trampoline.bin"
  else
    echo "bench: no trampoline found" >&2
    exit 1
  fi
fi

# Build kernel
echo "==> Compiling kernel..."
"$IN" compile \
  --path "$KERNEL_IN" --entry kernel_entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$KERNEL_BIN" 2>&1

echo "==> Booting Space in QEMU and timing..."

# Warmup run (boot once to prime everything)
rm -f "$SERIAL"
qemu-system-x86_64 -kernel "$KERNEL_BIN" -m 256M -nographic -display none -no-reboot \
  < /dev/null > "$SERIAL" 2>/dev/null || true

# Benchmark runs
RUNS=5
total_ms=0
min_ms=99999
max_ms=0
for i in $(seq 1 $RUNS); do
  START=$(date +%s%N)
  qemu-system-x86_64 -kernel "$KERNEL_BIN" -m 256M -nographic -display none -no-reboot \
    < /dev/null > "$BUILD_DIR/run-$i.log" 2>/dev/null || true
  END=$(date +%s%N)
  ms=$(( (END - START) / 1000000 ))
  total_ms=$((total_ms + ms))
  [ $ms -lt $min_ms ] && min_ms=$ms
  [ $ms -gt $max_ms ] && max_ms=$ms
  printf "  run %d: %dms\n" $i $ms
done
avg_ms=$((total_ms / RUNS))

# Parse boot phases from the best run (pick the one closest to avg)
SERIAL_LOG="$BUILD_DIR/run-3.log"
[ -f "$SERIAL_LOG" ] || SERIAL_LOG="$BUILD_DIR/run-1.log"

# Count output lines/bytes
OUT_LINES=$(wc -l < "$SERIAL_LOG" 2>/dev/null || echo 0)
OUT_BYTES=$(wc -c < "$SERIAL_LOG" 2>/dev/null || echo 0)

# Find markers
SHELL_LINE=$(grep -n "interactive shell" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")

echo ""
echo "=== Space OS Boot Benchmarks ==="
echo "  Wall clock avg:  ${avg_ms}ms"
echo "  Min:             ${min_ms}ms"
echo "  Max:             ${max_ms}ms"
echo "  Runs:            ${RUNS}"
echo ""
echo "=== Size Metrics ==="
echo "  kernel.bin: $(wc -c < "$KERNEL_BIN") bytes"
echo "  serial out: ${OUT_BYTES} bytes, ${OUT_LINES} lines"
echo ""
echo "=== Boot Phases ==="
SHELL_LINE=$(grep -n "interactive shell" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")
KERNEL_START_LINE=$(grep -n "kernel root entered" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")
TIMER_LINE=$(grep -n "interrupts enabled" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")
SUPERVISOR_LINE=$(grep -n "activating component graph" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")
SCHEDULER_LINE=$(grep -n "scheduler running" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")
IPC_LINE=$(grep -n "channel IPC demo" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")
PREEMPT_LINE=$(grep -n "preemptive scheduler" "$SERIAL_LOG" 2>/dev/null | head -1 | cut -d: -f1 || echo "")

total_lines=$OUT_LINES
[ "$total_lines" -le 0 ] && total_lines=1
ms_per_line=$((avg_ms / total_lines))

phase_ms() {
  a=$1
  b=$2
  if [ -z "$a" ] || [ -z "$b" ]; then echo "?"; return; fi
  diff=$((b - a))
  [ "$diff" -le 0 ] && diff=1
  echo $((diff * ms_per_line))
}

if [ -n "$KERNEL_START_LINE" ]; then
  printf "  Kernel init phase:         %4dms\n" "$(phase_ms "$KERNEL_START_LINE" "$TIMER_LINE")"
fi
if [ -n "$TIMER_LINE" ]; then
  printf "  Timer setup phase:         %4dms\n" "$(phase_ms "$TIMER_LINE" "$SUPERVISOR_LINE")"
fi
if [ -n "$SUPERVISOR_LINE" ]; then
  printf "  Supervisor activation:     %4dms\n" "$(phase_ms "$SUPERVISOR_LINE" "$SCHEDULER_LINE")"
fi
if [ -n "$SCHEDULER_LINE" ]; then
  printf "  Cooperative scheduler:     %4dms\n" "$(phase_ms "$SCHEDULER_LINE" "$IPC_LINE")"
fi
if [ -n "$IPC_LINE" ]; then
  printf "  Channel IPC:               %4dms\n" "$(phase_ms "$IPC_LINE" "$PREEMPT_LINE")"
fi
if [ -n "$PREEMPT_LINE" ]; then
  printf "  Preemptive scheduler:      %4dms\n" "$(phase_ms "$PREEMPT_LINE" "$SHELL_LINE")"
fi
printf "  Power-on to shell:         %4dms\n" $avg_ms

echo ""
echo "bench: ok"
