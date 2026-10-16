# Compositor / Client Split — Design

- **Status**: groundwork (design + first proof behind a check)
- **Date**: 2026-08-13
- **Scope**: `components/display.in`, `protocol/display.in`, SCI loader / domains

## Problem

Today every compositor window lives in the kernel's address space. The window
manager (`comp-*` in `components/display.in`) is kernel-linked: window records,
terminal ring buffers, the ~8 MB backbuffer, and the cursor all sit in the
kernel heap/identity map. A "display server" surface pipeline already exists in
the same file (`dsp-*`) with a wire protocol (`protocol/display.in`, SPDP), and
a bounded SCI producer now exercises complete frame transport. The persistent loop
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

### SCI transport and one-page client-pixel proof

`dsp sci left` and `dsp sci right`, with `fixtures/spdp-sci/client.in` loaded
by `scripts/check-spdp-sci.py`, synchronously run a real SCI producer in its
memory domain. Four complete 32-byte SPDP frames travel through the loader's
existing ring page and control surface geometry. `chan-page-*` validates a
captured ring header and publishes/consumes whole four-word frames; malformed
or partial frames do not advance the head or reach the dispatcher.
Scheduler-backed CSP channels retain their own layout.

The fixture packager reads the canonical named capability metadata emitted
beside the SCI artifact, verifies unchanged source/protocol hashes,
then validates exact component/target/entry, names, interfaces and operations.
It translates the compiler's ordinal SCI mask into Space's fixed memory/display
mask20, refusing unknown/duplicate/missing rights or an unexpected ordinal mask
before replacing any output. This is Space packaging policy, not a compiler
capability-name policy.

The existing memory+display capability bits enable one separate zeroed pixel
page at client VA `0x70001000`. The additive runtime-loader APP-API display
extension is VA@72, size@80, pool-id@88; these fields are explicitly zero for
nongranted launches. The required manifest bits (verified against the caller
ceiling) are the effective minted rights and APP-API grants; a permissive caller
ceiling alone never enables the pixel mapping. The loader retains physical-page/domain/size/grants
provenance privately and exposes it to synchronous kernel proof orchestration
only after the client returns. Pool adoption validates that record and active
domain, never client-writable descriptor values or physical pointers. The
client writes an asymmetric red/green 64x16 pattern and sends create/attach/
damage/commit, omitting SHM_CREATE_POOL because the granted pool already exists.
The fixture deliberately forges its descriptor after writing; adoption still
uses the trusted loader record. General SHM_CREATE_POOL remains zero-initialized.

This is a bounded **single-client pixel proof**, not authenticated cross-client
surface ownership, seat input, or an interactive SCI desktop window. Its live
domain retains the page; reclamation is not introduced. The synchronous drain
adds no scheduler/wakeup mechanism. The optional QEMU check exclusively uses
the existing Linux-proof slot at physical `0x280000`, bounds the fixture below
the 3MiB heap, checks both geometries and old-rectangle removal, and validates
actual SCI-generated pixels. `check-spdp-page-frames.py` covers malformed frame
and grant/adoption refusals under all compiler profiles.

### Logical teardown

The existing SURFACE_DESTROY and SHM_POOL_DESTROY requests now retire visible
state. Surface destruction marks an explicit tombstone and clears attachment,
geometry and commit state; later requests to that dead slot are ignored. IDs
are not recycled before `dsp-init`, so this does not solve the existing
32-surface/session limit. Pool destruction clears the compositor mapping/size
and detaches only surfaces referring to that pool. Repeated or out-of-range
destroy requests are harmless. Other live surfaces and pools remain intact.

This is logical teardown, not allocator reclamation: a pool may be a borrowed
loader-granted page, so the compositor never frees its underlying frame.
`dsp sci destroy` runs a real SCI producer sending both teardown frames. The
QEMU proof checks colored pixels before destruction and blue background after,
including a repeated destroy request. `check-spdp-lifetime.py` executes actual
handler/state functions under all profiles with dead-slot, invalid-ID,
other-surface and reattachment controls.

### Phase B (remaining work)
- Generalize the bounded loader-granted pixel proof above into per-client
  pool/surface ownership and lifetime management; client physical pointers
  must never be accepted as grants.
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
