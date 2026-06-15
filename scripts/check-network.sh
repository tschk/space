#!/usr/bin/env bash
#
# check-network.sh — Boot the nanokernel with an e1000 NIC, send a broadcast ARP
# from the `.in` driver, and verify the frame in a host-side pcap capture.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPACE_DIR="$(dirname "$SCRIPT_DIR")"
INAUG_DIR="${INAUGURATION_DIR:-$SPACE_DIR/../inauguration}"
BUILD_DIR="${BUILD_DIR:-/tmp/space-net}"
IN="$INAUG_DIR/in-cli/in"

mkdir -p "$BUILD_DIR"

echo "[1/3] Building compiler, trampoline, kernel..."
make -C "$INAUG_DIR/in-cli" >/dev/null
nasm -f bin "$SPACE_DIR/boot/multiboot.asm" -o "$BUILD_DIR/trampoline.bin"
"$IN" compile --path "$SPACE_DIR/kernel/kernel-root.in" --entry kernel_entry \
  --emit boot --trampoline "$BUILD_DIR/trampoline.bin" \
  --out "$BUILD_DIR/kernel.bin" >/dev/null

echo "[2/3] Booting with e1000 + pcap capture, sending ARP..."
rm -f "$BUILD_DIR/net.pcap" "$BUILD_DIR/serial.log"
printf 'help\rnet\rhalt\r' | perl -e 'alarm 10; exec @ARGV' qemu-system-x86_64 \
  -kernel "$BUILD_DIR/kernel.bin" -m 256M \
  -netdev user,id=n0 -device e1000,netdev=n0 \
  -object filter-dump,id=d0,netdev=n0,file="$BUILD_DIR/net.pcap" \
  -serial stdio -display none -no-reboot >"$BUILD_DIR/serial.log" 2>/dev/null || true

echo "--- driver serial output ---"
sed -n '/space> net/,/space>/p' "$BUILD_DIR/serial.log" 2>/dev/null || true
echo "----------------------------"

echo "[3/3] Inspecting the captured pcap..."
python3 - "$BUILD_DIR/net.pcap" <<'PY'
import sys, struct
data = open(sys.argv[1], "rb").read()
if len(data) < 24:
    print("FAIL: empty pcap"); sys.exit(1)
off = 24  # skip global header
found_arp = False
while off + 16 <= len(data):
    ts_s, ts_u, caplen, origlen = struct.unpack("<IIII", data[off:off+16])
    off += 16
    frame = data[off:off+caplen]
    off += caplen
    if len(frame) < 14:
        continue
    dst = frame[0:6]; src = frame[6:12]; eth = (frame[12] << 8) | frame[13]
    if eth == 0x0806:  # ARP
        op = (frame[20] << 8) | frame[21] if len(frame) >= 22 else 0
        spa = ".".join(str(b) for b in frame[28:32]) if len(frame) >= 32 else "?"
        tpa = ".".join(str(b) for b in frame[38:42]) if len(frame) >= 42 else "?"
        macs = ":".join("%02x" % b for b in src)
        print(f"  ARP frame: dst={dst.hex(':')} src={macs} op={op} sender={spa} target={tpa}")
        if dst == b"\xff\xff\xff\xff\xff\xff" and op == 1:
            found_arp = True
print("PASS: e1000 transmitted a broadcast ARP request (captured in pcap)." if found_arp
      else "FAIL: no broadcast ARP request found in capture.")
sys.exit(0 if found_arp else 1)
PY
