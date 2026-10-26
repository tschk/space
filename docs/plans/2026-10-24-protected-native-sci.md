# Protected native SCI execution

The goal is a native component execution profile using hardware-isolated CPL3
rather than the existing trusted CPL0 clone profile. Component declarations,
explicit grants, owned objects and bounded service imports remain the contract.
This work does not turn native SCI into a POSIX process personality. Existing
trusted CLI/GUI SCI activation and retained lifetimes keep their current ABI.

## Current evidence and prerequisite

Generic owned user contexts now have actual syscall suspension, independent
parent/child GP/FX state, terminal fault/deadline recovery and exact supervisor
state restoration. The existing runtime owns private images, heap backing,
component/capability records and generation-bearing retained handles. Its current
runner and destructor specifically assume trusted CPL0 clone domains.

The current SCI v2 emitter puts mutable data after code at only eight-byte
alignment. Its sidecar section sizes are placeholders and cannot authorize
RW/NX mappings. Mapping the whole artifact RX supports an explicitly bounded
immutable-image profile; writes to mutable image globals must fault. A general
native profile needs truthful compiler section boundaries and page-aligned
mutable data. This limitation must remain visible until the actual same-image
mutable-global test passes.

Inauguration owns a generic `SciLayout` and truthful sidecar with image-relative
text/data/binding offsets and sizes, load base, image size, page size and the
artifact SHA256. Text includes instructions/read-only literals. Mutable data's
virtual start aligns to a page. Existing v2 header, call-site offsets and import
records remain compatible. Space packaging verifies that sidecar against the
exact bytes and embeds a separately versioned bounded execution descriptor.
The compiler receives no Space capability names, syscall numbers or grant policy.

## Runtime integration boundary

New `native-protected-*` modules own profile admission, trap-service bindings and
execution. They consume `runtime-instance-image-valid(image, actual_extent)` and
preflight every import against their own finite allowlist before allocation.
They never consult the ordinary flat kernel export registry for a callable
address. No existing SCI loader entry changes profile implicitly. Supervisor
entry points stay unavailable as ordinary SCI imports.

Use the existing component object/private capability pool and retained generation
catalog, with an explicit execution-kind discriminator. Protected instances use
owned user page tables; trusted instances continue using owned clone page tables.
The shared destructor branches on validated kind and releases the matching table
tree before backing. It must never pretend a user domain is a clone by changing
ownership bitmaps. Protected heap metadata and context/stack/trap backing get
explicit ledger entries. Generic trusted resume refuses protected handles;
protected resume refuses trusted handles. Shared retirement/generation validation
continues to prevent stale-handle and capability ABA.

The initial fixture profile uses a private immutable SCI image mapped RX, a
private bounded heap, stack and capinfo mapped RW/NX, and a private RX service
stub page. All addresses are within explicit nonoverlapping user ranges. Capinfo
contains user addresses and granted masks; reserved raw-cap fields stay zero.
Arguments are bounded copies, never kernel pointers. Each invocation initializes
a generic user context and runs with strict IOPL0 and the scoped IRQ0 budget.
A normal entry return reaches an owned exit stub; explicit abort, fault and
exhausted budget terminate only that invocation/instance according to policy.

## Limited native service bridge

Each admitted import patches to an owned user stub that invokes SYSCALL, moves
native ABI argument four from RCX to R10, and returns RAX. The hook dispatches
native component service IDs, independent of foreign ABI syscall numbers. The
profile admits at most six register arguments and rejects unsupported imports
before patching or resources. Callee-saved registers follow the existing native
ABI; SYSCALL's RCX/R11 clobbers remain caller-saved.

The first service group is compiler abort, bounded memory allocation and console
output. Allocation returns only addresses in the owned user heap. Free-list and
allocation metadata stay supervisor-owned; the guest cannot forge kernel links.
Calloc checks multiplication; realloc copies only validated owned ranges. Any
allocation failure has real null/abort behavior and cannot fabricate success.
Console services require the declared/granted console capability and bounded
translation of the calling instance's user buffer. Kernel pointers, peer pages,
unterminated strings and oversized extents refuse without output or corruption.
Only explicitly enumerated serial/APP-API formatting helpers are supported;
legacy shared libraries containing IN/OUT are not silently mapped into CPL3.
No filesystem, display, networking or generic supervisor imports are promised by
this first slice. Later service groups must add explicit object/capability and
pointer/lifetime contracts rather than widening the raw registry.

## Acceptance gates

The first gate compiles actual `.in` SCI clients and runs two live instances with
private image and heap state. It proves admitted imports execute through real
CPL3 SYSCALL, exact native register ABI, output/heap behavior, peer survival and
fresh invocation semantics. Negative controls exercise RX text writes, NX heap
and stack execution, kernel/peer pointer reads and writes, privileged I/O, forged
service IDs/capabilities/arguments, denied imports and malformed descriptors.
Actual compiler-generated abort and a genuine infinite loop must return 134 and
124 while the other instance and shell survive.

Repeat more than 128 normal/abort/fault/deadline activations with exact cap/domain,
backing-frame, object/catalog and allocator accounting. Retire/release must
withdraw mappings before freeing backing; stale handles and recycled domains
cannot resume. Insufficient-memory admission must refuse before lifecycle
allocation or unwind every partial ledger. Retest existing trusted native CLI,
retained GUI, generic user-context and foreign process gates.

After truthful paged layout is available, promote to separate RX code and RW/NX
mutable data only after same-image global counters are independent, initialized
globals start correctly, data writes succeed, text writes and data execution
fault, canonical source bytes remain unchanged and exact teardown stays stable.
Then expand real native apps and protected GUI services as separate reviewed
capability groups. Each receipt must state the actual profile and unsupported
imports; RX-only fixture evidence is not general native application coverage.

## Checkpoint: explicit immutable and paged native profiles

The initial profile and truthful-layout prerequisite are now implemented.
Inauguration commit `0a0a5a2b` supplies frozen .325 generic SciLayout and independently
aligned mutable/binding sections. Space profile 2 has 279 actual CPL3 fixture
invocations; .324 immutable profile 1 has 274. Both pass 70 mixed trusted/protected
lifetime cycles (140 protected instances), actual compiler abort/fault/deadline,
slot-recycle generation denial and stable exact ownership/resource checks. The
32 MiB gate proves budget-minus-one admission refusal and peer/recovery survival.
See `docs/native-protected-sci.md` for exact contracts, receipts and limits.

The next bounded consumer is profile 3 protected readable GUI: exact memory/
display grants 20 or memory/display/storage 52, finite ring/note methods, owned
canvas/server view and startup data copies. Its packaging and consumer work are
separate from this implemented profile 1/2 checkpoint. Existing trusted desktop
defaults remain unchanged. Native filesystem and wider real CLI imports also
remain explicit future service groups.
