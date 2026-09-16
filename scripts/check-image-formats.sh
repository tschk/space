#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
# Host-side SCI boot-image packer + SparkFS/SCI header contract.
# No QEMU / compiler.
"""Validate pack-sci-image.py and on-disk header constants."""
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
passed = 0
failed = 0

SCI_MAGIC = 0x5343490000000001
BOOT_MAGIC = 0x5350414345424F4F
SF_MAGIC = 0x53504146
IMAGE_BASE = 0x100000
HANDOFF_OFFSET = 0xF00
IMAGE_LIMIT = 0x300000


def check(label: str, ok: bool) -> None:
    global passed, failed
    if ok:
        print(f"  ok: {label}")
        passed += 1
    else:
        print(f"  FAIL: {label}")
        failed += 1


def const_int(text: str, name: str) -> int | None:
    m = re.search(rf"const {re.escape(name)} = (0x[0-9A-Fa-f]+|\d+)", text)
    if not m:
        return None
    return int(m.group(1), 0)


def main() -> int:
    loader = (ROOT / "components/sci-loader.in").read_text()
    layout = (ROOT / "components/fs2-layout.in").read_text()
    sparkfs = (ROOT / "docs/sparkfs.md").read_text()
    packer = (ROOT / "scripts/pack-sci-image.py").read_text()
    posix = (ROOT / "components/posix.in").read_text()

    print("[1/4] SCI / SparkFS constants...")
    check("sci-loader SCI-MAGIC", const_int(loader, "SCI-MAGIC") == SCI_MAGIC)
    check("posix execve SCI magic", "0x5343490000000001" in posix)
    check("packer SCI magic", "0x5343490000000001" in packer)
    check("packer boot-image MAGIC", "0x5350414345424F4F" in packer)
    check("fs2 SF-MAGIC", const_int(layout, "SF-MAGIC") == SF_MAGIC)
    check("docs sparkfs magic", "0x53504146" in sparkfs)
    check("docs superblock magic at offset 0", "| 0 | 4 | magic:" in sparkfs)
    check("SF-SB-MAGIC offset 0", const_int(layout, "SF-SB-MAGIC") == 0)
    check("SF-SB-VERSION offset 4", const_int(layout, "SF-SB-VERSION") == 4)
    check("SF-SB-BLOCK-SIZE offset 8", const_int(layout, "SF-SB-BLOCK-SIZE") == 8)
    check("SF-SB-TOTAL-BLOCKS offset 12", const_int(layout, "SF-SB-TOTAL-BLOCKS") == 12)
    check("SF-INODE-SIZE 256", const_int(layout, "SF-INODE-SIZE") == 256)
    check("SF-BLOCK-SIZE 4096", const_int(layout, "SF-BLOCK-SIZE") == 4096)
    check("SF-DIR-ENTRY-HEAD 8", const_int(layout, "SF-DIR-ENTRY-HEAD") == 8)
    check("SF-NAME-MAX 255", const_int(layout, "SF-NAME-MAX") == 255)

    print("[2/4] SCI loader header + boot table bounds...")
    check("loader reads magic at +0, required at +8, entry at +16, size at +24",
          "load64(load-addr + 0)" in loader and "load64(load-addr + 8)" in loader
          and "load64(load-addr + 16)" in loader and "load64(load-addr + 24)" in loader)
    check("boot-image-find rejects phys outside 0x100000..0x300000",
          "phys >= 0x100000 && phys < 0x300000" in loader)
    check("boot-image-find rejects size < 32 or > 2 MiB",
          "size >= 32 && size <= 0x200000" in loader)
    check("boot-image-find rejects wrapping phys+size",
          "phys + size >= phys && phys + size <= 0x300000" in loader)
    check("boot-image-find caps table count at 64",
          "count < 0 || count > 64" in loader)

    print("[3/4] pack-sci-image.py happy path...")
    pack_py = ROOT / "scripts/pack-sci-image.py"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        kernel = bytearray(4096)
        kernel_path = tmp_path / "kernel.bin"
        kernel_path.write_bytes(kernel)
        sci = bytearray(64)
        struct.pack_into("<Q", sci, 0, SCI_MAGIC)
        sci_path = tmp_path / "guest.sci"
        sci_path.write_bytes(sci)
        out_path = tmp_path / "packed.bin"
        r = subprocess.run(
            [sys.executable, str(pack_py), str(kernel_path), str(out_path), f"1:{sci_path}"],
            capture_output=True, text=True,
        )
        check("packer exit 0", r.returncode == 0)
        blob = out_path.read_bytes() if out_path.exists() else b""
        check("packed image larger than kernel", len(blob) > 4096)
        table_phys = struct.unpack_from("<Q", blob, HANDOFF_OFFSET)[0] if len(blob) > HANDOFF_OFFSET + 8 else 0
        check("handoff at 0xF00 is a physical table pointer", IMAGE_BASE <= table_phys < IMAGE_LIMIT)
        table_off = table_phys - IMAGE_BASE
        if table_off + 16 <= len(blob):
            magic, count = struct.unpack_from("<QQ", blob, table_off)
            check("boot table magic", magic == BOOT_MAGIC)
            check("boot table count == 1", count == 1)
            kind, phys, size, _ = struct.unpack_from("<QQQQ", blob, table_off + 16)
            check("entry kind 1", kind == 1)
            check("entry size 64", size == 64)
            sci_off = phys - IMAGE_BASE
            packed_magic = struct.unpack_from("<Q", blob, sci_off)[0]
            check("packed SCI magic preserved", packed_magic == SCI_MAGIC)
            check("SCI payload 4 KiB aligned", sci_off % 4096 == 0)
        else:
            check("boot table magic", False)
            check("boot table count == 1", False)
            check("entry kind 1", False)
            check("entry size 64", False)
            check("packed SCI magic preserved", False)
            check("SCI payload 4 KiB aligned", False)
        check("packed image stays below kernel heap window", IMAGE_BASE + len(blob) <= IMAGE_LIMIT)

        print("[4/4] pack-sci-image.py rejects bad input...")
        bad = tmp_path / "bad.sci"
        bad.write_bytes(b"\x00" * 64)
        bad_out = tmp_path / "bad.bin"
        r_bad = subprocess.run(
            [sys.executable, str(pack_py), str(kernel_path), str(bad_out), f"1:{bad}"],
            capture_output=True, text=True,
        )
        check("invalid SCI magic is rejected", r_bad.returncode != 0)
        short = tmp_path / "short.sci"
        short.write_bytes(struct.pack("<Q", SCI_MAGIC))
        r_short = subprocess.run(
            [sys.executable, str(pack_py), str(kernel_path), str(bad_out), f"1:{short}"],
            capture_output=True, text=True,
        )
        check("SCI shorter than 32 bytes is rejected", r_short.returncode != 0)

        huge = bytearray(0x200001)
        struct.pack_into("<Q", huge, 0, SCI_MAGIC)
        huge_path = tmp_path / "huge.sci"
        huge_path.write_bytes(huge)
        # Two copies would overflow IMAGE_LIMIT from a 4096-byte kernel.
        r_huge = subprocess.run(
            [sys.executable, str(pack_py), str(kernel_path), str(bad_out),
             f"1:{huge_path}", f"2:{huge_path}"],
            capture_output=True, text=True,
        )
        check("packer rejects boot image that overlaps the heap window", r_huge.returncode != 0)

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: image format contracts")
        return 1
    print("PASS: image format contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
