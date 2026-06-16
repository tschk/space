# Space

Space is a component-based operating system. The native model is
component + capability + object + execution graph — not process + file + syscall
+ user. There is no POSIX personality in the kernel; that runs as a `.in`
microservice if needed.

The system is expressed in `.in`, a language and component contract format
compiled by the [Inauguration](https://github.com/tschk/inauguration) toolchain.

## Status: it boots

The nanokernel root, written in `.in`, boots to x86_64 long mode under QEMU and
drives the serial console:

```
space: kernel root entered
space: long mode active, multiboot info at 0x0000000000009500
space: nanokernel halting
```

All subsystems are exercised and verified: serial, memory management, virtual
memory, object graph, capabilities, interrupts, exceptions, preemptive
multitasking, typed IPC channels, SCI component loading, checkpoint/restore,
and an interactive shell. Two QEMU-based scripts (`check-qemu-boot.sh` and
`build-multicomponent.sh`) assert markers for every subsystem.

## Target architectures

| Arch | Status |
|------|--------|
| x86_64 | Boots, all subsystems verified |
| ARM64 | Planned (SCI table already lists it) |

The Inauguration compiler emits freestanding x86_64 code. ARM64 lowering is a
future target.

## Build and run

Requirements: `clang`, `make`, `nasm`, `qemu-system-x86_64`, and Inauguration
checked out at `../inauguration`.

```sh
bash scripts/check-qemu-boot.sh
```

Development is cross-platform — macOS (arm64) and Linux (x86_64, glibc and
musl) are all used for building and testing.

## Layout

- `kernel/` — nanokernel root and subsystem components in `.in`
- `boot/multiboot.asm` — x86_64 CPU bring-up (32-bit → long mode) and stubs
- `scripts/` — build, boot, and verification harnesses
- `examples/` — proposed `.in` component contracts
- `architecture.md` — full system architecture
- `os-design-notes.md` — design rationale and roadmap
- `sci-schema.md` — Space Component Image metadata profile
- `compatibility-personalities.md` — how non-native programs run

## Relationship to Inauguration

Per [AGENTS.md](AGENTS.md), Space owns the OS contracts, examples, SCI profile,
and boot plan. Inauguration owns the generic compiler: freestanding target
support, component metadata, and native lowering. Inauguration does not depend
on this repository.
