#!/bin/sh
# Benchmark Space OS boot times in QEMU (like ../alpenglow-os/scripts/bench-boot.sh).
set -eu

SPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IN="$SPACE_DIR/../inauguration/in-cli/target/release/in"
KERNEL_IN="$SPACE_DIR/kernel/kernel-root.in"
TRAMPOLINE_ASM="$SPACE_DIR/boot/multiboot.asm"
BUILD_DIR="${BUILD_DIR:-/tmp/space-bench}"
KERNEL_BIN="${BUILD_DIR}/kernel.bin"

mkdir -p "$BUILD_DIR"

# Build trampoline if needed
if [ ! -f "$BUILD_DIR/trampoline.bin" ]; then
  if command -v nasm >/dev/null 2>&1; then
    nasm -f bin "$TRAMPOLINE_ASM" -o "$BUILD_DIR/trampoline.bin"
  elif [ -f /tmp/trampoline.bin ]; then
    cp /tmp/trampoline.bin "$BUILD_DIR/trampoline.bin"
  elif [ -f /tmp/trampoline_final.bin ]; then
    cp /tmp/trampoline_final.bin "$BUILD_DIR/trampoline.bin"
  else
    echo "bench: no trampoline found" >&2; exit 1
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

RUNS=5
total_ms=0; min_ms=99999; max_ms=0
for i in $(seq 1 $RUNS); do
  t0=$(date +%s%N 2>/dev/null || date +%s000000000)
  timeout 20 qemu-system-x86_64 -kernel "$KERNEL_BIN" -m 256M -serial stdio -display none -no-reboot \
    < /dev/null > "$BUILD_DIR/run-$i.log" 2>/dev/null || true
  t1=$(date +%s%N 2>/dev/null || date +%s000000000)
  ms=$(( (t1 - t0) / 1000000 ))
  total_ms=$((total_ms + ms))
  [ "$ms" -lt "$min_ms" ] && min_ms=$ms
  [ "$ms" -gt "$max_ms" ] && max_ms=$ms
  printf "  run %d: %dms\n" $i $ms
done
avg_ms=$((total_ms / RUNS))

# Size metrics
KERN_SIZE=$(wc -c < "$KERNEL_BIN")
OUT_BYTES=$(wc -c < "$BUILD_DIR/run-3.log" 2>/dev/null || echo 0)
OUT_LINES=$(wc -l < "$BUILD_DIR/run-3.log" 2>/dev/null || echo 0)

# Phase markers
find_line() { grep -nm1 "$1" "$BUILD_DIR/run-3.log" 2>/dev/null | cut -d: -f1 || echo ""; }
KSL=$(find_line "kernel root entered")
TML=$(find_line "interrupts enabled")
SUL=$(find_line "activating component graph")
SCL=$(find_line "scheduler running")
ICL=$(find_line "channel IPC demo")
PRL=$(find_line "preemptive scheduler")
SHL=$(find_line "interactive shell")

phase_ms() {
  a=$1; b=$2
  [ -z "$a" ] || [ -z "$b" ] && { echo "?"; return; }
  d=$((b - a)); [ "$d" -le 1 ] && d=1
  echo $((d * avg_ms / OUT_LINES))
}

echo ""
echo "=== Space OS Boot Benchmarks ==="
echo "  Avg: ${avg_ms}ms  Min: ${min_ms}ms  Max: ${max_ms}ms  (${RUNS} runs)"
echo ""
echo "=== Subsystem Timing ==="
printf "  Kernel init:         %5dms\n" "$(phase_ms "$KSL" "$TML")"
printf "  Timer setup:         %5dms\n" "$(phase_ms "$TML" "$SUL")"
printf "  Supervisor:          %5dms\n" "$(phase_ms "$SUL" "$SCL")"
printf "  Coop scheduler:      %5dms\n" "$(phase_ms "$SCL" "$ICL")"
printf "  Channel IPC:         %5dms\n" "$(phase_ms "$ICL" "$PRL")"
printf "  Preemptive sched:    %5dms\n" "$(phase_ms "$PRL" "$SHL")"
printf "  Total to shell:      %5dms\n" "$avg_ms"
echo ""
echo "=== Size ==="
echo "  kernel.bin: ${KERN_SIZE} bytes, serial: ${OUT_BYTES} bytes"
echo ""
echo "bench: ok"
