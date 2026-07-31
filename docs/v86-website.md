# Space browser demo (v86)

`website/` is an Alpenglow-style [moonshine](https://github.com/tschk/moonshine) site: ghostty-web serial console + [v86](https://github.com/copy/v86) with a 32-bit multiboot image built from this repo. Bun serves React 19 rendered through `@tschk/moonshine-react`; `bun run build` emits a static `dist/`.

## Build

```bash
cd website
bun install
bun run build:kernel   # needs nasm + ../inauguration `in` release
bun run dev
```

`build:kernel` runs `scripts/build-space-v86-32.sh`, which:

1. Assembles `boot/multiboot32.asm` (32-bit protected-mode trampoline, no long-mode hop).
2. Compiles `kernel/v86-kernel.in` with `--target-triple i386-unknown-none`.
3. Copies the resulting boot image to `public/v86/space-multiboot.bin`.

## Layout

```
src/App.tsx       page markup
src/styles.ts     global CSS
src/document.ts   route artifact + document assembly
src/shell.js      browser entry (bundled to dist/shell.js)
src/build.ts      static build → dist/
src/server.ts     Bun dev/preview server
public/           static assets (fonts, v86 kernel + runtime)
```

## Architecture

| Piece | Value |
|-------|-------|
| CPU mode | 32-bit protected mode (trampoline in `boot/multiboot32.asm`) |
| Kernel codegen | `i386-unknown-none` via Inauguration |
| Boot image | 4096-byte trampoline + 256-byte SCI header + `.in`-compiled kernel |
| Serial | COM1 (`0x3F8`) shell with `help`, `info`, `ls`, `cat`, `echo`, `write`, `rm`, `touch`, `cp`, `mv`, `mkdir`, and `rmdir` commands |

## Deploy

The site is configured for Cloudflare Pages via Wrangler:

```bash
cd website
bun run deploy
```

- Project name: `space`
- Domain: `https://space.tsc.hk`

## Verification

- QEMU smoke test: `qemu-system-i386 -kernel public/v86/space-multiboot.bin -m 256M -serial stdio`
- Website gates: `bun run typecheck` and `bun test`
- Website build: `bun run build` (kernel image + static `dist/`)
- Browser test: `bun run dev`, then open the local URL and wait for the serial banner
- Live site: `https://space.tsc.hk`

See [`next-agent-32bit-v86.md`](next-agent-32bit-v86.md) for the original task breakdown and file references.