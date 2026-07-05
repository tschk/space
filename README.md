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

The native model is **component + capability + object + execution graph** — not
process + file + syscall + user. There is no POSIX in the kernel. Linux, Darwin,
and Windows compatibility are `.in` microservices that translate legacy concepts
into Space primitives.

## Status

The nanokernel root, written in `.in` and compiled by
[Inauguration](https://github.com/tschk/inauguration), boots to x86_64 long
mode under QEMU and verifies the boot-critical subsystems on every boot.

Subsystem status is tracked in [`architecture.md`](architecture.md).

## Benchmarks

Measured on macOS ARM64 (M3), Inauguration v0.7.1.

| Metric | Value |
|--------|-------|
| Boot image size | 259,316 B (trampoline 4,096 + kernel 254,964) |
| Kernel compile (cold) | ~50 ms |
| Kernel compile (warm, cached) | ~30 ms |
| Boot to interactive shell (QEMU TCG, Apple Silicon) | ~4 s |
| Boot to interactive shell (QEMU + KVM, x86_64) | ~40 ms |

The kernel is ~1,300 lines of `.in` across 15+ files, lowered to x86_64 machine
code and linked into a single bootable binary.

### Performance notes

- Most of the cold compile wall time is `in` process startup; the actual parse +
  lower + link is a few milliseconds. A compiler daemon or persistent server would
  drop this to the warm-cache level.
- The warm path is already cached by source hash, so repeated edits of the same
  file are fast.
- Next low-hanging fruit: reduce the number of separate files merged into the
  kernel root, and avoid re-allocating the string table across cache hits.

## Target architectures

| Arch | Compiler status | Kernel status |
|------|-----------------|---------------|
| x86_64 | Native lowering, boot image, ELF object | Boots verified subsystems |
| ARM64 | Planned (SCI table) | — |
| RISC-V | Planned | — |

## Build and run

Requirements: `clang`, `nasm`, `qemu-system-x86_64`, and Inauguration checked
out at `../inauguration`.

```sh
bash scripts/check-qemu-boot.sh      # full boot verification
bash scripts/build-multicomponent.sh # SCI component loading demo
bash scripts/check-sci-contract.sh   # metadata validation
bash scripts/check-network.sh        # e1000 ARP/UDP test
```

## Repository layout

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
  check-qemu-boot.sh      full boot verification
  build-multicomponent.sh SCI loading demo
  check-sci-contract.sh   metadata validation
  check-network.sh        network driver test
```

## Relationship to Inauguration

Per [`AGENTS.md`](AGENTS.md), Space owns the OS contracts, examples, SCI profile,
and boot plan. Inauguration owns the generic compiler capabilities:

- freestanding target support (`x86_64-unknown-none`)
- SCI-compatible component metadata emission
- native x86_64 lowering, instruction encoding, boot image assembly
- Core IR optimization
- multi-frontend support (.in, Rust, Go, V, Tree-sitter polyglot)

Inauguration does not depend on this repository. Space does not add
Space-branded targets to Inauguration.

## License

[Mozilla Public License 2.0](LICENSE)
