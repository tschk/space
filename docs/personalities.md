# Compatibility personalities

Space nanokernel does not implement foreign kernel ABIs. Personalities are
translator microservices: a small foreign-shaped call surface maps onto Space
VFS, process, and serial primitives.

## ReactOS / NT layering (research takeaway)

On real Windows / ReactOS:

- Win32 is **not** the kernel ABI.
- User-mode Native API lives in `ntdll` (`Nt*` / `Zw*`) and enters `ntoskrnl`.
- Win32 subsystem pieces (`CSRSS`, `kernel32`, …) sit **above** the Native API.

So a honest Space Windows personality is **not** “implement Win32 in the
kernel.” It is a thin translator, same idea as `linux.in` → `posix.in`.

## What Space implements

| Personality | Entry | Maps onto |
|-------------|-------|-----------|
| Linux / POSIX | `linux.in` / `posix.in` | VFS, process, serial |
| Darwin (BSD subset) | `darwin.in` | BSD nums → VFS/process; Mach stubs only |
| Windows (NT-shaped subset) | `windows.in` | handle table → VFS/serial/process; not PE/CSRSS |

Windows call numbers are **Space-local**, not real NT syscall numbers:

1. `WriteFile` / NtWriteFile — stdout/stderr → serial; files → VFS
2. `GetCurrentProcessId` → `current-task`
3. `ExitProcess` — demo status only (no halt)
4. `CreateFileA` — `vfs-open` (access 0=read, 1=write/create)
5. `ReadFile` — `vfs-read`
6. `CloseHandle` — free handle + `vfs-close`
7. `GetFileSize` — VFS/stat path size
8. `Sleep` — small pause loop (shell path cannot `thr-yield`)
9. `GetCurrentThreadId` → `current-task`
10. `DeleteFileA` — `fs-delete` / volume RPC
11. `SetFilePointer` — `vfs-lseek(vfd, off, whence)` (0=SET)
12. `GetStdHandle` — `-10`→0 stdin, `-11`→1 stdout, `-12`→2 stderr
13. `MoveFileA` — `fs-rename`; return 1/0
14. `FlushFileBuffers` — no-op success (1) for open handle
15. `CreateDirectoryA` — `fs-mkdir`; return 1/0
16. `RemoveDirectoryA` — `fs-rmdir`; return 1/0
17. `GetLastError` — `win-last-error` global (2=ENOENT-style, 6=invalid handle)
18. `SetLastError` — set `win-last-error` from `a0`
19. `VirtualAlloc` — `posix-sys-mmap` / `alloc(size)`; preferred addr ignored
20. `VirtualFree` — `posix-sys-munmap` stand-in; return 1/0
21. `CreateProcessA` — `proc-spawn-sci` on path; handle = `100+pid` or 0
22. `WaitForSingleObject` — process-like handles only → `proc-wait`
23. `GetCommandLineA` — static cstr `"space-windows"`
24. `WriteConsoleA` — alias `WriteFile` on handles 1/2

Handle table: max 16 slots; 1/2 reserved as stdout/stderr; 3..15 hold VFS fds.
Process handles are fake (`100+pid`), not full typed object table.

**Honest limit:** not full Win32, not PE loader, not CSRSS, not real NT objects.
Shell command `windows` runs `win-demo`.

## Darwin / XNU layering (research takeaway)

Darwin kernel = **Mach** + **BSD**. Userland OS personality for files/process is
mostly **BSD syscalls** (`syscalls.master`), not raw Mach IPC. Mach is for ports,
tasks, and VM; BSD supplies process model, VFS, networking, POSIX-ish APIs.

Space Darwin personality follows that split:

- Implement a **BSD-shaped** call surface first (not full XNU).
- Keep **Mach** as explicit stubs (`task_self` → 1, `mach_msg` → -1) until a real
  port/message fabric exists.
- Where Darwin and FreeBSD numbers conflict on Space (Darwin `wait4` vs `lseek`
  both claim 199 in some tables), Space uses FreeBSD-leaning picks: `wait4=7`,
  `lseek=199`.

BSD numbers used (classic / FreeBSD-leaning, documented in `darwin.in`):

| # | call | maps to |
|---|------|---------|
| 1 | exit | status only (no kernel halt) |
| 2 | fork | `posix-sys-fork` (dispatch only; shell demo skips) |
| 3 / 4 | read / write | VFS + serial stdio |
| 5 / 6 | open / close | `vfs-open` / `vfs-close` |
| 7 | wait4 | `posix-sys-wait4` (FreeBSD; Darwin 199 = lseek here) |
| 10 | unlink | `fs-delete` |
| 12 | chdir | `posix-sys-chdir` |
| 20 | getpid | `current-task` |
| 24 / 25 | getuid / geteuid | constant 0 |
| 33 | access | `fs-stat` probe → 0 / ENOENT |
| 37 | kill | `proc-signal` |
| 41 | dup | clone vfs-fd-table entry |
| 42 | pipe | ENOSYS (no pipe fabric yet) |
| 59 | execve | `posix-sys-execve` (dispatch only; shell demo skips) |
| 128 | rename | `fs-rename` |
| 136 | mkdir | `fs-mkdir` |
| 137 | rmdir | `fs-rmdir` |
| 189 | fstat | VFS path + `fs-stat` size into buf |
| 192 | getcwd | `posix-sys-getcwd` (Space-doc'd; FreeBSD 326) |
| 199 | lseek | `vfs-lseek` |
| 0x1000 | mach task_self | constant 1 |
| 0x1001 | mach_msg | -1 |

Checks: `scripts/check-darwin-personality.sh`, `scripts/check-windows-personality.sh`.
