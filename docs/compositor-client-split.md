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
memory domain. Four initial complete 32-byte SPDP frames (three on a resumed
geometry update) travel through the loader's
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

### Bounded synchronous instance reuse

The proof loads one SCI v2 instance on `dsp sci left`. Subsequent `right` and
`destroy` commands reenter that same retained entry/domain with fresh trusted
argument strings; they do not reload code, mint another capability, or allocate
another heap/ring/pixel page. Before reentry the kernel validates the active
domain/PML4, original capability target and exact rights, retained image entry
bounds, and one captured drained ring header. Malformed or undrained rings are
rejected without resetting/dropping frames. A new load invalidates this one
current-instance record; this is not a multi-client registry.

All 96 writable cap-info bytes are reconstructed from private loader state before
entry, including fresh args and the original heap/ring/pixel mappings. The fixture
forges descriptors and its args pointer between entries; its persistent heap word
proves subsequent calls reuse state rather than creating another surface. Existing
ring head/tail positions are preserved. The kernel checks successful domain entry
and restores the previous domain after return. Resume itself performs no allocation.
The QEMU check asserts one loader/domain creation and stable domain/capability/
heap/free-list counters plus the same ring and pixel physical pages through three
reentries. `check-sci-resume.py` covers descriptor reconstruction and invalid
domain/cap/entry/header/pending-frame/switch controls under all profiles.

This remains explicit kernel-driven synchronous reentry, not scheduled execution,
seat input, multi-client authority, frame reclamation, or hardware-fault recovery.

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

### Retained input service prerequisite

`python3 scripts/check-input-sci.py --in /path/to/in` builds the existing Input
component with synchronous `input-poll-entry`, loads it once, and drives actual PS/2
keys through repeated synchronous entries. `input sci` is the dedicated kernel
proof command; Escape returns to the shell. The existing asynchronous
`input-entry` still initializes and polls with interrupt wakeup for normal boot.
The first entry retains the existing hardware initialization waits; subsequent
poll steps are bounded and retain keyboard modifier/mouse-button state. Its one-word ring keeps the existing input ABI (producer head, consumer
tail), with captured header validation and drop-on-full behavior. This is distinct
from the four-word SPDP ring and does not deliver seat events to an app.

Only the kernel proof admits the known input artifact at its fixed load base to
unit-one reentry. Every new load resets the private role to SPDP; ordinary
`sci-resume-sync` rejects an admitted input instance. Shared resume validation
still checks live domain/capability/code provenance, a drained valid ring,
descriptor reconstruction and domain restoration. Reentry allocates nothing.
The QEMU gate checks five keys exactly once (including Ctrl release), one domain
and stable page/allocation counters. The isolated three-profile resume gate also
covers malformed headers, empty/full/wrap behavior and SPDP-role rejection.
This is one retained input service, not an app input endpoint, scheduler,
multi-client authority or authenticated seat routing.

### Two-endpoint keyboard-to-client proof

`python3 scripts/check-spdp-input.py --in /path/to/in` builds a separate
`fixtures/spdp-input/client.in` plus the existing bounded subsequent input poll.
The dedicated `input app` kernel command retains exactly two private snapshots as
flat `SciProofSnapshot` records with named fields and static storage:
one input domain/word ring and one client domain/frame ring/pixel grant. Named
kernel operations capture those known roles; every helper checks domain zero
before snapshot selection/access. The ordinary current-record API remains and
ordinary SPDP resume still rejects pending frames. Replacement and failures
that return to the kernel domain retire the relevant snapshot; this does not
reclaim domains or frames.

The existing keyboard SEAT opcode now specifies four words:
`[SPDP-OBJ-SEAT, SPDP-SEAT-KEYBOARD-KEY, kernel ticks, key | (state << 32)]`.
The low 32 bits are the input service's normalized ASCII/control code; the high
32 bits are state (0 released, 1 pressed). This proof routes actual KEY_DOWN
only; it does not invent release events or claim evdev keycodes, IME or a
modifier/repeat stream. The input word ring retains its distinct producer-head,
consumer-tail orientation.

Delivery is explicitly synchronous and half duplex. The kernel validates the
client ring drained, publishes one complete seat frame, rebuilds its writable
descriptor and invokes that retained client. The client consumes exactly that
frame before writing its pixels and publishing three rendering response frames
(or two teardown frames for the fixed proof's Escape close). The kernel validates the expected consumed head and the complete response header/count
before dispatch/composite. Failed consumption, malformed metadata or failed entry
retires the client snapshot when the kernel domain is restored: no composite or
replay. If restoration itself fails, helpers reject further calls in the guest
domain without writing private snapshot state. After explicit kernel recovery,
the still-pending exchange is refused and retired without another invocation;
this proof provides no general domain-fault recovery mechanism. No generic
pending-ring selector or new transport/endpoint is exposed to the guest.

This fixed proof filters keys other than `a`, `b` and Escape; it is not general
keyboard routing. Actual QEMU keys `a` then `b` produce distinct asymmetric
64x16 client-written pixel patterns. Screenshots verify every surface pixel,
blue bounds and the all-blue region after close. Empty
polls/key releases do not trigger another delivery. Actual Escape is delivered
as one seat key: the client sends the existing surface/pool destroy messages.
After validating both replies, the kernel verifies dead surface/detached pool,
composites blue, retires its app snapshot in domain zero and checks a later
delivery refuses without changing the drained ring or counters. Only then does
it return to the shell. This is logical teardown, not domain/frame reclamation.
Two distinct domain/ring identities, the trusted pixel grant and allocation
counters remain unchanged after setup. The three-profile `check-sci-seat.py`
gate exercises the actual snapshot/delivery code with guest-domain, stale-cap,
dead-domain, pending/malformed-ring, no-consume, overconsume and no-replay controls.
The old pixel proof and one-service input proof remain separate regressions.
This is one fixed client recipient, not a focus manager, app isolation boundary,
scheduler, authenticated multi-client seat or complete desktop environment.
