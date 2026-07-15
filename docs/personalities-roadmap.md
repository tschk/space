# OS Personalities Roadmap

Branch: `feat/personalities` (forked from `main` after translator depth 1–30 Windows + Darwin BSD surface).

Space does **not** put POSIX / Win32 / XNU in the nanokernel. Personalities are
`.in` **translator microservices**: foreign-shaped call numbers map onto Space
VFS, process, serial, net, and caps. Same idea as ReactOS (`ntdll` → `ntoskrnl`)
and Darwin (BSD layer over Mach) — see [`personalities.md`](personalities.md).

## Status snapshot (2026-07-15)

| Personality | Files | Approx LOC | Call surface | QEMU check |
|-------------|-------|------------|--------------|------------|
| Linux / POSIX | `linux.in` + `posix.in` | ~760 | Linux x86_64-ish syscalls (file, process, mmap, sockets, signals) | `linux` shell demo; execve SCI; volume path |
| Windows (NT-shaped) | `windows.in` | ~886 | Space-local **1–30** Win32/NT-shaped APIs | `scripts/check-windows-personality.sh` |
| Darwin (BSD-shaped) | `darwin.in` | ~908 | FreeBSD/xnu-leaning BSD nums + 2 Mach stubs | `scripts/check-darwin-personality.sh` |

**Honest ceiling:** not PE loader, not CSRSS, not full `syscalls.master`, not Mach IPC.

---

## Research anchors

### Windows / ReactOS
- Win32 is **not** the kernel ABI.
- Path: `kernel32` / CSRSS → **`ntdll` `Nt*`/`Zw*`** → **`ntoskrnl`**.
- Space Windows personality = thin **Native/Win32-shaped** translator onto Space
  objects (handles → VFS fds / fake process handles), **not** reimplementing
  ReactOS executive managers in full.

### Darwin / XNU
- Kernel = **Mach** + **BSD**.
- Files / process / POSIX-ish APIs = **BSD syscalls**.
- Mach = ports, tasks, VM messages.
- Space: BSD surface first; Mach only stubs until a real port fabric exists.

---

## What we have done

### Linux (most complete)
- [x] Personality service via domain + shared-page RPC (`linux.in` → `posix.in`)
- [x] File: open/read/write/close/stat/fstat/lseek
- [x] Process: fork/execve/wait/exit/getpid/kill (+ SIGTERM/SIGKILL)
- [x] Memory: mmap/munmap/brk
- [x] cwd/chdir
- [x] Sockets: UDP + TCP connect/send/recv path through netstack
- [x] `exec` shell + `check-execve-sci` (SCI from sparkfs)
- [x] Volume-ready FS path for file ops

### Windows translator (Space-local call IDs 1–30)
| Range | Coverage |
|-------|----------|
| 1–10 | WriteFile, GetCurrentProcessId, ExitProcess, CreateFileA, ReadFile, CloseHandle, GetFileSize, Sleep, GetCurrentThreadId, DeleteFileA |
| 11–14 | SetFilePointer, GetStdHandle, MoveFileA, FlushFileBuffers |
| 15–24 | Create/RemoveDirectoryA, Get/SetLastError, VirtualAlloc/Free, CreateProcessA, WaitForSingleObject, GetCommandLineA, WriteConsoleA |
| 25–30 | GetModuleFileNameA, HeapAlloc/Free, CopyFileA, GetEnvironmentVariableA, OutputDebugStringA |

Typed handle table: 16-byte records; 1/2 console; 3–15 file/process; types free/console/file/process.

### Darwin translator (BSD-shaped)
| Area | Calls (examples) |
|------|------------------|
| File IO | open/read/write/close/unlink/lseek/stat/fstat/access/dup |
| Dir / cwd | mkdir/rmdir/chdir/getcwd/rename |
| Process | getpid/getuid/geteuid/kill/exit; fork/wait4/execve **wired** (demo careful) |
| Memory | mmap/munmap |
| Net | socket/connect/sendto/recvfrom |
| IPC | pipe-lite (4KB ring, max 4) |
| Mach stubs | task_self → 1; mach_msg → -1 |

### Shared infrastructure used by personalities
- VFS + SparkFS / Volume RPC
- Process table + SCI load / `proc-spawn-sci`
- Netstack (UDP/TCP)
- Caps + shell demos (`linux` / `windows` / `darwin`)

### Automation
- `scripts/check-windows-personality.sh` — QEMU boot, `windows`, greps CreateFile/Heap/Copy path
- `scripts/check-darwin-personality.sh` — QEMU boot, `darwin`, greps file + pipe|mmap|socket|stat
- `scripts/check-personalities.sh` — runs both + `check-sci-contract` (this branch)

---

## Milestone ladder (“done enough” vs “full”)

True **full** Win32 or XNU is multi-year (ReactOS / XNU scale). Space defines
milestones that are **finishable** without lying.

### M0 — Demo stubs (done earlier)
Shell prints hello via WriteFile / write. No real FS.

### M1 — FS translator (done)
CreateFile/open + read/write/close + delete; QEMU demo complete.

### M2 — Dir / seek / process ids (done)
Seek, rename, mkdir/chdir/getcwd, GetFileSize/fstat, pids/tids.

### M3 — Process / memory / console (done / partial)
- Windows: CreateProcessA → SCI spawn, WaitForSingleObject, VirtualAlloc/Free, console/heap/env
- Darwin: fork/execve/wait4 **dispatch**, mmap, sockets, pipe-lite
- Still missing: safe fork+wait demo without halt; PE/Mach-O loaders

### M4 — Service-thread parity with Linux (partial)
- [partial] Windows typed handle table (file/console/process; 16-byte records) — done on `feat/personalities`
- Windows/Darwin optional domain + shared-page RPC like `posix-service` (next)
- Event/sync object types still missing
- LastError / errno consistency end-to-end (next)

### M5 — Binary loaders (far)
- Windows: PE/COFF load into domain + ntdll-shaped entry (not full kernel32)
- Darwin: Mach-O load + dyld stub
- ReactOS-inspired: separate “Native” vs “subsystem” layers in docs + code layout

### M6 — Subsystem fidelity (multi-year)
- Windows: CSRSS-like console/window server; real NT objects; sync primitives
- Darwin: Mach ports/MIG; launchd-shaped job model; full BSD socket options
- Conformance tests against ReactOS apitests / XNU syscall suites (subset)

---

## Gap matrix (next work)

| Gap | Why it matters | Depends on |
|-----|----------------|------------|
| Typed object/handle table | Wait/DuplicateHandle realism | **Windows file/console/process done**; event/sync still open |
| Windows PE load | “Run .exe” | SCI/domain loader + reloc |
| Darwin Mach-O load | “Run Mach-O” | same |
| Real pipe / socketpair | Shell pipelines under Darwin | channel fabric |
| Safe fork+wait demo | Process model proof | non-halting child exit |
| Personality RPC threads | Isolation like posix | domain + preempt policy |
| NTSTATUS / errno maps | Debuggable failures | tables only |
| Conformance harness | Measure “fuller” | QEMU + golden logs |

---

## Branch policy

| Branch | Role |
|--------|------|
| `main` | Integration; keep green product checks |
| `feat/personalities` | Windows/Darwin translator expansion + this roadmap |
| `windows-personality` (worktree) | Older/parallel experiment; do not confuse with `feat/personalities` |

Workflow:
1. Land personality features on `feat/personalities`.
2. Keep `check-personalities.sh` green before merge.
3. Merge to `main` when roadmap M3–M4 slice is reviewable.

---

## How to verify

```sh
git checkout feat/personalities
bash scripts/check-personalities.sh
# or individually:
bash scripts/check-sci-contract.sh
bash scripts/check-windows-personality.sh
bash scripts/check-darwin-personality.sh
```

Interactive:
```text
space> windows
space> darwin
space> linux
```

---

## Definition of “done” for this roadmap document

This document is **done** when:

1. Branch `feat/personalities` exists and is pushed.
2. Progress + gap matrix above matches the tree (call IDs 1–30 Windows; Darwin BSD table).
3. `check-personalities.sh` is present and green.

**Not** the definition of “full Windows/Darwin OS.” That is M5–M6.
