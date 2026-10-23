# Native owned address spaces

`components/user-address-space.in` owns native mapping backing and execution
references. `components/domain.in` enforces its page tables and exact owner;
`components/user-context.in` owns CPU state and typed stops. The manager contains
no foreign syscall, executable format, PID, brk or mmap policy. It is currently
kernel-linked supervisor code, not an isolated SCI service. Linux migration,
Darwin migration and vfork are subsequent acceptance gates.

The pool holds sixteen spaces, thirty-two execution bindings and up to 4,096
owned 4 KiB pages per space. Handles combine a pool slot with a monotonically
increasing generation; neither a domain number nor a ledger pointer is a handle.
The native permission states are read-only (1), read/write (2) and read/execute
(3), with no writable executable state. Low mappings below 64 KiB and addresses
outside the lower canonical half are refused. High addresses above 4 GiB are
permitted. Supervisor IDT, kernel-stack and trampoline mappings are reserved
before accepting user mappings.

## Ownership and admission

Create returns one constructor reference. Each attached CPU context adds a
counted execution reference. A cloned binding shares the existing domain and
backing but owns a distinct CPU context; `copy-into` instead creates distinct
backing in an empty destination. Populate is available only before the first
attachment. Ordinary stopped writes require read/write mappings. Protect and
unmap revoke saved bindings whose RIP, stack or TLS admission becomes invalid.

New mappings, bindings, copies and execution require the exact original live
memory capability index and target identity. Metadata and destructive release
remain available to that original owner after revocation. Foreign capability
indices do not gain access merely because they name the same target.

Mappings and references may change only with the kernel page-table root active,
domain zero current, and no active native CPU context or guest budget. One
mutation lease per object prevents reentrant changes. This is a single-CPU
contract; it does not establish SMP synchronization. Resume and binding-clone
also check that the context's current domain still equals the object's domain.
Reinitializing a context for a different object cannot redirect an old binding.
Releasing that old binding preserves the unrelated new context.

Cold construction preflights the exact 1,576,960-byte retained metadata pool,
rounded remaining bump capacity, at least sixty-four available frames, actual
domain capacity and generation capacity before allocating. Free-list frames can
fund frame allocations but cannot fund the bump-allocated metadata cache. A
failed cold capacity check leaves the cache and allocator unchanged. Metadata
storage remains cached after successful initialization; repeated resource checks
measure stability against that explicit initialized baseline.

## Supervisor API

Every interface below is private to trusted supervisors. `user-space-*` and
`domain-user-object-*` are excluded from the guest SCI symbol registry.

| Operation | Result and contract |
| --- | --- |
| `create(authority, pageLimit)` | Positive space handle; constructor reference owns a private domain |
| `map-zero(space, authority, address, permission)` | One aligned zero-filled owned page |
| `populate(space, authority, address, source, count)` | Complete checked staging write before first attachment |
| `write(space, authority, address, source, count)` | Complete checked stopped write to read/write pages |
| `protect` / `unmap` | One aligned owned page; revoke before freeing backing |
| `copy-into(destination, source, authority)` | Empty unsealed destination, independent copied frames and permissions |
| `attach(space, authority, context)` | Positive binding; valid fresh or genuinely suspended context |
| `clone-binding(binding, authority, target, bytes)` | Genuine suspended source, separate target context, same backing |
| `resume(binding, authority, ticks)` | Native Exit/Fault/Deadline/Suspend, with native admission checks |
| `release-binding(binding, authority)` | Invalidate associated CPU image before dropping its execution reference |
| `release(space, authority)` | Drop the constructor reference exactly once |
| `recover(space, authority)` | Destructively reclaim a repaired quarantined object with no references |
| `refs` / `pages` / `domain` / `phase` / `frame` | Owner-only metadata, including after authority revocation |
| `binding-phase(binding, authority)` | 1 live, 2 revoked, or -6 retired/stale; authoritative detach-commit projection |
| `constructor-owned(space, authority)` | 0 or 1; authoritative constructor-release projection |
| `quarantined(authority)` | Discover the first retained constructor failure for explicit cleanup |

Names in this table omit the `user-space-` prefix. Native errors are -1 invalid
request, -2 authority, -3 capacity, -4 busy or wrong execution phase, -5 retained
invariant failure/quarantine and -6 stale or revoked binding. They are not POSIX
errno values. The consumer translates them at its personality boundary.

## Checked guest-buffer copies

`user-space-copy-in(binding, authority, guest, kernelOutput, count)` and
`user-space-copy-out(binding, authority, guest, kernelSource, count)` validate the
complete span before copying any byte. A copy is bounded to 65,536 bytes and
checks ledger ownership against actual physical PTE backing and effective
permissions for every covered page. No raw physical pointer escapes the copy.
`frame` is metadata for diagnostics and cleanup, not a validated I/O translation.

The caller supplies a provenance-validated private kernel buffer. The defensive
numeric check against `heap-next` prevents arithmetic overflow; it does not
prove allocation ownership. A loader whose admitted payload is outside that
arena copies through its own bounded owned buffer. The manager never parses a
foreign image or broadens the heap to admit an arbitrary payload pointer.

At a real syscall trap, copies additionally require the exact currently resumed
binding, context, domain, generation, live grant and kernel CR3. This is a
separate service seam; it does not relax stopped mapping and lifetime mutation.
A supervisor can instead suspend first, service the saved context and resume.
An internal pin blocks map, protect, unmap, write, attachment, release, copy and
resume until the copy ends. Private `borrow-begin` / `borrow-end` helpers expose
that scoped guard for owning-function tests; they expose no physical pointer or
external loan token. Ending the guard remains possible after grant revocation.

If an active copy detects an ownership invariant failure it records a pending
failure; its trusted handler must stop rather than resume the guest. Once CPU
entry returns, the manager quarantines the object. It does not invalidate a
capturing active CPU image or invent a hardware fault vector.

## Final release and recovery

Direct `domain-destroy-user` refuses an object-owned domain before walking or
changing its page tables. The final-release helper requires the exact domain
owner and zero execution attachments, and grants a private IRQ-scoped permit.
Legacy unowned domain teardown retains its existing behavior. Ownership is
cleared only after successful teardown.

Last release validates every owned PTE, revokes the page-table tree, then frees
backing frames and retires the object. An uncertain teardown retains its domain,
ledger, backing, generation and opaque handle in quarantine. It invalidates only
CPU images still associated with that object and permits no entry or mapping
mutation. Release may drop remaining references while returning -5; it does not
report uncertain frames as reclaimed. Recovery requires zero references and
explicit invariant repair, then performs destructive teardown. It never resumes
the quarantined program.

Release errors do not imply rollback. After `release-binding` returns -5, query
`binding-phase`: a present revoked binding still owns its reference and can be
retried after repair; -6 means detach committed and only the space may remain
quarantined. Use `refs`, `phase` and `recover` on that retained space handle.
Similarly, `constructor-owned` distinguishes a committed constructor drop from
a precondition failure. Consumers must not inspect private binding rows or
blindly repeat a committed release. These projections retain original-owner
access after grant revocation and do not authorize new execution.

A constructor claim-provider failure similarly retains a quarantined object
and returns -5. The original owner discovers it with `quarantined`, repairs the
exact domain owner association, drops its constructor reference and invokes
recovery. No unreturned owner handle is silently abandoned. This recovery is a
trusted supervisor operation, not a guest-authorized page-table repair API.

## Verification boundary

The dedicated gate is `scripts/check-user-space.py`, with source snapshots,
compiler hash, private SCI denial, actual CPL3 accounting and repeated allocator,
domain and capability witnesses. It exercises shared bytes with independent
GP/FX state, private-copy isolation, real protection faults and IRQ deadlines,
generation/authority/capacity refusal, retained quarantine and recovery,
checked active copies, held pins and foreign-context reinitialization.
The .325 source compiler
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`
passed the complete eight-category corpus on both roots, each with one warmup
and ten measured cycles: 143 actual CPL3 entries, 33 genuine page faults and
eleven genuine IRQ deadlines per root. Receipts are
`/workspace/us-standard-release-final/report.json` and
`/workspace/us-minimal-release-final/report.json`. These include the public
release-commit projections and consumer-style failure/retry proofs. Cold allocation refusal/recovery runs
before first cache initialization in each receipt. Private SCI import refusal
precedes object creation. Repeated allocation/domain/capability witnesses remain
stable after warmup.

`/tmp/space-user-space-claim-first/report.json` separately records an explicit
snapshot-only claim-provider refusal, its exact source delta and original /
compiled hashes. The control proves retained construction failure, opaque-handle
discovery, closed admission, failed premature recovery, explicit owner repair
and reclamation. It claims zero CPL3 entries and is not unchanged-production
coverage. No original application or vfork success follows merely from this
native-only corpus.

The unchanged native CPU continuation corpus also passes 62 actual entries in
`/workspace/us-core-regression/report.json` after the domain ownership guard.
It retains genuine cloned continuations, GP/FX/TLS state, actual fault/deadline
and remaining-IRQ checks, cold MXCSR admission and supervisor restoration.
The existing complete twenty-three-case Linux child corpus also passes warmup
plus one measured cycle, 46 root launches, in
`/workspace/us-legacy-children/report.json`. This checks legacy unowned-domain
semantics; it does not migrate that personality to the new object.
