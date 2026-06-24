# Space

Space is a component-based operating system built on a five-layer architecture:

```
       .in          ← native language
       ↑
 Inauguration       ← compiler — the real OS contract
       ↑
      SCI           ← component image format (replaces ELF)
       ↑
    Space           ← operating system, component runtime
       ↑
 Nanokernel         ← hardware enforcement layer
```

Each layer exists to make the layer above possible.

The native model is **component + capability + object + execution graph** — not
process + file + syscall + user. There is no POSIX in the kernel. Linux, Darwin,
and Windows compatibility are `.in` microservices that translate legacy concepts
into Space primitives.

The compiler is the constitutional layer. The nanokernel is the enforcement
layer.

## Architecture

- [`architecture.md`](architecture.md) — system architecture and
  implemented subsystems
- [`sci-schema.md`](sci-schema.md) — Space Component Image metadata format
- [`AGENTS.md`](AGENTS.md) — repository workflow and boundaries

## Status: it boots

The nanokernel root, written in `.in` and compiled by
[Inauguration](https://github.com/tschk/inauguration), boots to x86_64 long
mode under QEMU and verifies the boot-critical subsystems on every boot.

Current boot output (timing varies by host):

```
space: kernel root entered
space: object arena 0x...
space: bootstrap realm object id 0x...
space: interrupts enabled (PIC remapped, PIT 100Hz)
space: timer ticks (sample)
space: supervisor loaded, component enforcing
space: scheduler quiesced after 3 round-robin passes
space: channel demo complete, remaining 0x0000000000000000
space: preemptive workers interleaved, switching OK
space interactive shell -- type 'help'
space>
```

## Benchmarks

### Boot image size (x86_64-unknown-none flat binary)

| Component | Size |
|-----------|------|
| Trampoline (multiboot + long-mode bring-up) | 4,096 B |
| SCI header | 256 B |
| Kernel code (compiled `.in`) | 160,120 B |
| **Total boot image** | **164,472 B** |

The kernel includes: serial shell with 25+ commands, framebuffer/compositor,
PS/2 mouse driver, e1000 NIC driver, NVMe/ATA disk driver, flat filesystem,
USB xHCI host controller driver, memory domain subsystem, component
supervisor, cooperative + preemptive scheduler, channel IPC, checkpoint/
restore, SCI loader, Linux personality layer.

### Compile speed (Inauguration v0.6.5, macOS ARM64)

```
benchmark                          time
----------------------------------------------------------
parse_textual_sil/representative   44.6 µs  (-5.9% vs v0.5.2)
remove_debug_insts/representative  26.3 µs  (-4.8% vs v0.5.2)
extract_call_graph/representative  25.2 µs  (-1.0% vs v0.5.2)
core_opt_optimize (10 fn + 100 call)  69.3 µs
```

### Runtime throughput (QEMU x86_64, emulated PIT 100Hz)

Measured during boot: preemptive scheduler runs two worker threads at 100Hz.
Each worker performs arithmetic loops. Typical output:
```
worker A iters ~3,200,000  worker B iters ~3,200,000
```
This gives ~640M iterations/second shared across 2 threads at 100Hz,
equivalent to ~320M iters/s/thread in QEMU emulation.

### Running Subsystems

The kernel is ~80 declarations in ~1300 lines of `.in`, compiled by
Inauguration into a ~160 KiB boot image:

| Subsystem | Status |
|-----------|--------|
| x86_64 long mode boot (Multiboot1) | ✅ |
| Serial console (COM1) | ✅ |
| Physical memory discovery | ✅ |
| Bump heap + 4K frame allocator | ✅ |
| Kernel 4-level page table management | ✅ |
| CR3-backed domain switching + private low page-table roots | ✅ |
| Object graph arena (typed objects, stable IDs) | ✅ |
| Capability table (minting, runtime check) | ✅ |
| IDT (256-entry), PIC remap, PIT 100Hz | ✅ |
| CPU exception handling (PF, #DE, #GP, #UD) | ✅ |
| Component supervisor (SCI loader rule) | ✅ |
| Cooperative M:N threading | ✅ |
| Preemptive multitasking (timer context switch) | ✅ |
| Typed IPC channels (ring buffer, poll-with-yield) | ✅ |
| Cross-domain shared-page channels | ✅ |
| Checkpoint / restore (object graph + memory) | ✅ |
| SCI loader (domain-mapped virtual component call, manifest/cap validation) | ✅ |
| e1000 NIC driver (PCI, ARP, UDP) | ✅ |
| Deterministic execution subsystem | ✅ |
| Interactive shell (16 commands) | ✅ |

## Target Architectures

| Arch | Compiler Status | Kernel Status |
|------|----------------|---------------|
| x86_64 | ✅ Native lowering, boot image, ELF object | ✅ Boots verified subsystems |
| ARM64 | ⬜ Planned (SCI table) | ⬜ |
| RISC-V | ⬜ | ⬜ |

The Inauguration compiler emits freestanding x86_64 code with SCI metadata for the verified kernel contract.
Multi-platform lowering is a target for future phases.

## Build and Run

Requirements: `clang`, `nasm`, `qemu-system-x86_64`, and Inauguration
checked out at `../inauguration`.

```sh
# Full boot check (compiles kernel, boots QEMU, asserts boot-critical subsystems)
bash scripts/check-qemu-boot.sh

# SCI component loading demo
bash scripts/build-multicomponent.sh

# SCI metadata validation
bash scripts/check-sci-contract.sh

# Network driver test
bash scripts/check-network.sh
```

Development is cross-platform — macOS (ARM64), Linux (x86_64).

## Repository Layout

```
kernel/
  kernel-root.in          nanokernel root component
  domain.in               memory domain subsystem
  channel.in              cross-domain channel fabric
  net.in                  e1000 NIC driver
  pci.in                  PCI bus enumeration
  guest-service.in        SCI guest component example
boot/
  multiboot.asm           x86_64 CPU bring-up (32-bit → long mode)
scripts/
  check-qemu-boot.sh      Full boot verification
  build-multicomponent.sh SCI loading demo
  check-sci-contract.sh   Metadata validation
  check-network.sh        Network driver test
```

## Relationship to Inauguration

Per [AGENTS.md](AGENTS.md), Space owns the OS contracts, examples, SCI profile,
and boot plan.

The [Inauguration](https://github.com/tschk/inauguration) compiler owns generic
compiler capabilities:

- freestanding target support (`x86_64-unknown-none`)
- SCI-compatible component metadata emission
- native x86_64 lowering, instruction encoding, boot image assembly
- Core IR optimization (inlining, constant folding, DCE, dead func elim)
- multi-frontend support (.in, Rust, Go, V, OCaml, Tree-sitter polyglot)

Inauguration does not depend on this repository. Space does not add
Space-branded targets to Inauguration.

### The Compiler Contract

```text
  .in source
       │
       ▼
  Inauguration
       │
       ├── code (machine code, data)
       ├── capabilities (required and exported)
       ├── object schemas
       ├── imports / exports
       ├── scheduling hints
       ├── checkpoint policy
       ├── determinism flags
       ├── migration metadata
       └── provenance
       │
       ▼
  SCI (Space Component Image)
       │
       ▼
  Space runtime → nanokernel enforcement
```

The compiler emits machine code plus component metadata for authority, imports,
exports, and policy fields. Runtime enforcement is currently limited to the
verified loader checks.

## License

[Mozilla Public License 2.0](LICENSE)
