# Protected Windows execution and file APIs

This advances the active [full application goal](../compatibility-coverage-goal.md)
through actual protected execution and filesystem behavior. It does not run an
unmodified Windows application or establish general Win32 compatibility. Native
components still deploy as SCI; PE validation and compatibility policy stay in
the personality. No ReactOS or Wine source is vendored.

## Two explicit PE profiles

`components/windows-protected.in` retains the original strict fixture profile:
two ordered sections (RX text and RW/NX data/BSS), read-only/NX headers, fixed
base in `0x44000000..0x48000000`, at most 128 KiB image extent and 64 KiB per
section. Imports are absent, five console imports, or all ten console/file
imports in the documented order. Existing malformed-image assertions remain.

The separate `components/windows-pe-application.in` profile accepts 1–16 ordered
nonoverlapping sections, including RX code, read-only/NX data, RW/NX data and
pure BSS. It checks header/file/VM ranges, page overlap, file padding, entry in
file-backed executable bytes, section permissions and a bounded page count
before allocation. Preferred bases are 64-KiB aligned, above the runtime's
reserved stack/stub region and below the canonical user boundary; actual tests
execute at `0x140000000`, the original jq base. This is fixed preferred-base
execution, with no ASLR or relocation claim. The file/image/section limits and
supported COFF/optional-header flags are explicit in the validator.

The application profile accepts a subset of the ten supported named imports,
in arbitrary order, from one `KERNEL32.dll` descriptor. DLL case is normalized;
nonzero import hints and an explicit IAT directory are supported. Ordinal,
unknown or malformed imports fail before binding. IAT bytes are patched only in
the private mapped copy, including a read-only data section before user entry.
Guest import slots receive user-accessible INT80 capsules, never privileged host
function addresses. Their operation numbers are runtime-local, not NT syscall
numbers. Imports may be absent. Relocations, resource/exception/TLS directories,
delay imports, other DLLs and generic Windows process startup remain refused.

The structural parser is separately testable. It accepts the checksum-pinned
original Windows jq's ten-section layout and `0x140001400` entry; the complete
runtime admission still rejects unsupported directories before allocation.
Accepting the layout does not claim execution of jq.

## Implemented APIs

| Import | Implemented behavior | Boundaries |
|---|---|---|
| `GetStdHandle` | Standard output/error return this instance's serial handles 1/2 | Other selectors return invalid handle/error 87; no stdin session |
| `WriteFile` | Synchronous serial output or owned regular-file write, BOOL plus DWORD count | At most 4096 bytes, writable count pointer, null OVERLAPPED; serial and storage grants checked separately |
| `GetCurrentProcessId` | Returns the live native domain identity | No general Windows process objects |
| `ExitProcess` | Ends this activation with the full low 32-bit status | No DLL detach/thread teardown semantics |
| `GetLastError` | Per-activation state, initialized to zero and preserved on ordinary successes | Single-threaded; TEB startup profiles synchronize offset `0x68` |
| `CreateFileA` | Actual VFS regular-file open/create/truncate with execution-owned handle and path storage | Explicit read/write access, share read/write bits, null security/template, normal attributes; synchronous direct SparkFS namespace |
| `ReadFile` | Actual VFS bytes into checked writable guest memory; EOF succeeds with zero bytes | At most 4096 bytes, writable count pointer, null OVERLAPPED |
| `SetFilePointerEx` | Owned VFS offset with begin/current/end origin and optional 64-bit result | Signed 31-bit distance magnitude; invalid negative result returns error 131 |
| `CloseHandle` | Closes only an execution-owned regular file | Allowed after storage revocation so cleanup can complete; other object types unsupported |
| `GetFileSizeEx` | Actual owned VFS file size into a writable 64-bit result | Requires a currently live storage grant |

`CreateFileA` supports `GENERIC_READ`, `GENERIC_WRITE`, or both; sharing values
0–3; and `OPEN_EXISTING`. `CREATE_NEW`, `CREATE_ALWAYS`, `OPEN_ALWAYS` and
`TRUNCATE_EXISTING` require explicit write access in this bounded profile.
Existing `CREATE_NEW` returns error 80; existing `CREATE_ALWAYS`/`OPEN_ALWAYS`
succeed with error 183; missing `OPEN_EXISTING`/`TRUNCATE_EXISTING` return error 2.
Owned-handle access/share conflicts return 32 before mutation. This is not a
global sharing-lock implementation across all foreign/native processes.
Unsupported flags/dispositions fail before backend changes. Each component of a
copied VFS path must fit SparkFS's 24-byte name bound; excess returns 206 instead
of silently aliasing a truncated name. Windows drive/UNC namespaces are absent.

Read/write count outputs are validated before writing zero; input/output spans
are translated through the activation's private frame ledger. All input bytes
and output permissions are validated before VFS transfer or serial output.
Read-only code/header memory cannot become a supervisor write target. Empty
input spans need no mapped input bytes. Read on a write-only handle and write on
a read-only handle fail with error 5. Zero-byte file writes do not grow a file or
advance its position. Sparse-write work is bounded: a write must end within the
first 64 KiB. Oversized transfer/flags fail explicitly. Native filesystem errors
are mapped to declared Windows errors; no unimplemented operation reports fake
success.

Serial and storage authority are borrowed separately and checked live for each
operation. Native application authority remains empty. Sixteen bounded
handle/path slots and one bounce buffer are retained and reused. Borrowed VFS
paths remain valid until close without per-open duplication. All owned handles
close on return, handled fault or deadline. Async Volume SCI RPC remains refused;
both RAM SparkFS and the synchronous direct NVMe backend are exercised.

## Execution, deadline and ownership

The runtime supplies private payload/header/stack/stub frames and uses native
user-domain page tables. Header/read-only data mappings are NX; writable data,
BSS and stack are NX; text is RX. A private return capsule converts the entry
result to the admitted exit convention. Fixtures reserve Microsoft x64 shadow
space and check nonvolatile GPR/SIMD preservation across import calls.

`domain-enter-user-budgeted` supplies a 100-PIT-tick default CPU budget. Actual
infinite CPL3 loops are cancelled with status 124, then a fresh activation works.
This is a scoped CPU-tick budget, not a wall-clock bound on arbitrary kernel
service work or a general asynchronous process scheduler. User-domain page
tables are destroyed before backing frames are freed; retired domain slots and
retained ledgers are reused. Caller IF/PIC/capability/dispatcher state is restored.

Direct NVMe revealed a shared service-context bug: logical `domain-current`
remains the guest during a CPL0 syscall, while actual CR3 is the kernel's tree.
The NVMe service must restore actual caller CR3 separately from logical domain
and capability; restoring the guest tree while continuing kernel instructions
faulted. The native runtime/NVMe owner fixed this boundary before the persistence
proof passed. This is not a Windows-specific CR3 workaround.

## Actual local evidence

Compiler: source-built frozen Inauguration `0.9.324` at
`/workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in`. Reports retain
compiler/kernel/payload hashes and relevant source identities. Run each command
with a new evidence directory; staging addresses and kernel overlap guards remain
explicit.

| Gate | Observed behavior / artifact |
|---|---|
| `check-windows-protected.py` | Original 505 strict-profile cases retained; infinite-loop/fresh-process controls bring the count to 507, including actual CPU denials, checked imports and repeated cleanup |
| `check-windows-files.py` | 527 protected read/file/seek/size runs, actual contents/EOF/counts, denied pointer/output permissions, host-descriptor isolation, exhaustion, live storage revocation and cleanup |
| `check-windows-write.py` | 527 protected writable runs in `/tmp/space-windows-write-general-final`: create dispositions, overwrite/append/sparse holes, reopen exact bytes, permissions/sharing/errors/counts, 25-byte path refusal, revocation, fault/deadline cleanup; zero metadata/activation heap growth after warmup |
| `check-windows-application.py` | 317 application-profile executions in `/tmp/space-windows-application-final`: high 64-bit base, three section permissions, pure BSS, mixed-case DLL/nonzero hints/arbitrary import subset, read-only IAT binding, CPU denial, deadline and stable cleanup |
| `check-windows-persistence.py` | Six independent QEMU/NVMe processes in `/tmp/space-windows-nvme-2`: protected client writes 8192 bytes, remount reads, `TRUNCATE_EXISTING`, `CREATE_ALWAYS`, non-inline 8-byte prefix overwrite preserving the suffix, remount verification |

The complete Windows set also passed after the frozen strict-entry register,
x87 and XMM sanitization change, with unchanged fixture assertions:
`/tmp/space-windows-strict-sanitize` (507),
`/tmp/space-windows-files-sanitize` (527),
`/tmp/space-windows-write-sanitize` (527),
`/tmp/space-windows-application-sanitize` (317), and
`/tmp/space-windows-nvme-sanitize` (six independent boots). The unchanged boot
source SHA256 was
`5f0cc717cd1f57d20606964303cb061edf366778464efd639d7b64d52056495f`;
the frozen source-built compiler SHA256 was
`43b5a2f166efb28ea3123e8030c549d1eac9e90ee7c642d013457ff7ade09168`.

The persistence gate creates a new owned 64 MiB raw disk. Only boot A formats
it, through Space; later boots reuse the same disk without formatting. Guest
`CreateFileA`/`WriteFile`/`CloseHandle` generate file content; the host only
configures the test mode and independently reads the raw disk afterwards. Each
stage checks exact bytes, close/reopen/EOF, native ownership cleanup and expected
allocation counts. Real NVMe readiness and absence of RAM fallback are mandatory.
This demonstrates completed writes/remount, not crash atomicity or journaling.

The file and write corpus uses an explicit supervisor revocation control only
in generated test source. The production dispatcher has no test-only service.
Existing strict malformed-image, protected-memory and original-jq refusal checks
are retained; no new unsupported action is exposed in the desktop launcher.
`git diff --check` and Python syntax checks accompany the runtime gates.

## Remaining original-application work

Original `jq-win64.exe` has ten sections and 217 imports across 14 DLLs (58 from
KERNEL32), plus resource, exception, relocation, TLS and IAT directories. UCRT
API sets supply startup, allocation, FILE/stdio, strings, environment, math,
locale, time, exceptions and threading; SHLWAPI supplies `PathIsRelativeA`.
The tested structural parser is progress toward this binary, but it still does
not execute. Next work needs supported Windows startup/PEB/TEB/TLS, coherent
UCRT APIs, explicit unwind/exception and relocation policies, and required DLL
resolution with real implementation and refusal tests. Unknown imports must not
be bound to zero-return shims. General Win32 GUI APIs and desktop integration
remain subsequent independent adapters within the full application goal.

Read-only disassembly of the checksum-pinned original jq identifies an immediate
startup dependency: entry `0x140001400` calls `0x140001010`, whose instruction at
`0x140001025` reads `GS:[0x30]` and then the TEB stack-base field. Initial GPR/FPU
sanitization does not supply a Windows TEB or GS base. Its static TLS directory
also declares an eight-byte template, an index at `0x1400fa4cc`, and three
callbacks (`0x140083b70`, `0x140083b50`, `0x14007e780`). These observations require
a deliberate startup/TLS framework plan; they do not justify skipping callbacks
or inventing success. Only five currently implemented import names intersect
the original jq import set: `CloseHandle`, `GetCurrentProcessId`, `GetLastError`,
`GetStdHandle` and `WriteFile`.

A separate bounded [TEB/static TLS startup profile](../windows-startup-checks.md)
now exercises private GS state and real CPL3 callbacks. The two profiles above
retain their existing TLS refusal; original Windows jq still does not execute.

The [bounded PE view and identity/error checkpoint](../windows-pe-view-checks.md)
adds variable checked PE header layout and larger protected-image bounds, plus
actual process/thread/pseudo-handle/TEB LastError behavior. The original strict
fixture admission and unknown-import/directory execution guards remain.


## Owned environment and native performance counter checkpoint

[Profile 5](../windows-environment-checks.md) now provides four bounded environment
APIs over an explicit caller-provided map. Canonical/scratch frames are native
only; immutable guest snapshots are owned RO/NX pages. The actual gate exercises
380 protected processes including mutation, snapshot lifetime, atomic failure,
CPU page denials and deadline cleanup. No host environment is inherited.

[Profile 6](../windows-counter-checks.md) now provides QueryPerformanceCounter and
QueryPerformanceFrequency through the native live-authorized HPET counter.
The Windows edge does no hardware discovery or reset. On PC/q35 the focused
proof executes 592 protected processes with exact native samples, counts beyond
2^32, IF0 advancement independent of PIT IRQ delivery, authority/pointer errors,
real backward/sign-bit provider failures and stable teardown. With HPET disabled,
21 counter admissions refuse without allocation and the independent FILETIME
profile executes successfully. Trusted destructive hardware fault-test recovery
creates new test epochs; no production monotonic recovery is claimed.

Fresh receipts for this checkpoint:

- `/tmp/space-windows-counter-complete/report.json`: 593 actual protected
  executions, three QEMU machine variants, unchanged source hashes.
- `/tmp/space-windows-environment-env-counter-regression/report.json`: 380.
- `/tmp/space-windows-{protected,files,write,application,startup,parameters,identity,pe-view}-env-counter-regression/report.json`:
  507/527/527/317/171/275/126/81 actual executions respectively, original jq
  refusal retained.
- `/tmp/space-windows-filetime-env-counter-regression/report.json`: 848 required
  executions against four actual UTC RTC epochs, no natural runtime failures.
- `/tmp/space-windows-persistence-env-counter-regression/report.json`: six actual
  independent NVMe boots, exact file bytes and durable truncate/reopen behavior.
- `/tmp/space-windows-cli-admission-env-counter-regression/report.json`: 294
  original SQLite/7za refusals across all seven profiles, before allocation.

The pinned original SQLite security-cookie startup calls FILETIME at
`0x140234e74`, current thread/process identity at `0x140234e82`/`0x140234e8e`,
and QPC at `0x140234e9e`. The bounded profiles now exercise those individual
contracts; this is not an original SQLite execution trace. Its unchanged PE still
has unsupported directory mask `0x46c`, 157 imports against the admitted limit of
32, and required heap, FLS/TLS, synchronization, encoding and other real APIs.
Read-only disassembly also identifies GetProcessHeap via `0x1402c91f8`, HeapAlloc
via `0x1402b3f96`/`0x1402b93d5`, HeapFree via `0x1402b3f22`, and critical-section
initialization via `0x1402435bf`/`0x1402babb6`. A coherent next slice is an owned
bounded Windows heap contract with real allocation/reallocation/free/size and
negative/lifecycle tests, followed by execution-local TLS/FLS and synchronization.
It must not bind these imports to successful stand-ins. Original Windows SQLite,
7za and jq have no version/help result yet.


## Owned heap checkpoint

[Profile 7](../windows-heap-checks.md) adds five real heap APIs behind an explicit
borrowed memory grant, with a 256KiB private RW/NX arena, native-only 128-record
ledger, per-activation opaque handle, 16-byte alignment, exact logical HeapSize,
zero-size allocation and atomic in-place/moving realloc. Unsupported exception
flags/imports remain refused. Memory authority is rechecked for every operation;
owned cleanup does not depend on the grant remaining live. Prior profiles do not
admit the new imports. The actual focused gate performs 485 protected executions
and seven allocation-free admission refusals, with real NX/native-ledger CPU
faults, overflow/bad-free/stale-handle/arena+record exhaustion, live revocation,
deadline and fresh activation evidence. The original SQLite/7za refusal gate
now checks eight profiles, 336 repeated refusals. This is still bounded runtime
fixture coverage: original applications remain unexecuted and their import-slot,
directory, TLS/FLS and synchronization requirements remain explicit blockers.


## Execution-local TLS/FLS and entry ABI checkpoint

[Profile 8](../windows-local-checks.md) adds 64 dynamic TLS slots at the real x64
TEB TlsSlots offset and 16 execution-local FLS slots, while keeping static TLS
separate. Its two-page TEB relocates the PEB without changing older profiles'
addresses. Entry RSP now reserves the actual Win64 return/home area below its
stack base. An independent private callback stack has valid home space and
scoped TEB stack bounds. FLS free and normal/explicit process exit invoke actual
CPL3 callbacks using the generic saved user context, preserving suspended outer
GP/FX and sharing execution-local values. Fault/deadline cleanup is real, and
nested termination/recursive callback requests have explicit bounded refusal.

The first repeated gate exposed hardware-captured RF in a suspended syscall
frame, which generic context validation had wrongly rejected. Exact failing
frames and the original binary were preserved before the generic CPU owner
fixed safe RF admission and proved actual IRET continuations. Windows neither
normalizes the saved flags nor weakens CPU validation itself.

Fresh focused receipt `/tmp/space-windows-local-final2/report.json` passes 443
activations, including 21 deterministic RF-bearing callback/outer continuations,
entry/callback home writes, all nonvolatile GP canaries, XMM6/XMM15/x87/MXCSR,
byte-exact native kernel FX preservation, real callback faults/deadlines,
recursive/destructor-cycle bounds, live revoke and stable 21-cycle cleanup.
Fourteen legacy gates under `/tmp/space-windows-*-local-final-regression/` retain
strict507, files527, write527, general317, startup171, parameters275, identity126,
PE-view81, six NVMe boots,848 FILETIME,380 environment,593 counter and485 heap
execution cases. Official SQLite/7za still refuse before allocation across nine
profiles (378 checks). Original Windows apps remain unexecuted; synchronization,
encoding/locale, other real APIs and the original PE directory/import-count
barriers remain subsequent work.

The final repeated focused gate
`/tmp/space-windows-local-eight-boots/report.json` passes 3544 activations over
eight fresh VMs using one compiled image, with unchanged source hashes. Its
public harness exposes `--boots` so the earlier intermittent admission failure
can remain a reproducible repeated acceptance check.


A final admission review found that frame capacity could not pay for the seven
first-use bump caches. The narrow fix reserves exact 26912 retained bytes before
page rounding/counting and validates signed/rounding heap bounds. The explicit
owned ledger maximum is 1096<1152, with the focused fixture's 83 entries checked
against live mappings. Profile 8's extra 6 frame allowance covers its 3 additional
guest pages, native context frame, callback page-table leaf and one spare.
`/tmp/space-windows-local-cache-final/report.json` passes 443 focused activations
plus exact cold recovery (444 total), with 200 actual free frames, zero/short-bump
refusal, exact 26912-byte recovery and three malformed-bound refusals (six total
admission refusals). Strict 507+jq refusal and heap 485 representatives pass at
`/tmp/space-windows-{strict,heap}-cache-regression/report.json`. These are the
fresh receipts for the final narrow admission change; the earlier 14-gate and
8-boot receipts retain their own source snapshots.


## Single-thread critical-section checkpoint

[Profile 9](../windows-critical-checks.md) implements the six critical-section
imports observed in the pinned SQLite CRT, including its AndSpinCount fallback
at 0x1402435bf. One native-only 64-record frame owns recursion and thread identity;
the full 40-byte guest ABI is validated before mutation. Recursive acquisition,
TryEnter, Leave, Delete and initialization/reuse are real. Foreign-owner Try
returns FALSE; Enter does not invent a runnable contender or successful wait.
Void invalid/unsupported state has explicit terminal policy rather than fake
BOOL success. Memory authority remains borrowed/live and teardown unconditional.

`/tmp/space-windows-critical-final/report.json` passes 653 focused activations
plus one exact cold-resource recovery (654 total), actual native SCI private
import denial, full-record/guest no-partial-write observers, capacity/overflow/
malformed/foreign-owner cases, CPU metadata-read/NX faults, live revoke,
held-section deadline/exit and stable 21-cycle cleanup. Fifteen fresh Windows
regression receipts under `/tmp/space-windows-*-critical-regression/` retain all
prior behavior and 420 original SQLite/7za refusals across ten profiles. The
original apps still do not execute; import-count and PE directory guards remain,
with encoding/locale, module resolution and other real CRT services subsequent.

## Composed startup checkpoint

[Profile 10](../windows-composed-checks.md) combines API IDs0–42 from the existing
command/identity, environment, FILETIME/QPC, heap, TLS/FLS and critical services.
A version1 native96-byte descriptor owns the explicit borrowed grant/input
configuration; the guest never receives its private backing. Clock service is
explicitly disabled, optional-counter, or required-counter. The older profiles
retain their import/layout contracts and native CPU mechanisms are unchanged.

The mixed CPL3 scenario executes a real FLS callback while a recursive critical
section is owned, allocates/frees from the same heap, changes TLS/environment,
uses actual RTC/QPC when available and resumes with preserved nonvolatile state.
The PC/Q35/noHPET focused receipt records773 activations; all16 prior Windows
gates pass again, including six NVMe boots and462 original-app refusals. The
exact cold bound is171 freeframes refused unchanged,172 recovered plus26912
retained bump bytes. Private configuration read, readonly environment write and
heap execution fault; deadline, live grant revoke and actual RTC SET failures
tear down all owned resources. Void-service terminal statuses remain terminal
through the composed context runner.

Original SQLite remains behind directory mask0x46c and157 imports versus the
execution limit32. Static union inspection finds42 implemented names and115
unsupported, with first unknown SetCurrentDirectoryW at one-based slot3. No
original Windows SQLite/7za/jq execution is claimed. Next implement strict
UTF8/UTF16/count/error and truthful code-page metadata; locale/collation, wide
file APIs, dynamic resolution and PE metadata semantics remain separate work.

## Explicit UTF8 checkpoint

[Profile11](../windows-unicode-checks.md) implements six observed original SQLite
encoding imports in a separate pure scalar provider plus Windows guest-memory/
authority policy. Its declared ANSI/OEM codepages are65001; UTF8/UTF16 count/query,
strict/replacement, surrogate and bounded failure semantics are executable. It
adds no activation pages or per-call allocations and keeps profile10 admission
unchanged. A narrow clock-scan fix reads the existing terminator for exactly32
imports, with no33rd import admitted.

The independent scalar oracle executes3410 cases per compiler profile under
default/lean/harden; actualQEMU separately executes3410 scalar vectors and4921
CPL3 activations. The mixed32-import fixture adds Unicode roundtrip/metadata in
main and actualFLS callback across773 PC/Q35/noHPET activations. All17 older
Windows gates pass again, including sixNVMe boots and504 original SQLite/7za
refusals across12 profiles. Locale/collation, wide file/module APIs and admitted
PE metadata remain next dependencies; no originalWindowsCLI executes.

## Owned cwd and wide file checkpoint

[Profile12](../windows-path-checks.md) adds a declared C: namespace over actual
borrowed synchronous Storage. The new native caller-buffer normalizer owns no
foreign policy, allocates nothing and commits output atomically. Six native-only
frames own cwd/scratch and1024-byte stable borrowed VFS paths; real file cleanup
precedes path-frame release. A/W opens share canonical identity only in this
new profile. Earlier profiles keep their existing behavior and admission.

The focused CPL3 receipt records1326 activations, real directory/file/Unicode/
query/denial semantics, exact177-refuse/178-recover and26912 bump reservation,
native inode/bitmap and handle invariants, private-pointer faults, held deadline
and live Storage revoke. Three independent NVMe boots add63 activations: onlyA
formats, the guest writes a Unicode file through CreateFileW and reopens through
A, thenB/C read it. A read-only raw-disk oracle validates nested UTF8 names/inode
and exact bytes. The native normalizer model passes233 cases×3 compilerprofiles.
Nineteen old Windows gates pass; a final profile12-only trailing-file separator
refusal retains an actual pre-fix failing kernel control and affected fresh
focused/NVMe/CLI receipts. Source/model/guest proofs are classified separately.

Original SQLite still refuses:52 implemented imports/105 unsupported, next name
FindClose at slot5,157 names versus limit32, unsupported metadata mask0x46c. No
original Windows CLI executes. A real bounded native directory iterator is the
next provider needed for FindFirst/Next/Close; timestamps, wide mutations, module/
locale/mapping APIs and admitted PE metadata remain distinct executable work.
