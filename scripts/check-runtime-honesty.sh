#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
# Host-side honesty gate for remaining kernel-audit surfaces.
# Asserts current behavior (including known gaps). No QEMU / compiler.
"""Lock TCP, UDP, PCI, SparkFS, ELF, DNS, channel, and cap-check contracts."""
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


def fn_body(text: str, name: str) -> str | None:
    m = re.search(rf"\nfn {re.escape(name)}\([^)]*\)[^{{]*\{{", text)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return text[start : i - 1]


def dns_skip_name(pkt: bytes, start: int, end: int, msg: int = 0) -> int:
    """Mirror components/dns.in dns-skip-name (follows compression, earlier-only)."""
    off = start
    jumps = 0
    result = -1
    while True:
        if off >= end:
            return -1
        lab = pkt[off]
        if lab == 0:
            return off + 1 if result == -1 else result
        if (lab & 0xC0) == 0xC0:
            if off + 1 >= end:
                return -1
            if result == -1:
                result = off + 2
            ptr = ((lab & 0x3F) << 8) | pkt[off + 1]
            dest = msg + ptr
            if dest < msg or dest >= end or dest >= off:
                return -1
            off = dest
            jumps += 1
            if jumps > 128:
                return -1
        elif (lab & 0xC0) != 0:
            return -1
        else:
            if off + 1 + lab > end:
                return -1
            off = off + 1 + lab
            jumps += 1
            if jumps > 128:
                return -1


def main() -> int:
    network = read("components/network.in")
    netstack = read("components/netstack.in")
    pci = read("components/pci.in")
    storage = read("components/storage.in")
    display = read("components/display.in")
    fs_file = read("components/fs2-file.in")
    fs_block = read("components/fs2-block.in")
    posix = read("components/posix.in")
    obj = read("components/object.in")
    syscall = read("components/syscall.in")
    channel = read("components/channel.in")
    dns = read("components/dns.in")
    loader = read("components/sci-loader.in")
    kernel = read("kernel/kernel-root.in")
    sched = read("components/sched.in")
    shell = read("components/shell.in")

    print("[1/6] TCP is one global connection; ISN and close are honest...")
    for name in (
        "tcp-last-seq",
        "tcp-last-ack",
        "tcp-local-seq",
        "tcp-remote-ack",
        "tcp-rx-buf",
        "tcp-rx-len",
        "tcp-peer-wnd",
        "tcp-peer-mss",
        "tcp-send-wnd",
    ):
        check(f"{name} is a network.in global", f"var {name}: Int" in network)
    check("sock table allows 16 sockets", "const SOCK-MAX = 16" in netstack)
    syn = fn_body(network, "build-tcp-syn-impl") or ""
    check(
        "SYN sequence number is taken from tcp-isn",
        "(tcp-isn >> 24)" in syn and "tcp-isn & 0xFF" in syn,
    )
    connect = fn_body(netstack, "sock-connect") or ""
    check(
        "connect mixes ISN from ticks and advances local seq to ISN+1",
        "tcp-isn = (ticks * 1103515245 + 12345)" in connect
        and "tcp-local-seq = tcp-isn + 1" in connect,
    )
    close = fn_body(netstack, "sock-close") or ""
    check(
        "sock-close sends FIN+ACK on an established TCP socket",
        "build-tcp-fin-impl" in close and "e1000-tx-impl(flen)" in close and "0x11" in (fn_body(network, "build-tcp-fin-impl") or ""),
    )
    send = fn_body(netstack, "sock-send") or ""
    check(
        "unacked TCP send reports only the acked prefix (not silent success)",
        "return sent" in send and "return len" in send,
    )
    accept = fn_body(netstack, "sock-accept") or ""
    check("TCP accept is unimplemented (-38)", "return -38" in accept)

    print("[2/6] UDP destination comes from the socket; cstr-len is capped...")
    udp = fn_body(network, "build-udp-to-impl") or ""
    check(
        "build-udp-impl is a 10.0.2.2:9999 wrapper",
        "return build-udp-to-impl(payload, -1, 0x0A000202, 9999, 9999)" in (fn_body(network, "build-udp-impl") or ""),
    )
    check(
        "build-udp-to-impl writes dest-ip/dest-port onto the wire",
        "(dest-ip >> 24)" in udp and "(dest-port >> 8)" in udp and "(src-port >> 8)" in udp,
    )
    sendto = fn_body(netstack, "sock-sendto") or ""
    check(
        "sock-sendto drives TX via build-udp-to-impl with len/rip/rport/lport",
        "build-udp-to-impl(payload, send-len, dest-ip, dest-port, src-port)" in sendto,
    )
    cstr = fn_body(network, "cstr-len-impl") or ""
    check(
        "cstr-len-impl stops at 1472 bytes",
        "while n < 1472 && load8(addr + n) != 0" in cstr,
    )

    print("[3/6] PCI BARs and SparkFS disk fields are validated...")
    e1000 = fn_body(pci, "pci-find-and-enable-e1000") or ""
    bar = fn_body(pci, "pci-bar-mmio") or ""
    check(
        "pci-bar-mmio rejects I/O BARs and reserved type",
        "(raw & 1) != 0" in bar and "kind == 0x6" in bar,
    )
    check(
        "pci-bar-mmio probes size by writing all-ones",
        "pci-write32(bus, dev, func, off, -1)" in bar and "size < need" in bar,
    )
    check(
        "e1000 BAR0 requires a 64 KiB memory BAR",
        "pci-bar-mmio(0, dev, 0, 0x10, 0x10000)" in e1000,
    )
    nvme_pci = fn_body(storage, "storage-pci-init") or ""
    check(
        "NVMe BAR0 requires a 32 KiB memory BAR before mapping 32 KiB",
        "pci-bar-mmio(0, nvme-bdf, 0, 0x10, 0x8000)" in nvme_pci
        and "while pg < mmio-phys + 0x8000" in nvme_pci,
    )
    e1000_init = fn_body(network, "e1000-init-impl") or ""
    check(
        "e1000 maps 64 KiB only after BAR validation",
        "while pg < bar0 + 0x10000" in e1000_init,
    )
    check(
        "VGA BAR scan uses pci-bar-mmio",
        "class-code == 0x030000" in display and "pci-bar-mmio(0, dev, 0, 0x10, 0x1000)" in display,
    )
    init = fn_body(fs_file, "sparkfs-init") or ""
    check(
        "sparkfs-init sizes bitmap/inode table from on-disk total/ino-count",
        "let total = load64(sf-super + SF-SB-TOTAL-BLOCKS)" in init
        and "let ino-count = load32(sf-super + SF-SB-INODE-COUNT)" in init
        and "sf-bitmap = alloc(bitmap-bytes)" in init
        and "sf-inodes = alloc(ino-count * SF-INODE-SIZE)" in init,
    )
    check(
        "sparkfs-init caps total and ino-count before alloc",
        "if total < 2 || total > SF-MAX-TOTAL-BLOCKS" in init
        and "if ino-count < 1 || ino-count > SF-MAX-INODE-COUNT" in init,
    )
    read_blk = fn_body(fs_block, "sf-read-block") or ""
    write_blk = fn_body(fs_block, "sf-write-block") or ""
    check(
        "sf-read-block rejects out-of-range bno",
        "sf-bno-in-range(bno) == 0" in read_blk,
    )
    check(
        "sf-write-block rejects out-of-range bno",
        "sf-bno-in-range(bno) == 0" in write_blk,
    )

    print("[4/6] ELF execve copies PT_LOAD then jumps at CPL0; DNS compression is followed...")
    elf = fn_body(posix, "posix-elf-exec-image") or ""
    check(
        "ELF magic is the 64-bit little-endian ident word",
        "const LINUX-ELF-MAGIC = 0x00010102464C457F" in posix,
    )
    check(
        "posix-elf-exec-image copies PT_LOAD filesz then zeroes BSS to memsz",
        "store8(vaddr + k, load8(image + off + k))" in elf
        and "store8(vaddr + k, 0)" in elf
        and "while k < memsz" in elf,
    )
    check(
        "posix-elf-exec-image still jumps with invoke1(entry, 0) at CPL0",
        "return invoke1(entry, 0)" in elf,
    )
    skip = fn_body(dns, "dns-skip-name") or ""
    check(
        "dns-skip-name follows compression pointers that point earlier",
        "(lab & 0xC0) == 0xC0" in skip and "dest >= off" in skip and "result = off + 2" in skip,
    )
    pkt = bytearray(32)
    pkt[0] = 0
    pkt[12] = 0xC0
    pkt[13] = 0x00
    check("python dns-skip-name matches: compression to earlier NUL returns start+2", dns_skip_name(pkt, 12, 32, 0) == 14)
    pkt_fwd = bytearray(32)
    pkt_fwd[12] = 0xC0
    pkt_fwd[13] = 20
    check("python dns-skip-name matches: forward pointer is rejected", dns_skip_name(pkt_fwd, 12, 32, 0) == -1)
    pkt2 = bytearray(b"\x03www\x07example\x03com\x00")
    check("python dns-skip-name matches: uncompressed name walk", dns_skip_name(pkt2, 0, len(pkt2), 0) == len(pkt2))
    check("python dns-skip-name matches: off>=end is -1", dns_skip_name(b"\x00", 1, 1, 0) == -1)
    long_labels = bytearray([1, ord("a")] * 129 + [0])
    check("python dns-skip-name matches: jumps>128 is -1", dns_skip_name(long_labels, 0, len(long_labels), 0) == -1)

    print("[5/6] Capabilities, channels, SCI grants, preempt-stop...")
    check(
        "sys-cap-check is a thin wrapper over the global cap table",
        "fn sys-cap-check(idx: Int, rights: Int) -> Int {\n  return cap-check(idx, rights)\n}" in syscall,
    )
    check(
        "kernel channel/domain/storage/net paths do not consult cap-check",
        "cap-check(" not in channel
        and "cap-check(" not in read("components/domain.in")
        and "cap-check(" not in storage
        and "cap-check(" not in network
        and "cap-check(" not in netstack,
    )
    check("shell demo is the only in-tree cap-check caller besides syscall 11", shell.count("cap-check(") >= 1)
    chan_new = fn_body(channel, "chan-new") or ""
    check(
        "channel wait queues are single-slot (wait_send + wait_recv)",
        "store64(c + 32, -1)" in chan_new and "store64(c + 40, -1)" in chan_new,
    )
    valid = fn_body(channel, "chan-valid") or ""
    check(
        "chan-valid is a syntactic header check, not a handle table",
        "cap < 1 || cap > 4096" in valid and "handle" not in valid.lower(),
    )
    check("SCI guest grant mask is a fixed constant", "const SCI-GUEST-GRANTS = 1" in loader)
    sci_load = fn_body(loader, "sci-load") or ""
    check(
        "sci-load deny mask is SCI-GUEST-GRANTS (image-supplied required bits)",
        "required & (-1 ^ SCI-GUEST-GRANTS)" in sci_load,
    )
    check(
        "guest cap-info does not publish cap-table-base",
        "cap-table-base" not in loader and "store64(cap-info + 8, 0)" in sci_load,
    )
    check(
        "kernel stops the preempt scheduler before the serial shell",
        "preempt-start(port)" in kernel
        and "preempt-stop(port)" in kernel
        and kernel.find("preempt-stop(port)") < kernel.find("shell(port)"),
    )
    thr = fn_body(sched, "thr-create") or ""
    check(
        "thr-create returns -1 at thread-max",
        "if thread-count >= thread-max {\n    return -1\n  }" in thr,
    )
    check(
        "int 0x80 gate is DPL3 and GDT has user CS/DS",
        "store8(e + 5, 0xEE)" in syscall
        and "idt-set-user" in syscall
        and "0x00AFFA000000FFFF" in read("boot/multiboot.asm"),
    )
    domain = read("components/domain.in")
    check(
        "SCI guests get exclusive user PML4s instead of a 4 GiB clone",
        "fn create-user-domain-pml4" in domain
        and "store64(dst-pd, 0x83)" not in domain
        and "fn domain-map-trampoline" in domain
        and "domain-create-user()" in loader
        and "domain-create-user()" in read("components/process.in"),
    )

    print("[6/6] Syscall channel handles remain raw pointers...")
    check(
        "sys-chan-send/recv pass the caller handle straight through",
        "fn sys-chan-send(ch: Int, msg: Int) -> void {\n  chan-send(ch, msg)" in syscall
        and "fn sys-chan-recv(ch: Int) -> Int {\n  return chan-recv(ch)" in syscall,
    )

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: runtime honesty contracts")
        return 1
    print("PASS: runtime honesty contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
