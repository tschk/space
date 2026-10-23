# Native directory snapshots

Provide real directory observations before foreign enumeration policy. The
native synchronous storage service copies a complete bounded directory into
caller-owned output, using distinct caller-owned scratch. It returns no raw
inode pointer, long-lived cursor or invented entry. The output is an immutable
observation after return, not an inode lease: deletion/reuse and remount do not
change saved bytes or authorize operations on their former identities.

The private trusted API requires kernel root, no active user context and a live
Storage grant. It currently supports the synchronous SparkFS provider. Volume
RPC has no equivalent structured operation and must refuse. Native byte names,
types, sizes and observation identities cross this seam. Windows wildcard,
casefold, UTF16, attributes, time conversion and Find handles belong outside it.

The versioned32-byte header precedes64-byte records. Caller output capacity is
32+64*N with at most4096 entries; scratch is exactly output capacity+4096 bytes.
Output and scratch are disjoint heap-owned trusted buffers. Output is committed
only after the whole observation succeeds; scratch may change on refusal. The
native path is a canonical absolute trusted C string and may alias output,
never scratch. Relative paths, repeated/trailing separators and dotsegments
are refused; the separate native normalizer can prepare such input first.
No allocator/cache or descriptor is owned by this helper. Existing synchronous
filesystem operations outside this helper may initialize separately owned
scratch on first use. Traversal here uses the supplied I/O scratch and validates
every parent inode and block before following it.

Directory geometry is bounded to the native direct+single-indirect block range.
Block addresses/bitmap ownership, inode ranges/types, record lengths and name
bytes are validated before dereferencing or publishing them. Tombstones are
skipped; a hole is not EOF. I/O failure, corrupt metadata, larger geometry and
insufficient capacity leave output unchanged. Double-indirect directories and
concurrent filesystem mutation require later provider contracts.

Required actual tests: empty and Unicode/nested directories, removed slots,
multiple blocks, metadata/type/size accuracy, short capacity and output tails,
alias and grant refusal, corrupt records/block pointers, independent snapshots
across delete/reuse, remount identity, exact allocation/descriptor/storage state
and private SCI import denial. Add actual NVMe reopen evidence before using this
provider to claim persisted foreign enumeration.

## RAM-backed actual checkpoint

The real QEMU kernel gate at `/workspace/native-directory-final3/report.json`
checks1698 entries over21 measured snapshots against an independent host-built
byte oracle. The directory contains1700 source-created regular files, a nested
directory and a supplementary Unicode name, with four deleted slots across
blocks. Its14 blocks exercise real direct and indirect addressing. Type, size,
name bytes, observation identities, reserved zeros and unused output tails are
checked. Empty directories, deletion/inode reuse with an unchanged earlier
snapshot, fresh observation, valid path/output alias, refused scratch alias,
short output, absent/wrong/revoked grants and malformed paths are exercised.

Snapshot-only read wrappers preserve the native operation except an explicit
I/O refusal and trusted mid-observation grant revocation. Corrupt root inode
indices, direct/indirect block addresses, superblock totals and name lengths
refuse without partial output. Exact native inode/bitmap bytes, heap/free list,
domains, capability count and an ambient open descriptor remain unchanged by
observation. Real SCI import ingress refuses the private raw provider before
lifecycle allocation. The first receipt preserved an incorrect test expectation
that mkdir returns zero; it actually returns its newly created inode. The test
was corrected to require a nonnegative inode before the actual data oracles ran.

This is a native CPL0 provider check with zero CPL3 entries, not upstream
application execution. The module is not added to the default storage root and
has no Windows Find API. Structured Volume RPC and concurrent mutation semantics
remain open before broader integration.

## NVMe reopen checkpoint

The same native implementation passes63 snapshots across three independent
NVMe boots at `/workspace/native-directory-nvme-final/report.json`. Only boot A
formats its new owned64MiB disk. It performs the complete create/delete/reuse
corpus and requires a real successful namespace FLUSH completion. Boots B/C
reopen1698 persisted entries21 times each, with no format or seed writes. Their
disk bytes remain exactly unchanged. An independent read-only host parser walks
actual direct/indirect directory blocks and inode records and verifies every
name/type/size/identity and1697 real inline file payloads after each boot.

The first attempt at `/workspace/native-directory-nvme/report.json` correctly
failed the whole-disk read-only oracle: the ordinary boot's `test-sci-loader`
creates and reads `test.sci`. Its first blank-disk write failed; boot B created
that unrelated root file. The generated NVMe test root now explicitly omits only
this mutating boot self-test; private SCI import denial still executes each boot.
The production snapshot provider is unchanged. Source variance and hashes are
recorded, and before-B/C disk copies are retained. This proves synchronous
completed-write/reopen observations, not crash atomicity or Windows enumeration.
