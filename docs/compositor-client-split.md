# Compositor / Client Split — Design

- **Status**: groundwork (design + first proof behind a check)
- **Date**: 2026-08-13
- **Scope**: `components/display.in`, `protocol/display.in`, SCI loader / domains

## Problem

Today every compositor window lives in the kernel's address space. The window
manager (`comp-*` in `components/display.in`) is kernel-linked: window records,
terminal ring buffers, the ~8 MB backbuffer, and the cursor all sit in the
kernel heap/identity map. A "display server" surface pipeline already exists in
the same file (`dsp-*`) with a wire protocol (`protocol/display.in`, SPDP), but
it is kernel-side-only, never exercised by a real client, and its only loop
(`dsp-run`) blocks on `hlt()` with no wakeup source after `preempt-stop`.

The goal is a model where **SCI components own surfaces** in their own memory
domains and a compositor **blits** them. Space already has the two primitives
this needs:

- **Channels** (`components/channel.in`) — typed ring buffers, including
  cross-domain shared-page channels, for SPDP messages (32-byte fixed frames).
- **Memory domains** (`components/domain.in`) — per-component page tables with
  `domain-create-shared-page` for exporting a surface to the compositor.

No new IPC mechanism should be invented. SPDP over a cross-domain channel +
a shared framebuffer page is the whole story.

## Target architecture

```
  client component (domain A)              compositor (domain B / kernel)
  ┌──────────────────────────┐             ┌───────────────────────────┐
  │ owns surface buffer      │             │ blits surface into fb      │
  │ writes pixels, damage    │             │ + decorations + cursor     │
  └───────────┬──────────────┘             └─────────────┬─────────────┘
              │ SPDP msgs (cross-domain chan)           │
              │ shared page (surface memory)            │
              └──────────────────────────────────────────┘
```

Message flow (already defined in `protocol/display.in`):

1. Client `SHM_CREATE_POOL` — allocate a shared page; **the compositor maps
   the client's shared page** rather than allocating kernel heap.
2. Client `COMPOSITOR_CREATE_SURFACE` → gets a surface id.
3. Client `SURFACE_ATTACH(sid, pool, offset)` — bind a buffer slice.
4. Client writes pixels into its shared buffer (owns the memory).
5. Client `SURFACE_DAMAGE(sid, x, y, w, h)` + `SURFACE_COMMIT(sid)`.
6. Compositor recomposes only the damaged region and blits (damage-rect
   compositing from the current compositor applies directly).

## Phasing

### Phase A (done in this change)
- `docs/` design (this document).
- Self-contained in-kernel proof: shell command `dsp demo` drives the existing
  `dsp-*` surface pipeline with a client-side pool buffer filled with a
  recognizable pattern, then composites once. Gated by
  `scripts/check-spdp-composite.sh` (screenshot pixel assertion).
- Fix the two correctness bugs found in the dsp path:
  - `dsp-run` allocates a 32-byte message every loop iteration and never
    frees it (heap exhaustion) — move the buffer outside the loop.
  - `dsp-composite` reads `pool + offset + w*h*4` with no bound against the
    pool size (OOB read into the heap) — add pool-size tracking and clip.

### Phase B (not yet implemented)
- Client surface buffers live in a `domain-create-shared-page` page. The
  compositor maps the page and blits from it instead of a kernel `alloc`.
  Requires the SCI loader to hand the client a shared-page capability and the
  compositor to learn the page's physical address (extend `SHM_CREATE_POOL`
  with a shared-page grant, or attach a pre-exported domain page).
- Input routing: seat events (SPDP) published from the input component back to
  the client that owns the focused surface.
- A real SCI client component (`.in`) that creates a surface, animates a test
  pattern, and drains seat input — the first component-owned window.

### Phase C (deferred)
- Move decorations (title bars, taskbar) out of the compositor into a decorator
  client; compositor becomes a pure surface blender + damage scheduler.
- Replace the kernel-linked `comp-*` window manager with the SPDP surface
  server once the SCI path is proven (mirrors `display-standalone.in`).

## Why channels + shared pages (not new IPC)

- `chan-send`/`chan-recv` already provide bounded, typed, blocking message
  transport with a `chan-count` non-blocking poll used by the dsp loop.
- `domain-create-shared-page` already exports physical memory between two
  domains at chosen virtual addresses; a surface is just a shared buffer the
  compositor reads at blit time.
- Both are capability-governed: a client must hold the channel and the
  shared-page grant, so the split does not introduce an unchecked path.

## Open questions

- **Tearing / pacing**: clients should get a frame callback (SPDP event) so
  they don't write while the compositor blits. Define `SPDP-FRAME-CALLBACK`
  before Phase B.
- **Damage ownership**: the client declares damage; the compositor must still
  clip it to the surface bounds and the pool size (defense in depth, see the
  `dsp-composite` bounds fix).
- **Standalone server location**: keep `dsp-run` in-kernel, or move it into
  `display-standalone.in` (a real SCI component) and fix its wakeup (a PIT-
  driven poll instead of `hlt()`)? Prefer the SCI component, which also
  removes the preempt-stop freeze.
