#!/usr/bin/env bash
# Prove trusted ELF/Mach-O SYSCALL and PE import output/exit under QEMU.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/inauguration-dir.sh"
INAUG_DIR="$(inauguration_dir "$SPACE_DIR")"
BUILD_DIR="${BUILD_DIR:-/tmp/space-foreign-syscalls}"
IN="$INAUG_DIR/in-cli/target/release/in"
NASM="${NASM:-nasm}"
SERIAL_BASE="$BUILD_DIR/serial"
SERIAL_LOG="$BUILD_DIR/serial.log"
PIDFILE="$BUILD_DIR/qemu.pid"
CATPID=""
mkdir -p "$BUILD_DIR"
rm -f "$SERIAL_BASE.in" "$SERIAL_BASE.out" "$SERIAL_LOG" "$PIDFILE"
cleanup() {
  if [ -n "$CATPID" ]; then
    kill "$CATPID" 2>/dev/null || true
    wait "$CATPID" 2>/dev/null || true
  fi
  if [ -f "$PIDFILE" ]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
  fi
  rm -f "$SERIAL_BASE.in" "$SERIAL_BASE.out" "$PIDFILE"
}
trap cleanup EXIT
[ -x "$IN" ] || cargo build --release -q --manifest-path "$INAUG_DIR/in-cli/Cargo.toml"
"$NASM" -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel-entry --emit boot \
  --trampoline "$BUILD_DIR/trampoline.bin" --target native \
  --target-triple x86_64-unknown-none --linkage static-lib --out "$BUILD_DIR/kernel.bin"
run_fixture() {
ABI="$1"
FIXTURE="$2"
COMMAND="$3"
EXPECTED="$4"
KIND="${5:-serial}"
SERIAL_LOG="$BUILD_DIR/$FIXTURE-serial.log"
"$NASM" -I "$SPACE_DIR/fixtures/" -f bin "$SPACE_DIR/fixtures/$FIXTURE.asm" -o "$BUILD_DIR/fixture.bin"
python3 - "$BUILD_DIR" "$ABI" "$KIND" <<'PY'
from pathlib import Path
import struct
import sys
build = Path(sys.argv[1])
image = (build / 'fixture.bin').read_bytes()
assert len(image) == 4096
if sys.argv[2] == 'linux':
    assert image[:8] == bytes.fromhex('7f454c4602010100')
    assert struct.unpack_from('<HHI', image, 16) == (2, 62, 1)
    assert struct.unpack_from('<Q', image, 24)[0] == 0x280080
    assert struct.unpack_from('<II6Q', image, 64) == (1, 5, 0, 0x280000, 0x280000, 4096, 4096, 4096)
elif sys.argv[2] == 'darwin':
    assert struct.unpack_from('<8I', image) == (0xfeedfacf, 0x1000007, 3, 2, 2, 96, 1, 0)
    assert struct.unpack_from('<II16s4Q4I', image, 32) == (0x19, 72, b'__TEXT'+bytes(10), 0x280000, 4096, 0, 4096, 5, 5, 0, 0)
    assert struct.unpack_from('<IIQQ', image, 104) == (0x80000028, 24, 128, 0)
else:
    assert image[:2] == b'MZ'
    assert struct.unpack_from('<I', image, 60)[0] == 128
    assert struct.unpack_from('<IHH', image, 128) == (0x4550, 0x8664, 1)
    assert struct.unpack_from('<H', image, 152)[0] == 0x20b
    assert struct.unpack_from('<I', image, 168)[0] == 512
    assert struct.unpack_from('<Q', image, 176)[0] == 0x280000
    assert struct.unpack_from('<II', image, 272) == (0x800, 40)
    assert image[0x900:0x90d] == b'KERNEL32.dll\0'
    assert struct.unpack_from('<5I', image, 0x800) == (0x840, 0, 0, 0x900, 0x880)
    if sys.argv[3] == 'file':
        assert struct.unpack_from('<6Q', image, 0x880) == (0x920, 0x940, 0x960, 0x980, 0x9a0, 0)
    else:
        assert struct.unpack_from('<3Q', image, 0x880) == (0x920, 0x940, 0)
if sys.argv[2] != 'windows':
    assert b'\x0f\x05' in image[128:]
kernel = (build / 'kernel.bin').read_bytes()
assert len(kernel) <= 0x180000, 'kernel overlaps foreign fixture'
(build / 'combined.bin').write_bytes(kernel + bytes(0x180000-len(kernel)) + image)
PY
mkfifo "$SERIAL_BASE.in" "$SERIAL_BASE.out"
qemu-system-x86_64 -kernel "$BUILD_DIR/combined.bin" -m 512M -no-reboot \
  -display none -serial "pipe:$SERIAL_BASE" -pidfile "$PIDFILE" -daemonize
timeout 40 cat "$SERIAL_BASE.out" > "$SERIAL_LOG" &
CATPID=$!
for _ in $(seq 1 300); do
  grep -qF "space interactive shell" "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
grep -qF "space interactive shell" "$SERIAL_LOG" || { echo 'FAIL: shell did not start' >&2; exit 1; }
printf '%s\n%s\nhalt\n' "$COMMAND" "$COMMAND" > "$SERIAL_BASE.in"
for _ in $(seq 1 100); do
  grep -qF 'halting on request' "$SERIAL_LOG" 2>/dev/null && break
  grep -qF 'validation FAILED' "$SERIAL_LOG" 2>/dev/null && break
  sleep 0.1
done
if grep -qE 'FAILED|CPU EXCEPTION|nanokernel fault' "$SERIAL_LOG"; then
  cat "$SERIAL_LOG" >&2
  exit 1
fi
if [ "$ABI" = linux ] && [ "$KIND" = serial ]; then
  grep -qxF 'linux: ELF validation scenarios 13/13' "$SERIAL_LOG"
fi
[ "$(grep -cxF "$EXPECTED" "$SERIAL_LOG")" = 2 ]
if [ "$KIND" = file ]; then
  [ "$(grep -cxF 'foreign: VFS file contents' "$SERIAL_LOG")" = 2 ]
  [ "$(grep -cxF 'foreign: file I/O handles restored' "$SERIAL_LOG")" = 2 ]
  [ "$(grep -cxF 'foreign: file I/O storage grant required' "$SERIAL_LOG")" = 2 ]
  if [ "$ABI" = windows ]; then
    [ "$(grep -cxF 'windows: PE file I/O validation scenarios 8/8' "$SERIAL_LOG")" = 2 ]
  fi
elif [ "$ABI" = windows ]; then
  grep -qxF 'windows: PE validation scenarios 15/15' "$SERIAL_LOG"
  [ "$(grep -cxF 'windows: PE import hello' "$SERIAL_LOG")" = 2 ]
else
  [ "$(grep -cxF "$ABI: hardware syscall hello" "$SERIAL_LOG")" = 2 ]
fi
grep -qF 'halting on request' "$SERIAL_LOG"
echo "PASS: $ABI foreign $KIND I/O (error ABI, output, exit 42, shell resumes)"
cleanup
CATPID=""
}
run_fixture linux linux-syscall-elf linuxsyscall 'linux: syscall ELF exit status 42'
run_fixture darwin darwin-syscall-macho darwinsyscall 'darwin: syscall Mach-O exit status 42'
run_fixture windows windows-import-pe windowspe 'windows: PE import exit status 42'
run_fixture linux linux-fileio-elf linuxfileio 'foreign: file I/O exit status 42' file
run_fixture darwin darwin-fileio-macho darwinfileio 'foreign: file I/O exit status 42' file
run_fixture windows windows-fileio-pe windowsfileio 'foreign: file I/O exit status 42' file
run_fixture linux linux-fileio-return-elf linuxfileio 'foreign: file I/O exit status 42' file
run_fixture darwin darwin-fileio-return-macho darwinfileio 'foreign: file I/O exit status 42' file
