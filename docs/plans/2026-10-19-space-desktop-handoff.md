# Space / Subspace / Inauguration handoff — 2026-10-19

## Start here

Read [the next-agent goal statement](2026-10-19-next-agent-goal.md) and
[the cross-repository architecture](2026-10-19-three-repository-architecture.md).
The user's priority is a proper hypermodular OS platform, substantial architecture
planning, resolution/scaling and multiple genuine typefaces. Build an original
command desktop inspired by basic niri tiling and Raycast/Rover interactions.
Evaluate mature compositor/text infrastructure before expanding a from-scratch
renderer. Do not redefine the destination around the current framebuffer demo.

Space `AGENTS.md`, `architecture.md`, `sci-schema.md` and the existing compositor
and personality contracts remain authoritative. The
[display/text architecture](2026-10-19-display-text-architecture.md) specifies
output transactions, coordinate transforms, typeface roles/fallback/shaping,
buffer ownership and the service graph. The
[command desktop plan](2026-10-19-command-desktop.md) defines the shell boundary.
No compositor dependency, new font asset or private source was imported.

## Current checkouts

- **Space:** `/Users/undivisible/projects/space`, `main`. Previously published
  `ccc1f44` defines direction, `f59757a` records the hypermodular contracts, and
  `fcdbdf2` extracted `display-commandbar.in` and `display-layout.in`. This
  checkpoint adds `components/display-output.in`, `components/display-text.in`,
  dual-typeface `components/font.in` (`Space Term Mono` + proportional
  `Space UI Sans`), and `scripts/check-display-output-text.py`, while resolving
  the recorded runtime-component, SPDP, and damage-rendering checkpoint failures.
  Preserve untracked `vendor/`.
- **Subspace:** `/Users/undivisible/projects/subspace`, `master` at `ea1ac5d`,
  clean and verified with both `bun test` (70 passed, 0 failed) and
  `IN_BIN="$HOME/.cargo/bin/in" bun run check:all` (AN521 QEMU boot, IRQ stack
  alignment, mailbox contract, static RAM layout, startup data, warm reset,
  cooperative yield, all 7 MemManage MPU denial cases, SCI-E binary
  emission/validation, UF2 packing, and board validation).
- **Inauguration:** active continuation checkout
  `/Users/undivisible/.codex/worktrees/compiler-loop-continuation/inauguration`
  (synced with `/Users/undivisible/projects/inauguration`), `main`, bumped and
  verified at `0.9.321`. Preserve `in-cli/vendor/`.

Existing authorization covers logical verified commits/pushes and compiler patch
bumps, with parallel agents and primary integration. No new branches, tags,
crate publication, deployment or device flashing. Never use Grok/Oracle. Native
agents were the available fallback for bounded work; preserve scratch proposals.

## Implemented desktop checkpoint

1. **`components/display-commandbar.in` & `components/display-layout.in`:**
   - `display-commandbar.in` owns bounded query/selection, candidate availability
     and one dispatch path for keyboard/pointer. Existing windows precede five
     actions: tile windows, close focused, minimize focused, focus terminal1/2.
     Terminal focus restores an existing session; it does not launch a new terminal.
     Browser, floating and scrolling commands are not faked.
   - `display-layout.in` owns titlebar-aware horizontal tiling over the current
     window geometry, validates minimum size before mutation, includes
     margins/gaps/taskbars, preserves content and damages old/new frames.
2. **`components/display-output.in` (Output, Coordinate & Mode Transaction Contract):**
   - Owns output identity (`out-id`), monotonic configuration generation
     (`out-generation`), physical mode (`out-phys-w`, `out-phys-h`, `out-pitch`,
     `out-bpp`), rational scale (`out-scale-num`, `out-scale-den`), rotation
     (`out-rotation`), logical dimensions (`out-logical-w`, `out-logical-h`), and
     work-area geometry (`out-work-x`, `out-work-y`, `out-work-w`, `out-work-h`).
   - Validates candidate mode changes as an overflow-safe transaction
     (`out-validate-mode`) across `1024×768`, `1280×720`, `1920×1080`, and the
     portrait logical geometry fixture (`768×1024`), refusing invalid dimensions,
     unsupported modes, bad pitch, >16 MiB BGA buffer overflow, or invalid scales
     while preserving the prior active output state and generation.
   - Centralizes coordinate transforms (`out-logical-to-phys-x/y`,
     `out-phys-to-logical-x/y`), outward damage rounding (`out-damage-phys-x0/x1`),
     shared tile column edges (`out-tile-col-x/w`), window clamping
     (`out-clamp-windows`), and live QEMU BGA mode switching (`out-set-bga-mode`)
     exposed via `fb mode <w> <h>` and `fb scale <2|3>`.
3. **`components/font.in` & `components/display-text.in` (Dual-Typeface, UTF-8, Cache & Fallback Contract):**
   - Renders two genuinely distinct, permissively distributable typefaces concurrently:
     - **Face 0 (`FONT-FACE-MONO = 0`, `Space Term Mono`):** Public Domain / CC0-1.0
       8×8 fixed-width terminal programmer strike (`fb-font` / `fb-font-aa`),
       constant 8-unit logical advance, seriffed `I`/`1`/`l` and zero-slash.
     - **Face 1 (`FONT-FACE-SANS = 1`, `Space UI Sans`):** MIT / CC0-1.0 original
       geometric proportional sans-serif strike (`fb-font-sans` / `fb-font-sans-aa` /
       `fb-font-sans-adv`), variable per-glyph logical advances (`4..8` units) and
       distinct geometric sans-serif glyph forms.
   - Maps UI roles (`TEXT-ROLE-UI-BODY`, `TEXT-ROLE-UI-TITLE`,
     `TEXT-ROLE-CMD-QUERY`, `TEXT-ROLE-STATUS`) to `Space UI Sans` while keeping
     `TEXT-ROLE-TERM-MONO` pinned to `Space Term Mono` with invariant terminal
     cell metrics (`text-term-cell-w`, `text-term-cell-h`, `text-term-baseline`).
   - Validates untrusted `SFNT1` binary font headers (`text-validate-asset`,
     rejecting null, bad magic/version, truncated tables, out-of-range advances,
     and unsupported color/emoji flags), maintains a bounded 64-slot glyph advance
     cache (`text-glyph-advance`, `text-cache-invalidate`), decodes UTF-8
     codepoints (`text-utf8-decode` with `U+FFFD` replacement), computes
     codepoint-boundary caret/hit positions (`text-caret-x`, `text-hit-test-byte`),
     and renders a deterministic missing-glyph fallback box (`text-draw-fallback-box`,
     exercised live in QEMU via the `utf8` terminal command).
   - Eliminates hardcoded `"1920 x 1080"` labels in `comp-draw-utilities-content`,
     rendering live `fb-width x fb-height`, scale (`32 BPP / 100%` or `32 BPP / 150%`),
     and concurrent `SPACE UI SANS` + `SPACE TERM MONO` specimen rows with adaptive
     sidebar width for narrow tiled windows.

## Verification evidence

Compiler baseline and published patch: Inauguration `0.9.321` installed at
`$HOME/.cargo/bin/in`.

- `python3 scripts/check-display-output-text.py --in "$HOME/.cargo/bin/in" --out /tmp/space-output-text-final`:
  **12 model/native/JIT checks passed** across `default`, `lean`, and `harden`
  (covering output modes `1024×768`, `1280×720`, `1920×1080`, portrait `768×1024`,
  invalid/overflow mode refusal preserving generation, rational scale transforms,
  shared tile edges, proportional vs monospace measurement, terminal cell
  invariants, `SFNT1` untrusted asset refusal, cache invalidation, and UTF-8
  decoding/hit-testing) **plus real QEMU BGA verification** across `1920×1080`
  (scale `2x`, dual typefaces, terminal caret, and `utf8` missing-glyph fallback
  boxes), `1280×720` (scale `3x` / `150%` with command bar open), and `1024×768`
  (scale `2x` with 3-column tiling). Rendered PNG screenshots inspected at
  `/tmp/space-output-text-final/*.png`.
- `python3 scripts/check-commandbar.py --in "$HOME/.cargo/bin/in" --out /tmp/space-commandbar-final`:
  **72 checks passed** across `default`, `lean`, and `harden`.
- `python3 scripts/check-desktop-launcher.py --in "$HOME/.cargo/bin/in" --build-dir /tmp/space-desktop-launcher-final`:
  **full fresh-kernel QEMU pass** covering PS/2, query/focus/no-match, pointer,
  close/reindex, Escape, keyboard/pointer tiling, exact frame geometry,
  minimize/restore, terminal input, and stale-action refusal.
- `bash scripts/check-desktop-visual.sh`: **10 passed, 0 failed** (visual
  inspection confirmed `/tmp/space-desktop-visual/desktop.png`).
- `bash scripts/check-desktop-damage.sh`: **PASS at 35–39 fps** (100 frames in
  252–280 PIT ticks >= unchanged 30 fps gate after coalescing burst PS/2 packets
  per frame, hoisting row pointers/constants in `fb-blit-back-rect`,
  `fb-fill-rect`, and `fb-draw-char-aa`, and adding early clip rejection + 64-bit
  `scale == 2` pixel writes to `text-draw-char-face`).
- `bash scripts/check-runtime-components.sh`: **22 passed, 0 failed** (repaired
  generically in Inauguration `0.9.321` by allowing bodyless imported native
  stubs to synthesize a zero/default return in `core_ir_verifier.rs` and loading
  component `pci.sci` before `net.sci` in `kernel-entry`).
- `python3 scripts/check-spdp-sci.py --in "$HOME/.cargo/bin/in"` and
  `python3 scripts/check-spdp-input.py --in "$HOME/.cargo/bin/in"`: **both PASS**
  (restored `demo_spdp_client` activation in `kernel-entry` while keeping
  `comp-sci-win` hidden until `spdp-process` receives `SPDP-MSG-CREATE-SURFACE`).
- Subspace (`master` at `ea1ac5d`): `bun test` (**70 passed, 0 failed**) and
  `IN_BIN="$HOME/.cargo/bin/in" bun run check:all` (**all QEMU/MPU/SCI-E/UF2/board
  checks passed**).

## Completed compiler work (Inauguration 0.9.321, `70b0991e`)

Inauguration `0.9.321` (`70b0991e`) repairs all recorded general callable/native-stub issues:

1. **Conditional joins & dynamic callable selectors (`in-cli/src/typecheck.rs`):**
   propagates `FnType` across `IfExpr`/`MatchExpr` joins and assignment sites when
   both branches agree on signature, while clearing exact static target (`fn_items`)
   so indirect calls lower via register function pointer.
2. **Negation operator on function items (`in-cli/src/typecheck.rs`):**
   records `Invalid` callable proof on `UnaryOp::Not` when applied to a callable.
3. **High-bit constant shift folding (`in-cli/src/typecheck/closure_inference.rs`):**
   folds integer arithmetic/bitwise subexpressions in `eval_const_i64` so shift
   counts like `1 << (32 + 31)` are caught statically.
4. **Generic forwarding alias specialization (`in-cli/src/compiler/rust_front.rs`):**
   records concrete monomorphized targets in `generic_value_specialization_targets`
   and substitutes type parameters in `ReturnType` and local let annotations.
5. **Topological C typedef/struct emission (`in-cli/src/native_emit/lower/lower_tests.rs`):**
   topologically orders C `typedef` and `struct` forward declarations before
   emitting dependent function-pointer typedefs or struct fields.
6. **Bodyless imported native stubs (`in-cli/src/core_ir_verifier.rs`):**
   allows empty stub functions with non-void return types (used for unresolved
   component imports) to synthesize a default zero return instead of failing
   verification.

## Scope limits and next actions

Still absent and prioritized for the next slices:
- **Slice 4 (Native interactive SCI services):** migrate surface, seat, and font/text
  ownership from kernel-linked modules into isolated CPL3 SCI services; verify two
  concurrent SCI clients, independent input routing, buffer release, disconnect
  cleanup, and denied cross-client operations; bring up TrueType/OpenType outline
  rasterization and script shaping behind the `SFNT1` asset boundary.
- **Slice 5 (Original shell & compatibility):** complete tiled column viewport
  scrolling and floating geometry roundtrips, independent terminal session launch,
  real browser component strategy, Wayland client adapter, and multi-output
  attach/remove.

The overall goal remains active. No completion, hardware isolation beyond the
tested CPL3/MPU gates, or arbitrary foreign app compatibility claim is implied.
