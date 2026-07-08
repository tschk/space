# Windows NT Personality for Space — Design

## Summary

A ring-3 NT personality server that translates Windows NT native syscalls
into Space kernel primitives, enabling Space to load and run Windows PE
executables. Clean-room `.in` implementation using Wine and ReactOS as
reference for NT semantics and bug-compatibility.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Windows PE .exe          │  Linux ELF             │  ← foreign binaries
│  (ring 3, user mode)      │  (ring 3, user mode)   │
└────────────┬──────────────┴──────────┬──────────────┘
             │ syscall (x86_64)        │ int 0x80
             ▼                         ▼
┌────────────────────────────────────────────────────────┐
│  Space Syscall Dispatcher  (kernel, ring 0)            │
│  Routes by syscall number range:                       │
│    0-31   → native Space syscalls                      │
│    32-63  → Linux personality (forward to posix svc)   │
│    64-127 → Windows NT personality (forward to nt svc) │
└────────────┬──────────────────────────┬────────────────┘
             │                          │
             ▼                          ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│ POSIX personality    │  │ NT personality                │
│ (ring 3, domain N)   │  │ (ring 3, domain M)            │
│ components/posix.in  │  │ components/ntos/              │
└──────────────────────┘  └──────────────────────────────┘
```

### Hybrid split

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Fast paths | kernel (ring 0) | Memory mapping, domain switching, preemption, interrupt delivery |
| NT executive | ring 3 personality | Object Manager, Process Manager, I/O Manager, Security |
| NT kernel core | ring 3 personality | Thread scheduling hints, APC delivery, DPC emulation |
| Win32 subsystem | ring 3, same domain | kernel32, user32, gdi32 (stubs → compositor) |

Safety: personality server runs in isolated memory domain. Kernel gates
all cross-domain IPC through capability checks. Personality cannot touch
kernel state or other personalities.

### Syscall flow

1. Windows PE issues `syscall` (x86_64: `syscall` instruction with NT number in RAX)
2. Space kernel traps the instruction, reads RAX
3. Range check: 64-127 → NT personality
4. Kernel writes args to shared page, sets REQ flag
5. NT personality server (polling or woken by kernel) reads shared page
6. Dispatches to appropriate NT executive function
7. Writes result, sets RESP flag
8. Kernel reads result, writes to RAX, returns to PE

## Reference Material

| Topic | Primary ref | Path |
|-------|------------|------|
| NT executive (Object, Process, I/O) | ReactOS | `ref/reactos/ntoskrnl/ob/`, `ps/`, `io/`, `mm/`, `se/` |
| NT kernel core (KE) | ReactOS | `ref/reactos/ntoskrnl/ke/` |
| ntdll (syscall stubs, RTL, loader) | Wine | `ref/wine/dlls/ntdll/` |
| ntdll (NT-side) | ReactOS | `ref/reactos/dll/ntdll/ldr/`, `rtl/` |
| kernel32 (Win32 base) | Wine | `ref/wine/dlls/kernel32/` |
| user32 (window management) | Wine | `ref/wine/dlls/user32/` |
| NT syscall table | Wine | `ref/wine/dlls/ntdll/ntsyscalls.h` |
| Win32k (GUI kernel) | ReactOS | `ref/reactos/win32ss/` |
| PE loader | Wine | `ref/wine/dlls/ntdll/loader.c` |
| PE loader | ReactOS | `ref/reactos/dll/ntdll/ldr/` |

## Component Tree

```
components/ntos/
├── ntoskrnl.in          NT executive entry + shared-page RPC loop
├── ob/                   Object Manager
│   ├── ob.in             Directory namespace, object types, handles
│   └── ob_types.in      Predefined types: File, Process, Thread, Event, Key, Section
├── ps/                   Process Manager
│   ├── ps.in             Process/thread create, terminate, query
│   └── ps_thread.in     Thread scheduling hints, APC queues
├── io/                   I/O Manager
│   ├── io.in             IRP dispatch, driver stack, device objects
│   └── io_file.in        File I/O → Space VFS
├── mm/                   Memory Manager
│   ├── mm.in             Virtual memory, sections, page fault handling
│   └── mm_heap.in        Process heaps on top of Space domain allocator
├── se/                   Security
│   ├── se.in             Access checks, tokens, SIDs
│   └── se_token.in       Token creation and validation
├── ke/                   Kernel core
│   ├── ke.in             DPC, APC, timer, interrupt object stubs
│   └── ke_wait.in        Wait objects: events, mutexes, semaphores
├── rtl/                  Runtime library
│   ├── rtl.in            String, memory, unicode, AVL tree, bitmaps
│   └── rtl_heap.in       Heap manager (ntdll-style)
├── ldr/                  PE Loader
│   ├── pe.in             PE32+ parser: DOS/PE/NT headers, sections
│   ├── ldr.in            Loader: import resolution, relocation, TLS
│   └── ldr_init.in       LdrInitializeThunk — process startup
├── ntdll.in              NT syscall stub layer (for PE binaries)
├── kernel32.in           Win32 base API (console, file, process, sync)
├── user32.in             Window management stubs → compositor
├── gdi32.in              GDI stubs → framebuffer primitives
├── advapi32.in           Registry + security API stubs
└── shell32.in            Shell API stubs
```

## Milestone 1 — NT Console Process (MVP)

**Goal:** Load a PE32+ `.exe`, provide ntdll syscall stubs for basic I/O, run "Hello World" on serial.

### What ships

1. **PE Loader** (`ldr/pe.in`, `ldr/ldr.in`)
   - Parse DOS header, PE signature, COFF header, optional header
   - Map sections (`.text`, `.rdata`, `.data`) into domain pages
   - Apply base relocations
   - Resolve import table against ntdll stubs
   - Call entry point

2. **ntdll stubs** (`ntdll.in`)
   - Process: `NtTerminateProcess`, `NtQueryInformationProcess`
   - Thread: `NtCreateThread`, `NtTerminateThread`
   - File: `NtCreateFile`, `NtReadFile`, `NtWriteFile`, `NtClose`
   - Memory: `NtAllocateVirtualMemory`, `NtFreeVirtualMemory`, `NtProtectVirtualMemory`
   - Misc: `NtQuerySystemInformation`, `NtQueryPerformanceCounter`
   - RTL: `RtlInitUnicodeString`, `RtlCompareMemory`, `RtlMoveMemory`, `RtlZeroMemory`

3. **NT Executive skeleton** (`ntoskrnl.in`, `ob/`, `ps/`)
   - Object Manager: root directory, object types, handle table per-process
   - Process Manager: create/terminate process, thread stub
   - I/O Manager: minimal IRP dispatch (file → VFS passthrough)

4. **kernel32** (`kernel32.in`)
   - Console: `WriteConsoleA`, `GetStdHandle`
   - File: `CreateFileA`, `ReadFile`, `WriteFile`, `CloseHandle`
   - Process: `GetCurrentProcessId`, `ExitProcess`
   - Heap: `GetProcessHeap`, `HeapAlloc`, `HeapFree`

5. **Syscall plumbing**
   - Shared-page RPC between kernel and ntoskrnl
   - NT syscall table (first 50 entries)
   - Kernel dispatcher range 128-255 → NT forward

6. **Demo**
   - `nt_demo` shell command loads `hello.exe` from filesystem
   - PE loaded, mapped, imports resolved
   - ntdll → ntoskrnl → VFS → serial output
   - Prints "Hello from Windows on Space!" and exits

### Syscalls implemented (≈30)

| NT # | Name | Mapping |
|------|------|---------|
| 0x00 | NtCreateFile | ob → VFS open |
| 0x03 | NtReadFile | ob → VFS read |
| 0x04 | NtWriteFile | ob → VFS write |
| 0x06 | NtClose | ob handle close |
| 0x13 | NtAllocateVirtualMemory | mm → domain alloc |
| 0x1B | NtFreeVirtualMemory | mm → no-op (bump) |
| 0x26 | NtTerminateProcess | ps → proc_exit |
| 0x2D | NtCreateThread | ps → thr_create |
| 0x34 | NtQueryInformationProcess | ps query |
| 0x36 | NtQuerySystemInformation | basic system info |
| 0x48 | NtTerminateThread | ps → thr_exit |
| 0x4E | NtQueryPerformanceCounter | rdtsc or ticks |
| 0x50 | NtProtectVirtualMemory | no-op (no page prot yet) |

### Reference files

- PE loader logic: `ref/wine/dlls/ntdll/loader.c` (LdrLoadDll, LdrInitializeThunk)
- PE header parsing: `ref/reactos/dll/ntdll/ldr/`
- NT syscall numbers: `ref/wine/dlls/ntdll/ntsyscalls.h`
- Object Manager types: `ref/reactos/ntoskrnl/ob/obdir.c`, `obhandle.c`
- Process Manager: `ref/reactos/ntoskrnl/ps/process.c`, `thread.c`
- kernel32 console: `ref/wine/dlls/kernel32/console.c`

## Milestone 2 — NT Executive Skeleton

**Goal:** Full NT executive subsystem framework. Programs can load, query, and use all major NT object types.

### What ships

1. **Object Manager** (`ob/`)
   - Directory namespace (`\Device\Harddisk0\...`)
   - Object types: Directory, File, Process, Thread, Event, Key, Section, Device
   - Handle table: per-process, access masks, handle inheritance
   - Object attributes parsing (OBJECT_ATTRIBUTES → path + security)
   - Parse routines for device objects
   - Reference counting, close callbacks

2. **Process Manager** (`ps/`)
   - Full process/thread lifecycle: create, open, terminate, query, suspend/resume
   - Process environment block (PEB) per-process
   - Thread environment block (TEB) per-thread
   - APC (Asynchronous Procedure Call) queues per thread
   - Process/thread enumeration
   - Job objects (minimal)

3. **I/O Manager** (`io/`)
   - IRP (I/O Request Packet) allocation and dispatch
   - Device stack: device objects, driver objects
   - I/O completion ports (minimal)
   - File objects backed by Space VFS
   - Async I/O: IRP queued, completion via APC

4. **Memory Manager** (`mm/`)
   - Section objects (file-backed memory mappings)
   - Virtual address space management per process
   - Working set tracking (simplified)
   - Page protection (read/write/execute)
   - Address windowing extensions (AWE) stubs

5. **Security** (`se/`)
   - Token objects (primary + impersonation)
   - SID representation and comparison
   - Access check: security descriptor → granted access
   - Privilege checking (SeShutdownPrivilege, etc.)
   - Audit stub

6. **Kernel Core** (`ke/`)
   - DPC (Deferred Procedure Call) emulation via tasks
   - Timer objects
   - Wait objects: Event, Mutex, Semaphore, Timer
   - WaitForMultipleObjects implementation
   - Interrupt object stubs (no real HW interrupts for personality)

7. **Runtime Library** (`rtl/`)
   - Unicode string handling (RtlInitUnicodeString, RtlCompareUnicodeString)
   - AVL table (RtlInitializeGenericTableAvl)
   - Bitmap operations
   - Memory: RtlMoveMemory, RtlZeroMemory, RtlCompareMemory
   - Critical sections (RtlInitializeCriticalSection)
   - NLS/unicode conversion

8. **kernel32** (`kernel32.in`)
   - File API: CreateFileA/W, ReadFile, WriteFile, CloseHandle, SetFilePointer
   - Console API: AllocConsole, WriteConsoleA/W, GetStdHandle
   - Process API: CreateProcessA/W, ExitProcess, GetCurrentProcess, OpenProcess
   - Thread API: CreateThread, ExitThread, GetCurrentThread
   - Sync API: CreateEvent, SetEvent, WaitForSingleObject, WaitForMultipleObjects
   - Memory API: VirtualAlloc, VirtualFree, VirtualProtect
   - Module API: LoadLibraryA/W, GetProcAddress, FreeLibrary
   - Error handling: GetLastError, SetLastError, FormatMessageA

9. **user32** (`user32.in`) — stubs only
   - Message queue skeleton (PostMessage, GetMessage, PeekMessage)
   - Window class registration (RegisterClassA/W)
   - Window creation (CreateWindowExA/W) — defer to compositor when ready
   - All GUI operations return success but are no-ops for now

### Syscalls (≈80 new)

Roughly 110 total NT syscalls by end of M2. Covers the NT executive API surface that kernel32 and user32 depend on.

### Reference files

- Object Manager: `ref/reactos/ntoskrnl/ob/` (all files)
- Handle table: `ref/reactos/ntoskrnl/ob/obhandle.c`
- Process: `ref/reactos/ntoskrnl/ps/process.c`, `psmgr.c`
- Thread: `ref/reactos/ntoskrnl/ps/thread.c`
- I/O Manager: `ref/reactos/ntoskrnl/io/iomgr/`
- IRP dispatch: `ref/reactos/ntoskrnl/io/iomgr/irp.c`
- Memory: `ref/reactos/ntoskrnl/mm/` (section.c, region.c)
- Security: `ref/reactos/ntoskrnl/se/token.c`, `accesschk.c`
- KE: `ref/reactos/ntoskrnl/ke/eventobj.c`, `mutex.c`, `dpc.c`
- RTL: `ref/reactos/dll/ntdll/rtl/`
- kernel32 file: `ref/wine/dlls/kernel32/file.c`, `process.c`, `sync.c`
- kernel32 console: `ref/wine/dlls/kernel32/console.c`

## Future Milestones (outline)

### M3 — Win32 GUI Light
- user32 → compositor IPC for real window creation
- gdi32 drawing primitives → framebuffer
- A single GUI app (e.g., Win32 "Hello World") renders a window
- Depend on compositor maturity

### M4 — Registry + Services
- Configuration Manager (registry hive reader)
- Service Control Manager (SCM)
- advapi32 registry API
- Persist registry to Space VFS

### M5 — Networking
- Winsock (ws2_32) → Space network channels
- TCP/IP stack mapped to NT I/O Manager network devices
- HTTP client demo

### M6 — Full Compatibility
- COM/OLE stubs
- DirectX translation layer (WineD3D reference)
- Shell (explorer.exe concept)
- Crash dumps, event logging

## Implementation Order

```
  M1: PE loader → ntdll stubs → kernel32 → first .exe runs
       │
       ▼
  M2: Object Manager → Process Manager → I/O Manager → Memory Manager
       │                → Security → KE → RTL → full kernel32 → user32 stubs
       │
       ▼
  M3: user32 real → gdi32 → compositor integration
       │
       ▼
  M4: Registry → SCM → advapi32
       │
       ▼
  M5: Winsock → TCP/IP
       │
       ▼
  M6: DirectX → Shell → polish
```

## Design Decisions

### Why ring-3 for NT executive?
- Isolation: a bug in the personality can't corrupt the kernel
- Matches existing pattern: Linux personality already runs ring-3
- Enables eventual multi-personality: Linux + Windows simultaneously
- The cost (IPC overhead) is acceptable for the MVP; optimize later with
  batched RPC or kernel-shared memory regions if needed

### Why clean-room .in instead of porting Wine C?
- Wine C is 4M+ lines, deeply tied to POSIX host assumptions
- .in gives us Space-native capability/component integration
- Wine's POSIX host is a different problem than Space's primitive set
- ReactOS C kernel is a better reference (it IS an NT kernel)
- But we gain more from writing fresh .in with full control

### Why shared-page RPC instead of real syscall forward?
- Existing pattern from Linux personality (`components/posix.in`)
- Simple, debuggable, no new kernel mechanisms needed
- The personality server polls the shared page; can be optimized later
  with kernel wake-on-write or a dedicated personality thread

### Why kernel32 + user32 in .in instead of PE DLLs?
- PE DLLs would need the full NT loader working first (circular)
- Native .in implementations can call Space primitives directly
- PE binary compatibility is for *applications*, not system DLLs
- The personality's own DLLs serve as the translation boundary

## File Count Estimate

| Component | Files |
|-----------|-------|
| ntoskrnl | 1 |
| ob | 2 |
| ps | 2 |
| io | 2 |
| mm | 2 |
| se | 2 |
| ke | 2 |
| rtl | 2 |
| ldr | 3 |
| ntdll | 1 |
| kernel32 | 1 |
| user32 | 1 |
| gdi32 | 1 |
| advapi32 | 1 |
| shell32 | 1 |
| ntsyscall (shared page protocol) | 1 |
| **Total** | **25** |

## Tests

- `nt_demo hello.exe` — smoke test, runs on every boot
- `nt_syscall_selftest` — exercises each implemented syscall
- `nt_pe_loader_test` — loads a test PE and verifies sections
- `nt_ob_test` — creates/destroys objects, walks directory namespace
- `nt_ps_test` — creates process, queries info, terminates

## Risks

| Risk | Mitigation |
|------|-----------|
| NT syscall surface is enormous (~400+) | Implement on-demand, guided by what kernel32 calls |
| PE format edge cases (relocations, TLS, SEH) | Narrow MVP: only statically-linked, no-SEH binaries |
| Unicode everywhere in NT | Rtl unicode in M2, ASCII-only in M1 |
| Async I/O complexity | Sync-only in M1, APC-based async in M2 |
| Compositor isn't ready for user32 | Stub user32 in M2, return success, real integration in M3 |
