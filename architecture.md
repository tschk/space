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
| 59      | execve    | load SCI/ELF image from volume or sparkfs |
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

## Current Status

### Verified Today
- Nanokernel enters x86_64 long mode under QEMU.
- The maintained checks verify the serial shell, in-kernel SCI loader
  self-test, Linux-personality demo, VFS, time service, network traffic,
  component deny policy, and external display/input SCI components.
- SCI metadata-sidecar validation passes.
- Display and input SCI components boot in isolated domains under an automated
  QEMU check.

### Component Transition
- Storage, network, and POSIX source has moved into `components/`, with
  kernel-side transition wrappers.
- Storage starts and creates SQ1/CQ1 under QEMU, but its first real I/O command
  times out; the successful Linux demo uses the memory-backed SparkFS fallback.
- Network has a passing component RPC/pcap check. POSIX dispatch runs through a
  component service thread.
- Display and input are optional boot-image SCI components. The memory-backed
  Volume SCI component completes init, write, and read RPCs under QEMU.
- SCI allow and deny paths are proven with per-image grants.
- The full SparkFS Volume source remains separate from the memory-backed SCI
  component and is not yet routed through POSIX.

### Repository Layout

```
kernel/
  kernel-root.in        nanokernel root component + boot entry
  guest-service.in      SCI guest component example
  v86-kernel.in         32-bit browser demo kernel
components/
  channel.in            cross-domain channel fabric
  domain.in             memory domain subsystem
  serial.in memory.in object.in interrupts.in syscall.in
  sched.in process.in shell.in libc.in linux.in vfs.in
  net.in nvme.in usb.in fb.in mouse.in compositor.in
  pci.in filesystem.in fs2-*.in storage.in network.in posix.in
  supervisor.in preempt.in sci-loader.in selftest.in
  diagnostics.in determinism.in editor.in time.in
  display.in input.in volume.in font.in
  volume-mem.in         standalone memory-backed Volume SCI component
boot/
  multiboot.asm         x86_64 CPU bring-up
scripts/
  check-qemu-boot.sh    Full boot verification
  check-sci-contract.sh SCI metadata validation
  build-multicomponent.sh  Multi-component image build
  check-network.sh      Network driver test
sci-schema.md           SCI format specification
```
