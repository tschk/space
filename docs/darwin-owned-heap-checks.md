# Darwin owned heap profile

`darwin-owned-heap.in` adds a separate finite personality adapter revision,
identity `0x4457414249000002`, dependency metadata version `0x20000`. It accepts
the existing eager profile's seven genuine services plus `_malloc`, `_calloc`,
`_realloc` and `_free`. The revision1 adapter is unchanged and still refuses the
four allocator imports. This is kernel-linked personality scaffolding over
native frames, mappings and user contexts; it is not an isolated SCI allocator
service or a complete libSystem/dyld implementation.

The supported input remains the strict five-command, two section-free segment
Mach-O with genuine chained-format6 fixups/import-format1 described in
[the eager profile](darwin-eager-checks.md). Every import is checked before
allocation. Other libraries, unknown symbols, initializers, TLS, frameworks,
lazy binding and arbitrary upstream application layouts remain refused.

## Ownership and API behavior

Each activation owns a 64-KiB user RW/NX arena at `0x4D000000` and one unmapped,
supervisor-only metadata frame containing128 records. Guest headers and free
links are never trusted. All allocations have16-byte alignment. First-fit
allocation splits free extents; free coalesces adjacent extents. Metadata and
arena exhaustion return NULL with Darwin ENOMEM12. Freed extents remain mapped
until invocation teardown; no use-after-free trapping is claimed. An old C
pointer cannot be distinguished from a later live allocation at the same VA.

Malloc/calloc of zero obtain distinct minimum16-byte live allocations. A zero
calloc factor succeeds even if its other unsigned factor is SIZE_MAX; other
multiplication overflow and oversized requests fail. Fresh allocations are
zeroed (a permitted stronger guarantee than malloc requires). Realloc retains
a suitable reserved extent or allocates/copies exactly the requested prefix
before releasing the old object. Shrinking retains reserved capacity. Failed
realloc preserves the old allocation and bytes. Darwin `realloc(p,0)` obtains
a fresh minimum block before freeing p; exhaustion therefore preserves p.
Success preserves private errno. `free(NULL)` is a no-op preserving errno.

An explicit borrowed native memory grant is checked before launch and at every
mutating heap call. Missing/wrong/revoked authority yields EACCES13 without
changing allocations. Free(NULL) needs no authority. Revocation does not revoke
already mapped CPU memory; teardown remains unconditional after revocation.
Invalid/interior/double-free or invalid realloc pointers terminate the bounded
invocation with134 without dereferencing the pointer. This is not Unix signal
delivery. Heap calls use private RX C-ABI capsules, not host function pointers
or purported Darwin syscall numbers. Calls outside their owned capsule return
EINVAL22. Existing genuine read/write/file services still validate full guest
ranges and their own borrowed grants.

All backing and metadata frames are reclaimed after normal return, invalid
pointer termination, hardware fault or actual IRQ deadline. Retained scratch
uses the bump heap: a first invocation with serial/storage roles requires
exactly10160 cached bytes plus a conservative96-frame reserve. The maximum is
56 guest backing pages, one metadata frame, at most18 page-table frames and
slack. The reserve is checked after accounting for retained bytes. These cached
buffers remain allocated across invocations; steady cycles do not grow them.
Raw `darwin-heap-*` helpers are excluded from the dynamic kernel registry.
Native capability checks here do not implement translation of compiler SCI
component-local ordinal declarations into native capability rights.

## Reproduce

Use an explicit source-built compiler and the toolchain's NASM/QEMU on PATH:

```bash
python3 scripts/check-darwin-heap-import-baseline.py --in /path/to/in --out /tmp/heap-before --app /path/to/jq-macos-amd64
python3 scripts/check-darwin-heap-owner.py --in /path/to/in --out /tmp/heap-owner
python3 scripts/check-darwin-heap.py --in /path/to/in --out /tmp/heap-runtime --app /path/to/jq-macos-amd64
```

The baseline uses genuine revision1 imports and proves all four allocator names
are refused before allocation. The owning-function gate extracts the exact
allocator bodies, replaces only byte access/page translation with bounded model
backing and executes default/lean/harden profiles. Independent byte patterns
check moves, shrink, zeroing, unsigned overflow, failure preservation,
record/arena exhaustion, coalescing and512 reuse cycles. A generated-source
negative control restores the wrong calloc zero-factor ordering and must fail
the corresponding assertion.

The runtime gate freezes sources and executes275 genuine CPL3 invocations over
21 stable cycles. It checks actual bound calls, pointer writes/readback, existing
write consuming heap bytes, zero-size realloc, actual127-record exhaustion/reuse, live grant revocation, invalid
pointer termination, heap NX/guards, unmapped metadata, IRQ deadline and
unfreed-allocation cleanup. Exact cold retained-byte recovery and95 actual free
frame refusal are checked before warmup. Every cycle preserves heap cursor,
free-frame count, domain count, capabilities, caller image and an ambient host
file descriptor. Nine malformed descriptor/import/fixup cases, including an unknown unused
import, refuse before
allocation. The private registry is checked at runtime. Test-only dispatcher
routing exposes only scoped real grant revocation and the metadata physical
address for a genuine inaccessible-pointer probe; production provides neither
request. Frozen-source hashes and complete compile/QEMU commands are retained.

Frozen .324 receipts from this implementation:

- `/tmp/space-darwin-heap-import-baseline/report.json`: initial old-profile refusal.
- `/tmp/space-darwin-heap-owner-final/report.json`: all3 owning profiles and negative control.
- `/tmp/space-darwin-heap-checkpoint275/report.json`: wired275-invocation gate.
- `/tmp/space-darwin-heap-{eager254,startup344,protected-imports483,files548}/report.json`:
  unchanged existing gates passed from the same frozen integrated source.
- `/tmp/space-darwin-heap-old-imports/report.json`: old revision1 remains closed.

An initial runtime failure is preserved at `/tmp/space-darwin-heap-first`: a
revision literal edit accidentally changed the new validator's CPU type. The
new module was corrected to x86_64 `0x1000007`; existing profile source and
assertions were unchanged. An initial owning-model parse failure is preserved
at `/tmp/space-darwin-heap-owner-first`; its model subtraction spacing was fixed.

## Original applications remain separate

Pinned original macOS jq is still actually refused with-8 before allocation.
Its17 commands, sections,136 chained imports and broader initialization needs
are not satisfied by this finite eleven-service fixture. Rosemary is a pinned
reference for behavioral seams; its mimalloc/zone implementation is neither
copied nor linked. See [the implementation plan](plans/2026-10-24-darwin-owned-heap.md).

A legitimate LuaBinaries5.2.4 MacOS10.11 archive was acquired separately; its
provenance, locally computed hashes and build/license assurance limits are in
[the inspection manifest](../fixtures/applications/lua-5.2.4-macos.json).
`inspect-lua-macos.py` verifies these hashes before read-only parsing. The
unmodified lua52/luac52 binaries are x86_64 Mach-O, embed Lua5.2.4, target macOS
10.11 and have97/44 undefined imports respectively. Both also declare libedit;
both use classic dyld-info fixups, outside this chained profile. Neither was
executed on the host or Space. This intermediate inspection does not replace
the Lua5.4.7 goal or count as application execution coverage.
