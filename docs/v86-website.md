# Space browser demo (v86)

`website/` is an Alpenglow-style Astro shell: ghostty-web serial console + [v86](https://github.com/copy/v86) with a 64-bit multiboot image built from this repo.

## Build

```bash
cd website
bun install
bun run build:kernel   # needs nasm + ../inauguration `in` release
bun run dev
```

`build:kernel` now runs `scripts/build-space-v86.sh`, which:

1. Assembles `boot/multiboot.asm` (64-bit long-mode trampoline).
2. Compiles `kernel/kernel-root.in` with `--target-triple x86_64-unknown-none`.
3. Copies the resulting boot image to `public/v86/space-multiboot.bin`.

## Architecture

| Piece | Value |
|-------|-------|
| CPU mode | 64-bit long mode (trampoline in `boot/multiboot.asm`) |
| Kernel codegen | `x86_64-unknown-none` via Inauguration |
| Boot image | 4096-byte trampoline + `.in`-compiled kernel |
| Serial | COM1 (`0x3F8`) shell with `help`, `info`, `ls`, `mkdir`, `write`, `read`, `stat`, and `halt` commands |

## Deploy

The site is configured for Cloudflare Pages via Wrangler:

```bash
cd website
bun run deploy
```

- Project name: `space`
- Domain: `https://space.tsc.hk`

## Verification

- QEMU smoke test: `qemu-system-x86_64 -kernel public/v86/space-multiboot.bin -m 256M -serial stdio`
- Website build: `bun run build` (Astro static site with `astro check`)
- Browser test: `bun run dev`, then open the local URL and wait for the serial banner
- Live site: `https://space.tsc.hk`

See [`next-agent-32bit-v86.md`](next-agent-32bit-v86.md) for the original task breakdown and file references.