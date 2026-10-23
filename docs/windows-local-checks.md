# Versioned execution-local Windows TLS/FLS

Profile 8, `windows-command-local-run(image,size,serial,storage,memory,line,bytes)`,
extends the bounded heap/command profile with TlsAlloc/GetValue/SetValue/Free and
FlsAlloc/GetValue/SetValue/Free. It retains the explicit borrowed native memory
grant and per-activation ownership. Unknown imports, unsupported PE directories
and the 32-import admission bound remain enforced. Original SQLite, 7za and jq
remain unexecuted; nine-profile SQLite/7za admission testing records 378 refusals.

## Layout and CPU boundary

Earlier profiles retain their existing partial TEB layout. Profile 8 reserves two
TEB pages at `0x4e000000`, relocates its PEB to `0x4e005000`, and keeps the static
TLS vector/data at `0x4e002000`/`0x4e003000` and parameter page at `0x4e004000`.
Dynamic TLS values use the actual x64 TEB TlsSlots offset `0x1480`, without
aliasing the PEB. GS:[0x58] remains the separate static TLS vector. Native policy
selects the owned PEB address; it does not trust a guest-rewritten TEB PEB pointer
when accessing privileged memory.

Initial process RSP is `0x4f003fd8`, with its return capsule at that address and
32 bytes of writable home space above it, entirely below the declared stack base
`0x4f004000`. The former `0x4f003ff8` left the home area above the declared base.
The five owned stack pages remain. Entry alignment is RSP modulo 16 = 8.

FLS callbacks execute at CPL3 using an independently owned callback stack at
`0x4c000000` (two RW/NX pages), with initial RSP `0x4c001fd8`, home space and a
fresh return address for each call. Its active TEB stack bounds switch to that
owned callback stack and restore on every callback result. Native-only contexts use the generic
[user-context contract](native-user-context.md). FlsFree suspends the outer guest
through action 2, runs the callback with its value in RCX, and resumes the saved
outer GP/FX context only after the callback returns through the private capsule.
The callback inherits the outer FX image, while outer GP/FX restoration protects
the suspended caller from callback register clobbers. TLS/FLS mutations remain
shared within this single execution. No guest callback is invoked at CPL0.

## Bounded service behavior

There are 64 TLS indexes (0–63) and 16 FLS indexes (1–16). Values are opaque
64-bit integers, including NULL. Allocation initializes the value to NULL;
exhaustion returns DWORD -1/error 8. Get-value success clears LastError, allowing
NULL to be distinguished from failure. Set/free success preserves LastError.
Invalid or unallocated indexes return failure/error 87. Every API checks the live
memory grant; denial returns error 5. The profile does not implement threads,
fibers, TLS expansion slots or an internal Windows FLS data-structure ABI.

FlsAlloc accepts NULL callbacks or an owned executable, nonwritable guest address.
Data/kernel/unmapped callback pointers refuse with DWORD -1/error 998. FlsFree
invokes a non-NULL callback only for a non-NULL value, then clears/frees the slot.
The callback can read its current value; recursively freeing that same active
slot, or requesting another callback-producing FlsFree from a callback, returns
FALSE/error 170 without pretending the callback ran. Callback-free operations
remain available. This is an explicit bounded recursion policy.

Normal entry return and explicit ExitProcess suspend into FLS rundown. Every
remaining non-NULL callback/value pair executes at CPL3 before the requested exit
status is returned. The remaining delivered guest IRQ quantum is shared across
outer/callback resumes; no callback receives a fresh timeout budget. A separate
64-callback transition cap stops a destructor cycle with status 127. Kernel policy
time is excluded from this IRQ budget, so it is not a wall-clock deadline.

A callback fault or IRQ deadline ends the activation with its actual fault status
or 124 and does not resume the suspended FlsFree caller. Forced termination does
not promise further destructor execution. ExitProcess inside a callback is an
unsupported nested termination: status 127 ends the activation without a false
return to user code. All context frames, callback stack, TLS/FLS state and heap
resources are released even after faults, deadlines or grant revocation.

## Validation status

The new fixture exercises entry/callback home writes and alignment, actual TEB
slots, NULL/high-bit values, index exhaustion and reuse, callback pointer denial,
real FlsFree/normal-exit/explicit-exit callbacks, callback heap calls, shared TLS
mutation, deliberate nonvolatile GP/XMM/x87 clobber with outer restoration,
callback faults/deadlines, live revoke, recursive free and bounded destructor
cycles. Legacy Windows gates pass with the lower initial stack pointer.

The final gate `/tmp/space-windows-local-final/report.json` passes 443 protected
activations: 21 modes over 21 cycles, live revoke and fresh callback activation.
The supervisor requires the exact number of actual return-capsule completions,
including zero on callback fault/deadline. Each activation compares a native
512-byte kernel FX canary byte-for-byte, checks FS/GS and all owned state, and
20 cycles after warmup preserve heap, free-frame count and domain count exactly.
Guest canaries cover RBX/RBP/RSI/RDI/R12–R15, XMM6/XMM15, x87 ST0 and MXCSR;
callback mutation of execution-local TLS persists after restoring outer GP/FX.
A trusted test hook injects RF into 21 actual suspended syscall frames and
requires callback plus outer continuation through real IRET.

The first gate found a real generic context validation bug: a hardware-captured
outer syscall frame contained RFLAGS `0x10283` (RF set). Copying that valid state
made the former generic setter reject a callback context. The unchanged failing
binary, exact outer/callback frames and memory dump are retained at
`/tmp/space-windows-local-context-refusal2/5/`. The generic owner fixed only safe
RF admission in `user-context.in`, retaining TF/IOPL/NT/AC denial, and independently
proved 20 RF-bearing parent/child IRET continuations in its 62-execution gate.
Windows does not normalize flags or widen CPU policy. The captured frame remains
part of the evidence rather than being hidden by retries. The final repeat gate
`/tmp/space-windows-local-eight-boots/report.json` runs the same compiled image
in eight fresh VMs: 3544 activations pass, with unchanged input source hashes.

Run the focused gate with the explicit frozen compiler:

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-local.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-local-proof --boots 8
```

Behavior references are Wine's pinned
[thread tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/thread.c),
[fiber tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/fiber.c)
and [FLS implementation](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/ntdll/thread.c)
at `840a939ee526137639665ff5f587224d6a36403f`. These are read-only contract
references; no implementation source is vendored.


## First-use retained storage and frame admission

The seven shared Windows scratch caches use the native bump allocator, rather
than the free-frame list. Cold admission therefore reserves their exact rounded
26912 bytes before aligning the remaining bump cursor and counting whole pages.
Negative/inverted heap bounds and a cursor/end range that could overflow page
rounding refuse with `-12`. Cached launches reserve zero additional bump bytes.
A large free-frame pool does not excuse insufficient retained bump capacity.

The exact guest backing ledger is checked separately from page-table/native
scratch reservations. At the largest admitted image it is:

```
1024 image/header/stub/stack + 4 startup + 1 parameters + 64 heap
+ 2 callback stack + 1 relocated PEB = 1096 < 1152 ledger entries
```

The extra six native frame reservations for profile 8 cover two callback pages,
one relocated PEB page, one native context/metadata frame, one new callback
region page-table leaf and one conservative spare. Existing heap/startup/frame
reservations remain separate. The focused fixture's exact 83 backing pages are
compared with the actual live frame ledger on every syscall.

The final narrow review-fix receipt
`/tmp/space-windows-local-cache-final/report.json` passes the 443 focused
activations plus one cold recovery (444 total), with six admission refusals and
unchanged source hashes. It supplies 200 actual free frames, proves no mutation
with zero or 26911 available bump bytes, and recovers with exactly 26912 bytes:
heap movement is exact, all seven caches initialize, and all 200 free frames
return. Three actual malformed heap-bound cases also refuse without mutation.
Strict 507 (including original jq refusal) and heap 485 representatives pass at
`/tmp/space-windows-{strict,heap}-cache-regression/report.json`. The earlier 14
regression receipts and eight-boot callback repetition precede this narrow
admission change; they are retained with their own source hashes.
