# Compatibility Personalities: Running Linux, Darwin, and Windows Apps Natively

## Philosophy

Space is not a compatibility layer pretending to be another OS. Space is a new
operating system built on capabilities, objects, and component graphs.

Compatibility personalities exist so that existing applications can run on Space.
They should not exist so that Space can pretend to be Linux, macOS, or Windows.

The native model is always:

```text
component + capability + object + execution graph
```

Compatibility personalities translate legacy concepts into Space primitives:

| Legacy Concept | Space Primitive |
|---|---|
| Process | Realm + component + protection domain |
| File descriptor | Object graph node + capability |
| Syscall | Channel message to personality service |
| Signal / Mach trap | Fault handler + channel notification |
| ELF / PE / Mach-O | Decompressed into component image |
| Dynamic linking | Capability + object graph resolution |
| Registry / plist | Object graph view |
| Window server | Compositor component + surface channel |
| Unix socket / Mach port | Named channel endpoint |
| Thread | Cooperative / preemptive unit in realm |
| `fork()` | Object graph snapshot + new realm |

## No POSIX As Native Contract

Space explicitly does not expose POSIX as its native programming model.

A compatibility personality may offer `read()`, `write()`, `open()`, or
`select()` to guest programs, but Space components should not use these
concepts. The native APIs are capability operations, channel sends, and object
graph transactions.

This means:

- No `/proc` or `/sys` in the native namespace
- No global PID namespace
- No `SIGKILL` as a native concept
- No `mmap()` as the primary memory interface
- No environment variables as a primary configuration mechanism
- No `errno` as a native error contract

Personalities wrap these concepts so existing software compiles and runs
without modification. They do not import them into the native OS surface.

---

## Part 1: Linux Personality

### Behaviors To Explore

Linux exposes a wide surface through ~400 syscalls, `/proc`, `/sys`, cgroups,
namespaces, seccomp, ptrace, futex, epoll, signalfd, eventfd, timerfd,
io_uring, memfd, userfaultfd, inotify, fanotify, perf_event_open, bpf, and
more. A minimal personality does not need all of these.

The priority behaviors for a first working personality (in order):

| # | Behavior | Space Mapping | Complexity |
|---|----------|---------------|------------|
| 1 | ELF loading (static PIE, no libc dependency) | Decompress ELF → map segments → resolve absolute symbols → jump to entry | Small |
| 2 | `read` / `write` on pipes and serial fds | Channel-backed file descriptor table in the personality | Small |
| 3 | `exit` / `exit_group` | Terminate realm, return exit code to supervisor | Small |
| 4 | `brk` / `sbrk` | Simple bump allocator within realm address space | Small |
| 5 | `mmap` / `munmap` (MAP_ANONYMOUS, MAP_PRIVATE) | VM object + page table manipulation | Medium |
| 6 | `open` / `close` / `read` / `write` for object-backed files | Object graph node exposed as fd | Medium |
| 7 | `clone` / `gettid` / `tgkill` | New thread within realm, signal delivery channel | Large |
| 8 | `nanosleep` | Timer capability | Small |
| 9 | `clock_gettime` / `gettimeofday` | Timer capability read | Small |
| 10 | `getrandom` | Random capability (if granted) | Small |
| 11 | `futex` (FUTEX_WAIT, FUTEX_WAKE) | Channel-based wait queue in personality | Medium |
| 12 | `epoll_create` / `epoll_ctl` / `epoll_wait` | Personality-level fd readiness tracking | Medium |
| 13 | `sigaction` / `sigreturn` / `rt_sigprocmask` | Fault handler table, signal delivery channel | Large |
| 14 | `set_robust_list` / `futex` PI | Thread exit + priority inheritance stubs | Medium |
| 15 | `getdents64` for simple filesystem | Directory listing over object graph | Medium |
| 16 | `execve` | Load new ELF, reset personality realm | Large |
| 17 | `ioctl` (TIOCGWINSZ, TCGETS, etc.) | Serial personality ioctl stubs | Medium |
| 18 | `writev` / `readv` | Scatter/gather over channel | Small |
| 19 | `prctl` (PR_SET_NAME, PR_GET_NAME) | Thread name through personality | Small |
| 20 | Dynamic linker (`ld-linux-x86-64.so.2`) | Full ELF loading with symbol resolution + TLS | Very Large |

### Linux Special Cases

#### `fork()`

Space does not have `fork()` as a native primitive. A personality can implement
`fork()` by:

1. Checkpointing the current realm's object graph
2. Creating a new realm with a copy of the page tables (COW)
3. Copying the fd table, signal handlers, and thread state
4. Returning 0 in the child and the child's realm ID in the parent

This is expensive and should be discouraged in native Space development,
but a compatibility personality must offer it for POSIX compliance.

#### Process ID Namespace

The personality assigns local PIDs within its realm. These are not global
OS-level identifiers. `getpid()` returns a personality-local number.

#### `/proc` and `/sys`

These are synthetic filesystems backed by object graph queries or personality
state, not real filesystem mounts.

### Implementation Plan

```
Phase 1: Static binary runner
  - Load static PIE ELF
  - Map segments
  - Stub syscall handler (exit, brk, write to serial)
  - Print "hello world" from a real Linux binary

Phase 2: libc-aware runner
  - Implement mmap, open/read/write for stdin/stdout/stderr
  - Implement nanosleep, clock_gettime
  - Run a C program compiled with `-static -nostartfiles`

Phase 3: Dynamic linking
  - Implement ld-linux loader within the personality
  - TLS support via `arch_prctl(ARCH_SET_FS)`
  - Run a dynamically-linked C program

Phase 4: Concurrency
  - clone/getpid/tgkill for threads
  - futex for synchronization
  - epoll for I/O multiplexing
  - Run a multi-threaded C program

Phase 5: Signals
  - sigaction/sigreturn/rt_sigprocmask
  - Signal delivery via channel
  - SIGSEGV from page faults
  - Run programs using signal handlers

Phase 6: Operating system personality
  - getdents64 for directory listing
  - execve for program loading
  - Limited /proc and /sys views
  - Run a shell (busybox sh)
```

---

## Part 2: Darwin / XNU Personality

### Behaviors To Explore

Darwin's surface is very different from Linux. It has Mach messages, host/port
notifications, IOKit, Grand Central Dispatch, the Objective-C runtime,
launchd, XPC, System Configuration, Core Foundation, and a BSD syscall layer
wrapped around the XNU kernel.

Key behaviors:

| # | Behavior | Space Mapping | Complexity |
|---|----------|---------------|------------|
| 1 | Mach-O loading (FAT + thin x86_64) | Parse Mach-O header, load segments, resolve dyld stub | Medium |
| 2 | `mach_msg` / `mach_msg_trap` | Channel-based message transport in personality | Medium |
| 3 | `task_self_trap` / `thread_self_trap` | Return personality-local task/thread port | Small |
| 4 | `host_get_clock_service` / `clock_sleep` | Timer capability gate | Medium |
| 5 | `vm_allocate` / `vm_deallocate` / `vm_protect` | VM object operations within realm | Medium |
| 6 | `mach_port_allocate` / `mach_port_deallocate` | Capability minting / revocation | Medium |
| 7 | `mach_port_insert_right` / `mach_port_extract_right` | Capability transfer over channels | Medium |
| 8 | `thread_create` / `thread_start` / `thread_terminate` | Thread creation in personality realm | Large |
| 9 | `syscall` (BSD layer: read/write/open/close/exit) | Channel-backed fd table (same as Linux) | Small |
| 10 | `getentropy` / `getpid` / `getppid` | Personality-local state | Small |
| 11 | `shm_open` / `shm_unlink` | Named VM object under personality scope | Medium |
| 12 | `kqueue` / `kevent` | fd readiness + mach port delivery events | Large |
| 13 | Dyld loading + `_dyld_start` | Dynamic linker within personality (similar to Linux ld-linux) | Very Large |
| 14 | `__thread_register` / TLS setup | `arch_prctl(ARCH_SET_FS)` equivalent | Large |
| 15 | `getattrlist` / `getdirentriesattr` | Object graph attribute query | Medium |
| 16 | IOKit `IOServiceOpen` / `IOConnectCallMethod` | Device capability + channel-based service dispatch | Very Large |
| 17 | Grand Central Dispatch (`dispatch_async`, `dispatch_apply`) | Work queue over cooperative threads | Very Large |
| 18 | Objective-C runtime (`objc_msgSend`, `sel_registerName`) | Message dispatch through method mapping | Very Large |

### Darwin Special Cases

#### Mach Messages

Mach messages are the core IPC primitive in XNU. They carry ports, data, and
out-of-line memory. Space channels map naturally: a Mach port is a capability,
a message send is a channel operation, and out-of-line memory is a VM object
transfer.

The personality maintains a port name space per realm. `mach_port_allocate`
creates a channel endpoint in the personality. `mach_msg` translates port
rights to capability transfers.

#### Launchd And XPC

launchd is the bootstrap daemon that manages services, sockets, and scheduled
jobs. XPC is the high-level IPC framework.

In Space, launchd maps to the component supervisor. A personality translates:

- `launchd` plist → component manifest + capability grants
- `xpc_connection_create` → channel creation
- `xpc_connection_send_message` → channel message with capability transfer

#### Objective-C Runtime

The Objective-C runtime (`libobjc.A.dylib`) depends on:

- Mach messages for `objc_msgSend` forwarding
- `pthread`-based thread-local storage
- `dlopen` for dynamic framework loading
- `mprotect` for method patching (JIT)

Each of these must be supported by the personality before Cocoa or
AppKit-based programs can run.

#### Grand Central Dispatch

GCD is fundamentally a work-stealing thread pool with:

- Global concurrent queues
- Serial dispatch queues
- Dispatch sources (fd, mach port, timer, signal, process)
- Dispatch groups and barriers

The personality can map GCD's dispatch queues to Space's cooperative
thread pool. Dispatch sources become channel + capability monitoring.
This is one of the most complex subsystems to emulate.

### Darling As Reference

The [Darling](https://www.darlinghq.org/) project translates Darwin syscalls
to Linux. Its approaches for Mach message translation, dyld loading,
and IOKit stubs are directly applicable to a Space personality. The key
difference: Space channels map more naturally to Mach ports than Linux
pipes or sockets do.

### Implementation Plan

```
Phase 1: Mach-O static binary runner
  - Load a static x86_64 Mach-O binary
  - Stub `syscall` (exit, write to serial)
  - Stub `mach_msg` (return success for simple traps)
  - Print output from a simple Darwin program

Phase 2: Mach IPC surface
  - Implement `mach_port_allocate`, `mach_msg`, `mach_port_deallocate`
  - Channel-backed port implementation
  - Run a program using `mach_clock_sleep`

Phase 3: Memory management
  - `vm_allocate`, `vm_deallocate`, `vm_protect`
  - `shm_open` for shared memory
  - Run a program using `mmap` (BSD wrapper)

Phase 4: Threads and synchronization
  - `pthread`-level thread creation via `thread_create`
  - `__thread_register` and TLS
  - `kqueue` / `kevent` for fd + port multiplexing

Phase 5: Dyld and frameworks
  - Load `dyld` and resolve framework dependencies
  - `dlopen` / `dlsym` within personality
  - Stub common system frameworks (CoreFoundation, IOKit)
```

---

## Part 3: ReactOS / Windows Personality

### Behaviors To Explore

Windows/NT has the largest emulation surface of the three. The NT kernel
provides system services through `ntdll!Nt*` functions dispatched via
`sysenter` (on x64). Win32 sits on top of NT through `kernel32`,
`user32`, `gdi32`, and `ntdll`.

ReactOS is the primary reference: a clean-room implementation of the
Windows NT kernel and Win32 API.

Key behaviors:

| # | Behavior | Space Mapping | Complexity |
|---|----------|---------------|------------|
| 1 | PE/COFF loading | Parse PE header, load sections, resolve IAT | Medium |
| 2 | NT syscall dispatch (`syscall` instruction handler) | Trap handler in personality → dispatch table | Medium |
| 3 | `NtCreateFile` / `NtReadFile` / `NtWriteFile` / `NtClose` | Object-backed IO in personality | Medium |
| 4 | `NtCreateProcess` / `NtCreateThread` / `NtTerminateProcess` | Realm + component creation | Large |
| 5 | `NtAllocateVirtualMemory` / `NtFreeVirtualMemory` | VM object management | Medium |
| 6 | `NtCreateEvent` / `NtSetEvent` / `NtWaitForSingleObject` | Channel-backed event object | Medium |
| 7 | `NtCreateMutant` (mutex), `NtCreateSemaphore` | Channel-backed synchronization objects | Medium |
| 8 | `NtCreateKey` / `NtOpenKey` / `NtQueryValueKey` / `NtSetValueKey` | Registry as object graph view | Medium |
| 9 | `NtQuerySystemInformation` | Personality state + capabilities | Small |
| 10 | `NtDeviceIoControlFile` | Device capability + channel (similar to IOKit) | Large |
| 11 | `RtlUserThreadStart` / `LdrInitializeThunk` | Process/thread initialization in personality | Large |
| 12 | SEH (Structured Exception Handling) via `RtlDispatchException` | Fault handler table in personality | Large |
| 13 | `LdrLoadDll` / `LdrGetProcedureAddress` | PE loader with import resolution + forwarding | Very Large |
| 14 | `NtCreateFile` for named pipes, mailslots | Channel-based named pipe backing | Medium |
| 15 | `RtlCreateHeap` / `RtlAllocateHeap` | Heap manager in personality address space | Large |
| 16 | Win32 subsystem (`kernel32!CreateWindowEx`, `user32!DispatchMessage`) | GUI service component + compositor surface | Very Large |
| 17 | `Gdi32!BitBlt` / `Gdi32!TextOut` | Surface compositor capability | Very Large |
| 18 | COM (`CoCreateInstance`, `IUnknown`, IDispatch) | Object graph + capability dispatch | Extremely Large |

### Windows Special Cases

#### NT Object Manager

The NT kernel has a global object namespace (`\BaseNamedObjects`, `\Device`,
`\Registry`, etc.) with security descriptors.

Space has per-realm object graphs with capability-gated access. The
personality presents a virtual NT object namespace backed by:

- `\BaseNamedObjects` → realm-scoped named objects
- `\Registry` → object graph registry view
- `\Device` → device capability resolution
- `\??` (DosDevices) → personality device mapping

#### NT Handle Table

NT handles are process-local indices into a kernel-managed handle table.
Space capabilities are already unforgeable references. The personality
wraps capabilities in an NT-compatible handle table.

A handle close is a capability revocation. A handle duplication
(`NtDuplicateObject`) is a capability mint. A handle inheritance
across `NtCreateProcess` is a capability transfer to a new realm.

#### Registry

The Windows registry is a hierarchical key-value store with typed values,
ACLs, and transaction support. The personality maps:

- Registry keys → object graph nodes
- Registry values → typed object fields
- Registry transactions → object graph checkpoint/rollback

#### Win32

Win32 is the largest subsystem. It depends on:

- Window station / desktop objects
- Message queue per-thread
- Window handle table
- GDI handle table
- USER object table
- Clipboard, atoms, hooks, timers

The personality maps these to Space primitives:

- Windows → surface channel + compositor component
- Messages → channel message queue per thread
- GDI → surface rendering capability
- USER → input event channel

#### COM / COM+

COM is an object model based on reference-counted interfaces,
class factories, and the registry (`HKEY_CLASSES_ROOT`).

Space's native object model (capabilities + channels + schemas) maps
naturally:

- COM `IUnknown` → capability with method dispatch
- `CLSID` → object schema ID
- `CoCreateInstance` → component instantiation with capability grants
- COM apartments → thread-local capability dispatch

#### PE Loading And DLL Hell

Windows executables depend on:

- Import Address Table (IAT) resolution
- Export forwarding (`ntdll.RtlAllocateHeap` → `heap32.HeapAlloc`)
- Side-by-side assemblies (SxS)
- Activation contexts
- Delay-load imports

The personality loader must implement all of these before any non-trivial
Windows executable can run. This is a Very Large task.

### ReactOS As Reference

[ReactOS](https://www.reactos.org/) is a clean-room Windows-compatible OS.
Its implementations of:

- `ntdll` syscall dispatch
- `kernel32` WIN32 API
- `csrss` client-server runtime
- Registry engine
- Object manager layout

...are all directly applicable as reference for a Space personality.
ReactOS runs real Windows apps (Notepad, regedit, 7-Zip, etc.) and
its architecture is thoroughly documented.

### Wine As Reference

[Wine](https://www.winehq.org/) translates Windows syscalls to POSIX on
Linux and macOS. Its PE loader, DLL loader, registry engine, and Win32
user/gdi implementations work without an NT kernel.

A Space Windows personality could start from Wine's loader and syscall
translation layer, replacing the POSIX backend with Space primitives
(channels, capabilities, object graph). This is a significant but
achievable engineering project.

### Implementation Plan

```
Phase 1: PE static binary runner
  - Load a static PE image (no imports)
  - Stub NT syscall handler for NtWriteFile (stdout)
  - Stub RtlUserThreadStart
  - Print output from a minimal Windows program

Phase 2: NT syscall surface
  - Implement object manager (NtCreateFile, NtClose)
  - Implement virtual memory (NtAllocateVirtualMemory, NtFreeVirtualMemory)
  - Implement synchronization (NtCreateEvent, NtWaitForSingleObject)
  - Implement registry (NtCreateKey, NtQueryValueKey)
  - Run a simple Windows CLI utility (e.g. cmd.exe --help)

Phase 3: PE loader + DLL resolution
  - LdrLoadDll / LdrGetProcedureAddress
  - Import Address Table resolution
  - Export forwarding
  - Run a dynamically-linked Windows program

Phase 4: Threading and processes
  - NtCreateProcess / NtCreateThread
  - RtlUserThreadStart initialization
  - Thread-local storage (TEB, PEB)
  - SEH handling
  - Run a multi-threaded Windows program

Phase 5: Win32 subsystem
  - kernel32 + user32 base stubs
  - Message queue + window handling
  - GDI surface capability
  - Compositor integration
  - Run Notepad or a simple Win32 app
```

---

## Part 4: Cross-Cutting Concerns

### Syscall Dispatch Architecture

All three personalities follow the same pattern:

```text
Guest application (x86_64 code)
  │
  ▼ executes syscall instruction
  ├── Linux:  syscall (0F 05)
  ├── Darwin: syscall (0F 05)  (Mach trap via SYSENTER)
  └── Windows: syscall (0F 05) (or int 0x2E on older)
        │
        ▼
  Personality trap handler in realm
        │
        ▼ dispatches to:
  ├── Linux:    linux_syscall_table[]
  ├── Darwin:   darwin_mach_trap_table[] + darwin_bsd_syscall_table[]
  └── Windows:  nt_syscall_table[] via ntdll ordinal
        │
        ▼ translates to:
  ├── Channel message to personality service
  ├── Capability operation
  ├── Object graph transaction
  └── Native Space component invoke
```

Each personality maintains its own dispatch table. The tables are populated
from a minimal core (exit, write) and grow as more behaviors are implemented.

### Memory Protection Domains

Personalities need per-process address space isolation similar to traditional
OSes. Space achieves this through:

- Per-realm page tables
- VM objects managed by the personality
- Separate TLB context per realm

A personality creates a new realm for each emulated process. The realm owns
the address space, handle table, and capability set. When the process exits,
the realm is destroyed and its resources are reclaimed.

### File Descriptor / Handle Table

Each personality maintains a table mapping guest-visible integers to Space
resources:

```text
Linux fd 0 → channel to serial input
Linux fd 1 → channel to serial output
Linux fd 3 → object graph node for /tmp/foo

Windows handle 0x4 → capability for \Device\KeyboardClass0
Windows handle 0x8 → event object capability
Windows handle 0xC → registry key object graph node
```

The personality translates guest operations (read, write, ioctl, DeviceIoControl)
into capability-channel operations.

### Signal / Exception Delivery

Linux signals, Mach exceptions, and Windows SEH all follow similar patterns:

1. An event occurs (fault, timer, IPC)
2. The personality intercepts it through a trap or channel notification
3. The personality saves guest register state
4. The personality delivers the event to the guest's handler
5. On return, the personality restores guest state or handles termination

Space already has fault handlers (page faults, divide errors). The personality
extends these to deliver signals to guest signal handlers.

### Dynamic Linker Loading

All three personalities need a dynamic linker:

| OS | Dynamic Linker | Entry |
|----|---------------|-------|
| Linux | `ld-linux-x86-64.so.2` | `_start` → `__libc_start_main` |
| Darwin | `/usr/lib/dyld` | `__dyld_start` → `main` |
| Windows | `ntdll.dll` | `LdrInitializeThunk` → `RtlUserThreadStart` |

The personality must:
1. Load the dynamic linker as the first user-space image
2. Map the guest executable
3. Have the linker resolve imports against personality-provided libraries
4. Jump to the guest's entry point

This is the single largest compatibility task for all three personalities.

---

## Part 5: Plan Summary

### Phase Table

| Phase | Linux | Darwin | Windows | Cross-Cutting |
|-------|-------|--------|---------|---------------|
| **0** | — | — | — | Design document, reference research, tooling |
| **1** | Static ELF runner | Static Mach-O runner | Static PE runner | Trap dispatch framework, realm-per-process |
| **2** | `libc`-aware runtime | Mach IPC + memory | NT syscall surface | Channel-backed fd/handle table |
| **3** | Dynamic linking | Threads + dyld | PE loader + DLLs | Dynamic linker host within personality |
| **4** | Threads + futex | Framework stubs | Threading + SEH | Thread model unification |
| **5** | Signals + shell | Dyld + frameworks | Win32 base | Compositor integration |
| **6** | Busybox, vim | Simple CLI Darwin apps | Notepad, regedit | Benchmark suite, CI for each personality |
| **7** | GUI programs | Lightweight Cocoa apps | GUI Windows apps | Shared compositor pipeline |
| **8** | Full LAMP stack | Native macOS CLI | Windows development tools | Cross-personality object graph sharing |

### Priority (Ponytail Assessment)

```
1. Linux personality Phase 1-2     (static ELF + libc)    ← start here
   Why: most existing tooling, largest ecosystem, best reference docs.
   Worth it before native components even mature (can dogfood the compiler).

2. Windows personality Phase 1-2   (static PE + NT syscalls)
   Why: ReactOS + Wine provide tested reference implementations.
   Larger surface but better-documented than Darwin.

3. Darwin personality Phase 1-2    (static Mach-O + Mach IPC)
   Why: Darling exists but is less mature than Wine/ReactOS.
   Mach IPC maps beautifully to Space channels (best fit of the three).

4. All Phase 3+                    (dynamic linking, concurrency, GUI)
   Why: each requires multi-person-year effort. Worth it when native
   space components are mature and the personalities are needed.
```

### First Actionable Step

Build a Linux static PIE runner in `.in`:

```text
1. Accept a static PIE ELF binary as a component argument
2. Create a new realm with isolated page tables
3. Parse the ELF Program Headers
4. Map LOAD segments at specified virtual addresses
5. Zero-fill .bss
6. Set up a minimal stack
7. Jump to ELF entry point (with RDI=0, RSI=0, argc=0, argv=0)
8. Trap the first `syscall` instruction
9. Dispatch to a personality handler: write("hello from Linux!") to serial
10. Halt
```

This fits in 200-400 lines of `.in` and proves the personality architecture
before any complex syscall translation exists.
