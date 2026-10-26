# Linux migration acceptance fixture

This is an additive ordinary static Linux ELF corpus. It preserves the completed
23-child, 14-blocking and all BusyBox case arrays. No vfork success is enabled.

`migration.asm` has a real host oracle: exit42, empty stdout and stderr. It grows,
shrinks and regrows brk; checks preserved first-page data and zeroed regrowth;
creates three anonymous pages; transfers sixteen bytes across a page boundary
through an actual pipe; checks a read-only destination gives EFAULT without
consuming the pipe; restores protection; copies a real child; changes and unmaps
child anonymous memory while the parent retains its own bytes; checks failed
exec vector validation preserves memory and descriptors; and rechecks zeroed
new mappings. The program contains no Space imports or native pointers.

The trusted supervisor wrapper supplies an unrelated owned stream carrying
`VM-OWNER`. Every warmup/measured activation must leave it intact and restore
CPU scope. Measured cycles require exact stable heap, free-list, domain,
capability and native descriptor witnesses. Counts describe root activations,
not uncounted descendant CPU slices.

The migration's native seams must use the public Linux VM companion and native
binding projections. Direct helper setup creates/maps/populates/attaches a real
object before guest-buffer I/O. No native private ledger or physical-address
helper may be used to transfer guest bytes. Resource- and pointer-denial tests
remain unchanged; their fixture construction must adapt to the owned object.

Additional trusted acceptance checks exercised by this migration:

- Save deliberately stale process projections, reload the companion, and prove
  sole current brk/mapped/native-page state wins; save cannot mutate it.
- Fail a valid exec after a new stage exists; release only staging ownership,
  retain the original binding/pages/FD flags and return the actual error.
- Force native reference refusal, distinguish retained binding from committed
  detach using public projections, repair, retry and recover exactly once.
- Retain both original and prepared exec objects on teardown refusal, without
  fabricated context MAGIC or independently authored backing ledgers.
- Exercise cold native constructor claim refusal in an explicitly recorded
  private provider-control snapshot; a failed create cannot abandon its native
  quarantine because no Linux companion was published.

Production remains in migration until all existing real application and
synthetic regression gates pass on both roots. This fixture alone cannot claim
Linux migration, shared-VM/vfork support, arbitrary exec, or all-app coverage.

The final phase-2 copied-process and original-application regressions now pass
on both roots. Exact source freezes, counts and receipts are recorded in
`docs/linux-owned-vm.md`. This is a handoff for review before vfork is enabled;
the original case arrays and their negative assertions remain intact. The
direct fixture uses a separate stack page so data-protection checks do not
accidentally revoke its control context.

The initial production migration smoke passed in
`/tmp/space-linux-vm-space-first/report.json` (two actual root launches). The
expanded companion/association proof passed in
`/tmp/space-linux-vm-association-first/report.json`. It deliberately poisons old
global and process-record page/domain/brk/ledger projections, then proves
state-save/load obtain the sole current native/companion state. `vm-use` and
`vm-drop` reject another live binding without changing either object's
references, constructors or the currently selected process view. Native public
queries retain exact-owner metadata access after grant revocation and reject
foreign or retired tokens.

`--stage-capacity` selects a separate bounded-capacity contract, not a replacement
for the default host-equivalent copied-memory probe. A genuine independent
native object retains 31 valid fresh execution bindings. The Linux root occupies
the final binding slot. Actual self-exec builds the new ELF and stack, then native
attachment refuses capacity. The real Linux request resumes with ENOMEM (-12),
and the old guest verifies unchanged data, FD_CLOEXEC flags and queued pipe bytes
before exit42. The same ordinary ELF genuinely self-execs and exits77 on the
host. No source injection or fabricated provider failure is needed. The initial
control passed `/tmp/space-linux-vm-exec-capacity-first/report.json`; the cached
unbound failed-stage context is invalidated and both stage and root resources
are reclaimed while the 31 witness bindings survive until explicit release.

Both profiles now also run an actual native data-PTE alias proof before their
regular root launches. A supervisor corrupts a stopped owned data PTE to name
another owned page, preserving valid entry/stack control mappings. A real CPL3
write syscall must detect native ownership inconsistency, copy zero bytes and
stop before the next guest instruction's marker store. The native captured stop
is Suspend (4), the Linux pending operation is invariant cancellation (7), and
the edge cause is -5; no CPU Fault vector is invented. Both actual entries retain
quarantine and reject a new job until explicit PTE repair/recovery. The first
receipt is `/tmp/space-linux-vm-invariant-first/report.json`. Reports count these
two additional direct native entries separately from ordinary root activations.

Adapted direct fixtures preserve their negative assertions while creating real
native objects/contexts through `direct.in`. Their grant belongs to the original
revocable capability index throughout. Failed-copy canaries are inspected after
the owner restores that grant, rather than bypassing checked guest-memory access.
The prepared-exec cleanup proof now retains real native objects and bindings,
corrupts actual PTEs, and consults public release projections; it never constructs
an independent physical ledger or fabricates context MAGIC.

`--constructor-control` is a separate explicit provider-failure profile. It
compiles a private snapshot whose native domain-claim provider refuses one
armed call, recording its exact unified source delta and original/compiled
hashes. Actual Linux launch returns -5 before guest entry but retains the
native quarantine handle in a companion and process record. Early cleanup
cannot discard it; subsequent launch is closed. After exact owner repair,
trusted recovery retires both identities and restores warmed frame/domain
witnesses. Both roots pass in `/workspace/vm3-constructor-{standard,minimal}`.
These controls claim zero guest entries, do not run the regular mutation corpus,
and do not add a production hook or passing upstream-application coverage.

The final vm3 default and stage-capacity gates also include `startup.asm` and
`startup.in`: actual argc/argv/env checks using immutable raw source addresses
above the heap arena, plus refused scalar/string startup copies. Each gate
counts 22 main-profile root calls, one startup root call and two direct native
invariant entries separately. `checks.in` cross-pairs real process-row tokens
and proves state-save/load refusal without selection changes, then actual family
runner refusal with zero syscall-hook entries and exact IF0/IF1 restoration.
Neither control invents a native execution or discards uncertain ownership.
