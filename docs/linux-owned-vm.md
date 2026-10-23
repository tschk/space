# Linux ownership through native VM objects

The Linux personality now uses the reviewed native `UserAddressSpace` object
for ELF, stack, brk and anonymous mappings, copied children and exec staging.
`components/linux-process-vm.in` owns Linux VM policy; the native manager owns
backing, page tables, execution references and final revocation. Both remain
kernel-linked supervisor components. This change does not establish an isolated
SCI service, shared Linux VM execution or vfork.

The Linux companion is keyed by the native generation-bearing space handle.
It holds the sole current break and mapped-break extent. Process records store
that token and a distinct native execution-binding token. Legacy page/domain/
brk fields are projections; saving a record reloads authoritative state and
cannot write stale process-local counters into the companion. The old physical
backing ledgers are no longer allocated or walked. A trusted negative test
deliberately corrupts the old projections and confirms the current object wins.
State selection validates the native pair before changing any process globals.
Every scheduler/service caller propagates selection and save failures; uncertain
rows retain their ownership in quarantine. The outer family runner always
restores the caller interrupt policy, including early failures. Both selecting
and dropping a companion compare the native `binding-space`
projection first, so cross-paired tokens under the same grant cannot select or
release another object's execution reference.

ELF admission still validates its complete source extent and segment layout.
The loader copies each page through its own bounded 4 KiB kernel buffer before
native population. After mapping code and stack, it initializes and attaches a
genuine fresh native context before constructing guest startup bytes through
checked copies. No helper returns a physical address for guest-buffer I/O.
Trusted startup strings above the heap arena are copied bytewise through that
owned buffer. All vector/scalar setup copies propagate their first error, so
failed construction cannot enter with unwritten argc/argv/env bytes. An ordinary
ELF checks raw sources at 0x13000000/0x14000000 while heap-end is 0x10000000.
Direct negative fixtures likewise create and attach real objects. Their stack
is separate from the data page targeted by protection tests.

## Stopped mutations and checked service

Actual mmap, mprotect, munmap and brk requests capture native Suspend with the
original syscall frame and pending operation 6. The scheduler services them
only after kernel CR3 and the stopped-context invariant have been restored.
It carries the native remaining IRQ quantum and existing preparation/work
limits across the stop. VM mutation never runs inside an active syscall hook.
Other syscall services use the native checked copy/borrow interface against
the exact current binding and original live memory grant. File, pipe and serial
transfers copy bounded chunks; VFS receives private kernel buffers.

Native ownership inconsistency is distinct from a guest pointer error. A native
-5 latches activation failure and forces actual suspension before another guest
instruction. The native wrapper quarantines after capturing CPU state. The Linux
edge reports owned invariant cancellation -5, with pending operation 7; it does
not invent a hardware Fault or Deadline. An actual PTE-alias test proves zero
published bytes, an unchanged post-syscall marker, retained quarantine, closed
subsequent admission and exact recovery after explicit repair.

## Copy, exec and release

Ordinary fork creates another native object and copies backing and permissions
through `user-space-copy-into`. It then genuinely clones the suspended CPU image
into that domain and attaches a new native binding. File descriptions and pipe
references retain their existing sharing semantics. Mutable user memory and
Linux VM state remain independent. Partial descriptor-copy failures release
only actually acquired ownership, retaining the parent and its contents.

Exec prepares another companion, mappings and fresh context before dropping the
old binding/object. A failed preparation reclaims only staging. Successful commit
preserves PID and inherited descriptors, applies CLOEXEC only to the replaced
process, and selects the new companion. Primary and prepared ownership have
separate tokens in the process record. Failed final revocation retains those
identities; release projections distinguish a retained binding from an already
committed detach. Cleanup never retries an already retired token blindly or
marks uncertain ownership free. An unbound context whose attachment fails is
invalidated before its stage is destroyed.

A real capacity test fills the native binding pool with 31 independent witness
bindings plus the Linux root. Actual exec maps its replacement ELF and stack,
then fails attachment with ENOMEM. The old guest resumes and verifies data,
CLOEXEC flags and queued pipe bytes. The same ELF genuinely self-execs and exits
77 on the host; the declared bounded Space control verifies ENOMEM and exits42.
This is a resource-profile control, not identical Linux-host success coverage.

Constructor claim-provider failure also retains its native handle in a Linux
companion and process row. A separate explicit snapshot-only provider control
proves failed early recovery, closed launch admission, exact owner repair and
reclamation. It records the precise provider source delta and hashes, claims zero
CPL3 entries, and adds no production fault-injection hook. Existing unrelated
native quarantine under the same grant blocks creation rather than being adopted
through first-quarantine discovery.

## Final .325 evidence

The source compiler is
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`.
Production was frozen at `/workspace/vm3-src`, with `freeze-receipt.json` recording
the base commit, live status and all source hashes. Every gate then compiled its
own immutable snapshot. All Linux production bytes match that freeze. The
constructor control records its explicit private provider modification separately.
The cross-paired process-row control proves zero native hook entries, unchanged
fresh contexts/references, and exact caller IF restoration for both IF0 and IF1.
High-source startup and refused string/scalar-copy controls run in each ordinary
and stage-capacity gate; no extra CLI option is required.

Each path below ends in `/report.json`; `*` is `standard` and `minimal`.

| Gate | Receipt directory | Actual count per root |
| --- | --- | ---: |
| Original 23 child cases | `/workspace/vm3-children-*` | 506 root launches |
| Original 14 blocking cases | `/workspace/vm3-blocking-*` | 308 root launches |
| Native pipe ABI | `/workspace/vm3-pipes-*` | 110 synthetic plus 2 upstream launches |
| Native object regression | `/workspace/vm3-native-*` | 143 CPL3 entries |
| Native CPU continuation | `/workspace/vm3-core` | 62 entries, one root profile |
| New copied-VM/brk/I/O probe | `/workspace/vm3-object-*` | 23 root launches plus 2 direct invariant entries |
| Genuine exec capacity control | `/workspace/vm3-stage-*` | 23 root launches plus 2 direct invariant entries |
| Unmodified jq 1.8.1 | `/workspace/vm3-jq-*` | 81 application launches |
| Unmodified Lua 5.4.7 | `/workspace/vm3-lua-*` | 222 application launches |
| Unmodified SQLite 3.46.1 RAM | `/workspace/vm3-sqlite-*` | 146 application launches |
| Unmodified BusyBox original 12 | `/workspace/vm3-busybox-*` | 100 application launches |
| Unmodified BusyBox child 9 | `/workspace/vm3-busybox-child-*` | 53 application launches |
| Unmodified BusyBox blocking 12 | `/workspace/vm3-busybox-blocking-*` | 122 application launches |
| Constructor provider control | `/workspace/vm3-constructor-*` | Zero guest entries, explicit modified provider |

Each new object/stage gate includes 22 main-profile launches and one separate
ordinary high-source startup launch. Constructor controls add no app success.

All measured repeated suites retain 21 cycles after warmup; the native object
regression retains ten. Existing guest IRQ budgets and 4096-byte pipe rings are
unchanged. Both original 110,000-byte numbered-line copies retain SHA256
`1c7898d6f3630eeddf65917d04f0a07a421f1192d6a6acd122108b5fc747af57`.
The case arrays and pinned application ELF bytes were preserved.

`/workspace/vm3-nvme/report.json` additionally passes original SQLite transaction,
update, rollback, close and reopen across three QEMU processes, fifteen actual
application calls. Matched successful hardware FLUSH counts remain 8/4/0; raw
database extraction passes the host integrity/content oracle after each boot.
Volume RPC remains refused rather than reported as synchronous durability.

The pre-review `/workspace/vm2-*` passing receipts remain historical. Subsequent
review found atomic row-selection/propagation, caller-IF restoration and trusted
high-source startup gaps; the final vm3 freeze and reruns include those fixes.
The vm3 snapshot also includes the ordinary-boot RAM-only diagnostic guard.

The earlier `/workspace/linux-vm-jq-first` through `-fifth` failures are retained.
They found revoked memory being translated to EFAULT before its grant check,
the direct fixture using its protected data page as its saved stack, and a lazy
test-only 4 KiB staging allocation after the measured baseline. The grant error
ordering was fixed, the fixture received an independent stack, and the already
owned fixture page became its staging buffer. No negative assertion was removed.
`/workspace/linux-vm-jq-diagnostic` is an explicitly labeled line-identification
snapshot, not acceptance evidence.

## Remaining goal

Phase2 was reviewed and committed as d9d1db9. The following vfork-refusal
evidence describes that historical copied-process checkpoint. The new bounded
syscall58 slice is documented separately in [the vfork contract](linux-vfork.md);
shared-VM clone flags remain refused. The earlier upstream xargs probe
`/workspace/vm2-vfork-refusal/report.json` deliberately remains failed: echo
passes, real syscall58 returns -38, both xargs requests exit126 with the genuine
unsupported diagnostic. Its separate reproducible ELF and private manifest
override are recorded in `/workspace/vm2-vfork-control-src`; this is not passing
vfork coverage.

Next acceptance requires a genuinely shared native object and Linux companion,
an explicitly blocked vfork parent, exec detach/failure continuation, typed child
termination, last-reference quarantine and the original upstream xargs success
and failed-exec cases. General threads, installed arbitrary signal handlers,
arbitrary executable lookup and unrestricted applications remain outside the
current bounded profile. The overall application and desktop goal stays open.
