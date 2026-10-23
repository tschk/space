# Native file identity, permissions, sync and range leases

These services supply native storage facts and ownership primitives. Linux
translates stat structures, chmod/fsync and fcntl commands at its edge; the
native service contains no Unix command numbers, process IDs or errno policy.

`fs-stat(path, buffer)` retains its existing fields and fills the previously
unused final 16 bytes of its 64-byte record:

| Offset | Constant | Meaning |
| --- | --- | --- |
| 48 | `SF-ST-INODE` | Actual SparkFS inode slot plus one, including root slot zero |
| 56 | `SF-ST-MOUNT` | Positive identity of the current mounted service/format epoch |

Aliases resolving to the same object share these identities; different objects
have different inode identities. Repeated stat calls allocate neither identity
nor heap storage. A successful mount or format establishes a new service epoch.
The mount identity is an in-process object identity, not a persisted volume UUID
or a globally unique device identifier. Inode slots may be reused after deletion.
Unsupported Volume stat identity fields are explicitly zeroed after the successful
64-byte RPC response copy; dirty trailing response bytes cannot become false
identities. RPC errors retain their original result.

`fs-set-mode(path, permissions)` persists the existing inode permission field.
It accepts native permission bits 0..511, including decimal 384 (`0600`), and
returns 0/-1. Failed writes restore the old in-memory mode and return an error;
this does not claim rollback of arbitrary partial hardware writes.

`fs-sync-path(path)` currently returns 0 only for an existing regular file or
directory on the synchronous RAM SparkFS backend. The RAM writer has already
completed each memory copy. NVMe and asynchronous Volume currently return -1:
a completed NVMe write is not a controller FLUSH or a power-loss durability
promise. No adapter should report durable NVMe fsync from this version.

## Advisory range ownership

`components/file-range-leases.in` owns one synchronous, nonreentrant ledger of
128 active records and a bounded 257-record staging area. It lazily retains
18,480 bytes of scratch; updates allocate nothing after initialization. Clients
may explicitly warm `fs-range-init()` before measuring repeated activations.

```text
fs-range-lease(owner, mount, inode, start, length, kind) -> Int
fs-range-release-owner-file(owner, mount, inode) -> void
fs-range-release-owner(owner) -> void
```

The owner is a positive identity supplied by a trusted caller/runtime binding;
it is not authority for a guest to choose another owner's identity. Mount and
inode must name an actual current regular file. The lease service is advisory:
it does not silently add mandatory access checks to native reads and writes.
Callers retain responsibility for their capability and object access checks.

Kinds are `FS-RANGE-SHARED=0`, `FS-RANGE-EXCLUSIVE=1` and
`FS-RANGE-RELEASE=2`. Nonnegative ranges are half-open; length zero extends to
infinity. Negative inputs, invalid objects and finite endpoint overflow return
-1. Shared owners may overlap; an overlapping exclusive request from another
owner returns -2. Replacing one's own range splits surviving tails, upgrades or
downgrades exactly the requested interval, and coalesces same-kind neighbors.
Unlock has the same splitting behavior. Beyond-EOF ranges are ownership facts
and never allocate file blocks, including SQLite's ranges beyond 1 GiB.

A request that cannot fit 128 records returns -3. Conflict and capacity refusal
leave the active ledger unchanged; a middle unlock that would need a 129th record
also fails without losing its old protection. The service builds and coalesces
a bounded staging representation before committing. Native file destruction
releases every owner's lease on that object before its inode slot can be reused.
New mounted epochs discard stale prior-epoch records on the next successful
request. Owner/file and owner-wide cleanup require no metadata reread, allocation
or still-live storage capability, so an adapter can close after revocation and
clean up faults or cancellation truthfully.

## Executed checks

```sh
python3 scripts/check-native-file-services.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/native-file-services
python3 scripts/check-file-range-leases.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/file-range-owner
```

The first gate executes the actual service owners in a RAM QEMU boot and three
independent NVMe boots sharing one owned blank 64 MiB raw disk. It explicitly
formats only the first NVMe boot. It checks actual inode aliases, distinct
objects, mounted identity, persisted 0600 permissions, invalid permissions,
truthful RAM/file/directory sync and NVMe sync refusal. An independent raw-disk
parser verifies the inode permission bytes and exact file content after every
NVMe boot, including both remounts.

Each boot also tests shared/exclusive conflicts, own-owner upgrade and split,
partial unlock, independent files, infinity near the signed 64 limit, invalid
inputs, exact capacity, coalescing at capacity, atomic capacity refusal and
native destruction cleanup. Twenty-one repeated SQLite-shaped lock sequences
require stable heap, zero remaining leases, unchanged free-block count and
unchanged file size/content. No foreign process or storage allocation is
substituted for this native service evidence.

The second gate executes the unchanged production lease functions through
Inauguration's actual default, lean and harden JIT profiles. Host Python builds
an independent per-byte oracle for 250 deterministic updates from four owners;
each profile compares 2,000 ownership masks covering 64 byte positions and checks
cleanup plus exactly two retained allocations. This complements the QEMU
infinity/capacity/real-object tests; it is not disk persistence evidence.

Fresh 2026-10-24 (Australia/Melbourne) receipts with frozen Inauguration 0.9.324:

- `/tmp/space-native-file-services-first/report.json`: RAM and all three NVMe
  boots pass, persisted mode 384, `source_changed_during_run: []`.
- `/tmp/space-file-range-owner/report.json`: all three compiler profiles pass.
- `/tmp/space-native-leases-compile/standard.bin`: complete standard image builds.
- Existing initialization, Volume preservation and block-slot checks pass at
  `/tmp/space-sparkfs-init-file-services.log`,
  `/tmp/space-volume-preservation-file-services-final.log` and
  `/tmp/space-block-slots-file-services.log`.

The earlier Volume model failure was an unrelated host translator limitation
for the updated domain-context restore assertion. Parent change 619b4e7 repaired
that model; the production storage result was not waived or replaced.


The focused owner check `scripts/check-fs-stat-identity.py` models a provider
that writes its defined first 48 bytes while the RPC copies 64 bytes from a dirty
prior response. The exact production `fs-stat` function must clear unsupported
identity fields after the copy, preserve defined metadata, propagate RPC errors
and retain direct SparkFS identities. All three compiler profiles pass at
`/tmp/space-fs-stat-identity-fixed/report.json`. Restoring the old pre-copy
zeroing order fails with result 102 at
`/tmp/space-fs-stat-identity-control/report.json`. This is owning-function/RPC
copy-contract evidence, not a claim that Volume supplies real file identities.
