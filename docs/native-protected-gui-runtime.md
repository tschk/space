# Protected GUI runtime mechanism

Native execution profile 3 composes the generic paged SCI image, the exact
64-byte readable-canvas descriptor, then the native execution descriptor. The
native raw size excludes both trailers. Profiles 1 and 2 retain their separate
single-trailer format and finite service policy. The trusted CPL0 desktop remains
the default; this checkpoint proves the protected runtime with compiled fixtures,
not the completed readable GUI consumer or a default promotion.

Admission accepts only GUI declarations 20 (memory/display) or 52 (also storage),
checks the caller actually holds them, validates every descriptor/import before
lifecycle allocation, and requires 48 copied startup bytes. A supervisor launch
capability is separate from the existing root boot capability. No application
receives its raw index, runtime handle, kernel address or physical frame number.

## Ring and presentation ownership

Each instance owns a frame endpoint at user `0x70000000`, mapped RO/NX. Finite
SYSCALL services 13/14 implement the existing frame send/receive signatures using
that instance's physical endpoint only. They check provenance, admitted imports,
current object/domain/capability, display authority, canonical selector and ring
structure. Receive validates all 32 writable destination bytes before dequeue,
then copies through an owned supervisor bounce. Peer/kernel/cross-end pointers
refuse without changing head, tail or destination. The bridge does not accept
client messages as compositor authority; the GUI supervisor must validate its
complete expected reply batch.

The 288-page RW/NX guest canvas at `0x70001000` is staging memory. A distinct
288-page front snapshot has an owned supervisor-only view above 4 GiB. Each has
its own backing ledger; physical contiguity is not assumed. Only the front has
a server view, and the guest page tables never map it.

A successful send of COMMIT queues a request. Acceptance happens when the trusted
supervisor validates the complete reply batch and calls
`native-protected-present(handle, epoch)` while the guest is stopped. The call
requires the exact live generation, current display grant, normal completed
invocation, latest epoch and an epoch greater than the previously accepted one.
It copies all staging pages to the front and records acceptance. Later resumed
guest writes cannot alter the accepted frame. Faulted, retired, revoked, stale,
replayed and future presentations refuse before touching the front. The
compositor must consume the projected front, never staging memory.

`native-protected-epoch(handle)` starts at zero and advances after each actual
completed invocation, including fault/deadline/abort stops. Admission failures
do not advance it. Epochs do not wrap. The return capsule is at trap-page offset
4080, separate from service 16 at offset 256.

## Supervisor API and storage boundary

The existing `native-protected-open/run/stop` and common retire/release APIs
remain. `native-protected-set-arguments(handle, source, bytes)` copies bounded
supervisor data for the exact inactive live owner; clear with `(handle,0,0)`
after startup. The next entry rebuilds capinfo from supervisor state, with only
owned user addresses and the startup copy at capinfo + 256.

Kernel-only `native-protected-ring/pixels/pixel-bytes/entry/profile/domain/grants`
projections validate exact profile, generation, object, capability and domain.
They accept live or retiring records so the supervisor can drain, detach and
composite before physical release. Released/stale handles return zero without
reading freed pages. Invocation and argument changes remain live-only.

Services 15/16 provide bounded note read/write transfers, at most eight bytes.
The runtime checks live storage authority before user pointer translation,
validates the entire extent, and copies through its own eight-byte bounce. The
private `native-protected-note-backend` is a supervisor callback taking one
request pointer: `{operation15or16, supervisorBouncePointer, bytes}`. The backend
owns fixed-file policy and must not receive or reinterpret a guest address.
No backend returns -19; missing storage returns -13; invalid note extents return
-22. Unsupported/unimported trap methods return -38. This mechanism does not
implement arbitrary paths, file handles or filesystem policy in the native core.

## Lifetime and capacity

The shared state retains execution kind 2. Its extra ledger owns ring +1000,
front ledger +1008, staging ledger +1016, copied arguments +1024, note bounce
+2048, note request +2080, receive bounce +2176, completed epoch +2320 and accepted
epoch +2328. These offsets are private runtime implementation details.

The fixed admission budget adds 581 frames to the existing protected base:
576 pixel backing frames, two ledgers, one server PD, one server PT and one ring.
The fixed allocation stream remains IRQ-masked after capacity checks. This is
bounded admission, not arbitrary mid-allocation failure recovery. User page
tables are withdrawn first. The owned server PDPT entry and PDE are then cleared
and flushed before either pixel ledger/backing or its table frames are freed;
pixel teardown precedes the enclosing protected extra ledger. Release follows
the GUI routing/drain/detach/composite fence. Epochs and recycled domain IDs do
not replace the catalog generation check.

## Actual evidence

- `/workspace/np-gui-final/report.json`: actual .325 compiled CPL3 fixtures,
  two same-image instances, 21 preallocation refusals, RO ring/NX canvas,
  cross-page receive and no-consumption refusal, live-grant note bounce,
  accepted whole-canvas hashes unchanged after hostile resumed writes and
  denied presentation, real faults/abort/deadline, peer survival, 140 lifecycle
  instances with alternating close order, exact resource accounting and stale
  view/handle withdrawal.
- `/workspace/np-gui-oom-final/report.json`: 32 MiB, 3704-frame conservative
  budget and 3703 available frames; IF0/IF1 admission refuses before allocation,
  with exact cap/domain/resource bytes unchanged, peer execution and a later
  fresh launch surviving.
- `/workspace/np-gui-paged-reg` and `/workspace/np-gui-immutable-reg`: unchanged
  profiles 2 and 1 actual runtime/lifecycle gates pass. The existing trusted
  noncontiguous-canvas gate passes at `/workspace/np-gui-trusted-canvas`; actual
  seat/resume/frame source models pass default/lean/harden with the real new
  ledger-slot helper included.

Repeat `scripts/check-native-protected-gui.py --in /explicit/.325/in --out
/new/output`, adding `--mode oom` for constrained memory. Readable protected
calculator/editor input/render/scale/persistence/session proofs belong to the
GUI consumer integration plan and are not implied by the core fixtures.
