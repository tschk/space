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
[Inauguration](https://github.com/tschk/inauguration), enters x86_64 long mode
under QEMU. Maintained checks: shell + full runtime display/input (preempt-stop),
SCI loader (`hello`/`uecho`), execve SCI from FS, Linux demo, VFS, NVMe volume
multi-file soak, UDP/TCP data path, DHCP lease, DNS A for dotted names.

Subsystem status is tracked in [`architecture.md`](architecture.md).

## Benchmarks

Measured on macOS ARM64 (M3), Inauguration v0.7.1.

| Metric | Value |
|--------|-------|
| Metric | x86_64 KVM | Apple Silicon TCG |
|--------|-----------|-------------------|
| Boot image size | 230,662 B | 230,662 B |
| Kernel compile (warm, cached) | ~27 ms | ~27 ms |
| Boot to interactive shell | ~2,000 ms | ~1,900 ms |
| SeaBIOS + boot | ~200 ms | ~200 ms |
| Kernel init to shell | ~1,800 ms | ~1,700 ms |

Measured via serial output polling.  KVM on Intel i9-7960X (Fedora 43, WSL2).
TCG on Apple M3 (macOS 15).  Boot time is dominated by SeaBIOS firmware init
and serial output through the emulated 16550 UART.

### Performance notes

- Most kernel init time is waiting for PIT ticks for timer calibration.
- The warm compile path is cached by source hash; repeated edits rebuild fast.
- `scripts/boot.sh` drops into an interactive shell.  Type `halt` to exit.
- `scripts/bench-boot.sh` runs 5 iterations and reports median/min/max.

## Target architectures

| Arch | Compiler status | Kernel status |
|------|-----------------|---------------|
| x86_64 | Native lowering, boot image, ELF object | Boots verified subsystems |
| ARM64 | Native lowering, boot image, ELF object | Platform boot work remains |
| RISC-V | Planned | — |

## Build and run

Requirements: `clang`, `nasm`, `qemu-system-x86_64`, and Inauguration (git
submodule under `vendor/inauguration`, or a sibling checkout at `../inauguration`).

```sh
git submodule update --init --recursive
```

```sh
bash scripts/check-qemu-boot.sh      # full boot verification
bash scripts/build-multicomponent.sh # SCI component loading demo
bash scripts/check-sci-contract.sh   # metadata validation
bash scripts/check-network.sh        # e1000 ARP/UDP test
bash scripts/check-terminal-editor.sh # serial editor save test
```

Browser demo (Alpenglow-style v86 shell): see [`docs/v86-website.md`](docs/v86-website.md) and `website/`.

## Repository layout

```
kernel/
  kernel-root.in          nanokernel root component
  domain.in               memory domain subsystem
  channel.in              cross-domain channel fabric
  net.in                  e1000 NIC driver
  guest-service.in        SCI guest component example
components/
  pci.in                  PCI bus enumeration
  volume-mem.in           standalone memory-backed Volume SCI component
boot/
  multiboot.asm           x86_64 CPU bring-up (32-bit → long mode)
scripts/
  check-qemu-boot.sh      full boot verification
  build-multicomponent.sh SCI loading demo
  check-sci-contract.sh   metadata validation
  check-network.sh        network driver test
  check-terminal-editor.sh serial editor save test
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
