# Original QuickJS and GNU sed execution

The full compatibility/desktop goal stays **OPEN**. Frozen source `8ed40f3`
passes the six-gate broader CLI cohort, the eleven-gate original three-OS cohort,
fourteen affected QEMU regressions and three source/metadata contracts. Source,
compiler and original-app integrity remain unchanged through both cohorts.
[Exact receipts and hashes](2026-10-25-broader-cli-evidence.json).

QuickJS2024-01-13 and GNU sed4.9 are unrelated upstream applications built
statically from pinned release archives without source patches or Space libc
wrappers. Two build directories produce identical normalized binaries. All49
QuickJS and508 GNU sed original source/template/license files remain unchanged.
The normalization removes the linker build ID and strips debug sections; initial
unstripped diagnostic builds retain distinct manifests. The first normalization
candidates correctly failed the previous artifact pin, and remain preserved.
Their reviewed hashes are reproduced by the second builds. Source/binary/license
hashes and configuration are recorded in the application manifests.

| Actual original-program profile | Activations | Behavior verified |
|---|---:|---|
| QuickJS standard | 80 | Arithmetic,100! BigInt, JSON/arrays, Unicode regex, promises, caught errors, actual file read/write/reopen, real Date/monotonic time,16 arguments and event timers |
| QuickJS minimal | 80 | Same workload and real stopped-CPU timer waits on the minimal boot root |
| GNU sed standard | 74 | Substitution, captures, hold space, real input/files, multi-option argv and real error status |
| GNU sed minimal | 74 | Same workload on the minimal boot root |
| QuickJS without HPET | 55 | Declared wall-clock/file/language profile; native monotonic service refuses unsupported hardware |

That is363 original program activations, separately from390 original fasmg
activations in the same-source cross-OS cohort. Each profile includes21 steady
ownership cycles and actual guest-IRQ cancellation. Synthetic CPU faults and
native clock/argv controls do not add original-application credit.

The event-loop test requires observed native interrupt waits, not just the
expected timer output. The earlier timer-output-only run still retried an
unsupported pselect6; it does not establish the completed wait profile. The new
native helper waits for a real IRQ with no guest CPU/budget active, restoring IF.
The existing owned process state holds a zero-descriptor deadline and resumes
the original saved CPU context. The Linux edge owns timeval/timespec and errors.
It implements finite select/pselect6, RTC gettimeofday and realtime/monotonic
clock_gettime/getres with explicit timer authority. Descriptors, infinite waits
and temporary signal masks remain outside that finite select profile.

Owned launch vectors reuse the existing process argv/env buffers and startup
builder:1..16 strings, at most511 bytes each. Invalid grants, spans, late invalid
arguments and oversized strings refuse before native process allocation. The
old three-slot entry keeps its original startup path. Optional terminal and GUI
launch integration remains separate work.

A discovered export gap is corrected: execution-clock, supervisor relocation,
classic Darwin and PE32 private helpers are excluded from raw kernel SCI imports.
The test compiles all six requested symbols and six importing SCI artifacts, then
proves exact unresolved-import refusal before entry, allocation or artifact
mutation. This is distinct from merely testing an absent/uncompiled function.

Affected regressions pass original jq/Lua/SQLite, native VM on both roots,
blocking pipes on both roots, VM/vfork, retained terminal, original vi navigation
on both roots, visible vi's independent pixel oracle, and desktop launcher/damage.
Architecture, SCI metadata and personality ABI contracts also pass. Receipt
scope remains separate from the historical full163-gate run. Current `all` defines
182 cached-artifact gates; no complete182-gate run is claimed.

Actual Space serial logs: [QuickJS](../evidence/2026-10-25-broader-cli/quickjs-standard.serial.txt)
and [GNU sed](../evidence/2026-10-25-broader-cli/sed-standard.serial.txt).
These are original CLI executions, not graphical application screenshots.
The original QuickJS REPL, foreign GUI frameworks, browsers/Electron, ordinary
installed launch and concurrency remain active next work.
