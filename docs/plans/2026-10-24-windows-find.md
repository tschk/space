# Windows Find through genuine stopped native directory observations

The full goal remains OPEN; original Windows executables are still refused.
Add a separate profile13 above the existing composed UTF8/wide-path profile.
Reuse the existing real768-byte user CPU context/FLS supervisor loop: Find traps
request native Suspend; only after actual capture returns to domain0/kernel CR3
may the private native directory provider run. Never clear active/domain flags
to simulate a stopped CPU. Keep the existing PE pager for this slice; native VM
migration remains required later. Add no foreign backing ledger or raw pointers
to the filesystem interface.

Initial contract: FindFirstFileA/W, FindNextFileA/W, FindClose and
FindFirstFileExA/W on the explicit C: root only. Root '*' and '*.*' enumerate
real entries; literal root names select actual metadata. Other wildcard grammar,
subdirectory enumeration/dot synthesis and unresolved Unicode case folding
refuse explicitly instead of returning pretend empty results. ASCII folding is
supported; exact Unicode names and explicitly case-sensitive Ex searches work.
If unsupported folding could affect a result, return ERROR_NOT_SUPPORTED.

A/W use the existing explicit UTF8 ACP65001 and strict UTF16 transcoding. Native
schema2 UTC seconds convert to real FILETIMEs; schema1 boot ticks are unsupported.
Map native file/directory/mode data, never invent zero times or 8.3 aliases.
Validate complete writable WIN32_FIND_DATAA320/W592 bytes before publication.
EOF/failed calls preserve output and cursor; success preserves LastError.
FindClose invalidates only its own typed generation-bearing handle and preserves
LastError, including EOF18. Wrong/stale/cross-kind handles refuse6.

At most two immutable observations live per process. Private buffers are bounded
and cached; grants/targets, process epoch and owner domain remain explicit.
Cleanup closes snapshots after success, actual CPU fault or IRQ cancellation.
Storage/Memory revocation stops publication; close remains possible. A finite
service quota supplements actual remaining guest IRQ budget. FLS callbacks
refuse this new service until callback suspension is explicitly supported.

Reference only, no copied implementation/test bodies: Wine840a939 file tests
(SHA d4d6783282f9802d518d870d11e53ff14d12d9232c4d34bdccbcd25cb2a3ebff,
LGPL2.1-or-later) and ReactOSe812443 FindFiles.c
(SHA e56506dc2f9c7a85f2b8340f8e807c8b6c63df7bad7db3722acc6881d1f6bf9f,
GPL2+). Local source/URL receipts live under
`/workspace/compatibility-references/find`. These establish behavior references,
not executed Wine/ReactOS or Space application coverage.

Acceptance must use actual CPL3 PE imports, real Suspend/capture, independent
full output records and FILETIME oracles, native UTC RAM/NVMe data, A/W/Ex and
EOF/close behavior, malformed/cross-page pointers, stale/foreign handles,
revocation, real CPU faults/deadlines and21 stable resource cycles. Preserve
baseline failures and old Windows profile outputs. Run the affected Windows and
desktop gates before a fresh integration source; no original-executable success
claim until the exact unchanged binary really executes.

## Implemented boundary

`windows-process-find.in` owns two bounded observations, their opaque generation
handles, owner domain/process epoch and Win32 encoding/error policy. The native
provider retains filesystem layout and traversal. Each observation has its own
393248-byte output and397344-byte scratch buffer; the two rows and marshaling
buffer bring first-use retained heap to1582400 bytes. Admission reserves that
heap before using the existing PE frame budget. Later activations reuse buffers;
process teardown retires every catalog row after normal exit, fault or deadline.

The existing private Windows supervisor resumes a genuine768-byte CPU context.
The seven Find imports suspend that context; the owning native service checks
captured Suspend state, kernel CR3, domain, live Memory/Storage grants and their
original targets before touching native filesystem observations. It preserves
IF and uses the remaining IRQ budget plus a128-service quota. It never fabricates
a stopped CPU or maps native snapshots into guest memory. FindNext rejects a
changed native mount or active unsupported Volume backing. FindClose still
retires a valid handle after grant revocation. All `windows-find-` exports are
private at the actual SCI registry boundary.

This remains a trusted kernel-linked personality prototype, using the existing
PE mapper. It does not establish a separate SCI personality domain or complete
native UserAddressSpace migration for PE. No additional renderer, IPC mechanism,
foreign backing-frame ledger or privileged foreign entry was added.

## Local execution evidence

`/workspace/windows-find-accept-ram/report.json` passes624 actual CPL3 PE fixture
activations:28 regular cases over22 observations,21 measured stable resource
cycles, and eight separate live-grant controls. Four additional cold admission
refusals check wrong Memory/Storage/TimeSource grants and insufficient heap before
any guest entry or allocation. Original Windows application entries remain zero.

The corpus checks entire320/592-byte records against independently constructed
host oracles, including reserved bytes, UTF8/UTF16 filenames, regular/directory
attributes, size and FILETIME conversion. Real native file creation, later write
and still later read produce three distinct UTC seconds; inode field ordering
is therefore observable. It checks A/W/Ex enumeration, exact Unicode names,
ASCII case folding, Ex basic/case-sensitive behavior, EOF18, LastError-preserving
close, stale handles across reuse and process activations, two-slot exhaustion,
failed-next output/cursor preservation, malformed and readonly/unmapped pointers,
invalid encoding, unsupported grammar, FLS callback refusal and quota exhaustion.
Twenty-two real page faults and22 actual IRQ deadlines occur after a live Find
handle exists. Storage/Memory revocation and retargeting are checked both before
next and immediately after a genuine native directory observation, before any
guest publication. Source snapshots record canonical and compiled hashes and
verify the exact reversal of the two test-only callback/call-site substitutions.

`/workspace/windows-find-accept-nvme/report.json` passes1248 fixture activations
across two actual NVMe boots. An independent raw-disk oracle checks native root
entries, inode kind/mode/size, inline payload and all six timestamps. The second
boot uses a later RTC date, retains the original persisted times and leaves the
entire64MiB disk byte-for-byte unchanged. The final checker also verifies both checker sources and exact canonical source
equality across boots. Actual fault/deadline runs must observe a live Find
handle before termination; early termination cannot count as that control.

Negative controls at `/workspace/find-negative-controls.json` deliberately
remove generation advancement or the foreign grant check in separate copied
sources. Both fail the actual PE corpus with expected42/actual99; logs and
mutated source identities are retained. The canonical source is unchanged.

Existing regressions on this development tree pass1326 Windows path activations,
4921 Windows Unicode activations plus3410 scalar models, and real desktop
launcher keyboard/pointer/focus/resize/pixel checks. The independent137-gate
run passes all137 from679 files at the earlier UTC commit1ffaa65, including
source/compiler/application integrity. It does not include Find. The next
integration adds separate RAM and NVMe Find gates and must preserve that scope.

Earlier failing receipts remain visible under `/workspace/windows-find-*`:
fixture MMIO string typing, an incorrect IAT-size declaration, a malformed empty
environment, an oracle-construction error and a coherent-RTC admission refusal.
The RTC refusal is not an application failure: bounded retries now require zero
guest calls and unchanged heap/free/domain/capability/epoch state before waiting
for a real PIT tick. An earlier final-ram receipt records one such pre-entry refusal separately
from its624 activations; the later accept-ram receipt records zero. No failed receipt was relabeled.

## Remaining goal

General wildcard semantics, subdirectory/dot enumeration, complete Unicode
case folding, larger handle catalogs, writable/schema1 translation policy,
Windows console/CRT/NT imports and general original Windows applications remain
open. The32-import admission bound is unchanged. Native PE VM migration, GUI
window/message/input adapters and unchanged Windows GUI applications remain
required by the full compatibility goal; this slice closes none of those rows.


The later full139-gate integration from686 committed files atad0a0be passes all
139 at `/workspace/lab139-retry/report.json`, including source/compiler/application
integrity. It includes both Find gates. The first attempt stopped during UTC
persistence without a final report; its completed gates and interruption receipt
remain under `/workspace/lab139` and `/workspace/lab139-interruption.json`. No
passing final status is assigned to that interrupted attempt.


The subsequent695-file source5b54e1e also passes the complete144-gate matrix at
`/workspace/lab144/report.json`, with integrity passed. Both Find gates remain
green alongside native file observations, original Linux workloads and desktop
regressions. This does not change the root-only Find contract or establish
original Windows application execution.
