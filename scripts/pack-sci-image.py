import os
import struct
import sys

MAGIC = 0x5350414345424F4F
IMAGE_BASE = 0x100000
HANDOFF_OFFSET = 0xF00
IMAGE_LIMIT = 0x300000

kernel_path, out_path, *specs = sys.argv[1:]
out = bytearray(open(kernel_path, "rb").read())
entries = []
for spec in specs:
    kind_text, path = spec.split(":", 1)
    blob = open(path, "rb").read()
    if len(blob) < 32 or struct.unpack_from("<Q", blob)[0] != 0x5343490000000001:
        raise SystemExit(f"invalid SCI: {path}")
    off = (len(out) + 4095) & -4096
    out += b"\x00" * (off - len(out))
    phys = IMAGE_BASE + off
    entries.append((int(kind_text, 0), phys, len(blob), 0))
    out += blob
table_off = (len(out) + 4095) & -4096
out += b"\x00" * (table_off - len(out))
table_phys = IMAGE_BASE + table_off
out += struct.pack("<QQ", MAGIC, len(entries))
for entry in entries:
    out += struct.pack("<QQQQ", *entry)
if IMAGE_BASE + len(out) > IMAGE_LIMIT:
    raise SystemExit("boot image overlaps the kernel heap window")
struct.pack_into("<Q", out, HANDOFF_OFFSET, table_phys)
open(out_path, "wb").write(out)
for kind, phys, size, _ in entries:
    print(f"  SCI kind {kind} at physical 0x{phys:x} ({size} bytes)")
print(f"  boot image table at physical 0x{table_phys:x}")
print(f"  {out_path}: {len(out)} bytes")
