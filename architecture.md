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

The loader compares a component's self-declared capability bitmask to a
kernel grant constant (packed SCI) or `SCI-GUEST-GRANTS` (file SCI) and
denies a superset. That is not hardware isolation. Syscalls consult
`cap-check` against the current domain's minted cap index; mint/revoke
from userspace return `-1`.

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
- **Memory domains** — per-component page tables that currently clone the 4 GiB identity map (not a security boundary)
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

Domains are separate page-table trees, not a security boundary today.

- Domain 0 is the kernel domain. After boot the live kernel PML4 is relocated
  off physical `0x1000` onto a heap frame.
- `domain_create()` allocates a new PML4 and **copies the kernel's four page
  directories** — the trampoline's 4 GiB identity map (`P|W|PS`, no NX).
  Extra SCI image/heap/shared mappings are additive. A guest can still
  `load64(0x200000)` (kernel globals) and reach MMIO.
- All component entry is CPL0 (`CS=0x08`). The GDT has no DPL3 segments.
  `cr3_write` is bound into a kernel global at `domain-init` and the
  published pointer at `0x4060` is cleared; guests still run at ring 0, so
  they can execute privileged instructions until CPL3+`iret` exists.
- `domain_switch()` changes CR3. `domain_map()` installs a mapping.
  Shared pages are for IPC, not isolation.

Exclusive maps plus CPL3 are required before domains can be advertised as
isolation. Do not land exclusive maps without a CPL3 trampoline: `invoke1`
under guest CR3 still needs kernel text mapped.

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
kernel mints capabilities into a root table. Each domain records a cap
index; `sys-write` / `sys-read` require `cap-serial`, channel syscalls
require `cap-graph`. `sys-cap-mint` / `sys-cap-revoke` always return `-1`.
`sys-cap-check` may only query the caller's current cap.

| Bit | Capability |
|-----|-----------|
| 1   | serial    |
| 2   | timer     |
| 4   | memory    |
| 8   | graph     |

The loader rule: a component may only activate if its declared
authority is a subset of the grant mask for that load path. Bits are
metadata plus syscall gates; they do not stop CPL0 `inb`/`outb`.

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

The Linux personality (`components/linux.in`) is **kernel-linked**. It
translates Linux x86_64 syscall numbers into Space kernel primitives.
`linux-init` may `domain-switch` into a POSIX helper domain, but the
translator is the same boot image as the nanokernel, not an isolated
microservice.

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

The VBE framebuffer driver lives in `components/display.in` (linked into the
kernel). It uses Bochs VBE I/O ports (0x1CE/0x1CF) for a 1920×1080×32 linear
framebuffer. BAR0 is discovered via PCI class 0x030000. The boot trampoline
identity-maps the first 4 GiB so MMIO (typically 0xFD000000) is reachable.

Drawing primitives: pixels, rectangles, lines, and scaled bitmap text
(`components/font.in`). `font.in` also builds grayscale coverage masks from the
1-bit glyphs; `fb-draw-char-aa` blends them at 2x scale for soft-edged chrome
text (title bars, top bar). The terminal keeps the bitmap fast path. The
compositor uses these for windows, bars, and cursor.

---

## Compositor

The compositor is also in `components/display.in` (not a separate stub file).
It manages windows and paints the framebuffer:

- **Damage-rect compositing** — only the pending damage rect is recomposed into
  the backbuffer (background + intersecting windows, bottom-up) and blitted;
  the cursor is reconciled on the real framebuffer. Event handlers accumulate
  damage instead of forcing full-screen redraws. Measured on M3 TCG: 19 fps
  eager full-screen → 38 fps damage-rect for a moving-window workload
  (`scripts/check-desktop-damage.sh`).
- **Window management** — create, focus, drag, resize, z-order; resize-corner
  grip; taskbar window buttons with overflow clamp.
- **Per-window translucency** — windows carry an alpha byte; translucent
  windows render into a per-window surface and blend over the composed desktop
  (UTILITIES uses alpha=180).
- **Dual terminals** — role TERMINAL with scrollback ring + fetch mode
- **Title bars / taskbar / top bar** — decorations and focus chrome
- **Mouse cursor** — arrow with backbuffer restore
- **Input** — real PS/2 keyboard+mouse (`components/mouse.in`); USB HID still
  stubbed in-kernel (`components/usb.in`), full xHCI lives in SCI `input.in`

Shell command `desktop` runs `comp-run` until ESC (serial or PS/2). The SPDP
surface pipeline (`dsp-*` in the same file) is exercised by the `dsp demo`
command (`scripts/check-spdp-composite.sh`); the compositor/client split is
designed in `docs/compositor-client-split.md`.

---

## Current Status

### Verified Today
- Nanokernel enters x86_64 long mode under QEMU.
- The maintained checks verify the serial shell, in-kernel SCI loader
  self-test, Linux-personality demo, VFS, time service, network traffic,
  component deny policy, and external display/input SCI components.
- SCI metadata-sidecar validation passes.
- Display and input SCI components boot in separate (still identity-mapped,
  CPL0) domains under an automated QEMU check.

### Component Transition
- Storage, network, and POSIX source has moved into `components/`, with
  kernel-side transition wrappers.
- Storage starts and creates SQ1/CQ1 under QEMU, but its first real I/O command
  times out; the successful Linux demo uses the memory-backed SparkFS fallback.
- Network has a passing component RPC/pcap check. POSIX dispatch runs through a
  component service thread.
- Display/compositor/fb are kernel-linked via `components/display.in`.
  Optional SCI display/input still load on full runtime images.
  Volume SCI completes init/write/read RPCs under QEMU.
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
  net.in nvme.in usb.in mouse.in display.in font.in
  pci.in filesystem.in fs2-*.in storage.in network.in posix.in
  supervisor.in preempt.in sci-loader.in selftest.in
  diagnostics.in determinism.in editor.in time.in
  input.in volume.in display-standalone.in
  windows.in darwin.in linux.in
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
