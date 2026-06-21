# Compatibility Model: Microservice Architecture

## Architecture

Space is designed to run Windows, Darwin, and Linux programs through a fabric of
`.in` capability microservices, not through syscall-translation layers or
personality traps in kernel mode.

The nanokernel provides only:

- memory domain records; page-table isolation is still the Phase 0 blocker
- channels (typed IPC)
- capabilities (unforgeable authority)
- scheduling (CPU time + thread primitives)
- hardware access (interrupts, IO ports, MMIO)

Everything else is a `.in` microservice — a separate component with its own
capability grants, fault isolation, and lifecycle.

## How A Guest Program Runs

```
  ┌─────────────────────────────┐
  │      loader.in              │  understands ELF/PE/Mach-O layout
  │  (cap: memory, channel)     │  creates memory domain for guest
  └────────┬────────────────────┘
           │ channel: "load this binary"
           ▼
  ┌─────────────────────────────┐
  │      linux-compat.in        │  maps POSIX semantics to microservice calls
  │  (cap: channel to fs, net,  │  guest libc links against this component's
  │         gfx, proc, ...)     │  channel interface (not raw syscalls)
  └────────┬────────────────────┘
           │ calls to:
           ├──► fs.in      (file I/O, directories, mounts)
           ├──► net.in     (sockets, DNS, TLS)
           ├──► gfx.in     (compositor, surfaces, input)
           ├──► proc.in    (process lifecycle, signals, exit)
           ├──► time.in    (clocks, timers, sleep)
           ├──► mem.in     (mmap, shared memory, heap)
           ├──► rand.in    (entropy)
           └──► ...        (audio, GPU, sensors, etc.)
```

Each microservice is an independent `.in` component:

- Compiled and sandboxed like any other Space component
- Declares exactly the capabilities it needs (no ambient authority)
- Communicates through typed channels only
- Can be restarted, upgraded, or replaced independently
- Shares nothing — no kernel object, no global state
- Verified by the SCI loader before attachment

## Why Microservices Over Translation Layers

| Aspect | Translation Layer (old) | Microservice Fabric (this) |
|--------|------------------------|---------------------------|
| Kernel complexity | Trap handler for every guest syscall | No guest syscall awareness |
| Isolation | Single personality realm has broad authority | Each microservice has minimal, declared capabilities |
| Development language | C or asm for trap handling | `.in` — the native Space language |
| Upgrade path | Must recompile personality | Hot-swap individual `.in` components |
| Debugging | Hard — syscall trace or nothing | Each microservice debuggable independently |
| Reuse | Personality-specific | `fs.in`, `net.in`, `gfx.in` serve ALL guests |
| Failure domain | One crash kills all guest programs | One microservice restarts independently |
| Testability | Full OS needed for test | Unit-test each `.in` microservice in isolation |

## Microservice Catalog

### Core Services (needed by all guests)

| Service | Capabilities | Channel Ops | Written In |
|---------|-------------|-------------|------------|
| `fs.in` | block device, memory | open, read, write, close, seek, stat, readdir, mkdir, unlink, rename, truncate, mount | `.in` |
| `net.in` | NIC, channel to fs | socket, bind, listen, accept, connect, send, recv, getaddrinfo, tls_handshake | `.in` |
| `gfx.in` | framebuffer, MMIO, channel | create_surface, present, blit, text_out, cursor, input_subscribe | `.in` |
| `proc.in` | memory, channel to loader | spawn, exit, wait, signal, kill, cred, cwd, environ | `.in` |
| `time.in` | timer, RTC | now, sleep, timer_create, clock_gettime, gettimeofday | `.in` |
| `mem.in` | memory | mmap, munmap, mprotect, madvise, brk, shm_open, shm_unlink | `.in` |
| `rand.in` | RDRAND, entropy source | getrandom, seed, bytes | `.in` |

### Guest-Specific Shims

| Shim | Purpose | Calls |
|------|---------|-------|
| `linux-compat.in` | Linux app ABI | maps POSIX to core services, manages fd table, thread creation |
| `darwin-compat.in` | Darwin app ABI | maps Mach IPC to channels, dyld, ObjC runtime, IOKit stubs |
| `win-compat.in` | Windows app ABI | maps NT syscalls, Win32 API, registry, COM |

These shims are thinner than traditional translation layers because the core
services (fs, net, gfx, proc) handle the heavy lifting. The shim mainly
translates data structures and calling conventions.

## Guest Binary Lifecycle

```
1. Guest binary arrives as a blob (ELF, PE, Mach-O)
         │
         ▼
2. loader.in opens the binary
   - Parses headers, segments, imports
   - Creates a memory domain for the guest
   - Maps segments at correct addresses
   - Loads the shim library (linux-compat's guest libc shim)
         │
         ▼
3. Guest's entry point starts
   - Guest libc shim connects to compat.in channel
   - Every "syscall" is actually a channel send to the shim
   - The shim translates and forwards to core microservices
         │
         ▼
4. Runtime
   - Guest calls write(1, buf, len)
   - Guest libc shim sends channel message to linux-compat.in
   - linux-compat.in calls fs.in's write operation
   - fs.in writes to serial (or file, or pipe, or socket)
         │
         ▼
5. Guest exits
   - proc.in is notified
   - Memory domain is reclaimed
   - Channel connections are closed
   - Object graph references are released
```

### Guest Libc Shim

The guest binary links against a small shim library at load time. This shim:

- Replaces libc's syscall wrappers with channel sends
- Keeps a local fd table (mapping guest fd → channel endpoint + capability)
- Manages thread-local storage
- Delivers signals as channel notifications

The shim is the only guest-specific code. It is ~50 KB for Linux, similar for
Darwin and Windows. The shim is loaded into the guest's memory domain.

## Memory Domains

Each guest program gets its own memory domain (page table tree + TLB context).

```
  ┌─────────────────────┐
  │   kernel domain     │  nanokernel, page tables
  └─────────────────────┘
         │
  ┌──────┴──────┐
  │  service    │  shared among all .in microservices
  │  domain     │  (fs.in, net.in, gfx.in, ...)
  └──────┬──────┘
         │
  ┌──────┴──────┐
  │  guest      │  isolated per guest program
  │  domain     │  (Linux app, Darwin app, Windows app)
  └─────────────┘
```

The service domain hosts all `.in` microservices. Microservices communicate
through channels once CR3-backed domains are implemented. Guest domains are
intended not to directly access each other or the service domain.

Microservices CAN share an object graph region for performance (zero-copy
data sharing between fs.in and net.in, for example). Guest domains never
share memory with other guest domains or with services — they communicate
only through channels handled by their `*-compat.in` shim.

## Channel Protocol Design

Each microservice exposes a typed channel protocol. Example for `fs.in`:

```
Request:   { op: "open", path: "/home/user/file.txt", flags: O_RDWR }
Response:  { status: 0, fd: 7, cap: "cap:fs:file-0x3f2a" }

Request:   { op: "read", fd: 7, offset: 0, len: 4096 }
Response:  { status: 0, data: <bytes>, len: 256 }

Request:   { op: "close", fd: 7 }
Response:  { status: 0 }
```

Protocols use flat capability references (not opaque handles). The `cap`
field in a response is an unforgeable reference that the caller can use
to mint sub-capabilities or delegate to other components.

## Graphics Pipeline (gfx.in)

```
  Guest app (SDL, GTK, Win32, Cocoa)
       │   channel: "create_surface 800x600"
       │             "blit x=10 y=20 w=200 h=100 pixels=..."
       ▼
  ┌──────────────────────────────────┐
  │  gfx.in                          │
  │  compositor, surface manager,    │
  │  input router, cursor renderer   │
  └────────┬─────────────────────────┘
           │   blit to framebuffer / virtio-gpu
           ▼
  ┌──────────────────────────────────┐
  │  hw surface (framebuffer, GPU)   │
  └──────────────────────────────────┘
```

`gfx.in` is the only component with direct framebuffer or GPU MMIO access. All
other components (guests and services) create surfaces through `gfx.in`
channels. The compositor handles:

- Surface allocation and damage tracking
- Input event routing (keyboard, mouse, touch)
- Cursor rendering
- Window management (position, focus, minimize, close)
- Copy-paste between surfaces (cross-guest clipboard)

## Thread Model

Guest threads map to Space's cooperative M:N threading:

- `clone()` / `CreateThread()` / `pthread_create()` → `thr_create()` in the
  guest's memory domain
- Each thread has its own channel receive queue
- Threads yield cooperatively (no preemption)
- Preemption is available as a timer capability for real-time threads
- `linux-compat.in` maintains the thread list and handles scheduling

The shim manages thread-local storage (TLS) in the guest domain:

- Linux: `arch_prctl(ARCH_SET_FS)` → set FS.base in shim
- Darwin: `__thread_register` → allocate TLS in shim
- Windows: TEB in user mode → shim maintains TEB pointer

## Signal / Exception Delivery

Space already has fault handlers (page fault, divide error, #GP). The compat
shim extends them:

1. A fault occurs in the guest domain
2. The nanokernel delivers the fault to the shim's registered handler
3. The shim saves guest register state on the signal stack
4. The shim delivers a signal to the guest's signal handler
5. The guest handler runs, modifies saved registers if needed
6. The shim restores register state and returns from the fault

For async signals (SIGTERM, SIGINT):

1. `proc.in` sends a channel message to `linux-compat.in`
2. `linux-compat.in` injects the signal into the guest's signal handler
3. The guest thread is interrupted on next channel operation

## Filesystem Architecture

```
  Guest (POSIX: open, read, write, stat)
       │ channel to linux-compat.in
       ▼
  linux-compat.in  (translates POSIX → fs.in protocol)
       │ channel to fs.in
       ▼
  fs.in
       │
       ├── rootfs  (object-graph-backed root filesystem)
       ├── tmpfs   (in-memory scratch)
       ├── devfs   (device nodes → capability resolution)
       └── mount   (block device → filesystem driver)
```

`fs.in` is NOT a kernel filesystem. It is a `.in` component that:

- Maintains a directory tree as an object graph
- Mounts block devices through filesystem driver components (ext4.in, etc.)
- Routes file operations to the correct backing store
- Implements POSIX file permissions as capability checks
- Provides `stat`, `readdir`, `symlink`, `hardlink`, `chmod`, `chown` as
  channel operations

The root filesystem is pre-populated at boot time from an object graph
snapshot (not a disk image). Additional filesystems mount on top.

## Registry (Windows)

For Windows compatibility, the registry is a view over an object graph subtree
served by `win-compat.in`:

```
  HKLM\SYSTEM\CurrentControlSet\Services\... → obj:/services/tcpip/config
  HKCU\Software\Microsoft\Windows\...        → obj:/users/default/windows
```

`win-compat.in` translates `NtCreateKey`, `NtSetValueKey`, etc. into object
graph operations. The registry hierarchy exists only within the Windows
compatibility shim — it does not leak into the native object graph namespace.

## Mach IPC (Darwin)

Darwin's Mach IPC maps beautifully to Space channels because BOTH are
capability-based message passing:

| Mach Concept | Space Primitive |
|-------------|-----------------|
| Mach port | Channel endpoint (capability-gated) |
| `mach_msg` | Channel send + receive |
| Port rights (send, receive, send-once) | Capability attenuation |
| Out-of-line memory | VM object transfer over channel |
| Port name space | Per-realm channel endpoint table |
| `mach_port_allocate` | Channel creation + capability mint |
| `mach_port_deallocate` | Capability revocation |
| `mach_port_insert_right` | Capability delegation over channel |
| Bootstrapping | Component supervisor grants initial channel |

The `darwin-compat.in` shim maintains a port name space for the guest
and translates Mach messages to channel operations. The bootstrapping port
is connected to the component supervisor, which provides service resolution
via the same mechanism as launchd.

This is the cleanest mapping of the three personalities because Space channels
were designed with the same semantics as Mach messages.

## Windows Object Manager

NT's object manager provides a hierarchical namespace of named objects
(\\Device, \\BaseNamedObjects, \\Registry, \\??, etc.). `win-compat.in`
presents a virtual object namespace that routes to microservices:

| NT Path | Backing |
|---------|---------|
| `\Device\KeyboardClass0` | Channel to input service |
| `\Device\Video0` | Channel to gfx.in surface |
| `\BaseNamedObjects\*` | Realm-scoped named objects |
| `\Registry\*` | Object graph registry view |
| `\??\C:` | fs.in volume mount |

NT handles are capabilities wrapped in a handle table. The shim maintains
the handle table and translates `NtClose`, `NtDuplicateObject`, etc. into
capability operations. Handle inheritance across `NtCreateProcess` becomes
capability delegation to a new memory domain.

## Microservice Write Path

Each microservice is written in `.in` and compiled by Inauguration:

```in
// fs.in — filesystem service
component "space.services/fs" {
  target "x86_64-unknown-none"
  deterministic true
  checkpoint "on-request"
  
  import "core.channel"
  import "core.block-device"
  
  capability block-device: read-sectors(dev: Int, buf: Int, lba: Int, count: Int) -> Int
  capability channel: accept-request() -> Request
  capability channel: send-response(resp: Response) -> void
}

fn fs_main() -> void {
  let ch = channel_accept()
  while true {
    let req = channel_recv(ch)
    match req.op {
      "open"   => handle_open(req.path, req.flags)
      "read"   => handle_read(req.fd, req.offset, req.len)
      "write"  => handle_write(req.fd, req.offset, req.data)
      "close"  => handle_close(req.fd)
      "stat"   => handle_stat(req.path)
      "readdir" => handle_readdir(req.path)
      _        => send_error(ch, EINVAL)
    }
  }
}
```

## How The Nanokernel Sees This

The nanokernel sees only:

```
channel endpoints
capability tables
memory domains
threads
```

It does NOT know about:

- ELF, PE, or Mach-O
- POSIX, Win32, or Cocoa
- Filesystems, sockets, or windows
- Processes, users, or signals

All of those are `.in` components. The nanokernel just enforces boundaries
and delivers messages. The microservices define what the OS looks like.

## Boot Flow With Microservices

```
1. Nanokernel boots (kernel-root.in)
   - Memory domains
   - Channel fabric
   - Capability root
   - Object graph arena

2. Component supervisor boots
   - Loads microservice manifests
   - Creates channels for each service
   - Grants declared capabilities

3. Core microservices start:
   ┌─ proc.in    (process lifecycle)
   ├─ fs.in      (filesystem)
   ├─ net.in     (networking)
   ├─ gfx.in     (compositor)
   ├─ time.in    (clocks)
   ├─ mem.in     (memory management)
   ├─ rand.in    (randomness)
   └─ ...        (audio, GPU, sensors)

4. Guest loader available:
   ┌─ loader.in  (ELF/PE/Mach-O parser)
   ├─ linux-compat.in
   ├─ darwin-compat.in
   └─ win-compat.in

5. User launches a program:
   - loader.in opens the binary
   - Creates a new memory domain
   - Loads the binary + shim
   - Connects shim to compat service
   - Program runs
```

## Implementation Order

### Phase 1: Microservice Framework (nanokernel + core services)

| Step | Component | What |
|------|-----------|------|
| 1 | kernel-root.in | Channel fabric, memory domains, capability tables |
| 2 | proc.in | spawn guest domain, exit, wait, thread list |
| 3 | mem.in | mmap-like, brk, shm_open in guest domain |
| 4 | time.in | sleep, clock_gettime, timer_create |
| 5 | rand.in | getrandom via RDRAND |

### Phase 2: Linux Compat

| Step | Component | What |
|------|-----------|------|
| 6 | fs.in | Directory tree, file ops, mount |
| 7 | net.in | Sockets, connect, send, recv |
| 8 | loader.in | ELF parser, segment mapper |
| 9 | linux-shim.in | Guest libc shim (channel-based), fd table, TLS |
| 10 | linux-compat.in | POSIX → microservice dispatch |

### Phase 3: Darwin Compat

| Step | Component | What |
|------|-----------|------|
| 11 | loader.in | Mach-O + FAT binary support |
| 12 | darwin-shim.in | Mach message → channel, dyld |
| 13 | darwin-compat.in | Dispatch to core services |

### Phase 4: Windows Compat

| Step | Component | What |
|------|-----------|------|
| 14 | loader.in | PE/COFF support, IAT resolution |
| 15 | win-shim.in | NT syscall → channel, handle table |
| 16 | win-compat.in | Registry, object namespace, Win32 dispatch |

### Phase 5: Graphics

| Step | Component | What |
|------|-----------|------|
| 17 | gfx.in | Compositor, surface manager, input |
| 18 | linux-compat.in | Wayland/X11 surface → gfx.in channel |
| 19 | win-compat.in | Win32 GDI/USER → gfx.in channel |
| 20 | darwin-compat.in | Cocoa/AppKit → gfx.in channel |

## First Actionable Step

The first thing to build is the **microservice channel framework** — the
nanokernel primitives that let a `.in` component declare a channel endpoint,
accept requests, and send responses. This already partially exists (channels
in kernel-root.in). The next step is a `proc.in` that can spawn a new memory
domain and load a binary into it.

After that, the path is:

```
proc.in (spawn + domain)
  → loader.in (ELF load)
    → linux-shim.in (guest libc with channel I/O)
      → "hello world" from a real Linux binary
```

No syscall traps. No kernel personality code. Just `.in` microservices
talking over channels.
