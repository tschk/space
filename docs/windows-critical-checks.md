# Owned single-thread Windows critical sections

`windows-command-critical-run(image,size,serial,storage,memory,line,bytes)` adds
profile 9: command/identity/heap APIs plus InitializeCriticalSection,
InitializeCriticalSectionAndSpinCount, EnterCriticalSection,
TryEnterCriticalSection, LeaveCriticalSection and DeleteCriticalSection.
It borrows a live native memory grant. The other Windows profiles retain their
existing imports and layouts. Original SQLite, 7za and jq still do not execute.

The pinned original SQLite imports all six names. Its CRT fallback calls
InitializeCriticalSectionAndSpinCount at `0x1402435bf`; a dynamically resolved
InitializeCriticalSectionEx path remains a separate unsupported dependency.
This checkpoint implements actual ownership transitions rather than replacing
startup synchronization with successful no-ops.

## Ownership and layout

One native-only frame holds 64 records containing the guest address, recursion,
spin state and owning thread. Each activation owns and releases this frame;
there are no per-call allocations. Critical-section objects occupy caller-owned
writable guest memory. Every API checks the live memory grant, the full writable
40-byte span and eight-byte alignment before changing any object or record.
Initializing duplicate or overlapping objects is refused without mutation.

The supported x64 object layout is:

| Offset | Field and supported state |
| --- | --- |
| 0 | DebugInfo: -1 while initialized; zero after deletion |
| 8 | LONG LockCount: recursion minus one, initially -1 |
| 12 | LONG RecursionCount: initially zero |
| 16 | OwningThread: zero or the execution's native thread ID 1 |
| 24 | LockSemaphore: zero; no wait event is invented |
| 32 | SpinCount: zero for this single-processor profile |

The -1 debug marker matches modern Windows behavior recorded in Wine's tests;
it is not a privileged diagnostic pointer. InitializeCriticalSectionAndSpinCount
accepts low 31-bit counts, ignored on the declared single processor. High-bit
preallocated-event requests are refused. InitializeCriticalSectionEx and
SetCriticalSectionSpinCount remain unsupported imports.

Native records are authoritative. Each subsequent operation verifies that the
guest fields still match its native record. Copied/uninitialized objects and
guest-forged owner/recursion/semaphore/debug fields do not acquire ownership.
Direct inline manipulation of critical-section fields is outside this bounded
profile. Deleted addresses can be initialized again; as with the Windows pointer
API, addresses can be reused and do not carry per-pointer generations.

Enter acquires an unowned section or increases recursion when thread 1 already
owns it. TryEnter performs the same transitions and returns TRUE. Leave reduces
recursion and releases the owner only at zero. Delete requires an unowned section,
clears its diagnostic marker and releases the native record for reuse. LastError
is preserved on success, and TryEnter preserves it when returning FALSE for a
foreign owner. Recursion is bounded before signed 32-bit overflow.

There are no runnable foreign Windows threads or wait/event service in this
profile. A contended Enter therefore ends the activation with status 127 instead
of claiming acquisition or waiting for a nonexistent thread. TryEnter returns
FALSE without mutation for consistent foreign ownership. Actual foreign-owner
cases in the gate are supervisor fault injection, not a claim of multithreaded
execution. Deleting a held object, unowned/wrong-owner Leave, invalid state and
unsupported void-API cases also terminate with status 127. Process teardown may
discard remaining owned/held records because their entire address space ends;
it does not pretend DeleteCriticalSection was called by the application.

## Failure and authority

The two BOOL APIs return FALSE and set bounded policy errors: 5 for revoked
memory authority, 998 for inaccessible/nonwritable spans, 87 for malformed or
unsupported state, 8 for record capacity, and 534 for recursion overflow.
Initialization failure and failed TryEnter leave the object and native ledger
unchanged. The void APIs cannot report BOOL failure: revoked authority ends the
activation with 126, invalid spans with 142, and other unsupported state with
127. These are explicit Space activation statuses, not synthesized Windows SEH
exceptions or successful Win32 returns.

Revocation is checked on every operation. It does not retract already owned
mapping pages. Cleanup releases the native ledger and all process-owned pages
on success, policy denial, CPU fault and guest deadline, independently of the
borrowed grant remaining live. The shared first-use cache reservation and page
ledger bounds from the TLS/FLS checkpoint remain enforced. Profile 9 reserves
one additional frame for its native critical-section ledger; it does not add
new guest backing pages or change old TEB addresses.

## Executable proof

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-critical.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-critical-proof
```

`/tmp/space-windows-critical-final/report.json` passes 653 protected activations
plus one cold recovery (654 total). Cases cover real recursive ownership and
thread identity, BOOL TryEnter, Leave, Delete, spin initialization, duplicate and
overlapping initialization, invalid/uninitialized/copied/forged structures,
read-only and valid/invalid cross-page spans, all 64 records and reuse, 100
init/enter/leave/delete cycles, foreign-owner refusal, overflow, live revocation,
held-object exit/deadline and a fresh clean activation. CPU page faults prove the
native ledger is unmapped and the guest object pages are nonexecutable.

A supervisor observer compares all native records, the target, the original
object and the mapped bytes before an invalid crossing on every failed API.
It checks actual live backing-frame counts. After one warmup cycle, 20 further
cycles preserve heap, free-frame count and domain count exactly; caller FS/GS,
grants and all execution state restore after each outcome. The cold-resource
case supplies only 158 free frames with exactly 26912 retained bump bytes and
requires allocation-free refusal; adding the 159th frame permits actual execution
with exact bump movement and all frames returned.

The same gate compiles and loads a structurally valid native SCI with a public
serial import and the private windows-parameters-critical-dispatch import. The
actual registry refuses the private import before allocation or entry; the
invalid-entry marker never executes. Helper and launch names retain existing
filtered windows-parameters-* and windows-command-* prefixes. No registry or CPU
core changes are required.

Fifteen fresh Windows regression gates at
`/tmp/space-windows-*-critical-regression/report.json` retain strict 507 (including
original jq refusal), files/write 527 each, general 317, startup 171, parameters
275, identity 126, PE-view 81, six independent NVMe boots, FILETIME 848,
environment 380, counter 593, heap 485 and TLS/FLS 443 plus its cold recovery.
Original SQLite/7za refuse before allocation in all ten profiles: 420 checks.
The original 157-import SQLite image still exceeds the 32-import bound and has
unsupported directory/dependency requirements; this fixture is not its execution.

Read-only references, without source vendoring, are Wine's
[critical-section implementation](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/ntdll/sync.c)
and [public tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/sync.c)
at `840a939ee526137639665ff5f587224d6a36403f`, and ReactOS
[critical.c](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/sdk/lib/rtl/critical.c)
at `e81244349554c4f98a97fdd7fb67d7a1b450eec5`.
