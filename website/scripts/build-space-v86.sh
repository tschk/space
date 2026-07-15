#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SPACE="$(CDPATH= cd -- "$ROOT/.." && pwd)"
source "$SPACE/scripts/inauguration-dir.sh"
INAUG="$(inauguration_dir "$SPACE")"
BUILD="${BUILD_DIR:-/tmp/space-v86}"
OUT_DIR="$ROOT/public/v86"
IN="$INAUG/in-cli/target/release/in"
NASM="${NASM:-nasm}"

mkdir -p "$OUT_DIR" "$BUILD"

if [ ! -x "$IN" ]; then
  cargo build --release -q --manifest-path "$INAUG/in-cli/Cargo.toml"
fi

"$NASM" -f bin "$SPACE/boot/multiboot.asm" -o "$BUILD/trampoline.bin"
[ "$(wc -c < "$BUILD/trampoline.bin")" -eq 4096 ]

"$IN" compile --path "$SPACE/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD/kernel.bin"

cp "$BUILD/kernel.bin" "$OUT_DIR/space-multiboot.bin"
BUILD_ID="$(git -C "$SPACE" rev-parse --short HEAD 2>/dev/null || date +%s)"
printf '%s\n' "$BUILD_ID" > "$OUT_DIR/kernel-build-id.txt"

if [ -d "$ROOT/node_modules/v86/build" ]; then
  for f in libv86.mjs v86.wasm v86-fallback.wasm seabios.bin vgabios.bin; do
    cp "$ROOT/node_modules/v86/build/$f" "$OUT_DIR/" 2>/dev/null || true
  done
fi

ls -lh "$OUT_DIR/space-multiboot.bin"