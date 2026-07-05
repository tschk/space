# Space browser demo (v86)

`website/` is an Alpenglow-style Astro shell: ghostty-web serial console + [v86](https://github.com/copy/v86) with a **multiboot** image built from this repo (`scripts/check-qemu-boot.sh` same kernel).

## Build

```bash
cd website
bun install
bun run build:kernel   # needs nasm + ../inauguration `in` release
bun run dev
```

## 32-bit (`i386`) vs current image

| Piece | QEMU (today) | v86 browser |
|-------|----------------|-------------|
| CPU mode | x86_64 long mode (trampoline in `boot/multiboot.asm`) | 32-bit protected mode unless long mode works in v86 |
| Kernel codegen | `x86_64-unknown-none` | Same multiboot blob today |
| Alpenglow pattern | N/A | i686 Linux `bzimage` + initrd |

A **true** `i386-unknown-none` Space kernel for v86 needs generic work in **Inauguration** (not Space-branded):

1. 32-bit multiboot trampoline (no long-mode hop) + boot link layout
2. x86 encoder without REX.W / 64-bit addresses in lowering
3. ELF32 relocatable objects (`EM_386`) — partial registry exists (`i386-unknown-none`)

`TL_IS_32BIT` in `native_emit/x86_64.rs` is the hook; wiring from `emit_native_object` and finishing opcode patches is still open.

Until that lands, treat the website as **integration smoke**: UI + artifact pipeline. Confirm boot in your browser; v86 long-mode support may still block full kernel bring-up.