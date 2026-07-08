# Space Architecture

```
         ┌─────────────────────────────────────┐
         │              Space                   │
         │     operating system, component      │
         │     runtime, capability fabric       │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │              SCI                     │
         │  Space Component Image format       │
         │  replaces ELF as native contract    │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │          Inauguration                │
         │  compiler — the real OS contract     │
         │  generates authority, graphs, SCI   │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │              .in                     │
         │  native language — describes         │
         │  components, capabilities, objects   │
         └──────────────────────────────────────┘
```

Each layer exists to make the layer above possible.

---

## .in

.in is the native language. It describes components, capabilities, objects,
effects, and execution graphs as language-level concepts, not runtime
annotations.

```in
component KernelRoot {
  target "x86_64-unknown-none"
  deterministic true
  checkpoint none

  export boot: BootEntry
  capability serial: DebugConsole(write)
  capability memory: PhysicalMemory(discover, map)
}
```

The compiler extracts capability manifests, object schemas, and execution
graphs from these declarations and emits them into the SCI artifact.

---

## Inauguration

Inauguration is the compiler. It lowers `.in` source through a frontend
(parser, typechecker, verifier) into Core IR, runs analysis passes
(capability graph, execution graph, object schema, effect tracking,
determinism), and emits SCI artifacts containing machine code plus
metadata manifests.

Multi-language support: Rust, Go, Swift, C, and other frontends all
lower into the same Core IR, so capability analysis and SCI emission
work across languages.

---

## SCI (Space Component Image)

SCI is the native binary contract — not ELF. An SCI artifact contains:

- Code sections (x86_64 machine code)
- Capability manifest (declared authority)
- Object schema manifest (struct definitions)
- Import/export table
- Provenance (compiler version, source hash)

The loader validates declared capabilities against the realm's grants
before transferring control. A component requesting undeclared
capabilities is denied before its entry point runs.

---

## Nanokernel

The nanokernel (`kernel-root.in`) is the root component. It runs in
long mode after the boot trampoline (`boot/multiboot.asm`) enters
x86_64. It provides:

- **Serial console** — COM1 UART output and interactive shell
- **Physical memory discovery** — Multiboot1 memory map parsing
- **Virtual memory** — 4 KiB page table walking and mapping
- **Object graph** — arena-allocated objects with checkpoint/restore
- **Capability table** — mint and track authority per realm
- **Interrupts** — IDT, 8259 PIC, PIT timer, exception handlers
- **Component supervisor** — validates and activates components
- **Cooperative scheduler** — M:N threading with ctxsw, blocking, yield
- **Preemptive scheduler** — timer-driven context switching
- **Typed channels** — CSP-style ring buffers with blocking send/recv
- **Cross-domain channels** — shared-page IPC between memory domains
- **Memory domains** — isolated page table trees (Phase 0)
- **SCI loader** — loads and validates external component images
- **e1000 NIC driver** — MMIO register access, TX/RX rings, ARP, UDP
- **Deterministic execution** — xorshift64 PRNG with seeded workloads
- **NVMe storage** — PCIe NVMe controller driver with admin/I/O queues
- **Flat filesystem** — superblock + file table + data area on NVMe disk
- **Process abstraction** — process table with lifecycle (spawn, exit, wait, kill)
- **Syscall interface** — int 0x80 trap with DPL=3, dispatch table, core syscalls
- **Linux personality** — POSIX syscall translation layer (Phase 5)
- **USB xHCI** — host controller + HID keyboard driver
- **VBE framebuffer** — Bochs VBE graphics mode, drawing primitives, bitmap font
- **PS/2 mouse** — polling-based mouse driver with packet parsing
- **Compositor** — Wayland-style window manager with desktop rendering

---

## Memory Domains

Domains are isolated page table trees. Domain 0 is the kernel domain
(shared PML4 at physical 0x1000). `domain_create()` allocates a new
PML4, copies the kernel's low mappings, and returns an ID.
`domain_switch()` changes CR3. `domain_map()` installs a mapping in
a domain's page table. Shared pages enable cross-domain IPC.

---

## Components

Components are registered as objects in the graph with a name, entry
address, and required capabilities. The supervisor checks required
caps against the realm's grants before invoking the entry point.

The SCI loader extends this to external components: it reads a binary
manifest from memory, validates capabilities, creates a domain, maps
the component image, and transfers control.

---

## Capabilities

Capability slots are 16 bytes: `[target_object_ptr][rights]`. The
kernel mints capabilities into a root table. Capability bits:

| Bit | Capability |
|-----|-----------|
| 1   | serial    |
| 2   | timer     |
| 4   | memory    |
| 8   | graph     |

The loader rule: a component may only activate if its declared
authority is a subset of what its realm grants.

---

## Objects

Objects live in a dedicated arena (32 bytes each:
`[id][type_tag][ref0][ref1]`). The arena can be checkpointed and
restored independently of kernel state.

---

## Channels

In-address-space channels are ring buffers with poll-with-yield
blocking. Cross-domain channels use shared physical pages mapped into
both domains' page tables.

---

## Syscall Interface

User programs request kernel services via `int 0x80`. The assembly stub
saves all 15 GP registers into a frame on the stack and calls
`syscall_dispatch` with a pointer to that frame. The dispatch function
reads the syscall number from RAX and arguments from RDI, RSI, RDX,
then writes the return value back into the RAX slot for `iretq` to
deliver to the caller. The IDT entry for vector 0x80 has DPL=3, so
user-mode code can invoke it directly.

Native Space syscalls (0-4): write, read, exit, yield, getpid.

---

## Linux Personality

The Linux personality (`kernel/linux.in`) translates Linux x86_64
syscall numbers into Space kernel primitives, providing a POSIX-compatible
interface on top of the native component model. This is the first OS
personality (Phase 5), demonstrating that Space can host foreign ABIs
by mapping their conventions onto the underlying capability/domain/channel
substrate.

Implemented POSIX syscalls:

| Linux # | Syscall    | Space mapping                          |
|---------|-----------|----------------------------------------|
| 0       | read      | serial (fd 0) or filesystem (fd 3+)    |
| 1       | write     | serial (fd 1/2) or filesystem (fd 3+)  |
| 2       | open      | fs_find / fs_write_file + FD table     |
| 3       | close     | FD table entry clear                   |
| 4       | stat      | fs_find + stat struct fill             |
| 5       | fstat     | FD table lookup + stat struct fill     |
| 8       | lseek     | FD table offset update                 |
| 9       | mmap      | kernel heap alloc + optional file map  |
| 11      | munmap    | no-op (bump heap)                      |
| 12      | brk       | program break tracking                 |
| 39      | getpid    | current_task                           |
| 57      | fork      | proc_create (simplified)               |
| 59      | execve    | ENOSYS (not yet implemented)           |
| 60      | exit      | halt                                   |
| 61      | wait4     | proc_wait                              |
| 62      | kill      | proc_kill                              |
| 79      | getcwd    | linux_cwd                              |
| 80      | chdir     | linux_cwd update                       |

The FD table maps Linux file descriptors to Space filesystem entries.
fds 0-2 are pre-opened std streams (serial console); fds 3+ are open
files on the Space filesystem.

---

## Framebuffer

The VBE framebuffer driver (`kernel/fb.in`) uses Bochs VBE I/O ports
(0x1CE/0x1CF) to set a 1024x768x32 graphics mode with linear framebuffer.
The framebuffer address is discovered by scanning PCI for a VGA display
device (class 0x030000) and reading BAR0. The boot trampoline identity-maps
the first 4 GiB so the framebuffer MMIO region (typically 0xFD000000) is
accessible.

Drawing primitives: pixels, rectangles, lines (Bresenham), and bitmap text
(8x8 font with ASCII subset). The compositor uses these to render windows,
title bars, taskbar, and mouse cursor.

---

## Compositor

The compositor (`kernel/compositor.in`) is a Wayland-style display server
that manages windows and renders them to the framebuffer. It provides:

- **Window management** — create, focus, drag, and render windows
- **Title bars** — clickable, draggable window decorations
- **Taskbar** — bottom bar with system info and mouse state
- **Mouse cursor** — arrow cursor rendered on top of all windows
- **Input handling** — PS/2 mouse polling, keyboard via serial

The `desktop` shell command launches the compositor. Three default windows
are created: Terminal, File Browser, and System Info. Press ESC to exit.

---

## Ring Architecture

Space enforces a strict ring separation. Ring 0 is the smallest possible
nanokernel. Everything else is a ring-3 SCI component.

### Ring 0 — Nanokernel Core

```
boot/multiboot.asm      x86_64 bring-up
serial.in               debug console (COM1)
memory.in               physical memory discovery + frame allocator
interrupts.in           IDT, PIC, PIT
syscall.in              trap dispatcher (int 0x80, DPL=3)
domain.in               page table management, memory domains
channel.in              cross-domain shared-page IPC
sched.in                cooperative scheduler
object.in               object arena + capability table
kernel-root.in          bootstrap + SCI component loader
```

These are the only files that run in ring 0. Everything below is a
ring-3 component.

### Ring 3 — Components

All drivers, filesystems, services, and personalities live in isolated
memory domains with declared capabilities and channel-based IPC:

| Category | Components |
|----------|-----------|
| Drivers | PCI, NVMe, e1000, USB, framebuffer, PS/2 mouse |
| Filesystem | SparkFS block/inode/dir/path, VFS |
| Services | Process manager, shell, compositor, time, display, input |
| Personalities | Linux/POSIX, Windows NT |
| Libraries | libc (compiled via Inauguration's C/C++/Rust frontend, not .in) |

Ring-3 components cannot access kernel memory, cannot modify page tables,
and can only communicate via shared-page channels with capability-gated
IPC. The kernel validates every component's declared capabilities at
load time.

This architecture ensures that a bug in the USB driver, e1000 driver, or
personality server cannot corrupt the kernel.

## Current Status

### Running Today
- Nanokernel boots x86_64 long mode under QEMU
- Serial console, physical memory discovery, page tables
- Object graph arena, capability table, bootstrap realm
- Cooperative + preemptive multitasking
- Cross-domain shared-page channels
- SCI manifest loader with capability-mask validation
- Interactive shell (20+ commands)
- e1000 NIC driver (UDP transmit, ARP)
- Memory domain isolation
- NVMe storage driver and SparkFS filesystem
- Process abstraction with lifecycle management
- Syscall interface (int 0x80) with DPL=3
- VBE framebuffer (1024x768x32 — QEMU-only)
- Wayland-style compositor (QEMU-only demo, not real GPU HW)
- PS/2 mouse driver
- Linux personality (POSIX syscall translation — currently in-kernel, moving to ring 3)
- Deterministic execution demo (xorshift64 PRNG, single-core only)

### Repository Layout

```
kernel/
  kernel-root.in        nanokernel root component
  domain.in             memory domain subsystem
  channel.in            cross-domain channel fabric
  net.in                e1000 NIC driver
  pci.in                PCI bus enumeration
  nvme.in               NVMe storage driver
  usb.in                USB xHCI + HID keyboard driver
  fs.in                 flat filesystem layer
  process.in            process abstraction layer
  libc.in               C standard library equivalent
  linux.in              Linux personality (POSIX syscalls)
  fb.in                 VBE framebuffer driver + bitmap font
  mouse.in              PS/2 mouse driver
  compositor.in         Wayland-style window manager + desktop
  guest-service.in      SCI guest component example
boot/
  multiboot.asm         x86_64 CPU bring-up
scripts/
  check-qemu-boot.sh    Full boot verification
  check-sci-contract.sh SCI metadata validation
  build-multicomponent.sh  Multi-component image build
  check-network.sh      Network driver test
sci-schema.md           SCI format specification
```
