# Compositor / Client Split — Design

- **Status**: groundwork (design + first proof behind a check)
- **Date**: 2026-08-13
- **Scope**: `components/display.in`, `protocol/display.in`, SCI loader / domains

## Shell and layout boundary (2026-10-19)

The original Space desktop uses a command bar and basic niri-like tiling, with
floating controls and application actions. This is shell/layout policy, not a
reason to move application state or authority into the compositor or nanokernel.
Keep command dispatch, layout, input/seat, surface presentation and applications
modular; see the [command desktop design](plans/2026-10-19-command-desktop.md).
The existing SPDP and shared-page ownership rules below remain authoritative.
A future Wayland adapter must translate into these native contracts rather than
replace them with foreign kernel semantics. Neither source modularization nor a
kernel-linked window demo establishes isolated SCI desktop services.

## Private owned canvas / original viewer checkpoint (2026-10-24)

A separately imported private native canvas library owns staging/accepted frames
and leases existing SPDP surfaces. Checked stopped uploads from native VM objects
publish only after full copy and validation; uncertain close retains ownership.
The [canvas evidence](plans/2026-10-24-native-canvas-upload.md) proves two real
protected producers, exact pixels, revocation and teardown controls. The later
[original fbv profile](plans/2026-10-24-linux-framebuffer-app.md) translates one
bounded Linux device mapping onto that contract and the existing renderer.
No second renderer, IPC fabric, foreign frame ledger or physical scanout map is
introduced. These libraries remain kernel-linked, explicitly imported prototypes;
ordinary launcher integration, concurrent tiling and interactive foreign seat
routing remain required work.

## Keyboard editing checkpoint (2026-10-24)

The protected default still uses the existing SPDP seat and shared-page frame
contracts. Normalized key values and private client cursor state now support
interior edits, with real PS/2 input and independently specified caret pixels.
No new input channel or compositor-side text buffer is introduced. See the
[keyboard/editing contract and receipts](plans/2026-10-24-keyboard-editing.md)
for bounds, USB model-only evidence and remaining keyboard limitations. The
standard client editor is still an eight-byte field, not a full text editor.

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

## Bounded two-client session (2026-10-24)

`components/gui-clients.in` extends the synchronous integration path with two
kernel-owned retained SCI instance records and generation tokens. The manager
accepts only a fixed local surface0/pool0 protocol, validates the complete reply
batch before dispatch and translates it to the instance's compositor surface and
pool. Guests receive no record pointer, arbitrary ring selector or compositor
pool allocation authority. Keyboard delivery requires the focused token; pointer
button hit testing changes focus and delivers one typed seat frame.

The loader allocates/maps each client's pixel and ring pages. The client writes
its pixel page while synchronously executing, consumes one event and returns a
complete bounded attach/damage/commit batch; the compositor reads only after
return and validation. This single-flight ownership rule has no asynchronous
buffer-release fence. Close retires the exact runtime generation, withdraws its
token/routing, drains its owned exchange and detaches/composites the surface/pool
before releasing owned backing. The manager is kernel-linked
and clients use existing CPL0 clone domains, so this proves neither hostile-code
hardware isolation nor general multi-client SPDP authorization. Foreign GUI
applications remain a separate protected process/adapter milestone.

`scripts/check-gui-clients.py` builds a temporary root around
`fixtures/gui-clients/session.in`, input SCI and two independently emitted client
SCI images. Its acceptance sequence checks every client pixel and its border:
left keyboard render, real PS/2 pointer click focusing/rendering right, right
keyboard render, right Escape close, stale-token refusal and surviving left
keyboard render. It also checks guest-context and stale-capability refusal, unfocused input
refusal, complete malformed batch
refusal before compositor changes and stable post-initialization allocation
counters. This fixture is a native integration workload, not an upstream GUI app.
The original single-client SPDP/input tests remain independent regressions.

Initial execution exposed shared leaf page tables in `create-shared-domain-pml4`:
a later loader mapping could replace an earlier client's ring mapping. Clones now
copy present non-huge leaf PTs into individually owned frames, preserving flags;
large identity leaves remain copied values. The runtime's explicit clone-owned
ledger now releases those private table frames without freeing borrowed identity
mappings.

Fresh local execution with source-built Inauguration 0.9.322 passed the full
three-SCI QEMU sequence, including genuine pointer focus and exact pixels after
all five interactions. The unchanged `check-sci-seat.py` also passed default,
lean and harden guard profiles. Artifacts, compiler/source hashes, serial log and
six full-resolution screenshots are retained under the selected build directory
(default `/tmp/space-gui-clients`). This native fixture checkpoint does not
complete the real-application GUI corpus in the full compatibility goal.

### Useful bounded native GUI applications

`components/app-gui-calc.in` and `components/app-gui-editor.in` build independent
SCI applications with named memory/display declarations. `gui-widget.in` imports
the existing `font.in` assets and glyph lookup into each SCI image, allocates font
state in its own heap and writes only its granted pixel page. It introduces no
new font parser or shaper. The calculator accepts an eight-character single
binary integer expression with `+`, `-`, `*` or `/`, computes on Enter and renders
its answer or a bounded error. The editor accepts eight printable characters and
Backspace; it now declares a separate fixed-file storage capability for Ctrl-S
and startup reopen. These are small native apps, with no full notes application,
foreign application or CPL3 isolation claim.

`scripts/pack-gui-sci.py` has an explicit two-identity policy, validating exact
`GuiMemory(map)` / `GuiDisplay(present)` metadata and the editor's explicit
`GuiNoteFile(read, write)` authority before SCI ordinal/envelope translation. Unknown identities, entry points, interfaces,
operations and mismatched export metadata are negative packaging cases.

`scripts/check-gui-apps.py` uses a separate temporary-root orchestration; it keeps
the synthetic retained-client checker unchanged. Its real PS/2 scenario enters
`6*7`, checks exact existing-font glyph pixels for `42`, clicks the other SCI
surface, edits/backspaces a field to `notes`, checks calculator pixels remain
unchanged, closes the editor, refuses its token, then computes `6*8` → `48` in the
surviving calculator. It then checks `1/0` renders `err` and the same instance
recovers to compute `6+7` → `13`. Every client pixel and border is compared with the glyph
assets, while domain/capability/allocation counters stay stable after setup.

The workflow exposed missing Shift normalization in input SCI. Kernel and SCI
PS/2 decoders now reuse `protocol/keyboard.in`: separate left/right Shift bits,
shifted US punctuation, Caps Lock letters with repeat-make suppression, and
existing Ctrl-letter normalization. Releasing one Shift keeps the other active;
releasing both restores unshifted input. The launcher gate executes both actual
decoders under default/lean/harden with those sequences. Normalized key-down
routing still does not provide raw key releases, repeat policy, right-Ctrl/Alt,
IME or general keyboard-layout support.

### Retained buffer retirement and reclaim boundary

The private runtime catalog owns each retained instance through a generation
handle bound to its exact component ID, private capability, domain and ledger.
GUI records capture that handle alongside the physical endpoint snapshot.
Before event publication, the manager checks that the handle still identifies
that exact entry/capinfo/ring/pixel owner. Resume establishes the instance's
allocator and domain context. Retire prevents further entry; the GUI then
withdraws token/focus routing, drains/discards the owned ring and removes every
surface/pool consumer before release. In-flight writes finish when synchronous
entry returns; no compositor read overlaps it. Failed exchanges use the same
one-way fence. Closed endpoints are never dereferenced after release.

The loader records private image/import copies, heap frames, ring/pixel frames
and explicitly clone-owned tables. Kernel ring/pixel aliases and the temporary
root-realm edge are restored immediately after initial activation, before
publishing the handle; teardown cannot later restore a freed predecessor's
alias. The empty CPL3-tree teardown remains inapplicable to identity-map clones.
Only the explicit ledger's private frames are released. This remains trusted
CPL0 lifecycle management, not termination of hostile native code.

`check-gui-lifecycle.py --observe` instruments product entry/close calls in a
temporary root and requires more than128 sessions with stable resource counts,
actual backing release, stale-generation/canary/new-client refusal, wrong-owner
and guest denial, and no kernel alias referencing a free frame. Its ordinary
mode tests the unchanged distributable image separately. See the
[lifetime plan](plans/2026-10-24-retained-gui-lifetime.md) for the recorded
19-session capacity baseline and ownership contract.

### Standard-image session integration

The ordinary standard image now packages explicit optional GUI kinds20/21/22.
The full shell's `gui apps` action delegates to `components/gui-session.in`; no
fixture source is imported into the kernel and no foreign application code lives
in the shell. This service launches input/calculator/editor from the boot-image
registry through explicit `sci-load-retained-component` activation, routes pointer/Tab focus and keyboard events, and runs until both apps
are closed. It preserves the surviving client after one closes. Reopening clears
only fully released manager records, reuses its tables/event scratch and mints
fresh GUI/runtime tokens. The input instance is fenced and released after both
clients close. Preflight checks count reusable runtime/domain/private-cap slots;
partial launch and failed exchanges retire already admitted instances.

`check-standard-gui.py` exercises the distributable build, including same-boot
close/reopen and minimal-image refusal. See [native GUI session usage and limits](native-gui-session.md).
This product entry point is independent of the temporary-root proof orchestration.

### Readable standard application profile

The default standard kinds20/21 now select `GuiWindowCalc`/`GuiWindowEditor`,
with explicit `GuiDisplay(present, window)` declarations and the exact bounded
canvas trailer. The original64×16 named clients remain one-page fixtures;
`GUI_PROFILE=legacy` explicitly builds that profile. Their existing protocol
checks remain separate from the readable application tests.

Each readable client owns288 possibly noncontiguous BGRA pages, mapped into a
contiguous kernel-only view above4GiB. The compositor stores a separate explicit
stride per surface and checks the final sampled byte against the owned pool;
old packed geometry and48-byte surface records keep their original meaning.
The supervisor configures visible dimensions that fit the output and translates
local surface0/pool0 into the same exact generation-owned server records.

Clients paint backgrounds, Sans titles/labels and Mono content/result/status,
with visible focus border/caret and real keyboard/pointer input. Versioned SPDP
surface configure/ACK and seat focus events carry scalar generation/extent/scale
data. The entire response is validated before compositor mutation. Ctrl+G text
size and Ctrl+O output mode preserve content through actual hardware resize;
both shortcuts are visible in the windows. The current trusted CPL0 startup
borrows a48-byte supervisor visual config read-only, copies its scalar fields
and retains no pointer; a protected startup will require an owned bounded copy.

The input service's optional version1 scalar poll argument updates its physical
output bounds and clamps position after shrink; legacy zero preserves the old
descriptor behavior. This fixes real pointer reach beyond the old800×600 range.
Motion updates the visible cursor. Since the compositor already repaints the
entire scene, it does not clear an old cursor rectangle over fresh client pixels.

`check-gui-windows.py` checks all six1024/1280/1920 output and2×/3× text
combinations, exact labels/content/caret/status/hints, both pointer targets,
live resize and close/survivor/reopen. Standard product,129-session ownership and
fiveboot NVMe gates auto-detect the actual artifact profile and keep their
assertions. See [native GUI usage](native-gui-session.md) and the
[readable profile plan](plans/2026-10-24-readable-native-gui.md).


### Native GUI persistence

The editor's exact artifact mask is now52 (memory4, display16, storage32), while
the calculator and synthetic clients remain20. The session explicitly grants the
editor's declared profile; manager admission accepts only those two exact pixel
profiles. No existing client receives storage implicitly. The standard-only
`gui-note-store.in` service exposes a bounded eight-byte `/gui-note.txt` contract
through the existing filesystem facade. Current-domain/capability checks precede
pointer access, filesystem calls and allocation, and a real NVMe backend is
required. `check-gui-persistence.py` drives Ctrl-S with actual PS/2 events and
verifies save/reopen, VM reboot/remount, shortening, empty save, independent
calculator survival and missing-storage-grant refusal without target inode/byte
mutation. See [native GUI usage](native-gui-session.md) for limits and commands.

The standalone display SCI's fill/copy calls now import the existing native CPU
memory contracts explicitly, matching the kernel compositor's wrappers. Its
GUI application action remains unavailable because that artifact has no GUI
supervisor binding; it never imports private kernel launch authority. This
repairs the standalone build closure without changing the ordinary protected
desktop launch policy or creating another renderer. Runtime-component and
legacy Volume checks use an explicit read-only SCI selftest artifact rather
than relying on automatic persistent diagnostic-file writes. See the
[UTC metadata/runtime regression evidence](plans/2026-10-24-native-utc-file-metadata.md).
