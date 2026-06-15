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

echo "[2/3] Booting with e1000 + pcap capture, sending ARP + UDP..."
rm -f "$BUILD_DIR/net.pcap" "$BUILD_DIR/serial.log"
printf 'help\rnet\rhalt\r' | perl -e 'alarm 12; exec @ARGV' qemu-system-x86_64 \
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
off = 24
found_arp = False
found_udp = False
while off + 16 <= len(data):
    _, _, caplen, _ = struct.unpack("<IIII", data[off:off+16]); off += 16
    f = data[off:off+caplen]; off += caplen
    if len(f) < 14:
        continue
    dst = f[0:6]; src = f[6:12]; eth = (f[12] << 8) | f[13]
    if eth == 0x0806 and len(f) >= 42:
        op = (f[20] << 8) | f[21]
        print(f"  ARP  dst={dst.hex(':')} src={src.hex(':')} op={op} "
              f"sender={'.'.join(map(str,f[28:32]))} target={'.'.join(map(str,f[38:42]))}")
        if dst == b"\xff\xff\xff\xff\xff\xff" and op == 1:
            found_arp = True
    elif eth == 0x0800 and len(f) >= 42 and f[23] == 17:
        sp = (f[34] << 8) | f[35]; dp = (f[36] << 8) | f[37]
        payload = f[42:].split(b"\x00")[0]
        print(f"  UDP  {'.'.join(map(str,f[26:30]))}:{sp} -> "
              f"{'.'.join(map(str,f[30:34]))}:{dp} payload={payload!r}")
        if dp == 9999 and payload == b"hello from spaceOS":
            found_udp = True
ok = found_arp and found_udp
print("PASS: e1000 sent a broadcast ARP and a valid IPv4/UDP datagram (captured)."
      if ok else "FAIL: expected ARP request and UDP datagram not both found.")
sys.exit(0 if ok else 1)
PY
