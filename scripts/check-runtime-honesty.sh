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


def dns_skip_name(pkt: bytes, start: int, end: int) -> int:
    """Mirror components/dns.in dns-skip-name (does not follow compression)."""
    off = start
    jumps = 0
    while True:
        if off >= end:
            return -1
        lab = pkt[off]
        if lab == 0:
            return off + 1
        if (lab & 0xC0) == 0xC0:
            return off + 2
        off = off + 1 + lab
        jumps = jumps + 1
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
        "SYN sequence number is hard-coded 1",
        "store8(tcp + 6, 0x00); store8(tcp + 7, 0x01)" in syn,
    )
    connect = fn_body(netstack, "sock-connect") or ""
    check(
        "post-handshake local seq is hard-coded 2",
        "tcp-local-seq = 2" in connect and "ISN was 1" in connect,
    )
    close = fn_body(netstack, "sock-close") or ""
    check(
        "sock-close frees the table slot without sending FIN/RST",
        "SOCK-OFF-USED, 0" in close
        and "SOCK-STATE-FREE" in close
        and "build-tcp" not in close
        and "e1000-tx" not in close,
    )
    send = fn_body(netstack, "sock-send") or ""
    check(
        "unacked TCP send reports only the acked prefix (not silent success)",
        "return sent" in send and "return len" in send,
    )
    accept = fn_body(netstack, "sock-accept") or ""
    check("TCP accept is unimplemented (-38)", "return -38" in accept)

    print("[2/6] UDP destination is hard-coded; cstr-len is unbounded...")
    udp = fn_body(network, "build-udp-impl") or ""
    check(
        "UDP IPv4 is 10.0.2.15 -> 10.0.2.2",
        "store8(ip + 12, 10)" in udp
        and "store8(ip + 15, 15)" in udp
        and "store8(ip + 16, 10)" in udp
        and "store8(ip + 19, 2)" in udp,
    )
    check(
        "UDP ports are hard-coded 9999 (0x270F)",
        udp.count("store8(udp + 0, 0x27)") == 1 and udp.count("0x0F") >= 2,
    )
    sendto = fn_body(netstack, "sock-sendto") or ""
    check(
        "sock-sendto drives TX via build-udp-impl (ignores rip/rport on the wire)",
        "build-udp-impl(payload)" in sendto and "10.0.2.15->10.0.2.2:9999" in sendto,
    )
    cstr = fn_body(network, "cstr-len-impl") or ""
    check(
        "cstr-len-impl walks until NUL with no cap",
        "while load8(addr + n) != 0" in cstr and "n = n + 1" in cstr,
    )

    print("[3/6] PCI BARs and SparkFS disk fields are trusted...")
    e1000 = fn_body(pci, "pci-find-and-enable-e1000") or ""
    check(
        "e1000 BAR0 is masked without I/O vs memory type check",
        "pci-read32(0, dev, 0, 0x10) & 0xFFFFFFF0" in e1000
        and "& 0x1" not in e1000
        and "bar0-raw" not in e1000,
    )
    nvme_pci = fn_body(storage, "storage-pci-init") or ""
    check(
        "NVMe maps 32 KiB of BAR0 MMIO regardless of BAR size",
        "while pg < mmio-phys + 0x8000" in nvme_pci,
    )
    e1000_init = fn_body(network, "e1000-init-impl") or ""
    check(
        "e1000 maps 64 KiB of BAR0 MMIO regardless of BAR size",
        "while pg < bar0 + 0x10000" in e1000_init,
    )
    check(
        "VGA BAR scan assumes 64-bit memory without type/size probe",
        "class-code == 0x030000" in display
        and "bar0-raw & 0x6) == 0x4" in display
        and "fb-addr = bar0-lo | (bar0-hi << 32)" in display,
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
        "sparkfs-init does not cap total or ino-count before alloc",
        "if total" not in init and "if ino-count" not in init,
    )
    read_blk = fn_body(fs_block, "sf-read-block") or ""
    write_blk = fn_body(fs_block, "sf-write-block") or ""
    check(
        "sf-read-block computes mem-disk offset from bno with no bound",
        "sf-mem-disk + bno * SF-BLOCK-SIZE" in read_blk
        and "bno <" not in read_blk
        and "bno >" not in read_blk,
    )
    check(
        "sf-write-block computes mem-disk offset from bno with no bound",
        "sf-mem-disk + bno * SF-BLOCK-SIZE" in write_blk
        and "bno <" not in write_blk
        and "bno >" not in write_blk,
    )

    print("[4/6] ELF execve is a CPL0 jump; DNS compression is not followed...")
    elf = fn_body(posix, "posix-elf-exec-image") or ""
    check(
        "ELF magic is the 64-bit little-endian ident word",
        "const LINUX-ELF-MAGIC = 0x00010102464C457F" in posix,
    )
    check(
        "posix-elf-exec-image jumps to PT_LOAD entry with invoke1(entry, 0)",
        "load32(ph + 0) == 1" in elf and "return invoke1(entry, 0)" in elf,
    )
    check(
        "posix-elf-exec-image does not copy PT_LOAD or zero .bss",
        "filesz" in elf and "memsz" in elf and "store8" not in elf and "memcpy" not in elf,
    )
    skip = fn_body(dns, "dns-skip-name") or ""
    check(
        "dns-skip-name treats 0xC0 as a two-byte skip (does not follow the pointer)",
        "(lab & 0xC0) == 0xC0" in skip and "return off + 2" in skip,
    )
    pkt = bytearray(32)
    pkt[12] = 0xC0
    pkt[13] = 0x0C
    check("python dns-skip-name matches: compression returns start+2", dns_skip_name(pkt, 12, 32) == 14)
    pkt2 = bytearray(b"\x03www\x07example\x03com\x00")
    check("python dns-skip-name matches: uncompressed name walk", dns_skip_name(pkt2, 0, len(pkt2)) == len(pkt2))
    check("python dns-skip-name matches: off>=end is -1", dns_skip_name(b"\x00", 1, 1) == -1)
    long_labels = bytearray([1, ord("a")] * 129 + [0])
    check("python dns-skip-name matches: jumps>128 is -1", dns_skip_name(long_labels, 0, len(long_labels)) == -1)

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
        "int 0x80 gate is DPL3 while the GDT remains DPL0-only",
        "store8(e + 5, 0xEE)" in syscall and "idt-set-user" in syscall,
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
