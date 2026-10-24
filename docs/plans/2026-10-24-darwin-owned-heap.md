# Darwin owned allocator slice

Advance the committed eager adapter with a separate finite descriptor revision
and a per-activation heap. Preserve the existing seven-service profile and all
its gates. Original macOS jq imports `_malloc`, `_calloc`, `_realloc` and `_free`;
they remain unknown to the existing adapter. Capture their actual refusal in a
valid revision-1 Mach-O import fixture before implementing this expansion.
Original jq itself remains refused for its wider layout and 136 dependencies.

Reference-only review of Rosemary's pinned `darwin/src/malloc.rs` confirms useful
behavioral seams: 16-byte minimum alignment, zero-size allocations with a minimum
block, `free(NULL)` no-op, failure preserving the original realloc allocation,
and Darwin `realloc(p,0)` obtaining a new minimum block before freeing p. Its
host mimalloc/zone implementation is not copied or linked. Full malloc zones,
threading and host pointers are outside this slice.

## Bounded native ownership

Add `darwin-owned-heap.in`, above generic frame/page/domain/context mechanisms.
Reuse native backing frames and existing protected mapping ledgers, without
putting Darwin allocation policy in CPU/native kernel primitives. The existing
native-SCI allocator is tied to its own runtime state kind and address layout;
no fake SCI state is constructed to use it. A private supervisor-only metadata
frame owns 128 records; the guest sees a 64-KiB RW/NX arena at a reserved VA.
No allocator header or free-list link is trusted from guest memory.

A new immutable adapter identity/revision admits the previous seven real typed
services plus `_malloc/_calloc/_realloc/_free` through the established genuine
chained fixup format. The old descriptor and startup/eager providers remain
unchanged. Unknown APIs, other dependencies, constructors, TLS and framework
metadata remain refused before allocation.

Borrow a live native memory-service grant explicitly at admission, alongside
serial/storage roles. Require it for allocation changes and check revocation
at each actual heap operation. Grant revocation denies further allocator
service calls; it does not pretend to unmap previously granted CPU pages.
Teardown reclaims all arena/metadata frames without needing the revoked grant.
`free(NULL)` remains a side-effect-free no-op. Raw provider helpers are private
from the dynamic registry, not an ordinary declarative SCI binding.

## Allocation semantics

All live pointers are aligned to16 bytes and designate an exact live record in
this invocation. First-fit bounded gap search reuses freed extents; metadata
capacity and total bytes are explicit. Zero-size malloc/calloc yield distinct
minimum16-byte allocations while live. calloc checks unsigned multiplication
before allocation and zeroes the result; a zero factor stays a zero product.
Exhaustion/oversized requests return NULL with Darwin ENOMEM12, preserving
existing live blocks. Success and free(NULL) preserve errno.

Realloc(NULL,n) is malloc(n). Realloc(p,0) reserves a new minimum block first;
failure preserves p. Shrink/growth can stay in place if the bounded live ledger
permits it; a move copies exactly min(old requested size,new size), then releases
the old record. All failed reallocations preserve the original pointer, bytes
and ownership. No reallocf behavior is implied.

An invalid/interior/double-free pointer is never dereferenced. A contract
violation terminates this bounded guest with status134 and reclaims its owned
resources; this is not a Unix signal-delivery claim. Plain C pointer values
cannot distinguish an old address from a later live allocation at the same
address; do not claim generation-safe pointers or hardware use-after-free traps.
Freed bytes remain within the mapped arena until teardown.

## Evidence required

Before expansion, retain actual unknown-import refusals for all four names in
revision1. Then use genuine revision2 Mach-O fixtures at CPL3 to verify real
heap reads/writes, alignment, zero and overflow cases, record/arena exhaustion,
free reuse/coalesced gaps, grow/move/shrink/zero realloc and failure atomicity.
Exercise invalid pointers, protected metadata/guard and executable-heap denial,
missing/wrong/revoked grants, actual fault/IRQ deadline and unfreed allocations
at exit. Repeat at least21 cycles and assert stable backing frames, domains,
heap cursor, capabilities and ambient host descriptors. Re-run unchanged
254 eager,344 startup,483 protected and548 file gates.

Inspect legitimate upstream Mach-O Lua acquisition/build options separately;
only distributable unmodified upstream artifacts with pinned provenance may be
counted. A custom/patched fixture is never original application coverage.

## Implemented slice

The finite revision2 provider and its actual CPL3/owning-function regressions
are implemented. See [the checked contract](../darwin-owned-heap-checks.md) for
semantics, frozen receipts and retained limitations. Original macOS jq remains
refused; Lua5.2.4 acquisition is read-only inspection, not execution coverage.
