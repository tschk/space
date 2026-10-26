# Bounded PE layout and Windows identity/error startup

The official Windows SQLite 3.46.1 image now passes structural validation at its
original entry `0x140003a8a`, with nine sections and 946 pages under the runtime's
existing counting formula. Its bytes remain unchanged. Full execution still
refuses before allocation: resources, unwind/exception data, relocations, debug
and load configuration remain unsupported, and unknown imports are not bound.
This does not execute SQLite or produce its version/help output.

## Validated layout view

`components/windows-pe-view.in` supplies private helper addresses derived from a
checked PE header offset. General profiles accept a four-byte-aligned
`e_lfanew` from 64 through 3832, with the complete PE32+ fixed header in the file
and first header page. COFF/optional/section fields are read through this view;
section count remains 1–16, optional header 240 bytes, headers at most 4096 bytes,
and section/file alignments remain 4096/512. Header/section tables must fit their
declared spans before section traversal. The original strict fixture profile
keeps its fixed 128-byte PE offset and exact two-section admission.

The general section extent bound grows from 2 MiB to 4 MiB. The page-count bound is
1024, including the existing seven header/stub/stack pages in its counting
formula. The reusable frame ledger holds 1152 entries; startup/TLS/parameter pages
fit within that bound, with a conservative 80-frame reserve for native page
tables and fixed activation resources. Resource shortage returns `-12` before
activation. This is a bounded synchronous loader, not unbounded PE allocation.

Terminal-server-aware DLL metadata is admitted alongside the existing NX/ASLR
flags. The `GUARD_CF` bit and other unknown flags still refuse; load-configuration
and exception/unwind directories are not treated as inert padding. Execution is
at the validated preferred base only; no slide, relocation application or ASLR
claim is added. The relocation directory remains an execution barrier even
when a zero slide would avoid relocation writes. Static TLS remains available
only through the previously tested explicit startup profiles.

Read-only diagnostics require structural validation and allocate nothing:

- `windows-application-directory-mask` reports unsupported nonzero directories.
- `windows-application-import-barrier` reports the first unsupported named import
  (one based), or a malformed/non-KERNEL32/unterminated-table classification.
  This diagnostic does not widen the executable 32-import limit or resolve a
  dependency. It stops at the first barrier and does not prove every later slot.

For the original pinned SQLite, the runtime verifies entry `0x140003a8a`, pages 946,
unsupported directory mask `0x46c` (indices 2/3/5/6/10), and first unsupported import
2: `GetEnvironmentVariableA`. The manifest independently records all 157 actual
KERNEL32 imports. The original 7za still fails structural admission (including its
lower base and different dependency graph). All four launch profiles refuse both
originals with `-8` and unchanged heap/frame/domain ownership.

## Actual CRT identity and error group

SQLite's actual MSVC startup cookie initialization at `0x140234e82` calls
`GetCurrentThreadId`; other runtime paths import `GetCurrentProcess` and
`SetLastError`. The explicit command/startup profile now admits these three
additional names. No clock, heap, thread creation or UCRT function is substituted.

`components/windows-process-identity.in` returns the sole activation thread's
DWORD identity from the owned TEB and the Windows current-process pseudo handle
`-1`. The pseudo handle is not a native capability or file descriptor; attempting
to close it through `CloseHandle` returns false/error 6. There is one active
Windows guest thread and no broader scheduler/threading claim.

`SetLastError` stores the low 32 bits. For TEB-based profiles, dispatch loads the
activation's fixed owned TEB `LastErrorValue` at offset `0x68`, performs the API,
then stores the resulting DWORD back. Thus direct guest TEB writes, successful
API preservation, native adapter failures and explicit SetLastError agree.
Kernel policy locates the owned TEB through its frame ledger and never follows
a guest-written NT_TIB self pointer. The earlier strict/general profiles retain
their existing personality-owned state because they have no TEB mapping.
Fault/deadline/normal completion clears the native activation state; the next
execution receives a fresh zero LastError. FS/GS restoration is unchanged.

## Fresh proof

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-pe-view.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-pe-view-view-final

PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-identity.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-identity-view-final
```

The large-image gate performs 81 actual CPL3 executions across header offsets
64/128/256. Each synthetic image has a 3 MiB RX section and 778 baseline mapped
pages. It actually calls code in the final RX page, checks BSS, denies text/header/
read-only writes and data execution, refuses kernel/initial-GS reads, cancels an
infinite loop 124, restores FS/GS and proves exact repeated heap/frame/domain
invariants. Thirty malformed/resource refusals precede entry. Payloads are staged
with explicit QEMU generic-loader devices and a guarded heap ceiling, keeping
large image bytes out of the kernel's code/data/heap ranges.

The identity gate performs 126 actual launches: process/thread identity, pseudo
handle refusal, DWORD truncation, direct TEB writes, successful LastError
preservation, native error 6 synchronization, kernel-read faults, infinite-loop
cancellation and fresh-zero state afterward, with 21-cycle exact resource and
segment restoration checks. Both gates record source/compiler/kernel hashes and
commands. The explicit source-built compiler remains 0.9.324, SHA256
`43b5a2f166efb28ea3123e8030c549d1eac9e90ee7c642d013457ff7ade09168`.

Original-app refusal receipt:
`/tmp/space-windows-cli-refusal-view-final/report.json` (168 refusals, executed
false for both originals). Existing strict 507/file 527/write 527/general 317,
startup 171, parameters 275 and six-boot NVMe gates are retained as regressions.

The next startup work needs real native clock/heap/TLS/thread-local/encoding
contracts and a deliberate policy for remaining PE metadata. In the original
CRT cookie initializer, FILETIME at `0x140234e74` and QPC at `0x140234e9e` remain
separate prerequisites. A coherent native RTC service can support an honest
FILETIME translation; constant time or zero-success clock answers cannot.

The following [FILETIME checkpoint](windows-filetime-checks.md) implements actual
UTC RTC conversion under a borrowed timer grant with explicit terminal failures.
QPC and the remaining original SQLite dependencies remain unavailable.
