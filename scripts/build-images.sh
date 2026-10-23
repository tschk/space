#!/usr/bin/env bash
set -euo pipefail

# build-images.sh — Build the two distributable boot images (Space 0.1.0):
#
#   standard.bin — full nanokernel (network, NVMe/USB, personalities,
#                  display/input) + libspace + user demos + dynmod + apps.
#   minimal.bin  — core-only nanokernel (serial, VM, domains, dynamic
#                  linking, filesystem shell) + libspace + apps.
#
# Apps are preinstalled dynamic modules (boot kinds 9-13) that bind kernel
# services and libspace at load time and run on demand via `runapp`.

# Default remains the full two-image build. A targeted build never certifies
# the other variant; this allows standard-app testing while minimal is broken.
VARIANT=all
if [ "$#" -gt 0 ]; then
  if [ "$#" -ne 2 ] || [ "$1" != --variant ]; then
    echo "usage: $0 [--variant all|standard|minimal]" >&2
    exit 2
  fi
  VARIANT="$2"
fi
case "$VARIANT" in
  all|standard|minimal) ;;
  *) echo "unknown image variant: $VARIANT" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=inauguration-dir.sh
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-images}"
IN="${IN:-$INAUG_DIR/in-cli/target/release/in}"
GUI_PROFILE="${GUI_PROFILE:-protected}"
case "$GUI_PROFILE" in
  legacy|window|protected) ;;
  *) echo "unknown native GUI profile: $GUI_PROFILE" >&2; exit 2 ;;
esac

LIB_BASE=0x3F000000
API_BASE=0x3E000000
HELLO_BASE=0x70000000
ECHO_BASE=0x71000000
DYNMOD_BASE=0x72000000
CALC_BASE=0x73000000
NOTES_BASE=0x74000000
HD_BASE=0x75000000
SYSMON_BASE=0x76000000
BENCH_BASE=0x77000000
FILES_BASE=0x78000000
CLOCK_BASE=0x79000000
SUM_BASE=0x7A000000
MAN_BASE=0x7B000000
SYSINFO_BASE=0x7C000000

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler and trampoline..."
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
NASM="${NASM:-nasm}"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"

sci() { # path entry base out
  "$IN" compile --path "$1" --entry "$2" \
    --target native --target-triple x86_64-unknown-none --emit sci \
    --base "$3" --out "$4"
}

echo "[2/3] Compiling shared libraries, demos, and apps..."
sci "$SPACE_DIR/components/libspace.in" lib-entry "$LIB_BASE" "$BUILD_DIR/libspace.sci"
sci "$SPACE_DIR/components/appapi.in" api-entry "$API_BASE" "$BUILD_DIR/appapi.sci"
sci "$SPACE_DIR/components/user-hello.in" hello-entry "$HELLO_BASE" "$BUILD_DIR/user-hello.sci"
sci "$SPACE_DIR/components/user-echo.in" echo-entry "$ECHO_BASE" "$BUILD_DIR/user-echo.sci"
sci "$SPACE_DIR/components/dyn-mod.in" dyn-mod-entry "$DYNMOD_BASE" "$BUILD_DIR/dynmod.sci"
sci "$SPACE_DIR/components/app-calc.in" app-calc-entry "$CALC_BASE" "$BUILD_DIR/app-calc.sci"
sci "$SPACE_DIR/components/app-notes.in" app-notes-entry "$NOTES_BASE" "$BUILD_DIR/app-notes.sci"
sci "$SPACE_DIR/components/app-hd.in" app-hd-entry "$HD_BASE" "$BUILD_DIR/app-hd.sci"
sci "$SPACE_DIR/components/app-sysmon.in" app-sysmon-entry "$SYSMON_BASE" "$BUILD_DIR/app-sysmon.sci"
sci "$SPACE_DIR/components/app-bench.in" app-bench-entry "$BENCH_BASE" "$BUILD_DIR/app-bench.sci"
sci "$SPACE_DIR/components/app-files.in" app-files-entry "$FILES_BASE" "$BUILD_DIR/app-files.sci"
sci "$SPACE_DIR/components/app-clock.in" app-clock-entry "$CLOCK_BASE" "$BUILD_DIR/app-clock.sci"
sci "$SPACE_DIR/components/app-sum.in" app-sum-entry "$SUM_BASE" "$BUILD_DIR/app-sum.sci"
sci "$SPACE_DIR/components/app-man.in" app-man-entry "$MAN_BASE" "$BUILD_DIR/app-man.sci"
sci "$SPACE_DIR/components/app-sysinfo.in" app-sysinfo-entry "$SYSINFO_BASE" "$BUILD_DIR/app-sysinfo.sci"

echo "[3/3] Compiling kernels and assembling images..."
if [ "$VARIANT" != minimal ]; then
# Optional native GUI artifacts are only built and packed into standard.
sci "$SPACE_DIR/components/input.in" input-poll-entry 0x50000000 "$BUILD_DIR/gui-seat.sci"
GUI_CALC_SOURCE=app-gui-calc.in
GUI_EDITOR_SOURCE=app-gui-editor.in
if [ "$GUI_PROFILE" = window ]; then
  GUI_CALC_SOURCE=app-window-calc.in
  GUI_EDITOR_SOURCE=app-window-editor.in
fi
GUI_CALC_BASE=0x48000000
GUI_EDITOR_BASE=0x49000000
GUI_CALC_KIND=20
GUI_EDITOR_KIND=21
GUI_PACK_ARGS=()
if [ "$GUI_PROFILE" = protected ]; then
  GUI_CALC_SOURCE=app-protected-window-calc.in
  GUI_EDITOR_SOURCE=app-protected-window-editor.in
  GUI_CALC_BASE=0x60000000
  GUI_EDITOR_BASE=0x60000000
  GUI_CALC_KIND=23
  GUI_EDITOR_KIND=24
  GUI_PACK_ARGS=(--protected)
fi
sci "$SPACE_DIR/components/$GUI_CALC_SOURCE" client-entry "$GUI_CALC_BASE" "$BUILD_DIR/gui-calc.raw.sci"
sci "$SPACE_DIR/components/$GUI_EDITOR_SOURCE" client-entry "$GUI_EDITOR_BASE" "$BUILD_DIR/gui-editor.raw.sci"
for GUI_APP in calc editor; do
  if ! python3 "$SCRIPT_DIR/pack-gui-sci.py" "$BUILD_DIR/gui-$GUI_APP.raw.sci" "$BUILD_DIR/gui-$GUI_APP.raw.component-metadata.json" "$BUILD_DIR/gui-$GUI_APP.sci" "${GUI_PACK_ARGS[@]}"; then
    if [ "$GUI_PROFILE" = protected ]; then
      echo "Protected GUI packaging refused this compiler/artifact. Set IN to a source-built Inauguration0.9.325+ with valid hash-bound page-aligned sci_layout metadata, or explicitly choose GUI_PROFILE=window/legacy for a trusted baseline." >&2
    fi
    exit 1
  fi
done
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel-standard.bin" >/dev/null

python3 "$SCRIPT_DIR/pack-sci-image.py" "$BUILD_DIR/kernel-standard.bin" "$BUILD_DIR/standard.bin" \
  "7:$BUILD_DIR/libspace.sci" "14:$BUILD_DIR/appapi.sci" "5:$BUILD_DIR/user-hello.sci" "6:$BUILD_DIR/user-echo.sci" \
  "8:$BUILD_DIR/dynmod.sci" "9:$BUILD_DIR/app-calc.sci" "10:$BUILD_DIR/app-notes.sci" \
  "11:$BUILD_DIR/app-hd.sci" "12:$BUILD_DIR/app-sysmon.sci" "13:$BUILD_DIR/app-bench.sci" \
  "15:$BUILD_DIR/app-files.sci" "16:$BUILD_DIR/app-clock.sci" "17:$BUILD_DIR/app-sum.sci" \
  "18:$BUILD_DIR/app-man.sci" "19:$BUILD_DIR/app-sysinfo.sci" \
  "$GUI_CALC_KIND:$BUILD_DIR/gui-calc.sci" "$GUI_EDITOR_KIND:$BUILD_DIR/gui-editor.sci" "22:$BUILD_DIR/gui-seat.sci"

fi

if [ "$VARIANT" != standard ]; then
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root-minimal.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" \
  --target native --target-triple x86_64-unknown-none --linkage static-lib \
  --out "$BUILD_DIR/kernel-minimal.bin" >/dev/null

python3 "$SCRIPT_DIR/pack-sci-image.py" "$BUILD_DIR/kernel-minimal.bin" "$BUILD_DIR/minimal.bin" \
  "7:$BUILD_DIR/libspace.sci" "14:$BUILD_DIR/appapi.sci" "9:$BUILD_DIR/app-calc.sci" "10:$BUILD_DIR/app-notes.sci" \
  "11:$BUILD_DIR/app-hd.sci" "12:$BUILD_DIR/app-sysmon.sci" "13:$BUILD_DIR/app-bench.sci" \
  "15:$BUILD_DIR/app-files.sci" "16:$BUILD_DIR/app-clock.sci" "17:$BUILD_DIR/app-sum.sci" \
  "18:$BUILD_DIR/app-man.sci" "19:$BUILD_DIR/app-sysinfo.sci"

fi

echo "Done: requested image variant $VARIANT. Boot with:"
if [ "$VARIANT" != minimal ]; then
  ls -lh "$BUILD_DIR/standard.bin"
  echo "  qemu-system-x86_64 -kernel $BUILD_DIR/standard.bin -m 256M -nographic -no-reboot -serial stdio"
fi
if [ "$VARIANT" != standard ]; then
  ls -lh "$BUILD_DIR/minimal.bin"
  echo "  qemu-system-x86_64 -kernel $BUILD_DIR/minimal.bin -m 256M -nographic -no-reboot -serial stdio"
fi
