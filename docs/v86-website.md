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

### Writable globals and compiler ownership

Issue [#109](https://github.com/tschk/space/issues/109) records the compiler's
explicit refusal to emit 32-bit boot images containing writable globals. This
kernel uses writable globals for shell, history and editor state; substituting
an older image or the 64-bit desktop kernel does not verify this demo.

Inauguration already relocates bounded 32-bit addresses and loads initialized
data at `0x200000`. Its boot entry point retained an obsolete refusal above that
working path. Compiler commit
[`ec8cc355`](https://github.com/tschk/inauguration/commit/ec8cc355e127902c75250de80a1e748e01248fb5) removes
the refusal and tests scalar mutation and relocated pointers in real i386/i686
QEMU boots. Website CI builds that source revision, runs the normal website build
and boots the resulting image. It does not change the older compiler pin for the
separate 64-bit desktop gates.

For local builds, check out that compiler revision in `../inauguration` or set
`INAUGURATION_DIR` to its checkout. In the compiler checkout, run
`cargo build --release --manifest-path in-cli/Cargo.toml`.
The website script reuses an existing release binary, so rebuild after changing
compiler revisions. A published compiler release without this fix still refuses
the image. Space retains its protected-mode trampoline and existing kernel.

### Mobile navigation

The header has two destinations: the Space releases page and `tsc.hk`.
At 390×844 both fit on one line, from x164 to x376, with no clipping or overlap.
Keep the existing links rather than adding a mobile page switcher. Recheck this
decision if the site gains more destinations.

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
- Kernel state gate: from the repository root, `python3 scripts/check-v86-shell.py`
  boots the built website image in QEMU and checks persistent command history.
  It does not compile or substitute another image.
- Browser test: `bun run dev`, then open the local URL and wait for the serial banner
- Live site: `https://space.tsc.hk`
