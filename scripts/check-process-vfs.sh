#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
# Host-side process / VFS / shell / DHCP / libc contracts. No QEMU / compiler.
"""Assert process table, VFS fds, DHCP xid, and libc bounds still hold."""
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


def src(rel: str) -> str:
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


def const_int(text: str, name: str) -> int | None:
    m = re.search(rf"const {re.escape(name)} = (0x[0-9A-Fa-f]+|\d+)", text)
    if not m:
        return None
    return int(m.group(1), 0)


def dhcp_find_opt(bootp: bytes, end: int, code: int) -> int:
    """Mirror components/dhcp.in dhcp-find-opt over a byte buffer."""
    i = 240
    while i + 1 < end:
        t = bootp[i]
        if t == 255:
            return 0
        if t == 0:
            i = i + 1
        else:
            l = bootp[i + 1]
            if i + 2 + l > end:
                return 0
            if t == code:
                return i + 2
            i = i + 2 + l
    return 0


def main() -> int:
    process = src("components/process.in")
    vfs = src("components/vfs.in")
    shell = src("components/shell.in")
    dhcp = src("components/dhcp.in")
    libc = src("components/libc.in")
    syscall = src("components/syscall.in")
    posix = src("components/posix.in")

    print("[1/5] Process table / signals...")
    check("PROC-SIZE is 72", const_int(process, "PROC-SIZE") == 72)
    check("SIGKILL is 9", const_int(process, "SIGKILL") == 9)
    check("SIGTERM is 15", const_int(process, "SIGTERM") == 15)
    init = fn_body(process, "proc-init") or ""
    check("proc-init clamps max to [1, 256]", "if n < 1 { n = 16 }" in init and "if n > 256 { n = 256 }" in init)
    create = fn_body(process, "proc-create") or ""
    check(
        "proc-create returns -1 when the table is full",
        "if proc-count >= proc-max { return -1 }" in create,
    )
    check(
        "proc-create treats domain 0 as failure",
        "if domain <= 0 { return -1 }" in create,
    )
    kill = fn_body(process, "proc-kill") or ""
    check(
        "proc-kill writes 128+SIGKILL and does not halt the OS",
        "128 + SIGKILL" in kill and "cli()" not in kill and "hlt()" not in kill,
    )
    sig = fn_body(process, "proc-signal") or ""
    check(
        "proc-signal only accepts SIGKILL and SIGTERM",
        "if sig != SIGKILL && sig != SIGTERM" in sig and "return -1" in sig,
    )
    wait = fn_body(process, "proc-wait") or ""
    check(
        "proc-wait rejects pid < 0 and pid >= proc-count",
        "if pid < 0 || pid >= proc-count { return -1 }" in wait,
    )
    check("ps command lists processes", "fn proc-list" in process and 'line-eq("ps")' in shell)

    print("[2/5] VFS descriptor table...")
    check("VFS-MAX-FDS is 16", const_int(vfs, "VFS-MAX-FDS") == 16)
    check("stdin is O_RDONLY, stdout/stderr O_WRONLY", const_int(vfs, "VFS-O-RDONLY") == 0 and const_int(vfs, "VFS-O-WRONLY") == 1)
    alloc = fn_body(vfs, "vfs-fd-alloc") or ""
    check("vfs-fd-alloc starts at fd 3", "let i = 3" in alloc and "return -1" in alloc)
    valid = fn_body(vfs, "vfs-fd-valid") or ""
    check("fds 0..2 are always valid", "if fd < 3 {\n    return 1" in valid)
    close = fn_body(vfs, "vfs-close") or ""
    check("closing stdin/stdout/stderr is a no-op success", "if fd < 3 {\n    return 0" in close)
    read_fn = fn_body(vfs, "vfs-read") or ""
    check("vfs-read(0) is serial stdin", "if fd == 0" in read_fn and "serial-read(port)" in read_fn)
    write_fn = fn_body(vfs, "vfs-write") or ""
    check("vfs-write(1/2) is serial stdout", "if fd == 1 || fd == 2" in write_fn and "serial-put(port" in write_fn)
    check("ENOENT is -2, EMFILE is -16, EBADF is -9", "return -2" in vfs and "return -16" in vfs and "return -9" in vfs)

    print("[3/5] Shell help / history / halt...")
    help_line = next((ln for ln in shell.splitlines() if "halt up/down=hist" in ln), "")
    check(
        "help lists core commands (hardening is a separate command, not on the help line)",
        'line-eq("help")' in shell
        and "halt" in help_line
        and " ps " in help_line
        and " mem " in help_line
        and "hardening" not in help_line,
    )
    check('hardening command is registered', 'line-eq("hardening")' in shell)
    check("read-line history slot is bounded at 254", "len < 254" in shell)
    check("halt command exists", 'line-eq("halt")' in shell)

    print("[4/5] DHCP xid and option walker...")
    bootp = fn_body(dhcp, "dhcp-frame-bootp") or ""
    check(
        "DHCP xid is hard-coded 0x12345678",
        "load8(bootp + 4) != 0x12" in bootp
        and "load8(bootp + 5) != 0x34" in bootp
        and "load8(bootp + 6) != 0x56" in bootp
        and "load8(bootp + 7) != 0x78" in bootp,
    )
    check("DHCP server fallback is 10.0.2.2", "return 0x0A000202" in dhcp)
    find = fn_body(dhcp, "dhcp-find-opt") or ""
    check("dhcp-find-opt is bounded against packet end", "if i + 2 + l > end" in find)
    pkt = bytearray(256)
    pkt[240] = 53
    pkt[241] = 1
    pkt[242] = 2
    pkt[243] = 255
    check("python dhcp-find-opt finds type 53 at offset 242", dhcp_find_opt(pkt, 256, 53) == 242)
    check("python dhcp-find-opt returns 0 on truncated option", dhcp_find_opt(bytes([0] * 242), 242, 53) == 0)
    overrun = bytearray(244)
    overrun[240] = 53
    overrun[241] = 10
    check("python dhcp-find-opt rejects option that walks past end", dhcp_find_opt(overrun, 244, 53) == 0)

    print("[5/5] libc bounds / syscall numbers / posix wait...")
    strlcpy = fn_body(libc, "strlcpy") or ""
    check("strlcpy NUL-terminates within dsize", "while i < dsize - 1" in strlcpy and "store8(dst + i, 0)" in strlcpy)
    malloc = fn_body(libc, "malloc") or ""
    check("malloc rejects negative / overflowing sizes", "if n < 0 || n > 0x7FFFFFFFFFFFFFF0" in malloc)
    calloc = fn_body(libc, "calloc") or ""
    check("calloc detects n*size overflow", "if total / n != size" in calloc)
    free = fn_body(libc, "free") or ""
    check("free is a bump-allocator no-op", "fn free" in libc and "return" in free and "store" not in free)
    check(
        "syscall numbers: write=0 read=1 exit=2 chan-create=5 cap-mint=9 cap-check=11",
        "if num == 0" in syscall
        and "else if num == 1" in syscall
        and "else if num == 2" in syscall
        and "else if num == 5" in syscall
        and "else if num == 9" in syscall
        and "else if num == 11" in syscall,
    )
    wait4 = fn_body(posix, "posix-sys-wait4") or ""
    check(
        "posix wait4 rejects pid < 0 like proc-wait",
        "if pid < 0 || pid >= proc-count" in wait4,
    )

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: process/VFS contracts")
        return 1
    print("PASS: process/VFS contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
