# Darwin high-address owned mapper

Consume the committed original-image plan using the generic native
`UserAddressSpace` object committed in `4a4b631` (`user-address-space.in`). Do not
add the previously proposed independent576-entry mapping ledger/704-frame
allocator. Native ownership, permissions, context attachments, references,
quarantine and last-release reclamation belong to that shared mechanism.
Darwin owns image layout, chained fixups, startup vectors and finite ABI policy.
Keep all existing finite low-address profiles unchanged.

## Scope and address layout

A separate explicit mapper profile initially binds only `_write`, `_exit` and
`___error`, all real typed operations with private RX capsules. It must refuse
other imports before creating a native VM, even when another existing low-VA
adapter implements them. Do not reuse that adapter's hardcoded low-address
errno, pointer translation, allocator arena or capsules. Original jq remains
unavailable at `__DefaultRuneLocale`; no Apple dependency is pretended loaded.

Preserve preferred image VAs in the validated4GiB..4GiB+2MiB window. Honor
PAGEZERO by installing no user mapping below4GiB. Put four stack pages at
`0x110000000`, private errno at `0x110004000`, argv/envp/apple at
`0x110005000`, an owned return/exit stub at `0x130000000` and typed import
capsules at `0x130001000`. DATA_CONST is populated/fixed up before being sealed
read-only, then execution attaches. BSS is explicitly zeroed even when segment
file padding is nonzero. Existing native RO/RW/RX permissions forbid RWX.

## Caller-owned launch state

Use a bounded trusted supervisor-owned launch state, not per-activation bump
allocations or guest allocation headers. It contains the3840-byte image plan,
an aligned native768-byte context, a4KiB population/service bounce buffer and
a second4KiB plan-verification buffer. Caller provenance is required; numeric
bounds alone do not authorize arbitrary kernel pointers. Raw mapper helpers
remain excluded from the dynamic registry.

Preparation records a source change-detection digest alongside the plan. This
is not authentication or cryptographic provenance. Before native object
creation, regenerate/compare the entire plan, recheck source bytes and run full
chain/import preflight against this profile's finite APIs. Original unknown
imports refuse without native-object allocation or hidden retained state.
Recheck the source digest after population/fixups and before entry; an injected
setup-time source change must fail and release the owned VM. Caller source and
plan remain immutable throughout a real launch.

Copy validated source chunks through the owned bounce before calling native
populate; do not widen the native buffer bounds to admit loader payloads at
`0x11000000`. Startup inputs are validated/copied into private high-address
guest memory. Never copy caller kernel pointers into guest argv/environment.

## Execution and service bridge

The syscall hook only requests native suspension. Once at kernel root with no
active user context, validate/copy through native checked binding copy-in/out
services. Do not walk another component's mapping ledger or use its forensic
physical-frame query for guest I/O. Service the saved native context, preserving
genuine Darwin carry/positive-errno raw syscall results and C ABI wrappers'
private errno behavior. Resume through the counted native binding with the
remaining actual guest IRQ budget. A separate bounded service-call count must
not silently reset that budget.

Borrow explicit live native memory and serial grants. Serial revocation can be
reported as EACCES by a subsequent stopped service. Memory revocation prevents
new native entry, so this profile terminates/refuses further resume and performs
unconditional cleanup; it does not promise continued guest execution or CPU
unmapping at the instant a grant is revoked. No declarative SCI capability
ordinal translation or isolated personality process is claimed.

Create one native object and attach one context. Release the constructor once
attached; the binding keeps the mapping alive. Terminal return, fault, deadline
or refused service releases the binding, invalidates its context and lets the
native object reclaim mappings on the last reference. Failed setup releases
its constructor. Native quarantine retains ownership rather than claiming
success or freeing uncertain pages. Preserve native errors honestly.

## Required actual evidence

Use a genuine modern17-command, five-segment Mach-O fixture with real chained
imports/rebases at high addresses. Prove high-VA code entry, RW data, copied
argc/argv/envp/apple, owned return and typed write/exit/private errno. BSS must be
zero despite nonzero file padding. Verify DATA_CONST fixed pointers then write
fault, TEXT/LINKEDIT write faults, DATA/stack execution faults and direct
PAGEZERO/old-low-window faults. Test valid high pointers, crossing/bad pointers,
missing/wrong/revoked grants, actual IRQ deadline and bounded unknown syscalls.

Force failures at mapping/population/fixup/protect/attach stages in scoped test
source, without changing production semantics. Assert exact cleanup and source/
plan immutability, native owner/ref/domain counts, backing frames, heap cursor,
capabilities and ambient descriptors over at least21 cycles. Verify altered
source/plan and unknown imports refuse before native object allocation; retain
original jq's actual-38 result. A fixture is not upstream app coverage. Keep
this adapter separate from the default personality dispatcher until its finite
profile is explicitly selected. It remains kernel-linked trusted policy over
native ownership, not a separately isolated personality service.

## Actual checkpoint

`scripts/check-darwin-mapped.py` freezes committed dependencies plus explicit
mapper/fixture overrides. `/workspace/dmapped-final2/report.json` passes318 actual
CPL3 entries,21 measured cycles and147 forced setup refusals using frozen
Inauguration0.9.325. Entry cases include normal return, typed exit, seven
PAGEZERO/low/RO/NX faults with exact CPU page-fault error codes, actual IRQ
deadline, UD2, raw Darwin unknown-call carry/errno and a crossing high pointer.
The fixture checks high argc/argv/envp/apple data, fixed GOT/rebase values and
zeroed BSS despite nonzero file padding. Source bytes and the launch plan remain
unchanged outside explicit trusted mutation controls.

Snapshot-only hooks inject map/populate/fixup/startup/seal/attach refusals and a
source change during setup. Genuine native reference-decrement refusal retains
the binding; genuine corrupted PDE finalization retires the binding while
retaining its VM. Both recover through public native ownership projections after
the trusted fixture repairs the invariant. Production contains no injection
hooks. Exact frames, bump cursor, domains, capabilities and an ambient open
descriptor remain stable after warmup.

Missing/wrong grants, altered plans/source and malformed startup refuse before
native creation. Serial/Memory revocation occurs in a real stopped guest call.
An actually loaded bounded SCI importing the raw mapper is refused before any
lifecycle allocation. The original pinned macOS jq remains-38 before VM creation
at `__DefaultRuneLocale`, with zero application entries. A `_close` control
accepted by the older finite import provider still refuses this profile before
VM creation. This checkpoint is not original macOS application coverage.

Earlier complete versions also pass default/lean/harden profiles at
`/workspace/dmapped-{final,lean,harden}/report.json`; the final default receipt
adds exact hardware fault codes, startup string contents and launch-plan
immutability checks without production mapper changes. Earlier232-entry and
318-entry intermediate receipts remain separate.

The minimal root initially exposed an undeclared dependency on the old protected
Darwin provider, which the full personality hub had supplied implicitly. The
mapper now imports that dependency explicitly. The corrected minimal-root gate
passes the same318 entries/147 setup refusals at
`/workspace/dmapped-minimal2/report.json`; the compile-only failure remains at
`/workspace/dmapped-minimal/report.json`. This test adds the finite mapper to a
minimal test root; the shipped minimal image still has no personality import.
