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
    shell = read("components/shell.in") + "\n" + read("components/shell-common.in")
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
        "domain-create reuses only free slots and rejects ids beyond MAX-DOMAINS",
        "while id < domain-count && load64(domain-table + id * 24 + 8) != DOMAIN-FREE" in domain
        and "if id >= MAX-DOMAINS { return -1 }" in domain
        and "if id == domain-count { domain-count = domain-count + 1 }" in domain,
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
        "GDT has DPL0 kernel and DPL3 user segments plus enter_user",
        "0x00AF9A000000FFFF" in boot
        and "0x00AFFA000000FFFF" in boot
        and "0x00CFF2000000FFFF" in boot
        and "enter_user:" in boot
        and "leave_user:" in boot,
    )
    check(
        "CR3 read/write stubs remain published at 0x4058/0x4060",
        "0x4058" in boot and "0x4060" in boot and "cr3_write:" in boot,
    )

    print("[3/5] Channels / storage / net...")
    check(
        "chan-new rejects capacities outside 1..4096 before allocation",
        re.search(r"fn chan-new\(cap: Int\) -> Int \{\n  //[^\n]*\n  if cap <= 0 \|\| cap > 4096 \{\n    return 0\n  \}", channel)
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
        "shell hardening command asserts chan/syscall/dns/frame reuse, CPL3 enter, and exclusive maps",
        "chan-new(0)" in shell
        and "hardening PASS" in shell
        and "dns-parse-a" in shell
        and "domain-enter-user" in shell
        and "kernel globals are mapped in the guest tree" in shell
        and "2-4 GiB identity window" in shell
        and "boot kernel stack" in shell
        and "published ISR pointers" in shell
        and "trampoline is missing or user-accessible" in shell,
    )
    check(
        "read-line stops before overflowing the 256-byte history slot",
        "len < 254" in shell,
    )

    print("[5/5] Isolation honesty...")
    clone = domain[domain.index("fn create-shared-domain-pml4()"):domain.index("fn create-user-domain-pml4()")]
    check(
        "SCI guests use exclusive trees; clone PDPT[0..3] owns copied mutable leaf tables",
        "while j < 4" in clone
        and "let entry = load64(src-pd + k * 8)" in clone
        and "if (entry & 1) != 0 && (entry & 128) == 0" in clone
        and "let leaf = frame-alloc()" in clone
        and "cpu-mem-copy64(leaf, entry & PAGE-ADDRESS-MASK, 512)" in clone
        and "entry = leaf | (entry & (-1 ^ PAGE-ADDRESS-MASK))" in clone
        and "store64(dst-pd + k * 8, entry)" in clone
        and "fn domain-enter-user" in domain
        and "fn domain-create-user" in domain
        and "fn domain-map-trampoline" in domain
        and "fn domain-map-boot-stack" not in domain
        and "store64(dst-pd, 0x83)" not in domain
        and "domain-create-user()" in read("components/sci-loader.in")
        and "domain-enter-user(entry, cap-info, domain)" in read("components/sci-loader.in"),
    )
    check(
        "kernel domain-init privatizes the cr3 stubs before use",
        "cr3-write-stub = load64(0x4060)" in domain
        and "store64(0x4060, 0)" in domain
        and "cr3-write(kernel-pml4)" in domain
        and "invoke1(load64(0x4060)" not in domain,
    )

    shell = read("components/shell.in") + "\n" + read("components/shell-common.in")
    guest = shell[shell.index('let guest-comp = component-register("hard-guest"'):]
    guest = guest[:guest.index("// DNS parser")]
    check(
        "hardening selftest binds a minted serial capability before entering guest",
        "sci-bind-domain-cap(" not in shell
        and guest.index("cap-mint(guest-comp, cap-serial())") < guest.index("domain-create()")
        and guest.index("domain-set-cap(guest-dom, guest-cap)") < guest.index("domain-switch(guest-dom)")
        and "if guest-dom > 0" in guest
        and "cap-revoke(guest-cap)" in guest
        and guest.count("component-unregister(guest-comp)") == 2,
    )

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: kernel contracts")
        return 1
    print("PASS: kernel contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
