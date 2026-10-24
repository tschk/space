# Retained native SCI ownership

Retained mode2 now owns its private component/capability record, clone page-table
tree, image frames,512-frame application heap, ring/pixel frames, metadata and
allocator ledger. Mode1 owns the same resources and releases them when its entry
returns. Whole-image copying preserves compiled mutable globals per activation;
import patches target the owned image frames, including patches across a page
boundary. Shared library providers retain their explicit shared lifetime.

The old actual same-image test returned1 then2 across two fresh activations at
`/tmp/space-global-state-baseline-2/`. A separate heap did not establish fresh
initialized data. The new counter fixture is compiled from ordinary source and
checks independent initialized globals on initial and resumed entries.

`runtime-retained.in` maintains a bounded64-record catalog. An opaque positive
handle contains a slot and monotonic generation, never a metadata pointer or raw
capability index. Every operation checks that generation against the live ledger,
component ID, exact component/capability ownership and domain. Generation wrap
refuses admission. Only kernel-owned callers may use these helpers; the whole
`runtime-instance-` prefix is absent from the flat SCI registry.

The supervisor captures `runtime-instance-last-handle` immediately after load.
`sci-sync-handle` travels with the existing retained record and proof snapshots.
`runtime-instance-resume(handle,entry,argument)` requires the original entry and
owned cap-info address, establishes that instance's allocator/context and invokes
the abort-aware runtime boundary. An emitted abort marks the instance retiring.
`runtime-instance-retire(handle)` prevents further resume; repeated retirement of
the same still-owned generation succeeds. After withdrawing routes, draining the
ring and detaching owned surfaces, the supervisor calls
`runtime-instance-release(handle)`. Stale release/retire/resume fail after reuse.

`runtime-instance-can-admit(count)` checks reusable catalog, domain and private
capability capacity. Global capability allocation remains monotonic; only the
private never-escaped runtime slots are recycled. These handles do not turn
trusted CPL0 SCI execution into hardware protection.

Kernel ring/pixel aliases and the temporary root-realm component edge are
restored immediately after initial activation, before handle publication. Their
saved locations are cleared, so later close cannot restore a freed predecessor
when instances retire in a different order. Supervisors use physical owned
ring/pixel addresses; guests use their clone mappings. General retained serial
syscall translation and asynchronous volume lifetimes remain separate contracts.
Retained clients publish no free-form exports; future retained service providers
need explicit owned export leases before they can participate in that registry.

The independent core check at `/tmp/space-native-retained-source-immutable/report.json`
passed70 cycles,280 initial and490 resumed activations. This includes70 real
emitted allocation aborts after successful allocation during resume, plus
byte-identical comparison of both original boot images after every cycle. It
checks independent globals of simultaneous copies of the same image, interleaved close/reuse, continued peer execution,
stale-generation refusal and stable frame/heap/domain/capability/object/export
state after warmup. Run `scripts/check-native-retained.py --in /path/to/in --out
/new/output` to repeat it. GUI close/fence integration and its actual product
session stress are a further gate, owned by the GUI supervisor.
