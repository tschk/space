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
| Darwin (stub+) | `darwin.in` | serial + process ids |
| Windows (subset) | `windows.in` | VFS handles, serial, yield |

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

Handle table: max 16 slots; 1/2 reserved as stdout/stderr; 3..15 hold VFS fds.

**Honest limit:** not full Win32, not PE loader, not CSRSS, not real NT objects.
Shell command `windows` runs `win-demo`.
