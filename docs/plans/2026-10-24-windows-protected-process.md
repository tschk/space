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
| `GetLastError` | Per-activation state, initialized to zero and preserved on ordinary successes | Single-threaded; no Windows TEB/TLS slot yet |
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
