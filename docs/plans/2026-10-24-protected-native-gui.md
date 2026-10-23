# Protected readable native SCI applications

## Goal and current evidence

Run the existing readable calculator and eight-character persistent editor as
independent CPL3 SCI clients. Keep their actual two-face rendering, keyboard and
pointer focus, output/text scaling, resize, close/survivor/reopen, and NVMe
save/reboot behavior. Prove that a client cannot write supervisor or peer memory,
forge another endpoint, bypass storage grants, execute writable pages, or keep
using a retired generation. Repeated sessions must reclaim every owned frame.

The standard desktop remains the trusted CPL0 profile until the protected path
passes all of those gates. Its current 52-gate application lab and explicit
0.9.324 compiler receipts remain the baseline. This is native GUI work, not a
claim of foreign GUI support or an isolated input driver/compositor.

The protected native runtime's immutable and paged profiles are committed in
`78fdae6`; the GUI staging/ring/accepted-frame core is committed in `f3e12fd`.
Its independent generation catalog, owned user page tables, bounded heap,
syscall stubs and lifecycle have actual CPL3 proofs. An opt-in readable client
gate passes real keyboard/pointer/pixels across six output/scale modes at
`/workspace/local-evidence/gui-protected-readable-standalone/report.json`.
Repeated-session, reboot-persistence and fault integration remain acceptance
requirements before default promotion.
Generic Inauguration 0.9.325 now supplies exact hash-bound SCI layout metadata,
with independently page-aligned data and bindings. Its compiler tests include
actual imported calls with RX text, mutable RW/NX data, RO/NX bindings, and
faulting write/execute controls. This prerequisite does not prove GUI execution.

## Ownership and changes

| Owner | Scope |
|---|---|
| Native runtime owner | CPU/trap entry, native import allowlist and syscall dispatch, protected admission/resume APIs, private ring/canvas/config backing, page mappings, generation projections, allocation budgets and teardown ledgers |
| GUI owner | Explicit GUI packaging composition, protected client adapter and application declarations, supervisor session/reply handling, bounded note-service adapter, model and actual interaction/lifetime/isolation tests |
| Existing display/text services | Output transactions, compositor stride/bounds, focus/layout, current Mono/Sans assets and raster path |
| Inauguration | Generic SCI bytes and truthful layout only; no GUI profile, Space grants, native service IDs or boot policy |

Do not change CPU, loader or shared runtime ownership from GUI modules. Agree
the native APIs and descriptor profile with the runtime owner before production
calls land. Keep the prototype behind an explicit protected build/test choice;
do not reinterpret existing trusted clients or SCI snapshots as user contexts.

## Packaging contract and admission

The runtime and GUI owners agreed on explicit native execution profile
`GUI-PAGED` (profile 3 in the existing version-1 native descriptor, reserved
field zero). Profiles 1 and 2 keep their existing single-descriptor contract.
Agreement is not an implemented or passed admission path yet.

The protected GUI image consists of:

1. Exact generic SCI v2 bytes compiled at the protected native image base with
   entry `client-entry` at base + 64.
2. The exact existing 64-byte GUI canvas descriptor: 768 by 384 BGRA, stride
   3072, 1,179,648 bytes, version 1 and existing flags/reserved values.
3. The final 64-byte native execution descriptor selecting `GUI-PAGED` and
   carrying the raw compiler image size and actual text/data ranges.

The native descriptor's raw size excludes both Space descriptors. The canvas
is at that raw offset, immediately before the native descriptor. The final SCI
manifest size includes both descriptors. Old trusted canvas recognition and old
native single-descriptor admission stay separate; unsupported combinations,
ordering, versions, duplicate trailers or missing descriptors refuse.

Before changing any header or appending either descriptor, packaging verifies
the generic `sci_layout` SHA-256 and image size against the raw compiler bytes,
all integer bounds and independent virtual page alignment, binding extent,
actual import call sites, exports, entry and load base. It also verifies the
corresponding `.text`/`.data` metadata and static size. Only then may Space
translate capability ordinals and write its descriptors/final size.

Use separately named protected calculator/editor declarations, with exact
`GuiMemory(map)` and `GuiDisplay(present, window)` rights. Only the editor also
declares `GuiNoteFile(read, write)`. Space masks remain 20 and 52; no console,
filesystem path, arbitrary mapping, registry or supervisor authority is implied.
The protected native validator must admit these masks only with the explicit
GUI profile and trusted launch grants, not widen its ordinary native profiles.

## Owned mappings and startup

Each handle owns a private image copy and mutable globals. Header/text pages
are user RX; initialized data pages are user RW/NX; bindings and non-text image
pages are user RO/NX. Imports patch only private backing before final mapping.

The runtime owns one SPDP endpoint page, a 288-frame client staging canvas and
a distinct 288-frame supervisor-only presentation snapshot. Physical contiguity
is not assumed. Only staging pixels are user RW/NX at the bounded canvas window.
The compositor receives the presentation snapshot's owned high virtual view,
never the writable staging view. No guest mapping aliases a snapshot frame, and
no guest receives its server address or a physical frame number. Both backing
ledgers are separate: 576 frames do not fit one 512-entry ledger. The existing
owned 2-MiB high view maps the snapshot only. Staging has no additional kernel
virtual view; the runtime copies through its physical frame ledger. Admission
and teardown account for both ledgers and all frames without requiring physical
contiguity or sharing page-table ownership.

The agreed ring access maps the canonical guest endpoint address read-only and
non-executable, preserving the existing client's bounded empty-header reads.
The client cannot edit head, tail, capacity or frame slots directly. Its only
mutation/consumption route is the finite frame bridge below. The kernel view
remains private to this exact runtime instance and its GUI supervisor.

Startup passes exactly 48 visual-configuration bytes copied into owned user
memory: magic, generation, visible width, height, text scale and focus. Capinfo
contains that user address only for initial entry. Later entries expose zero
startup args and receive scalar configure/focus events over SPDP. A supervisor
pointer, manager record, private capability or runtime handle never crosses the
boundary. Guest mutation of its capinfo/config copy cannot change runtime grants,
owned mappings, the configuration recorded by the supervisor or catalog identity.

Keep the generic protected heap address rather than add an obsolete scratch
alias. Adapt the existing app model's scratch base and font bump allocator to
validated private heap descriptors. Preserve the trusted wrapper's existing
addresses and behavior. Reuse the current font assets and drawing functions;
do not add a font parser, renderer or application implementation to the shell.

Protected state offset 112 already owns a native extra ledger and offset 32
owns capinfo; they are not the trusted runtime's pixel-ledger/ring offsets.
New GUI resources belong to an explicit protected GUI ledger. A kernel-only
handle projection validates the exact kind, profile, generation, object,
capability, domain and lifecycle phase before exposing ring/canvas metadata to
the supervisor. Do not reuse trusted `sci-sync` provenance/resume by changing
offset meanings or domain ownership flags.

## Finite service contracts

The agreed native bridge IDs are 13 for frame send, 14 for frame receive,
15 for note read and 16 for note write. The runtime must move its current exit
trampoline outside these 16-byte stub slots: its old offset 256 collides with
service 16. The agreed replacement is the last 16-byte slot at offset 4080 in
the owned trap page. Stub provenance, return addresses and negative controls
must use that distinct exit location. GUI code does not own that change.

### SPDP frame send and receive

Preserve the native function signatures for client reuse, but bind their
implementation through admitted user syscall stubs:

- `chan-page-send-frame(endpoint, object, opcode, arg0, arg1)` accepts only the
  canonical endpoint selector, resolves backing from the current exact live GUI
  instance, checks display authority and ring structure/capacity, and appends
  exactly one existing 32-byte frame. No physical pointer or arbitrary endpoint
  is resolved from the supplied integer.
- `chan-page-recv-frame(endpoint, destination)` performs the same ownership and
  authority checks, validates the entire writable 32-byte destination through
  owned user mappings before changing the queue, and copies one frame. Failure
  must not consume a message or partially change its destination.

Neither call exposes runtime handles, kernel addresses, arbitrary channels,
capability selectors, memory mappings or direct compositor operations. Unknown
service IDs/imports, forged stub provenance, wrong selectors, peer/kernel
buffers, wraparound and cross-page invalid extents refuse without side effects.
The supervisor still validates the complete expected reply batch and local
surface/pool identities before changing compositor state. The bridge does not
turn unvalidated client frames into authority.

### Bounded editor storage

Expose only the existing fixed `/gui-note.txt` read/write behavior, at most eight
bytes. The protected bridge checks the exact live instance and actual storage
grant before translating user pointers or doing filesystem work. A calculator
or editor launched without storage cannot gain it by changing user capinfo.
Validate the full user extent, copy through a bounded supervisor scratch buffer,
and reuse the current filesystem/backend contract. Never pass a raw user address
as a kernel filesystem buffer. No caller supplies a path or file handle.

The agreed private backend is `native-protected-note-backend`, initially zero,
with callback `(request) -> Int`. The request is a runtime-owned supervisor
24-byte descriptor containing operation, bounce-buffer pointer and byte count.
Operations are 15/read and 16/write, and the runtime owns an eight-byte bounce
buffer. The single-argument raw-call wrapper already exists; no new compiler or
CPU calling convention is required. Runtime
code validates the exact instance, live grant and entire user extent before
invoking it, preserves the actual instance's current capability, and returns
-19 if no backend is installed. GUI policy owns the fixed-file callback and its
kernel-only session-scoped install/restore. Extract private storage helpers so
the old trusted pointer/authority guards remain in place; do not pass a protected
user pointer through the trusted component's old fixed-heap guard or into VFS.

Keep established return values and status text, real NVMe requirements, empty
save, shortening, and unchanged-inode/bytes refusal checks. A denied grant or
invalid pointer must not increment service effects, allocate file storage, or
mutate the target. Any small shared storage-policy extraction requires explicit
coordination with the filesystem owner; do not widen or duplicate its VFS.

## Supervisor and lifetime

The agreed kernel-only API surface, pending runtime implementation, is:

- `native-protected-open(port, image, available, name, grants, args_descriptor)`
  returns the opaque catalog handle; arguments are an explicit pointer/length
  descriptor and GUI startup requires exactly 48 copied bytes.
- `native-protected-run(handle, budget)` returns the actual invocation status.
- `native-protected-set-arguments(handle, source, bytes)` updates only the exact
  live owner and returns zero on success; clear with zero bytes after startup.
- `native-protected-ring`, `pixels`, `pixel-bytes`, `entry`, `profile`, `domain`
  and `grants` projections take an exact handle and validate its kind, profile
  and lifecycle phase before returning supervisor-only metadata.
- An invocation-epoch projection and `native-protected-present(handle, epoch)`
  bind presentation to the exact stopped successful invocation. Present refuses
  stale, repeated, running or faulted epochs before changing snapshot bytes.

The protected runtime owns separate staging and presentation ledgers: ring at
private offset 1000, snapshot ledger at 1008 and staging ledger at 1016;
state 112 remains the native extra ledger. Shared explicit server-view/page-count
fields can remain state 40/304/312 under runtime ownership. Pixel resources must
be released before the enclosing extra ledger. These private offsets are
implementation coordination, never a client ABI or a basis for GUI-side frees.

### Acceptance and immutable presentation

A successful client frame-send syscall queues a request. In particular, sending
COMMIT is not yet acceptance of a displayed frame. After entry returns, the GUI
supervisor validates the complete expected reply batch, exact generation and
owned identities. While the client remains stopped, it calls present with the
current invocation epoch. The runtime copies staging pixels into the private
presentation snapshot and records that epoch. Only after successful present may
the compositor attach/read that snapshot and consume it into scanout, before any
subsequent guest resume.

Later guest writes can change staging only. They cannot change the accepted
snapshot or an already consumed frame. Other-client redraws also sample the
accepted snapshot, not the peer's writable staging memory. A later valid present
explicitly replaces the snapshot; a malformed/faulting invocation cannot publish
its staging pixels. This is the enforcement boundary, not merely a claim that
one CPU or synchronous invocation makes shared writable pixels immutable.

Actual controls must accept a known rendered frame, resume hostile code that
changes its staging pixels without another accepted present, and require the
snapshot hash/exact glyph pixels to stay unchanged. A direct user attempt to
write/execute the supervisor snapshot must fault. Exercise stale/repeated epoch
denial, incomplete reply batches, fault/abort/deadline after an earlier accepted
frame, surviving-peer redraw/input and full resource reclaim including both
canvases. No GUI consumer reads staging as a fallback after a failed present.

Use protected open/run/projection APIs; generic trusted resume must continue
refusing protected handles. Initial configuration and every subsequent event
have a bounded invocation budget. The instance's own globals, heap, pixels and
ring persist across successful entries. Input remains routed by current focus;
clients receive no global device or other-client input access.

Normal close, malformed replies, emitted abort, page fault and deadline all use
the same ordering: stop further invocation; withdraw token/focus/event routing;
discard the exact owned endpoint; detach every surface/pool consumer and
composite; release only after that fence. A faulting invocation may already have
marked the exact catalog generation retiring; the GUI fence must still precede
physical release. No post-release page/header/PD dereference is permitted.

Synchronous entry completion permits a bounded snapshot while the client is
stopped; the separate snapshot then prevents post-accept guest mutation.
An incomplete/faulting response is never presented as a valid frame. Closing or
faulting one client must preserve the other's focus, mutable state, input,
pixel pages and storage behavior. Reopening creates fresh GUI/runtime tokens;
recycled component/domain IDs cannot revive stale handles or aliases.

## Executable progression and promotion gates

1. Lock the explicit profile/bridge/projection contract with the runtime owner.
   Add packaging and source-extraction models for exact descriptors, raw SHA
   verification before transforms, malformed composition, import/grant refusal,
   cross-page pointer checks and all-or-nothing receive behavior.
2. Compile actual protected client adapters with frozen 0.9.325. Exercise real
   CPL3 send/receive and startup-copy lifetime first. Assert current CS/IOPL,
   syscall provenance, private image globals, exact page permissions and peer
   ring/canvas refusal; no screenshot-only isolation claim.
3. Run actual calculator/editor rendering and input with the existing precise
   pixel oracle: two typefaces, labels, focus border/caret/status/hints,
   expression/error recovery, editing, pointer/Tab focus, both close orders and
   surviving-client work. Test all six output/text size combinations and saved
   content/status through live scale and hardware mode changes.
4. Preserve all five actual owned-NVMe boot checks: save/reopen/reboot, shortening,
   empty save, calculator survival and denied storage leaving inode/bytes
   unchanged. Add forged capinfo, invalid/cross-page buffer and stale-generation
   storage controls with effects counters checked before/after refusal.
5. Run more than 128 sessions with exact backing/table/cap/domain/object/catalog
   accounting, alternating close order, reopen/reuse, fragmented canvas frames
   and all pixel pages reclaimed. Inject actual client abort, fault and deadline
   during initial entry and later event/render/save paths; fence the failed
   owner and continue real interaction with the peer and shell. Check stale
   endpoint/handle/alias ABA, bad profile/grant admission and constrained-memory
   refusal without changing existing owners or lifecycle counters.
6. Rerun trusted readable/legacy fixtures, native lifecycle, generic user-context,
   launcher/damage, minimal/standard packaging and affected personality gates
   from a recorded immutable source/compiler snapshot. Inspect rendered output.
   Promote the protected default only after matching existing behavior and all
   additional permission/lifetime gates; retain an explicit trusted regression
   profile and report unsupported imports/limits honestly.

Every receipt records source hashes, exact compiler path/hash, raw and packed
artifact hashes, selected execution profile, actual app inputs, screenshots and
disk origin. This document is the implementation plan; it does not report any
protected GUI gate as passed yet.

## Packaging checkpoint

`pack-gui-sci.py --protected` now implements the explicit profile-3 composition
for the two separately named protected identities. It validates the exact raw
hash, generic ranges/section metadata/zero padding, actual binding tables and
entry, admitted unpatched text call sites, and exact capability declarations
before changing bytes. Its ordinary trusted behavior remains the default.

`check-gui-protected-profile.py` compiled six actual artifact-policy fixtures
with frozen 0.9.325 across default/lean/harden and passed 147 refusal controls.
The receipt is `/tmp/space-gui-protected-package-second/report.json`; fixtures
are explicitly not product applications or runtime execution evidence. Existing
four trusted/tiny canvas identities passed their unchanged policy gate with
both frozen 0.9.324 and 0.9.325. Production protected runtime calls and GUI launch
integration remain held until the core API's actual lifecycle proof is ready.

Pure client preparation is isolated in
`/tmp/space-gui-protected-client-source`, with working-tree consumers untouched.
It extracts the existing window state/paint functions, adds explicit scratch-base
calculator/editor helpers while retaining trusted wrappers, and supplies separate
protected entry/descriptor/allocator adapters. Six actual app/font artifacts
compiled and packaged across default/lean/harden; source copies and raw/packed
hashes are preserved in
`/workspace/local-evidence/gui-protected-clients-prepared/report.json` and its
adjacent `source` directory. The source-extraction startup/allocator/event model
passed all three profiles at
`/workspace/local-evidence/gui-protected-client-model-third/report.json`.
Initial extraction checkpoints passed actual trusted standard desktop and
six-mode rendering. Subsequent protected-only focus validation and wrapper
formatting are covered by fresh artifact/model checks, not represented as final
protected Space GUI receipts. No alternate host-service harness was built.

### Explicit supervisor launch authority

Keep the boot root capability at `0xF`. During explicit supervisor bootstrap,
create one private supervisor object bound to the current root realm and mint
one launch capability with exactly memory, display and storage (`52`). Keep its
object identity, realm, capability slot and initialized state private; validate
all of them and live rights before borrowing this capability only around
`native-protected-open`, restoring the exact caller capability immediately on
success or refusal. Calculator admission requests the `20` subset. Bootstrap is
one-shot; revocation must not trigger reminting. No app receives the launch
capability index. Reuse across sessions avoids new capability/object high-water
marks. This is a kernel-linked supervisor bootstrap contract, not an existing
independent service authorization boundary. The protected default stays opt-in
until the full interaction, persistence and lifetime gates pass.
