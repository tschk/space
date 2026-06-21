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

### Running Subsystems

The kernel is 90 declarations in 1517 lines of `.in`, emitting 46,599 bytes of
x86_64 machine code in a 55,047-byte boot image:

| Subsystem | Status |
|-----------|--------|
| x86_64 long mode boot (Multiboot1) | ✅ |
| Serial console (COM1, TX buffered) | ✅ |
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
| Object graph edges (typed references, DFS walk) | ✅ |
| Checkpoint / restore (object graph + memory) | ✅ |
| SCI loader demo (domain-mapped virtual component call, manifest/cap validation, lifecycle object) | ✅ |
| e1000 NIC driver (PCI, ARP, UDP) | ✅ |
| Deterministic kernel workload + time-service tick source | ✅ |
| Shell (16 commands: help, uptime, peek, poke, echo, ...) | ✅ |
| Kernel benchmark script (boot timing, approximate phase breakdown) | ✅ |
| `free_frame` LIFO reclaim | ✅ |
| `chan_select` multi-channel poll | ✅ |
| `cap_revoke` | ✅ |

## Target Architectures

| Arch | Compiler Status | Kernel Status |
|------|----------------|---------------|
| x86_64 | ✅ Native lowering, boot image, ELF object | ✅ Boots verified subsystems |
| ARM64 | ⬜ Planned (SCI table) | ⬜ |
| RISC-V | ⬜ | ⬜ |

The Inauguration compiler emits freestanding x86_64 code with SCI metadata for the verified kernel contract.
Multi-platform lowering is a target for future phases.

## Implementation Roadmap

The [architecture document](architecture.md) defines 9 phases:

```
Phase 0: Domain subsystem       ← NOW (multiple memory domains)
Phase 1: Cross-domain channels  ← NEXT (IPC between domains)
Phase 2: Core microservices     ← proc.in and time.in exist; mem.in and rand.in planned
Phase 3: Component loader       ← SCI runtime loads .in components
Phase 4: Filesystem             ← fs.in as .in microservice
Phase 5: Networking             ← e1000 ARP + UDP transmit path; TCP/IP stack planned
Phase 6: Graphics               ← gfx.in compositor
Phase 7: Compatibility          ← Linux/Darwin/Windows guests
Phase 8: Distribution           ← remote components, migration
```

The current Phase 0 blocker is service scheduling: the SCI demo now maps a
component at a private virtual address in a switched domain and records it as a
component object, but proc/time/fs services are not scheduled as isolated
microservices yet.

## Build and Run

Requirements: `clang`, `make`, `nasm`, `qemu-system-x86_64`, and Inauguration
checked out at `../inauguration`.

```sh
# Full boot check (compiles kernel, boots QEMU, asserts boot-critical subsystems)
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
  kernel-root.in          nanokernel (1510 lines, 90 declarations)
  domain.in               Phase 0 memory domains
  channel.in              Phase 1 channel fabric
  loader.in               Phase 3 loader integration
services/
  proc.in                 process lifecycle service
  time.in                 deterministic monotonic time service
  fs.in                   filesystem service
  net.in                  networking service
  gfx.in                  graphics/compositor service
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

The compiler emits machine code plus component metadata for authority, imports,
exports, and policy fields. Runtime enforcement is currently limited to the
verified loader checks.

## License

[Mozilla Public License 2.0](LICENSE)
