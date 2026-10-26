# Native owned address spaces and bounded Linux vfork

Status: native owned-address-space mechanism and Linux copied-process migration
are committed. Bounded syscall58 shared-VM vfork is implemented with actual
upstream and ownership proofs, awaiting review; see [the vfork contract](../linux-vfork.md).
The migration evidence is in [the Linux contract](../linux-owned-vm.md).
The mechanism's current
API and proof boundaries are documented in [the native contract](../user-address-space.md).
The completed copied-fork/blocking-pipe corpus remains unchanged. This follows
the component/capability/object/execution graph in `AGENTS.md`, `architecture.md`
and `sci-schema.md`: native mechanisms own memory and execution lifetimes;
Linux owns its foreign flags, PIDs, waiting, signals, brk and mmap policy.

## Actual upstream next case

The completed BusyBox ELF has SHA256
`f8ffdbe7aba9e92515a65e0262d454b3a3bfffc9278823d327378b018e9ee032`.
Its ash uses `fork()` and its configuration disables xargs and timeout. Merely
finding a linked vfork symbol does not establish a reachable upstream test.

A separate planning profile builds official unmodified BusyBox 1.36.1 with the
existing static profile plus `CONFIG_XARGS=y` and
`CONFIG_FEATURE_PREFER_APPLETS=y`. It does not replace the completed ELF or its
manifest. Provenance is `/workspace/busybox-vfork-plan-build/report.json`:

| Item | Observed value |
| --- | --- |
| Official archive | `https://busybox.net/downloads/busybox-1.36.1.tar.bz2` |
| Archive SHA256 | `b8cc24c9574d809e7279c3be349795c5d5ceb6fdf19ca709f80cde50e47de314` |
| Source comparison | 752 archived C/header/assembly files checked, none modified |
| Resolved config SHA256 | `f77147bac0c405bac26c70fa6cd884065009f0190dc91b258ccc28d8f3457bcc` |
| Separate static ELF | `/workspace/busybox-vfork-plan-build/busybox`, 1,172,176 bytes |
| ELF SHA256 | `b1c758ba922f7c06a741f3d5e77a2d6ef6baba226bda04c56385244f457ab727` |

Reproduce by extracting the pinned archive, running `make allnoconfig`, applying
the completed manifest's `build.kconfig` plus the two selections above, running
`make oldconfig`, then `make -j4 V=1`. Use `SOURCE_DATE_EPOCH=0`,
`KCONFIG_NOTIMESTAMP=1`, `LC_ALL=C`, `TZ=UTC` and the compiler/linker recorded in
that receipt. The resolved config, build log, license hash and commands are
retained. A second clean build and a separate reviewable manifest/builder are
required before promoting this planning profile into the application corpus.
The second clean build is now recorded in
`/workspace/busybox-vfork-clean2/report.json`: the ELF and resolved-config hashes
match the first build, all 752 archived C/header/assembly files remain unchanged,
and all three host controls pass. The separate manifests are
`fixtures/applications/busybox-1.36.1-vfork.json` and
`fixtures/applications/busybox-1.36.1-vfork-cases.json`. Reproduce with
`scripts/build-busybox-corpus.py --out <new-directory> --manifest
fixtures/applications/busybox-1.36.1-vfork.json --case-config
fixtures/applications/busybox-1.36.1-vfork-cases.json`. These are host provenance
controls; Space vfork acceptance remains failed and is not counted as coverage.

The exact root argv is `["/xargs", "-r", "ash"]`; stdin is the literal line
`-c printf${IFS}vfork\n`. Both host and Space use `LC_ALL=C`, `HOME=/`, cwd `/`.
The host exits 0 with stdout `vfork` and empty stderr.
`/workspace/busybox-vfork-plan-build/host.strace` observes the actual sequence:

1. Upstream xargs calls `spawn_and_wait()` and `spawn()`.
2. libc executes syscall 58, `vfork()`.
3. The child executes `/proc/self/exe` with
   `["ash", "-c", "printf${IFS}vfork"]` through upstream `BB_EXECVP`.
4. The parent returns from vfork, then waits for that real child.

The Space acceptance attempt is deliberately **failed** in
`/workspace/linux-busybox-vfork-before2/report.json`. Its ordinary echo control
passes; the xargs case executes real syscall 58, receives -38, emits
`xargs: ash: Function not implemented\n`, and exits 126 through actual
`exit_group(231)`. That application exit is distinct from the scheduler's typed
policy cancellation -7/status 126. No vfork, IRQ or quota success is claimed.
The private control tree changes only the planning-profile manifest/config;
the production runtime and completed application manifest are unchanged.

A host failed-exec control is retained in
`/workspace/busybox-vfork-plan-build/host-exec-failure.json`: argv
`["/xargs", "-r", "space-vfork-missing-command"]`, stdin `x\n`, exit 127,
and the genuine ENOENT diagnostic. Upstream `spawn()` writes its volatile
`failed` word on the shared parent stack before `_exit(111)`. This supplies a
useful real-application failure path alongside direct shared-memory proofs.

## Native object contract

Introduce a runtime-owned `UserAddressSpace` object, provisionally in
`components/user-address-space.in`. The domain module continues to own page-table
enforcement; native CPU contexts continue to own GP/IRET/FX/FS/GS and typed stops.
The address-space manager owns mappings, backing and reference lifetime. It has
no Linux syscall numbers, ELF flags, brk, PIDs, wait statuses or vfork policy.
Initial kernel linkage is boot scaffolding, not proof of an isolated SCI service.

Use a bounded pool, initially sixteen address spaces and thirty-two execution
bindings, with at most 4,096 owned 4 KiB mappings per space. Preflight actual
domain/frame availability as well as those limits. A handle identifies a slot
and monotonic generation; a domain slot or raw ledger address is not a handle.
Raw helpers must remain absent from the guest SCI registry. Future isolated
service binding must use the existing capability/channel contracts.

Each object owns its domain, backing ledger, page count, permission metadata,
generation, phase, mutation lease and live execution-binding references. An
execution binding associates a distinct owned native context with that object
and generation. Creating a second binding retains the object; it does not copy
a ledger or allocate a second set of backing pages. Zombies retain PID/status
metadata after dropping their execution binding, without pinning the whole VM.

The proposed kernel/supervisor-only operations are conceptual contracts, not
already exported APIs:

| Operation | Required behavior |
| --- | --- |
| Create | Validate authority and quotas; own a fresh private domain and empty ledger |
| Attach / retain | Validate live handle/generation and owned context; issue one counted binding |
| Copy | Copy current owned mappings/protections into a separately owned object for ordinary fork |
| Map / protect / unmap | Validate an exclusive mutation lease and complete range; update actual PTEs and the sole ledger |
| Populate | Copy a validated loader-owned byte slice into a stopped staging space, without foreign image parsing |
| Resolve / resume | Validate the binding, current object generation and execution admission before using its domain |
| Detach / release | Invalidate that execution binding; destroy backing only on the last reference |
| Recover | Reclaim a quarantined object only after explicit invariant repair; never resume an uncertain context |

Permissions are native read-only, read/write or read/execute states; reject
writable executable pages. Initial mapping ownership is exclusive backing;
arbitrary shared-page loans require a separate explicit backing-object contract.
Foreign PF/MAP/PROT constants are translated by their personality.

All contexts sharing a space must be stopped before a mapping mutation. Route
Linux VM mutations through a captured pending operation when necessary instead
of weakening native context admission. A single mutation lease prevents
reentrant changes; do not claim SMP safety from the current single-CPU runtime.
No mapping may be revoked under an outstanding borrowed guest-memory operation.
Validate complete changes before publication; retain backing on any uncertain
partial failure rather than pretending the transaction was undone.

Domain ownership must prevent a legacy direct `domain-destroy-user` caller from
destroying an object-owned domain with live bindings. Only the final-release
path may authorize its revocation. Binding-generation validation must also
prevent a stale context/handle from entering a reused domain slot. Live authority
is checked before new bindings or mutations; explicit object/binding revocation
closes subsequent execution admission. Release remains possible after revocation.

## Shared mutable Linux VM state

Add a Linux-owned VM companion record, provisionally
`components/linux-process-vm.in`, keyed by the native handle and generation.
It owns the current break, mapped break extent, mmap placement/region policy and
other mutable Linux VM bookkeeping. It is shared by vfork-related processes and
copied for ordinary fork. The native manager must not acquire those concepts.

`LPS-VM-OBJECT` at offset 400 is currently reserved. Bind it to that companion
instead of aliasing the parent's cached ledger pointer. Domain/ledger/page-count
globals may temporarily be validated views, but cannot remain independent owners.
`state-save` must never write a stale process-local page count or brk back into a
shared object. All map/protect/unmap/brk operations resolve and update the sole
live VM state. Exec creates a new companion; it does not reset the parent's.

Test child-created mappings, changed break, protections and removed data mappings
through actual parent CPU accesses after resumption. A child can also invalidate
a parent's saved RIP/RSP/TLS mapping. Preserve strict native admission in that
case: mark a distinct binding/VM-revocation cause and translate it at the Linux
edge, without fabricating a hardware fault vector. Ordinary user access to an
unmapped data page must still produce a genuine CPU page fault.

## Bounded vfork execution policy

Initially admit syscall 58 and exact clone flags
`CLONE_VM | CLONE_VFORK | SIGCHLD` (0x4111) with a null replacement stack.
Other shared-VM/thread flags and non-null clone stacks remain explicit refusals;
posix_spawn's alternate-stack profile is a subsequent case. Preserve current
process/depth, thirty-two preparation, 4,096 work-unit and delivered-IRQ limits.

After a real suspended request, register a distinct child PID and execution
context, copy descriptor bindings/FD_CLOEXEC and signal disposition/mask state,
clear inherited pending signals and clear-tid state as appropriate, and retain
the same VM object/companion. The existing native context-clone contract permits
the same valid domain; its phase requirement must not be forged. Parent and child
share user stack/data/TLS memory but have independent GP/FX/context ownership.

The parent enters an explicit vfork-blocked state. It must not become runnable
merely because the child blocks on a pipe. A private waiter links parent to that
child's exec-detach or terminal event; ordinary wait4 remains a separate operation.
The parent receives the actual child PID once, without reaping it.

| Child event | Required result |
| --- | --- |
| Successful exec | Prepare a complete new space/context; commit child binding to it, drop old shared reference, then unblock parent |
| Ordinary exec failure | Release only the failed staging space; resume child with real errno in the unchanged shared VM; parent stays blocked |
| Exit, signal, actual fault or IRQ deadline | Invalidate/detach child context, drop its VM reference, preserve typed wait cause, then unblock parent |
| Pipe block with another runnable owner | Retain both contexts and run that owner; parent remains vfork-blocked |
| No runnable owner | Existing explicit edge deadlock 125 closes the whole owned job |
| Root cancellation or work quota | Existing typed cancellation closes every binding; never label it a hardware deadline |

Exec keeps PID, inherited descriptors and ignored signals according to the
existing contract. CLOEXEC closes only the replaced child's bindings. Parent
pages and shared Linux VM state must remain intact after child exec. Captured
remaining IRQ quantum is retained per process; blocked parent time is not
fabricated guest CPU time or an excuse to reset its budget.

## Last-release ordering and failure

Invalidate a departing execution context before dropping its binding. Non-last
release changes only actual ownership references. On last release, first validate
and revoke every mapping/page table, then free owned backing exactly once, clear
the object and retire its generation. Never free the parent ledger during child
exec or mark a record free while its object still owns uncertain backing.

If final revocation fails, retain the object/domain/ledger/pages in QUARANTINED
state, invalidate all affected execution bindings, and fail the activation closed.
Do not reuse its slot/generation or report resources reclaimed. A prepared exec
object that cannot be destroyed is retained separately from the old shared space;
the parent must not be resumed through an ownership ambiguity. Repair/recovery
is destructive cleanup of stopped objects, not speculative process continuation.
Ordinary failed exec with successful staging cleanup still resumes the child.

## Implementation and acceptance gates

1. Prove native object create/retain/copy/last-release on three compiler profiles
   and actual QEMU. Reject stale generations, wrong authority, foreign bindings,
   active mutation and capacity exhaustion before changing ownership. Distinct
   spaces remain hardware isolated; explicit same-object bindings share bytes.
2. Migrate existing Linux root launch, copied fork, mmap/brk/protect/unmap, exec
   staging and quarantine to the object contract. Keep old copied semantics and
   all current real-app/23-child/14-blocking/pipe tests passing before enabling vfork.
3. Run host/Space synthetic vfork ELFs proving shared global/stack/TLS writes,
   shared mapping metadata, actual parent blocking, stable distinct child PID,
   successful exec detach and failed exec continuation. Assert native domain and
   backing identity for the shared case and fresh identity after child exec.
4. Exercise child fault/deadline/SIGPIPE, blocked child deadlock, root cancellation,
   partial descriptor-copy failure and reference-capacity refusal. After a failed
   clone preparation, parent pages, offsets, descriptor flags and native pair
   contents must remain unchanged; no phantom child or retained reference.
5. Inject a real last-release teardown refusal in an owned object. Prove retained
   PTE/backing ownership, closed admission, no double free, explicit repair and
   exact stable free-list/domain/object recovery. Repeat with a prepared exec
   object while its old shared object still has the blocked parent reference.
6. Promote the reproducibly built separate xargs profile and run both real upstream
   commands above: success `vfork`/0 and genuine failed-exec diagnostic/127. Preserve
   the preimplementation -38/126 failure. Require actual vfork, self-exec and wait
   paths, shared stack failure propagation, original ELF hashes, pointer/capability
   negatives and resource recovery over warmup plus 21 cycles on both roots.
7. Rerun original jq/Lua/SQLite RAM, both BusyBox corpora, copied-child/blocking/
   pipe suites and original SQLite three-boot NVMe durability against the final
   migration snapshot. Counts describe actual root launches, not source admission
   or uncounted descendant CPU slices. Keep observer-only IRQ test source deltas
   separate from unchanged native production code and real application evidence.

Do not enable vfork by pointing two process records at copied counters or by
returning a successful PID without real execution. General CLONE_VM threads,
arbitrary executable lookup and a complete Linux process environment remain
separate goals after this bounded shared-address-space milestone.
