# Retained GUI instance lifetime and reclaim

Scope: advance the working native calculator/editor session from logical close to
physical reclamation through explicit runtime ownership. Keep the five-boot
NVMe persistence and ordinary native application checks intact. This does not
create protected native GUI domains or a foreign GUI adapter.

## Actual baseline

`/tmp/space-gui-lifecycle-baseline/report.json` targets129 same-boot sessions on
the ordinary standard image, alternating which client closes first. It completed
19 sessions and refused session20 with the existing capacity message. This is a
recorded baseline failure, not a lifecycle pass. Image SHA256:
`5266456a13142a5dc0c36203c96fd88dc95887d4bea3fedc9be3c214aae0b3f1`.
The independent five-boot persistence gate already passes saved8byte text,
shortening, empty saves and missing-storage-grant refusal.

At that baseline, mode1 execution had an owned runtime ledger and teardown.
Mode2 retained activation had no equivalent ledger, used monotonic component/
capability state, left kernel ring/pixel aliases installed and did not establish
the instance allocator context on resume. GUI close detached surfaces and
retired its token while leaving input/client backing live. `gui-session-run`
also allocated an eight-byte event scratch buffer on every session.

## Implemented ownership and core boundary

The runtime/loader owner implements an opaque generation handle for retained
instances. A handle identifies an exact live ledger, private capability,
component object and object generation, and domain. Domain ID, object membership
or a reused metadata-frame pointer alone cannot authorize resume or release.
No handle layout or privileged record pointer is passed to application code.

The current runtime ledger owns a metadata frame,512 heap frames, ring/pixel
frames, cloned page-table frames, imported malloc allocations and private
capability/component records. Retained activation needs the same explicit
ownership with a live→retiring→dead lifecycle. Resume must validate the generation
and exact ownership, establish the matching allocator/context and use the
abort-aware runtime entry boundary. Kernel service allocations keep their own
persistent allocator; only the client's rebound allocator imports are scoped to
the instance. The GUI's existing embedded font allocations are already inside
its owned SCI heap.

The agreed private supervisor API is `runtime-instance-last-handle` captured
immediately after activation, `runtime-instance-resume(handle, entry, info)`,
`runtime-instance-retire(handle)`, `runtime-instance-release(handle)` and
`runtime-instance-can-admit(count)`. Resume requires the exact owned entry and
capinfo address; the runtime owns context switching. Retire/release return0 on
success; admission returns1/0. The core owner delivered a compile-ready boundary
with actual same-image/global/allocator proof; GUI calls now use it. The
generation encoding stays private. Existing input/app proof snapshots carry
`sci-sync-handle`; adding it
only to the GUI manager would leave independent regressions with stale context.

Retained activation also owns a private image/import patch copy. Reclaiming
only heap/ring/page-table ownership would leave independently loaded instances
sharing mutable emitted globals. The core's same-image counter control proves
independent mutable state, including interleaved resume and release/reuse.

## Alias lifetime and ABA refusal

A retained client currently installs its ring/pixel at the same two kernel VAs.
If right saves left's PTE and left is freed first, restoring right's saved PTE
later would restore a pointer to freed/reused left memory. Never repair that
chain solely from the old PTE value or domain ID.

Current GUI/SPDP/input supervisors consume physical ring/pixel addresses. Restore
or remove the retained activation's kernel aliases immediately after initial
entry returns and before publishing the retained handle. Leave the client's own
private mappings intact. Teardown must not restore those aliases again. This
removes the retained-instance chain rather than attempting to unwind stale
owners. Validate that the mapping being removed still belongs to this activation.

The saved root-realm component edge has the same ABA risk: input→left→right,
then left-first close, must not let right's teardown restore a freed/reused left
component pointer. Validate the prior object's exact ID/generation before any
restoration or clear the invalid edge; pointer/type equality is insufficient.
The runtime handle catalog owns the retained lifetime independently of this
single compatibility graph edge.

Admission must count reusable catalog/domain/private-capability slots rather than
rejecting on monotonic high-water counters alone. A high-water table can be full
while owned free slots remain available. Any partial launch failure must retire
already admitted handles through the same fences.

Separate Volume initialization and old serial shared-buffer syscall paths also
refer to the same VAs. Preserve their behavior; current bounded GUI clients do
not use those serial syscalls. General retained profiles need their own syscall
buffer-translation proof before this observation is generalized.

## GUI-side close fence

1. Entry has returned to kernel authority; validate and consume the whole close
   response, leaving the client's ring drained.
2. Retire the exact runtime handle, then retire the GUI token and prevent further
   input/entry. Clear focused routing before another event can select it.
3. Destroy its server surface, clear its owned pool and all compositor references
   to that pixel page, and finish a composite that cannot read it.
4. Ask the runtime to release the exact retired handle. Its teardown verifies no
   invocation/allocator context is active, revokes the owned capability, removes
   mappings and releases only the ledger's resources.
5. Keep the other client's token, mapping, pool and input behavior unchanged.
   Do not dereference the closed client's physical page after release.

After both clients close, stop polling the input instance, drain its typed word
ring, retire its private snapshot and release its exact handle. Reuse the GUI
manager/server/event scratch allocations between sessions. Reopen gets fresh
runtime handles and GUI tokens, even when domain/capability/object storage is
reused. A failed exchange needs an equivalent one-way retirement/fence; it must
not revive the token to retry teardown.

## Acceptance evidence

A fresh same-boot run must complete more than128 actual sessions, alternating
left-first/right-first closure, with real keyboard/pointer input, exact client
pixels, live-other-client updates, stale-generation refusal and fresh reopen
identities. Include explicit allocator use on resume to test the scoped context.
Keep the existing GUI calculator/editor and five-boot persistence gates.

After warmup, compare heap high-water, free-frame count, domain/capability
high-water, object-arena extent, export count, clone ownership and live runtime
ledger count. Logical object/token generation counters may advance. Free-list
head pointers can legitimately differ with close order; compare bounded counts
and ownership, and reject cycles/double frees. Observe zero outstanding GUI/input
ledgers after a session rather than treating a successful close marker as proof.

For alias ABA, verify neither kernel ring/pixel PTE points into a frame on the
free list after either close order. Prove that old handles/tokens cannot touch a
new instance's rings/pixels or a deliberately recycled canary allocation. Direct
foreign/guest, stale-capability and wrong-owner release attempts must refuse
before any resource mutation. Preserve existing assertions and distinguish a
capacity refusal, protocol mismatch, fault or source-drift run from a pass.

`scripts/check-gui-lifecycle.py` supplies the standard-image behavioral portion:
at least129 sessions, calculation and editing each session, real pointer focus
every16 sessions, alternating close order, survivor input, and exact glyph and
surface-clear pixels after every transition. It records all frame digests and
keeps sampled full screenshots. Ordinary mode explicitly does not establish core
physical ownership. Its `--observe` mode compiles temporary copies of the actual
manager/session with private observer wrappers; product close/entry functions
remain intact. It additionally verifies at least512 reclaimed frames per client
close, exact capability/domain withdrawal, no residual compositor references,
guest/wrong-owner refusal, dead handles against deliberately recycled canary
frames and new live-client pages, zero live ledgers after each session and stable
resource counts after16 warmup sessions. Kernel ring/pixel aliases are checked
against the complete bounded free list after either close order.

Fresh frozen-source Inauguration0.9.324 receipts:

- `/tmp/space-gui-lifetime-retained-snapshot/report.json`:129 uninstrumented
  standard-image sessions passed.
- `/tmp/space-gui-lifetime-observer-final/report.json`:129 actual sessions with
  private resource/ABA observer passed;367-file source snapshot manifest at
  `/tmp/space-gui-retained-final-source.source.json`.
- `/tmp/space-gui-lifetime-token-final/report.json`:129 additional sessions
  passed with explicit stale GUI-token denial after reopen and retired reply
  refusal before reading freed endpoints. Latest source manifest:
  `/tmp/space-gui-retained-token-final-source.source.json`.
- `/tmp/space-gui-persistence-lifetime-final/report.json`: unchanged fiveboot
  actual NVMe eight-byte save/reopen/shorten/empty and denied-inode proof passed.
- `/tmp/space-standard-gui-lifetime-final`,
  `/tmp/space-gui-clients-lifetime-final`,
  `/tmp/space-gui-lifetime-launcher-final`, and
  `/tmp/space-gui-lifetime-variants-final`: product/minimal, synthetic protections,
  actual desktop launcher and ordinary applications in both images passed.
  `/tmp/space-gui-lifetime-damage-final` passed188fps against30fps minimum.

These are native CPL0 lifecycle and bounded application-workflow results. The
64×16 content remains too small for usable desktop windows; readable independent
application surfaces and output/scale coverage are the next GUI quality slice.
