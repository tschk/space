# Space

Space is a true new 64-bit x86_64-first operating system design centered on
`.in` as the native systems and orchestration language.

The design source of truth is [os-design-notes.md](os-design-notes.md).

## Status: it boots

The Space nanokernel root, written in `.in`, now boots to 64-bit long mode under
QEMU and drives the serial console directly:

```
space: kernel root entered
space: long mode active, multiboot info at 0x0000000000009500
space: nanokernel halting
```

The `.in` language and its compiler (Inauguration) live in `../inauguration`.
Building this required building that compiler from scratch in C: a lexer,
parser, semantic analysis, an x86_64 instruction encoder, a code generator, a
component-metadata emitter, and a bootable-image writer — no external assembler
or linker.

## Boot it yourself

Requirements: `clang`, `make`, `nasm`, `qemu-system-x86_64`, and the
Inauguration compiler checked out at `../inauguration`.

```sh
bash scripts/check-qemu-boot.sh
```

This builds the compiler, assembles the long-mode boot trampoline, compiles
`kernel/kernel-root.in` to a flat Multiboot1 image, boots it in QEMU, and
verifies the `space: kernel root entered` marker on the serial line.

## Layout

- `kernel/kernel-root.in` — the nanokernel root component and its lowerable
  serial/bring-up code, written in `.in`.
- `boot/multiboot.asm` — the irreducible CPU bring-up shim (32-bit protected
  mode → x86_64 long mode), the only non-`.in` code in the kernel.
- `scripts/check-qemu-boot.sh` — the build-and-boot pipeline.
- `sci-schema.md` — the Space Component Image (SCI) metadata profile.
- `bootstrap-plan.md` — the kernel-in-`.in` implementation plan.
- `examples/` — proposed `.in` component contracts.

## Relationship to Inauguration

Per [AGENTS.md](AGENTS.md), Space owns the OS contracts, examples, SCI profile,
and boot plan. Inauguration owns the generic compiler: freestanding x86_64
output, component metadata, and native lowering. Inauguration does not depend on
this repository.
