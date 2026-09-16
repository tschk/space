#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
# Host-side nanokernel contract regressions. No QEMU / compiler.
"""Assert syscall, domain, channel, storage, and net hardening still holds."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
passed = 0
failed = 0


def check(label: str, ok: bool) -> None:
    global passed, failed
    if ok:
        print(f"  ok: {label}")
        passed += 1
    else:
        print(f"  FAIL: {label}")
        failed += 1


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


def main() -> int:
    syscall = read("components/syscall.in")
    obj = read("components/object.in")
    domain = read("components/domain.in")
    memory = read("components/memory.in")
    channel = read("components/channel.in")
    storage = read("components/storage.in")
    network = read("components/network.in")
    dns = read("components/dns.in")
    shell = read("components/shell.in")
    boot = read("boot/multiboot.asm")

    print("[1/5] Syscall / capability surface...")
    check(
        "sys-cap-mint is a hard deny",
        re.search(r"fn sys-cap-mint\([^)]*\) -> Int \{\n  return -1\n\}", syscall) is not None,
    )
    check(
        "sys-cap-revoke is a hard deny",
        re.search(r"fn sys-cap-revoke\([^)]*\) -> Int \{\n  return -1\n\}", syscall) is not None,
    )
    check(
        "sys-write/sys-read reject null/oversized buffers",
        syscall.count("if len <= 0 || len > 4096 || buf == 0") >= 2,
    )
    check(
        "sys-exit reaps via proc-exit (does not halt the OS)",
        "proc-exit(code)" in syscall and "cli()" not in syscall and "hlt()" not in syscall,
    )
    check("cap-mint is bounded by table capacity", "if cap-count >= cap-table-cap" in obj)

    print("[2/5] Domain / memory / boot...")
    check(
        "domain-create returns -1 when the table is full",
        re.search(r"if domain-count >= MAX-DOMAINS \{\n    return -1\n  \}", domain) is not None,
    )
    check(
        "SCI mapping helpers exist (code RX / data RW NX)",
        "fn domain-map-user-code" in domain and "fn domain-map-user-data" in domain,
    )
    check(
        "frame-alloc panics at heap-end instead of wrapping",
        'panic("frame heap exhausted")' in memory,
    )
    check(
        "boot trampoline identity-maps 4 GiB with 2 MiB RW pages",
        "identity-map the first 4 GiB" in boot and "0x83" in boot,
    )
    check(
        "GDT is DPL0-only (no CPL3 user segments)",
        "DPL0" in boot and "0x00AF9A000000FFFF" in boot,
    )
    check(
        "CR3 read/write stubs remain published at 0x4058/0x4060",
        "0x4058" in boot and "0x4060" in boot and "cr3_write:" in boot,
    )

    print("[3/5] Channels / storage / net...")
    check(
        "chan-new rejects cap<=0",
        re.search(r"fn chan-new\(cap: Int\) -> Int \{\n  if cap <= 0 \{\n    return 0\n  \}", channel)
        is not None,
    )
    check("chan-valid exists before send/recv", "fn chan-valid" in channel)
    check(
        "nvme-io-submit rejects count<=0 and clamps to 8 sectors",
        "if count <= 0" in storage and "if count > 8" in storage and "count = 8" in storage,
    )
    check(
        "tcp-parse-data treats RST as failure",
        re.search(r"if \(flags & 0x04\) != 0 \{\n    return -1", network) is not None,
    )
    check(
        "dns-skip-name is bounded against packet end",
        "if off >= end" in dns and "jumps > 128" in dns,
    )
    check(
        "DNS replies require 10.0.2.3 and query id 0x1234",
        "rid == 0x1234" in dns and "src0 == 10" in dns and "src3 == 3" in dns,
    )

    print("[4/5] Shell hardening command + read-line bound...")
    check(
        "shell hardening command asserts chan/syscall/dns/frame reuse",
        "chan-new(0)" in shell and "hardening PASS" in shell and "dns-parse-a" in shell,
    )
    check(
        "read-line stops before overflowing the 256-byte history slot",
        "len < 254" in shell,
    )

    print("[5/5] Isolation honesty...")
    check(
        "create-domain-pml4 still copies PDPT[0..3] (cloned identity map)",
        "while j < 4" in domain and "store64(dst-pd + k * 8, load64(src-pd + k * 8))" in domain,
    )
    check(
        "kernel domain-init still invokes the published cr3_write stub",
        "invoke1(load64(0x4060), kernel-pml4)" in domain,
    )

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: kernel contracts")
        return 1
    print("PASS: kernel contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
