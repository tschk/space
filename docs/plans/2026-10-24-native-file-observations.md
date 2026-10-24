# Native file observations and captured executable names

The full compatibility/desktop goal remains OPEN. Ordinary desktop application
installation/launch, interactive foreign GUI input, original Darwin/Windows apps
and SCI isolation of these private providers remain required. This is a native
Storage prerequisite with actual upstream consumers, not completion of those
application or desktop rows.

## Ownership and boundary

`file-observation.in` is a trusted synchronous native Storage provider prototype.
It captures immutable bytes without adopting foreign executable, file descriptor,
pathname encoding or window semantics. It uses the existing native directory
traversal/block reader, allocation bitmap and native filesystem storage backend.
It adds no renderer, IPC fabric, guest physical I/O or backing-frame ledger.

Two generation-bearing objects retain separate heap buffers. Constructor staging
is never published as a handle. Captured mount/geometry and the entire native
inode are checked around each content read; live Memory/Storage rights and the
original target are checked before publication. Read permission uses the current
bounded native owner-read bit. Refusal retires staging ownership; caches remain
bounded. Missing/corrupt metadata on first use may warm that documented cache;
authority and insufficient-heap refusals allocate nothing.

The maximum payload is2146304 bytes, the existing12 direct plus512 indirect
blocks. Both slots together retain4301568 bytes including rows, scratch and
inode copies. This is the current native filesystem extent limit. Larger jq and
SQLite executables still require expanded native file storage; their established
external-image execution coverage remains separate. No larger-file support or
general ACL/namespace authority is claimed here.

Native callers borrow a readonly pointer/range under the exact owner and handle.
These are trusted native loans, not hardware readonly mappings or public SCI
pointers. Close fences new loans and retains bytes while any of the64 bounded
loans remain. Returning a loan and retrying close remain possible after grant
revocation. A consumer must hold its loan through all execution and retained VM
cleanup; the framebuffer test does so across actual quarantine and recovery.
Accepted snapshots retain no inode or disk-block references and survive deletion
and reuse of their backing file. Observation does not update access time or
require a TimeSource; this is a native immutable-data contract, not POSIX read.

Every endpoint rejects an active foreign context and is excluded by the actual
`file-observation-` SCI registry rule. The raw SCI import denial is executed
before guest entry or changes to heap, frames, domains or grants. This remains
kernel-linked scaffolding and does not establish an isolated filesystem service.

## Linux source identity

The new `linux-process-run-named-input` accepts a captured canonical native name
separately from guest `argv[0]`. It requires native Memory/Serial/Storage grants,
refuses reentry and validates a511-byte name with24-byte native components before
activation. The caller lends the immutable name, like the ELF bytes, through the
whole synchronous family and any retained cleanup. No native policy branch
manufactures a captured CPU context or clears active/domain flags. The existing source/VM owner
and counted launch path perform execution; no foreign code runs at CPL0.

The process row retains that source identity for `/proc/self/exe`. `AT_EXECFN`
has a separate bounded stack string when using this profile; guest arguments are
preserved. Legacy profiles retain their previous stack layout. This is a captured
label, not a live inode/rename/deletion or general execve pathname contract.

A real original fbv startup exposed the gap: relative `argv[0]` had been reused
as the executable's readlink target. Glibc rejected that relative target and
reached its real abort/GP path. Separating identity fixes the unchanged program;
no application patch, successful stub or alternate payload is used.

## Focused execution evidence

`/workspace/file-observation-handoff.json` verifies production/relevant checker
identities against the focused receipts. The final reports are:
`file-observation-accept-ram`, `file-observation-accept-nvme`,
`file-observation-accept-nvme-utc`, `file-observation-accept-apps-scope-v1` and
`file-observation-accept-apps-scope-utc`, each under `/workspace` with its
`report.json`. They cover:

- RAM viewer:22 original fbv launches and88 separate syscall/fault/deadline/
  retained-VM controls, exact whole1024x768 pixels and21 stable cycles.
- Native v1 and UTC NVMe viewer profiles: two actual boots each,44 original
  launches and176 controls per profile. Reopen stages no application ELF. A raw
  disk oracle checks stored payload and unchanged executable inode; captured
  executable bytes equal the pinned original SHA256. UTC reopen captures the
  executable before TimeSource binding, then binds the provider for ordinary
  viewer image-file reads.
- Native v1 and UTC CLI profiles: each executes original fbv, BusyBox and Lua
  132 times across two actual boots with exact host CLI output and21 measured
  resource cycles per boot. All original ELF test loaders are absent on reopen,
  and the entire64MiB disk remains unchanged on that read-only second boot.
  Actual context/CS/IOPL assertions and syscall observations classify execution.
  Each boot records1146 real active-context refusal pairs: nested named entry
  and private snapshot access refuse without spoofing CPU/domain state. The
  independent named fixture uses argc3 and checks both arguments and executable
  name, so its auxiliary-name and readlink controls are independently observable.
- An independent own CPL3 ELF checks distinct relative argv and canonical
  `AT_EXECFN`/readlink, including no readlink NUL terminator. These two fixture
  entries per profile are counted separately from original applications. Native
  admission controls (ten per boot) check invalid names, missing Storage and malformed ELF
  before allocation or entry; source scope always clears on refusal/return.

The viewer checks two independent snapshots, slot exhaustion,64 loans, retirement
and cleanup after revocation, exact generation refusal, backing deletion/reuse,
wrong authority, cold heap refusal and six real after-read grant/target/inode/
mount controls. Source snapshots identify canonical/compiled hashes and verify
exact reversal of both test-only native call substitutions. The host verifies
full accepted ELF bytes and independently specifies every screenshot pixel.

Negative controls preserve separate mutated sources and failure receipts at
`/workspace/file-observation-negative-controls.json` and
`/workspace/source-name-negative-controls.json`. Removing native grant validation
or outstanding-loan retention fails. Independent auxiliary-name and readlink-name
controls make the own CPL3 proof fail42/99. Neither negative receipt changes the
canonical implementation or becomes application coverage.

Earlier failures remain retained: unsupported constant initializer syntax in the
new provider, an unquoted HMP memory-dump filename, an explicitly blank NVMe disk
requiring test-owned formatting, absent RDRAND on the initial default CPU profile,
and the real glibc executable-name abort. The app corpus now uses the established
`-cpu max` profile; unsupported entropy still refuses without inventing a seed.

The separate139-gate integration from686 files atad0a0be passes completely at
`/workspace/lab139-retry/report.json`, including integrity. Its first interrupted
attempt remains at `/workspace/lab139` with an interruption receipt and receives
no all-pass claim. That source predates this file-observation/identity work.
The next integration adds five explicit stored-application gates and must run
from its own committed source; focused results do not retroactively extend139.

Legacy original fbv CLI/counting regressions also pass44 upstream entries plus
66 separate startup fixtures on each standard/minimal root. The independent
auxiliary/readlink negative controls fail the actual named fixture with42/99;
the original named-source app failure remains available as its own glibc/GP
receipt. The new API has no data/VM ledger or alternate syscall dispatcher.
