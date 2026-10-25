# Broader original application execution

Continue the open compatibility/desktop goal using unrelated original programs,
not only one compiler family. Next targets are QuickJS2024-01-13 and GNU sed4.9,
built statically from exact upstream release archives without source patches.
Record configuration/compiler/source/binary/license hashes and host reference
outputs separately from actual Space execution. Every supported scenario needs
real program output, statuses, file effects and repeated ownership checks.

Use the existing native owned process/VM/VFS/terminal contracts. Keep foreign
syscall semantics at the Linux edge and refuse missing services honestly.
Clock APIs must consume an explicit timer grant and actual RTC/monotonic samples;
argument vectors must use owned storage and real startup data. Do not add app-name
exceptions, synthetic app output or host-GUI substitution. The current known
three-argument CLI limit and missing gettimeofday/clock_gettime are candidate
runtime gaps; demonstrate actual failures before choosing the next change.

This step does not replace the Windows/macOS and real graphical-app targets.
The full goal stays open, and broader GUI applications remain required.

QuickJS first executes arithmetic, BigInt, JSON/arrays, Unicode regex and promise
jobs. Real files also read/write correctly. Its Date case exposes missing Linux
gettimeofday; that failure remains preserved. Native-clock translation now
supplies explicit-grant UTC RTC and HPET monotonic APIs with full output-range
preflight. Provider controls independently check invalid/RO pointers, timezone
atomicity, clock IDs, int widths, monotonic range and revoked timer authority.

The next startup change removes the three-argument restriction through a
private trusted native vector API (at most16 strings,511 bytes each). Reuse the
process row's existing owned argv/env buffers and exec-stack builder; no raw SCI
pointer API or alternate process/VM ownership is introduced. Existing fixed
three-slot entry and its stack remain intact. A caller borrows stable native
strings only through synchronous startup; execution copies and owns them before
CPU entry. Validate the complete request before process allocation. Test real
QuickJS `--std -e` and GNU sed multi-option invocations as well as refusal paths.

The first QuickJS event timer reaches its output while retrying unsupported
pselect6. That output alone is insufficient: require an observed native interrupt
wait with the user CPU stopped. Add a bounded no-descriptor select/pselect6
profile over actual native Counter deadlines and the existing blocked-process
state. A private native execution-clock helper may enable interrupts and halt
for one real IRQ only with kernel CR3, no guest/budget context and no preemptive
scheduler active. Restore the caller's IF state and revalidate clock authority.
The Linux edge owns timeout layout, deadlines, resume and errors; it must not
invent readiness, spin in an interrupts-masked syscall, or add a second wait/IPC
fabric. Descriptor selects and temporary signal masks remain unsupported.

Audit private export discovery alongside this boundary: new execution helpers,
classic PE32/Darwin helpers and supervisor-window initialization must be absent
from raw SCI imports even when explicitly linked into a test image. Prove actual
compiled symbols are present but unavailable, and refuse emitted artifacts before
entry or resource mutation.

Minimal boot now initializes the existing optional native Counter provider from
its actual Multiboot/ACPI inputs, as standard boot already did. It does not link
a legacy personality into the minimal root. Without HPET, the wall clock remains
available from RTC and monotonic operations return unsupported; a separately
named no-HPET workload verifies that boundary. The first no-HPET runner used an
unsupported QEMU option; its launch log is retained and the corrected command
uses `-machine pc,hpet=off`.

Initial runtime receipts now pass on standard and minimal roots, including
actual native IRQ waits; the separately declared no-HPET profile passes with
wall-clock/file/language work and explicit monotonic refusal. Two builds in
different directories produce the same stripped static artifact hashes while
all49 QuickJS and508 GNU sed original source/template/license files remain
unchanged. Initial unstripped diagnostic artifacts retain their own manifests.

`--cohort cli` now retains five original-program profiles (both roots per tool
and the explicit QuickJS no-HPET profile) plus actual private-import refusal.
With cached artifacts, complete `all` definitions rise from176 to182; two absent
CLI artifacts may add source-build gates. A complete182-gate run is not claimed.
Frozen-source cohort and affected regression receipts follow before publication.

Continue after this foundation toward the real QuickJS REPL using retained native
terminal input and a client-owned SCI screen. Its descriptor select/readiness and
termios requests must be implemented through owned queues, not replaced by
synthetic prompt/output. Capture actual keyboard effects and original engine
results; a terminal screenshot alone does not establish a graphical framework.
