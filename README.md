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

- [`architecture.md`](architecture.md) — full system architecture, all five
  layers, implementation roadmap in 9 phases with dependencies
- [`os-design-notes.md`](os-design-notes.md) — original design rationale,
  non-negotiables, chosen architecture
- [`sci-schema.md`](sci-schema.md) — Space Component Image metadata format
- [`compatibility-personalities.md`](compatibility-personalities.md) — how
  Linux, Darwin, and Windows programs run as guest components
- [`bootstrap-plan.md`](bootstrap-plan.md) — original task breakdown
- [`AGENTS.md`](AGENTS.md) — repository workflow and boundaries

## Status: it boots

The nanokernel root, written in `.in` and compiled by
[Inauguration](https://github.com/tschk/inauguration), boots to x86_64 long
mode under QEMU and verifies every subsystem on every boot.

Current boot output (~1230ms to shell):

```
space: kernel root entered
space: object arena 0x...
space: bootstrap realm object id 0x...
space: interrupts enabled (PIC remapped, PIT 100Hz)
space: timer ticks (5 samples)
space: supervisor loaded, component enforcing
space: scheduler quiesced after 3 round-robin passes
space: channel demo complete, remaining 0x0000000000000000
space: preemptive workers interleaved, switching OK
space interactive shell -- type 'help'
space>
```

### Running Subsystems

The kernel is 88 functions in 1420 lines of `.in`, emitting ~35 KB of x86_64
machine code:

| Subsystem | Status |
|-----------|--------|
| x86_64 long mode boot (Multiboot1) | ✅ |
| Serial console (COM1, TX buffered) | ✅ |
| Physical memory discovery | ✅ |
| Bump heap + 4K frame allocator | ✅ |
| 4-level page table management | ✅ |
| Object graph arena (typed objects, stable IDs) | ✅ |
| Capability table (minting, runtime check) | ✅ |
| IDT (256-entry), PIC remap, PIT 100Hz | ✅ |
| CPU exception handling (PF, #DE, #GP, #UD) | ✅ |
| Component supervisor (SCI loader rule) | ✅ |
| Cooperative M:N threading | ✅ |
| Preemptive multitasking (timer context switch) | ✅ |
| Typed IPC channels (ring buffer, poll-with-yield) | ✅ |
| Object graph edges (typed references, DFS walk) | ✅ |
| Checkpoint / restore (object graph + memory) | ✅ |
| SCI loader (load separate binary, validate manifest) | ✅ |
| e1000 NIC driver (PCI, ARP, UDP) | ✅ |
| Deterministic execution | ✅ |
| Shell (16 commands: help, uptime, peek, poke, echo, ...) | ✅ |
| Kernel benchmarks (boot timing, per-subsystem) | ✅ |
| `free_frame` LIFO reclaim | ✅ |
| `chan_select` multi-channel poll | ✅ |
| `cap_revoke` | ✅ |

## Target Architectures

| Arch | Compiler Status | Kernel Status |
|------|----------------|---------------|
| x86_64 | ✅ Native lowering, boot image, ELF object | ✅ Boots, all subsystems |
| ARM64 | ⬜ Planned (SCI table) | ⬜ |
| RISC-V | ⬜ | ⬜ |

The Inauguration compiler emits freestanding x86_64 code with full SCI metadata.
Multi-platform lowering is a target for future phases.

## Implementation Roadmap

The [architecture document](architecture.md) defines 9 phases:

```
Phase 0: Domain subsystem       ← NOW (multiple memory domains)
Phase 1: Cross-domain channels  ← NEXT (IPC between domains)
Phase 2: Core microservices     ← proc.in, mem.in, time.in, rand.in
Phase 3: Component loader       ← SCI runtime loads .in components
Phase 4: Filesystem             ← fs.in as .in microservice
Phase 5: Networking             ← net.in, TCP/IP stack
Phase 6: Graphics               ← gfx.in compositor
Phase 7: Compatibility          ← Linux/Darwin/Windows guests
Phase 8: Distribution           ← remote components, migration
```

The current blocker is Phase 0: the kernel has one address space. Every
component needs an isolated memory domain before microservices can exist.

## Build and Run

Requirements: `clang`, `make`, `nasm`, `qemu-system-x86_64`, and Inauguration
checked out at `../inauguration`.

```sh
# Full boot check (compiles kernel, boots QEMU, asserts all subsystems)
bash scripts/check-qemu-boot.sh

# Boot timing benchmark (5 runs)
bash scripts/bench-boot.sh

# SCI component loading demo
bash scripts/build-multicomponent.sh

# SCI metadata validation
bash scripts/check-sci-contract.sh
```

Development is cross-platform — macOS (ARM64), Linux (x86_64, glibc and musl).

## Repository Layout

```
kernel/
  kernel-root.in          nanokernel (1420 lines, 88 functions)
  domain.in               Phase 0 — planned
  channel.in              Phase 1 — planned
  loader.in               Phase 3 — planned
services/                 Phase 2+ — planned .in microservices
  proc.in                 process lifecycle
  mem.in                  memory management
  time.in                 clock and timer
  rand.in                 entropy
  fs.in                   filesystem
  net.in                  networking
  gfx.in                  graphics/compositor
  linux-compat.in         Linux binary compatibility
  darwin-compat.in        Darwin binary compatibility
  win-compat.in           Windows binary compatibility
drivers/
  e1000.in                NIC driver
boot/
  multiboot.asm           x86_64 CPU bring-up (32-bit → long mode)
scripts/
  check-qemu-boot.sh      Full boot verification
  bench-boot.sh           Boot timing benchmark
  build-multicomponent.sh SCI loading demo
  check-sci-contract.sh   Metadata validation
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

The compiler generates authority, ownership, scheduling, imports, exports, and
policy — not just machine code. The runtime loads, validates, and enforces
before execution.

## License

Per-repository. See `LICENSE` if present.
