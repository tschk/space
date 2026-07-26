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
under QEMU. Desktop works via shell `desktop` (kernel-linked `components/display.in`
+ PS/2 `components/mouse.in`). Maintained checks: shell + full runtime
display/input (preempt-stop), SCI loader (`hello`/`uecho`), execve SCI from FS,
Linux demo / ELF personality, VFS, NVMe volume multi-file + deep soak, UDP/TCP
data path, DHCP lease, DNS A for dotted names, personalities (Linux/Windows/Darwin).

Subsystem status is tracked in [`architecture.md`](architecture.md).
Linux/Windows/Darwin personality progress: [`docs/personalities-roadmap.md`](docs/personalities-roadmap.md).

## Benchmarks

Measured on macOS ARM64 (M3 TCG), Inauguration v0.9.3 via `scripts/bench-boot.sh`
(5 iterations, median / min / max).

| Metric | Median | Min | Max |
|--------|--------|-----|-----|
| Boot image size | 542,332 B | — | — |
| Kernel compile (warm) | 132 ms | 103 ms | 187 ms |
| Boot to interactive shell | 676 ms | 611 ms | 769 ms |
| Boot to halt | 1,095 ms | 955 ms | 1,326 ms |

Measured via serial output polling on Apple M3 (macOS, QEMU TCG).

### Performance notes

- Boot-to-shell is ~700 ms class on M3 TCG; dominated by firmware + serial path.
- The warm compile path is cached by source hash; repeated edits rebuild fast.
- `scripts/boot.sh` drops into an interactive shell. Type `halt` to exit.
- `scripts/bench-boot.sh` runs 5 iterations and reports median/min/max.
- Shell `desktop` starts the kernel-linked display + PS/2 mouse path.

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
bash scripts/check-qemu-boot.sh       # full boot verification
bash scripts/build-multicomponent.sh  # SCI component loading demo
bash scripts/check-sci-contract.sh    # metadata validation
bash scripts/check-network.sh         # e1000 ARP/UDP test
bash scripts/check-terminal-editor.sh # serial editor save test
bash scripts/check-desktop-visual.sh  # desktop / display visual path
bash scripts/check-linux-elf.sh       # Linux ELF personality
bash scripts/check-volume-deep-soak.sh # NVMe volume deep soak
bash scripts/check-fs-dirs.sh         # mkdir/rmdir/mv/rm full coverage
bash scripts/check-personalities.sh   # Linux/Windows/Darwin personalities
```

Browser demo (Alpenglow-style v86 shell): see [`docs/v86-website.md`](docs/v86-website.md) and `website/`.

## Repository layout

```
kernel/
  kernel-root.in            nanokernel root component
  guest-service.in          SCI guest component example
  v86-kernel.in             browser/v86 kernel variant
components/
  display.in                kernel-linked display (shell `desktop`)
  display-standalone.in     standalone display SCI component
  mouse.in                  PS/2 mouse input
  shell.in                  interactive serial shell
  pci.in                    PCI bus enumeration
  volume-mem.in             memory-backed Volume SCI component
  linux.in / windows.in / darwin.in   OS personality surfaces
boot/
  multiboot.asm             x86_64 CPU bring-up (32-bit → long mode)
scripts/
  check-qemu-boot.sh        full boot verification
  check-desktop-visual.sh   desktop / display visual path
  check-linux-elf.sh        Linux ELF personality
  check-volume-deep-soak.sh NVMe volume deep soak
  check-fs-dirs.sh          mkdir/rmdir/mv/rm full coverage
  check-personalities.sh    Linux/Windows/Darwin personalities
  bench-boot.sh             boot timing (median/min/max)
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
