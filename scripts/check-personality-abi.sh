#!/usr/bin/env bash
"exec" "python3" "$0" "$@"
# Host-side Linux/Darwin/Windows personality ABI contracts. No QEMU / compiler.
"""Lock personality syscall numbers, errno, and NTSTATUS mappings."""
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


def const_int(text: str, name: str) -> int | None:
    m = re.search(rf"const {re.escape(name)} = (-?0x[0-9A-Fa-f]+|-?\d+)", text)
    if not m:
        return None
    return int(m.group(1), 0)


def expect_consts(text: str, pairs: list[tuple[str, int]]) -> None:
    for name, val in pairs:
        got = const_int(text, name)
        check(f"{name} == {val}", got == val)


def main() -> int:
    posix = src("components/posix.in")
    darwin = src("components/darwin.in")
    windows = src("components/windows.in")
    linux = src("components/linux.in")
    vfs = src("components/vfs.in")

    print("[1/4] Linux x86_64 syscall numbers / errno...")
    expect_consts(posix, [
        ("LINUX-SYS-READ", 0),
        ("LINUX-SYS-WRITE", 1),
        ("LINUX-SYS-OPEN", 2),
        ("LINUX-SYS-CLOSE", 3),
        ("LINUX-SYS-STAT", 4),
        ("LINUX-SYS-FSTAT", 5),
        ("LINUX-SYS-LSEEK", 8),
        ("LINUX-SYS-MMAP", 9),
        ("LINUX-SYS-MUNMAP", 11),
        ("LINUX-SYS-BRK", 12),
        ("LINUX-SYS-SOCKET", 41),
        ("LINUX-SYS-CONNECT", 42),
        ("LINUX-SYS-ACCEPT", 43),
        ("LINUX-SYS-BIND", 49),
        ("LINUX-SYS-LISTEN", 50),
        ("LINUX-SYS-FORK", 57),
        ("LINUX-SYS-EXECVE", 59),
        ("LINUX-SYS-EXIT", 60),
        ("LINUX-SYS-WAIT4", 61),
        ("LINUX-SYS-KILL", 62),
        ("LINUX-SYS-GETCWD", 79),
        ("LINUX-SYS-CHDIR", 80),
        ("LINUX-ENOENT", -2),
        ("LINUX-ENOEXEC", -8),
        ("LINUX-EBADF", -9),
        ("LINUX-ECHILD", -10),
        ("LINUX-ENOMEM", -12),
        ("LINUX-ENOSPC", -28),
        ("LINUX-ESPIPE", -29),
        ("LINUX-ENOSYS", -38),
        ("LINUX-O-CREAT", 64),
        ("LINUX-ELF-LOAD-ADDR", 0x280000),
    ])
    check("linux personality probes the ELF load address", "LINUX-ELF-LOAD-ADDR" in linux)
    check(
        "VFS ENOENT/EMFILE/EBADF match Linux errno magnitudes",
        "return -2" in vfs and "return -16" in vfs and "return -9" in vfs,
    )

    print("[2/4] Darwin BSD syscall numbers / flags...")
    expect_consts(darwin, [
        ("DARWIN-SYS-EXIT", 1),
        ("DARWIN-SYS-FORK", 2),
        ("DARWIN-SYS-READ", 3),
        ("DARWIN-SYS-WRITE", 4),
        ("DARWIN-SYS-OPEN", 5),
        ("DARWIN-SYS-CLOSE", 6),
        ("DARWIN-SYS-WAIT4", 7),
        ("DARWIN-SYS-GETPID", 20),
        ("DARWIN-SYS-KILL", 37),
        ("DARWIN-SYS-PIPE", 42),
        ("DARWIN-SYS-EXECVE", 59),
        ("DARWIN-SYS-SOCKET", 97),
        ("DARWIN-SYS-CONNECT", 98),
        ("DARWIN-SYS-MMAP", 197),
        ("DARWIN-SYS-LSEEK", 199),
        ("DARWIN-O-CREAT", 0x200),
        ("DARWIN-O-TRUNC", 0x400),
        ("DARWIN-SOCK-STREAM", 1),
        ("DARWIN-SOCK-DGRAM", 2),
        ("DARWIN-MACH-TASK-SELF", 0x1000),
        ("DARWIN-SYS-ERRNO", 0x2000),
        ("DARWIN-ENOENT", -2),
        ("DARWIN-ENOSYS", -38),
    ])
    check("Darwin O_CREAT is 0x200, not Linux 64", const_int(darwin, "DARWIN-O-CREAT") != const_int(posix, "LINUX-O-CREAT"))

    print("[3/4] Windows call table / NTSTATUS...")
    expect_consts(windows, [
        ("WIN-CALL-WRITEFILE", 1),
        ("WIN-CALL-EXITPROCESS", 3),
        ("WIN-CALL-CREATEFILEA", 4),
        ("WIN-CALL-READFILE", 5),
        ("WIN-CALL-GETLASTERROR", 17),
        ("WIN-CALL-CREATEPROCESSA", 21),
        ("WIN-CALL-RTLGETLASTNTSTATUS", 34),
        ("WIN-CALL-RTLNTSTATUSTODOSERROR", 35),
        ("WIN-MAX-HANDLES", 16),
        ("WIN-ERROR-FILE-NOT-FOUND", 2),
        ("WIN-ERROR-INVALID-HANDLE", 6),
        ("WIN-STATUS-SUCCESS", 0),
        ("WIN-STATUS-UNSUCCESSFUL", -1073741823),
        ("WIN-STATUS-NOT-IMPLEMENTED", -1073741822),
        ("WIN-STATUS-INVALID-HANDLE", -1073741816),
        ("WIN-STATUS-OBJECT-NAME-NOT-FOUND", -1073741772),
        ("WIN-STATUS-END-OF-FILE", -1073741805),
    ])
    check(
        "NTSTATUS OBJECT_NAME_NOT_FOUND is 0xC0000034",
        (const_int(windows, "WIN-STATUS-OBJECT-NAME-NOT-FOUND") & 0xFFFFFFFF) == 0xC0000034,
    )
    check(
        "NTSTATUS SUCCESS/UNSUCCESSFUL match unsigned 0 / 0xC0000001",
        const_int(windows, "WIN-STATUS-SUCCESS") == 0
        and (const_int(windows, "WIN-STATUS-UNSUCCESSFUL") & 0xFFFFFFFF) == 0xC0000001,
    )

    print("[4/4] Personality translators are kernel-linked microservices...")
    kernel = src("kernel/kernel-root.in")
    check("kernel-root imports linux.in", 'import "../components/linux.in"' in kernel)
    check("kernel-root imports darwin.in", 'import "../components/darwin.in"' in kernel)
    check("kernel-root imports windows.in", 'import "../components/windows.in"' in kernel)
    check("posix.in is pulled in via linux.in, not kernel-root", 'import "../components/posix.in"' not in kernel)
    check("linux.in imports posix.in", 'import "posix.in"' in linux or 'import "../components/posix.in"' in linux)

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    if failed:
        print("FAIL: personality ABI contracts")
        return 1
    print("PASS: personality ABI contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
