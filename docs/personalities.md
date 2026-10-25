# Compatibility personalities

## Original Windows PE32 compiler continuation

The [cross-OS continuation](plans/2026-10-25-original-cross-os-execution.md)
adds a distinct hardware compatibility-mode CPU context and a separate PE32
profile over native owned address spaces. The original upstream Windows
`fasmg.exe` now executes its own instructions, prints help, reads source files
and produces exact macro/arithmetic output in Space. The first expanded run has
65 original activations including real compiler error exits and 21 ownership
cycles. Nineteen checked KERNEL32 imports, an explicit empty environment and a
bounded private heap/file profile are supported. The existing PE32+ profiles
remain separate. This is a private kernel-linked integration path; normal
installed-app launch, broader dependencies and Windows GUI apps remain open.

The original upstream macOS x86_64 `fasmg` also executes its own code and
produces the same exact source-derived output through a separate classic
UNIXTHREAD/indirect-symbol profile. The initial expanded run passes65 original
activations,42 actual compiler-error exits and21 lifetime cycles. A high
supervisor window allows its complete original low-address image. Thirteen
bounded libSystem imports translate into native file/clock/VM services after
CPU suspension. This does not execute Apple's dyld/libSystem or provide GUI
frameworks. Normal installed-app/desktop launch remains open.

The original Linux x86_64 assembler also runs unchanged with larger bounded
BSS support. Its65-entry suite includes exact generated macro bytes,42 actual
compiler errors,21 ownership cycles and an original `%t` output checked against
the actual native RTC. Linux `time(2)` requires the timer grant; image limits
are8192 total pages,6144 image pages and24 MiB per segment, with the existing
64-KiB minimum and reserved low supervisor addresses.

The later [original vi checkpoint](linux-vi-workload.md) adds finite protected
Linux syscall7 regular-file readiness and syscall77 inline-file resize. Its EX
edit/save/reopen profile executes original vi; focused interactive TUI support
remains open. Native providers own readiness, bytes and identity, with Linux
structures/errors at the edge. They remain private kernel-linked prototypes.

Space provides bounded foreign ABI fixtures and translator microservices.
The compatibility surface maps onto Space VFS, process, and serial primitives;
it does not provide a general Linux, macOS, or Windows process environment.

**Progress + milestones:** [`personalities-roadmap.md`](personalities-roadmap.md)
Verify: `bash scripts/check-personalities.sh`.

The separately imported [initial Linux framebuffer profile](plans/2026-10-24-linux-framebuffer-app.md)
now runs the original pinned fbv BMP viewer against an explicitly owned native
canvas:22 original activations,88 separately counted syscall/failure controls,
exact pixels and21 resource cycles. Ordinary CLI images import only the optional
private device contract; they acquire no display implementation or authority.
The profile admits one completed mapping per sole-process lease and publishes
on checked stopped unmap. Interactive input, remapping/aliases, X11 and FLTK
remain open. Neither private adapter is an isolated SCI service.

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
| Windows (NT-shaped subset) | `windows.in` | handle table → VFS/serial/process; bounded PE imports, no CSRSS |

Linux syscall79 `getcwd` returns bytes including NUL, with `-34` for insufficient capacity and `-14` for a null destination. The Darwin Space-local adapter retains its pointer/zero return convention.

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
11. `SetFilePointer` — `vfs-lseek(vfd, off, whence)` (0=SET); Space-local full `Int` position on success, `-1` with paired error/status on failure (not the Win32 low-DWORD/high-pointer ABI)
12. `GetStdHandle` — `-10`→0 stdin, `-11`→1 stdout, `-12`→2 stderr
13. `MoveFileA` — `fs-rename`; return 1/0
14. `FlushFileBuffers` — no-op success (1) for open handle
15. `CreateDirectoryA` — `fs-mkdir`; return 1/0
16. `RemoveDirectoryA` — `fs-rmdir`; return 1/0
17. `GetLastError` — `win-last-error` global (2=ENOENT-style, 6=invalid handle)
18. `SetLastError` — set `win-last-error` from `a0`
19. `VirtualAlloc` — `posix-sys-mmap`; preferred addr ignored
20. `VirtualFree` — `posix-sys-munmap` stand-in; return 1/0
21. `CreateProcessA` — `proc-spawn-sci` on path; typed table handle (type process) or 0
22. `WaitForSingleObject` — type process only → `proc-wait`
23. `GetCommandLineA` — static cstr `"space-windows"`
24. `WriteConsoleA` — alias `WriteFile` on handles 1/2
25. `GetModuleFileNameA` — copy `"space.exe"` into buf; return len
26. `HeapAlloc` — `alloc(size)` zeroed; heap handle/flags ignored
27. `HeapFree` — return 1 (bump heap: no real free)
28. `CopyFileA` — `fs-read-file` src + `fs-write-file` dst; return 1/0
29. `GetEnvironmentVariableA` — `PATH` → `"/"`, else empty; return len
30. `OutputDebugStringA` — `serial-write-cstr`

Typed handle table: max 16 slots, 16-byte records (`type` + `value`).
Types: `0=free`, `1=console`, `2=file`, `3=process`.
Slots 1/2 reserved console (value 1/2); 3..15 hold file `vfd` or process `pid`.
All handles (file + process) are table indices 1..15 — no `100+pid` fakes.

**Honest limit:** no full Win32, general DLL loading, CSRSS, or real NT objects.
The bounded PE fixture path is described below.
Shell command `windows` runs `win-demo`.

## Darwin / XNU layering (research takeaway)

Darwin kernel = **Mach** + **BSD**. Userland OS personality for files/process is
mostly **BSD syscalls** (`syscalls.master`), not raw Mach IPC. Mach is for ports,
tasks, and VM; BSD supplies process model, VFS, networking, POSIX-ish APIs.

Space Darwin personality follows that split:

- Implement a **BSD-shaped** call surface first (not full XNU).
- Keep **Mach** as explicit stubs (`task_self` → 1, `mach_msg` → -1) until a real
  port/message fabric exists. The raw `mach_msg` stub returns -1; the public
  dispatcher normalizes this unspecified backend error to EINVAL (-22).
- Darwin `wait4=7`, `recvfrom=29`, and `lseek=199` agree with ravynOS's
  [XNU syscall table](https://github.com/ravynsoft/ravynos/blob/darwin/Kernel/xnu/bsd/kern/syscalls.master).
- The `.in` dispatcher accepts bare BSD numbers and x86_64 Unix-class numbers
  (`0x2000000 | number`); other classes and tagged local shims return ENOSYS.
  This dispatcher is separate from the bounded hardware SYSCALL fixture path
  described below, which supplies Darwin carry/errno handling.
- Dispatch translates internal Linux-shaped errors to Darwin numbers in both
  the negative result and the errno slot (`ENOSYS=78`, not Linux's 38).
- `getcwd=192`, `getpagesize=276`, and the Mach/errno shims remain Space-local
  interfaces; they are not macOS binary ABI promises.

The separate high-address owned mapper also has a finite C-locale data profile:
`__DefaultRuneLocale` binds a private RO/NX guest object, and
`__CurrentRuneLocale` binds a read-only guest pointer to it. Cached classes/case
maps are pinned BSD-licensed Apple data, populated through the native owned VM
API. This is distinct from function capsules and the older image/heap symbol
policy. It does not provide locale mutation, multibyte conversion or a general
libSystem/dyld runtime. Original macOS jq remains refused before entry at the
next unavailable import,`____chkstk_darwin`. See the
[data ownership and executable evidence](plans/2026-10-25-darwin-data-imports.md).

BSD numbers used (Darwin where implemented; Space-local shims noted):

| # | call | maps to |
|---|------|---------|
| 1 | exit | status only (no kernel halt) |
| 2 | fork | `posix-sys-fork` (dispatch only; shell demo skips) |
| 3 / 4 | read / write | VFS + serial stdio |
| 5 / 6 | open / close | `vfs-open` / `vfs-close` |
| 7 | wait4 | `posix-sys-wait4` |
| 10 | unlink | `fs-delete` |
| 12 | chdir | `posix-sys-chdir` |
| 20 | getpid | `current-task` |
| 24 / 25 | getuid / geteuid | constant 0 |
| 29 | recvfrom | `sock-recvfrom` |
| 33 | access | `fs-stat` probe → 0 / ENOENT |
| 37 | kill | `proc-signal` |
| 41 | dup | clone vfs-fd-table entry |
| 42 | pipe | lite 4KB ring, max 4 pipes; vfs type=2 |
| 59 | execve | `posix-sys-execve` (dispatch only; shell demo skips) |
| 73 | munmap | `posix-sys-munmap` |
| 97 | socket | `sock-socket` (AF_INET; STREAM=1 DGRAM=2) |
| 98 | connect | `sock-connect` |
| 128 | rename | `fs-rename` |
| 133 | sendto | `sock-sendto` (a3=rip, port 0 demo) |
| 136 | mkdir | `fs-mkdir` |
| 137 | rmdir | `fs-rmdir` |
| 188 | stat | path `fs-stat` size into buf |
| 189 | fstat | VFS path + `fs-stat` size into buf |
| 192 | getcwd | `posix-sys-getcwd` (Space-doc'd; FreeBSD 326) |
| 197 | mmap | `posix-sys-mmap` (a0 addr a1 len a2 prot; anon) |
| 199 | lseek | `vfs-lseek` |
| 0x1000 | mach task_self | constant 1 |
| 0x1001 | mach_msg | raw stub -1; dispatch -22 / EINVAL |

Checks: `scripts/check-darwin-personality.sh`, `scripts/check-windows-personality.sh`.

Source review and acceptance checks: [ravynOS Darwin reference](ravynos-darwin-review.md).
For user-space frameworks and the staged GUI path, see the
[Rosemary macOS reference](rosemary-macos-reference.md).

## Trusted Mach-O fixture path

`darwinmacho` validates and invokes a boot-injected thin x86_64 Mach-O image at
`0x2f0000`. `components/darwin-macho.in` accepts only MH_EXECUTE/subtype 3,
MH_NOUNDEFS, exactly one RX LC_SEGMENT_64 with no sections, and one LC_MAIN.
The segment must already reside at its declared address, be entirely file-backed,
and contain the entry after the commands. Command bounds and all 64-bit ranges
are checked before invocation; unsupported commands, dyld, PIE, BSS and imports
are rejected. The caller must supply a readable image buffer.

This is a trusted fixture executed as a returning function at CPL0, using Space's
existing identity map. It does not implement macOS process startup, syscalls,
isolation, dynamic linking, or execution of arbitrary applications.

Run `bash scripts/check-darwin-macho.sh` to assemble the checked-in fixture,
exercise malformed-image rejection under QEMU, and verify its return value 42.
Ordinary boot images report a missing fixture without modifying that region.

The experimental `linuxsyscall` and `darwinsyscall` commands extend this trusted
fixture path with hardware SYSCALL instructions for bounded serial writes and
exit. Linux uses syscall numbers 1/60 and negative errors; Darwin uses Unix-class
numbers 0x2000004/0x2000001 and carry plus positive errno. Buffers must remain
inside the loaded image, writes are limited to 4096 bytes, and exit restores the
shell continuation. These run synchronously at CPL0 with interrupts disabled;
they provide neither process isolation nor general application compatibility.

`windowspe` validates a PE32+ console image with one fixed-address, file-backed
section, equal 512-byte file/section alignment, and named imports from
`KERNEL32.dll`: `WriteFile`, `ExitProcess`, optionally followed by `CreateFileA`,
`ReadFile`, `CloseHandle` in that order. Only after validation does it bind
the import address table to Microsoft x64 adapters. `WriteFile` accepts handles
1/2, bounded image buffers and a bytes-written pointer inside the image, with
null OVERLAPPED; it returns BOOL and the written byte count. `ExitProcess`
restores the same shell continuation. Binding is undone after exit. General
DLL loading, relocations, TLS, exceptions, LastError, process startup and memory
protection are unsupported. This is a trusted in-place fixture, not a Windows
process environment.

`linuxfileio`, `darwinfileio`, and `windowsfileio` run read-only file fixtures.
They seed `foreign-read.txt` on RAM SparkFS and exercise actual Linux
open/read/close syscalls 2/0/3, Darwin Unix-class calls 0x2000005/0x2000003/0x2000006,
or the three Windows file imports. Unix opens accept flags 0 only. `CreateFileA`
accepts GENERIC_READ, FILE_SHARE_READ, null security attributes, OPEN_EXISTING,
FILE_ATTRIBUTE_NORMAL, and null template only. Other arguments fail without
backend access. `ReadFile` requires an image-owned byte-count pointer and null
OVERLAPPED, returns BOOL plus bytes read, and succeeds with zero bytes at EOF.

Paths must terminate within the image and 256 bytes; transfers stay inside the
image and at most 4096 bytes. A caller-supplied storage capability is required.
Each execution owns only descriptors it opened; read/close cannot use another
execution's or the kernel's handles. All owned descriptors are closed on return
or exit. The fixtures keep kernel fd 3 open, probe its protection, exhaust the
remaining 12 slots, then exit without closing them. Tests first run without a
storage grant, then with one, and repeat to verify cleanup and import restoration.
Linux and Darwin return variants check the same cleanup when the entry returns normally.
Asynchronous volume RPC and direct NVMe SparkFS are rejected by this runner,
which disables interrupts. Fixture commands require a fresh descriptor table.
Existing VFS path copies use the bump allocator; descriptor cleanup does not
reclaim those allocations.

Linux `lseek=8` and Darwin Unix-class `lseek=199` now seek only execution-owned
regular-file descriptors with a storage grant. SET/CUR/END use VFS offsets;
invalid whence, negative targets and host/closed descriptors are refused. The
file fixtures check tail reads, read advancement and rewind on both ABIs.
Windows fixtures additionally check a boundary-crossing output-count pointer
refuses without consuming data, and zero-byte read success preserves position.

File writes, process isolation and general Windows
path/sharing semantics remain unsupported.

Run `bash scripts/check-foreign-syscalls.sh` (also included in personality gates).
It checks 13 malformed/valid ELF scenarios, 15 PE scenarios, error conventions,
exact output, exit status 42, and shell resumption for serial and file fixtures
on all three ABIs, plus eight malformed/valid PE file-import cases. The
separate Mach-O gate covers 22 validation scenarios. Use `INAUGURATION_DIR` to
select a different compiler checkout. Investigation also found and fixed a
generic reassigned-binding constant-propagation bug in the sibling compiler;
the fixture dispatcher compares ABI numbers directly without mutable aliases.

### Personality mapping lifetime

The trusted POSIX compatibility allocator tracks at most 64 live mapping intervals.
Mappings are page-aligned private eager snapshots; address hints are ignored.
Flags 0 (legacy private), 2 (private), and 34 (private anonymous) are accepted;
shared/fixed and other flags are rejected. Protection 0 is the existing Windows
compatibility request and 3 requests read/write; other protections are rejected.
These are allocator records, not page-table protection or per-process isolation.
File snapshots require a valid descriptor and a nonnegative page-aligned offset.
Anonymous requests use descriptor -1 and offset 0.

Unmap requires a positive page-aligned address and positive length (rounded up),
and the entire range must still belong to live mapping records. Partial unmap
splits records when capacity permits; invalid, duplicate, overflowing, or exhausted
requests fail before heap, record, or frame-list changes. Released pages can be
reused by the frame allocator; the bump heap does not shrink. Windows stand-ins
translate allocation/unmap failures to zero and LastError rather than reporting
success. This does not implement Windows MEM_RELEASE or full POSIX VM semantics.
