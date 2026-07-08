# Space OS Roadmap

## Principle: nanokernel core only in ring 0

Everything that isn't boot, memory, traps, domains, channels, and scheduler
lives in a ring-3 component with its own memory domain, declared capabilities,
and channel-based IPC.

Drivers, filesystems, personalities, libc, compositor, shell — all ring 3.

---

## Phase 0: Nanokernel Core (current — ring 0 only)

The smallest thing that boots x86_64 long mode and enforces isolation.

| Component | Status | Notes |
|-----------|--------|-------|
| x86_64 boot (multiboot.asm) | ✅ | 32→64 trampoline |
| Serial COM1 | ✅ | debug console, polling |
| Physical memory discovery | ✅ | multiboot memory map |
| Frame allocator | ✅ | bump allocator |
| Page tables (4-level) | ✅ | identity map first 4 GiB |
| IDT / PIC / PIT (100 Hz) | ✅ | interrupt dispatch |
| Memory domains (isolated PML4) | ✅ | per-component page trees |
| Cross-domain shared-page channels | ✅ | ring-buffer IPC |
| Cooperative scheduler | ✅ | M:N threading |
| Syscall trap (int 0x80, DPL=3) | ✅ | dispatch table |
| Object arena + capability table | ✅ | 16-byte cap slots |
| Preemptive scheduler | ✅ | timer-driven context switch |

**Ring 0 scope ends here.** Everything below is a ring-3 component.

---

## Phase 1: Ring-3 Component Migration

Move every driver and subsystem out of the kernel. Each component gets
its own memory domain, capability declaration, and channel interface.

### Boot-critical (cannot be deferred — needed before ring-3 runs)

| Component | Status | Path |
|-----------|--------|------|
| Domain subsystem | ✅ (ring 0) | `kernel/domain.in` |
| Channel fabric | ✅ (ring 0) | `kernel/channel.in` |
| Scheduler | ✅ (ring 0) | `kernel/sched.in` |
| SCI component loader | ✅ (ring 0) | `kernel/kernel-root.in` |
| Basic serial (boot logging) | ✅ (ring 0) | `kernel/serial.in` (minimal) |

### Drivers (move to ring 3)

| Component | Status | Notes |
|-----------|--------|-------|
| PCI bus enumeration | ❌ in kernel | → ring-3 component: `components/pci.in` |
| NVMe storage driver | 🔄 in kernel | planned move, provides block I/O |
| e1000 NIC driver | ❌ in kernel | → ring-3 component: `components/net.in` |
| USB xHCI controller | ❌ in kernel | → ring-3 component |
| PS/2 mouse | ❌ in kernel | → ring-3 component |
| VBE framebuffer | ❌ in kernel | → ring-3 component (QEMU-only VBE, not real GPU) |
| PS/2 keyboard | ❌ in kernel | → ring-3 component |

### Filesystem (move to ring 3)

| Component | Status | Notes |
|-----------|--------|-------|
| SparkFS block layer | ❌ in kernel | → ring-3 component |
| SparkFS inode/dir/path | ❌ in kernel | → ring-3 component |
| VFS abstraction | ❌ in kernel | → ring-3 component |

### Services (move to ring 3)

| Component | Status | Notes |
|-----------|--------|-------|
| Process manager | ❌ in kernel | → ring-3 component |
| Compositor | ❌ in kernel | → ring-3; QEMU-only demo, not real GPU HW |
| Font renderer | ❌ in kernel | → library used by compositor |
| Display server (SPDP) | ✅ ring 3 | already `services/display.in` |
| Input service | ✅ ring 3 | already `services/input.in` |
| Time service | ❌ in kernel | → ring-3 component |
| Shell | ❌ in kernel | → ring-3 component |

### Libc (replace with multi-language compilation)

| Component | Status | Notes |
|-----------|--------|-------|
| libc.in (925 lines) | ❌ in kernel | → remove; use Inauguration multi-language frontend |
| C compiled via Inauguration | 🔄 planned | compile C stdlib through Inauguration for Space targets |
| C++ compiled via Inauguration | 🔄 planned | compile C++ stdlib through Inauguration |
| Rust compiled via Inauguration | 🔄 planned | compile Rust stdlib through Inauguration |

The libc.in file reimplements string.h, stdlib.h, ctype.h, math.h, stdio.h
in .in — each bugfix is done twice (once in .in, once for the actual C
compiler). Inauguration already supports C, C++, and Rust frontends that
lower to the same Core IR. Use those instead.

### Personalities (move to ring 3)

| Component | Status | Notes |
|-----------|--------|-------|
| Linux/POSIX personality | ❌ in kernel | → ring-3 component; `components/posix.in` exists but kernel dispatches |
| Windows NT personality | 🔄 planned | full design at `docs/superpowers/specs/2026-07-08-windows-personality-design.md` |

---

## Phase 2: OS Personalities

Seamless Windows and Linux program execution on Space.

### Linux Personality

- [ ] Move POSIX dispatch from kernel to ring-3 component
- [ ] POSIX shared-page RPC protocol (kernel ↔ posix component)
- [ ] Socket syscalls: socket, bind, listen, accept, connect, send, recv
- [ ] Signal handling: SIGTERM, SIGKILL
- [ ] ELF loader for ELF64 binaries
- [ ] FD table mapped to VFS

### Windows NT Personality

Full design in `docs/superpowers/specs/2026-07-08-windows-personality-design.md`.

- [ ] PE32+ loader
- [ ] NT function endpoints (fn NtCreateFile, fn NtReadFile, etc.)
- [ ] NT executive: Object Manager, Process Manager, I/O Manager
- [ ] ntdll, kernel32, user32 (ring 3)
- [ ] Windows console app support
- [ ] Windows GUI support (depends on compositor)

---

## Phase 3: Networking

Not a priority until ring-3 migration is complete.

- [ ] TCP/IP stack (SYN/ACK, sliding window, retransmit)
- [ ] Socket API for user programs
- [ ] DHCP client
- [ ] DNS resolver
- [ ] Winsock (ws2_32) → Space network channels (for Windows personality)

---

## Phase 4: Real Hardware Support

Current drivers are QEMU-only (VBE Bochs, e1000 emulated, NVMe emulated).

- [ ] Real framebuffer: Intel GTT / modesetting
- [ ] Real NIC: Intel PRO/1000, Realtek RTL8139
- [ ] Real NVMe: AHCI fallback
- [ ] ATA/PIO driver (QEMU IDE disk)
- [ ] USB 3.0 real hardware support
- [ ] SMP (multiprocessor boot + scheduler)

---

## Phase 5: Self-hosting

- [ ] Inauguration compiler runs on Space
- [ ] Space compiles itself from .in source
- [ ] .in language tooling (LSP, formatter) runs on Space

---

## Current Limitations (honest)

| Area | Limitation |
|------|-----------|
| Compositor | QEMU VBE only. Bochs VBE is not available on real GPUs. Real GPU drivers (Intel/AMD/NVIDIA) require GEM/KMS or proprietary interfaces that are ~100x more complex than VBE. |
| Deterministic execution | xorshift64 on single core. Real determinism requires deadline scheduling, priority inheritance, and hardware with guaranteed timing. Not there yet. |
| Ring 3 isolation | Domain isolation works (separate page tables) but all code still runs in ring 0. No syscall/sysenter MSR setup for proper user-mode. Shared-page IPC is cooperative. |
| Networking | UDP transmit + ARP only. No TCP, no IP routing, no socket API. |
| PCI | Configuration space scan only. No MSI-X, no hotplug, no ACPI. |
| USB | xHCI works for HID keyboards only. No mass storage, no isochronous, no hub support. |
