# Native UTC file metadata before Windows directory enumeration

The full goal remains OPEN. The original Windows executables still refuse
before entry; implementing directory names without meaningful file timestamps
would not complete their Find APIs. Native SparkFS version1 stores boot ticks,
which cannot be reinterpreted as absolute FILETIME across reboot.

Add an explicit version2 formatting profile, retaining the version1 formatter,
layout and tick semantics. Version2 inode creation/modification/access values
are Unix UTC seconds sampled through the existing coherent native RTC provider.
Borrow one live Timer/TimeSource grant, with original target identity and mount
identity. No cached/fabricated fallback sample; denied/unavailable clock refuses
before file/output changes. A fresh mount requires an explicit clock binding
before timestamp-changing operations. Reading persisted metadata needs Storage,
not a fresh TimeSource sample. Reject unknown filesystem versions before mounting.
No silent conversion or automatic formatting/migration of existing disks.

Provide a separate96-byte native directory-details snapshot on version2 volumes,
reusing the existing bounded traversal and atomic caller-owned output contract.
Keep version1's64-byte snapshot unchanged. The new magic/record size fixes UTC
seconds as the time domain, includes real creation/access/modification times and
native mode, and explicitly refuses boot-tick volumes. Windows wildcard, UTF16,
FILETIME conversion and Find-handle lifetime remain a separate foreign edge.

Acceptance: actual QEMU RAM create/read/write/truncate/rename timestamp effects;
wrong/revoked grants and unavailable coherent clock before mutations; legacy
behavior preserved; malformed metadata/source bounds and atomic refusal;
private SCI denial;21 stable observations. Then three real NVMe boots at
independent explicit UTC bases: persist creation time, update modification time
on boot2, and preserve complete metadata/disk bytes on read-only boot3. Verify
raw disk fields independently on the host. Follow affected native/Linux/Windows
and ordinary desktop regressions before integrating the profile.

## Implemented contract and limits

The default formatter and version1 tick semantics remain. The new private
`fs-metadata-format-utc` requires separate live Storage and Timer grants, native
supervisor context, real native backend and bounded heap/layout admission. It
probes the advertised extent through actual backend I/O before formatting; an
out-of-namespace request returns an actual NVMe error and the next valid request
still succeeds. Version2 invalidates the old superblock magic during explicit
format, persists all free inode records, writes real root timestamps and publishes
the valid header after metadata writes. NVMe completion includes checked FLUSH.
This does not establish power-loss/crash-atomic formatting or general journaling.

A fresh version2 mount validates exact geometry before following disk offsets,
propagates bitmap/inode read failures and requires an explicit borrowed clock
binding for timestamp-changing operations. The grant's original target and mount
identity are checked, so old bindings, revocation and target replacement cannot
turn into fabricated time. Invalid/unavailable coherent RTC samples refuse; no
cached fallback is used. Metadata observations remain possible with Storage after
the separate TimeSource grant is revoked. Times have one-second resolution.

The existing64-byte directory observation is unchanged. The96-byte details
revision uses magic0x5346444952530002; creation/access/modification Unix seconds
are at record offsets64/72/80 and native mode at88. Legacy boot-tick volumes
refuse-8 rather than producing apparent FILETIMEs. Caller-owned output remains
unchanged on capacity, authority, source-data and metadata refusal. No cursor,
new frame ledger, foreign wildcard or Windows handle escapes the native provider.
These APIs remain private kernel-linked prototypes, not isolated SCI services.

The standalone Volume SCI still owns its older fixed1MiB/256-inode version1
profile. Its controller now validates that profile at its actual reserved
`VOLUME-NVME-LBA` before domain/heap admission. The component also refuses unknown
versions/layouts rather than formatting them as a mount fallback. UTC operations
refuse while that separate Volume provider is active; TimeSource binding and
schema2 support inside Volume remain a future component task. A bounded private
NVMe LE32 read projects scalars through the existing driver-owned DMA page and
existing mailbox. It allocates no scratch frame or second transport and is not
exported to SCI guests.

## Evidence and preserved failures

The actual acceptance source and receipts are recorded in the final handoff;
earlier iterations are retained separately. The RAM profile proves native
creation/access/modification and directory updates, multi-block reads/pread,
truncation, rename, real RTC setup-freeze refusal, grant revocation/target change,
heap/layout admission and21 stable observations. It creates20 real old-format
files, reformats its own RAM disk and checks raw backing records are genuinely
free, rather than inspecting only newly zeroed in-memory inode caches. Its raw
SCI import of the private formatter is denied before entry/resources change.

The NVMe profile uses three independent boots at explicit UTC bases one day
apart. Creation survives; boot2 updates access/modification; boot3 changes neither
the complete disk bytes nor the128-byte metadata snapshot. Independent host
inspection verifies on-disk schema, inode mode/size/time fields and actual guest-
written file bytes. Four additional real NVMe boots refuse unknown version,
wrong block size, overlapping inode table and outside data start, with every
backing byte unchanged. Native scalar bounds refuse without submitting an I/O;
an actual out-of-range I/O is followed by a healthy real read. The unsupported
Volume check uses a copy of the actual Space-written UTC superblock at Volume's
reserved backing offset and leaves heap, frame list, domains and grants unchanged.

Causal negatives remove only the inode-table clearing loop or only the UTC
mount-geometry admission. Both fail their unchanged actual QEMU assertions.
Initial source-freeze omissions and model-translator setup errors remain failed
receipts, not guest execution. An intermediate extent probe incorrectly used
mounted-filesystem bounds on a blank namespace; it now probes the real backend.
An intermediate frame-based Volume probe retained cold allocator capacity; the
scalar projection fixes it without relaxing resource assertions. Earlier Volume
checks probed namespace LBA0; they do not prove Volume admission. The corrected
check probes its actual reserved backing and verifies the header bytes there.

## Compatible runtime-component checks

The extra regressions exposed a prior standalone display build failure, reproduced
on committed9a014c2. The standalone renderer has no GUI application supervisor,
so that action is explicitly unavailable. Its actual fill/copy operations now
use the existing native CPU contracts through explicit SCI imports; no second
renderer or privileged GUI-launch import is added. The ordinary kernel compositor
uses those same CPU wrappers and still needs launcher/damage/pixel regressions.

The old runtime-component check also expected automatic creation of persistent
`test.sci`, incompatible with the earlier boot-preservation repair. Its original
loader assertion is retained: the test build now packages an explicit kind25
native SCI selftest returning42, loaded through the owned transient lifecycle.
The diagnostic hub selects it read-only. Ordinary images without that artifact
retain the original diagnostic only on their newly allocated RAM disk. Existing
user files, NVMe volumes and the Volume provider are never overwritten to create
a test fixture. The narrowly selected host C models include the new helper
closure and retain all original preservation/output assertions; they remain
host models, distinct from actual native/QEMU evidence.

Windows Find APIs and original Windows execution remain OPEN. The application
lab adds two native UTC gates for137 total, requiring a new committed integration
run after the focused checks complete.

## Final focused checkpoint

`/workspace/utc-metadata-handoff.json` verifies all production, fixture and
checker hashes against frozen candidate4394bf4. Its final acceptance reports
are `/workspace/utc-accept-ram/report.json` (22 observations/21 measured cycles)
and `/workspace/utc-accept-nvme/report.json` (three metadata boots plus four real
malformed-volume refusals). The latter uses the correct reserved Volume offset
and verifies the mirrored actual Space header there. Both C preservation models
also pass, including unsupported Volume version/layout refusal with no activation,
allocation or writes and the initialized v1 RPC positive control.

From that same final candidate, original fbv passes22 launches plus88 separately
classified controls with exact pixels; minimal CLI passes44 original plus66
startup entries; Windows Unicode paths pass63 actual entries across three NVMe
boots. The runtime-component and two-boot Volume regressions pass. The desktop
launcher exercises real keyboard/pointer/focus/resize/restoration, and the
100-frame damage gate passes322fps/31 ticks against its unchanged30fps threshold.
SparkFS name limits/deep paths pass three NVMe boots. Earlier directory, large-
file and file-service receipts have their own older source scopes; they are
retained separately rather than retroactively attributed to4394bf4. No complete
137-gate integration pass is claimed by these focused results.
