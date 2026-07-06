#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SPACE="$(CDPATH= cd -- "$ROOT/.." && pwd)"
INAUG="${INAUGURATION_DIR:-$SPACE/../inauguration}"
BUILD="${BUILD_DIR:-/tmp/space-v86-32}"
OUT_DIR="$ROOT/public/v86"
IN="$INAUG/in-cli/target/release/in"
NASM="${NASM:-nasm}"

mkdir -p "$OUT_DIR" "$BUILD"

if [ ! -x "$IN" ]; then
  cargo build --release -q --manifest-path "$INAUG/in-cli/Cargo.toml"
fi

"$NASM" -f bin "$SPACE/boot/multiboot32.asm" -o "$BUILD/trampoline.bin"
[ "$(wc -c < "$BUILD/trampoline.bin")" -eq 4096 ]

"$IN" compile --path "$SPACE/kernel/v86-kernel.in" --entry kernel_entry --emit boot \
  --trampoline "$BUILD/trampoline.bin" \
  --target native --target-triple i386-unknown-none --linkage static-lib \
  --out "$BUILD/kernel.bin"

cp "$BUILD/kernel.bin" "$OUT_DIR/space-multiboot.bin"
BUILD_ID="$(git -C "$SPACE" rev-parse --short HEAD 2>/dev/null || date +%s)"
printf '%s\n' "$BUILD_ID" > "$OUT_DIR/kernel-build-id.txt"

if [ -d "$ROOT/node_modules/v86/build" ]; then
  for f in libv86.mjs v86.wasm v86-fallback.wasm; do
    cp "$ROOT/node_modules/v86/build/$f" "$OUT_DIR/" 2>/dev/null || true
  done
fi

ls -lh "$OUT_DIR/space-multiboot.bin"
