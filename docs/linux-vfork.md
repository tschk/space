# Bounded Linux vfork over native owned VM

The Linux personality implements syscall58 using one native owned address-space
object, its sole Linux VM companion and a separately counted child CPU binding.
This is kernel-linked supervisor policy, not an isolated SCI service or a native
Unix process manager. The copied-fork profile remains separate and unchanged.

The real syscall first captures native Suspend. The supervisor clones the saved
CPU image with `user-space-clone-binding`, sharing the exact generation-bearing
VM handle. The child has its own PID, descriptor table/flags, signal metadata and
remaining IRQ allowance. Native descriptor references retain shared offsets and
pipe endpoint state. The parent enters `LINUX-STATE-VFORK-WAIT`, associated with
the actual child PID. Ordinary IO wake and ready selection cannot run it.

The child shares mutable anonymous mappings, permissions and the companion's
brk state. Mapping operations still capture Suspend and run only under stopped
native mutation rules. Every guest-buffer transfer uses native checked copies
against the exact current binding and original live grant. No physical backing
ledger, private native object catalog, new CPU assembly or alternate buffer
translation is introduced.

Successful exec constructs another native VM/context first. Only after old
shared binding detach, replacement commit and process-state save does the
scheduler wake the parent. Failed path/vector/admission/preparation preserves
the shared child and keeps the parent blocked. Typed normal exit, fault, signal
or real IRQ Deadline closes the child's descriptors and detaches its CPU binding
before waking the parent. A failed detach closes admission and retains ownership;
it cannot fabricate successful parent continuation.

The constructor reference belongs to the object, not either process. Native
`constructor-owned` commits its release once. A committed process detach with
positive native peer refs succeeds while retaining the companion, including a
quarantine now owned by peer bindings. The final reference attempts native
revocation/recovery; uncertain final teardown retains the native handle and
companion. This distinction prevents an already-detached process row from being
stranded after a later peer reclaims the object. An uncommitted binding detach
continues to fail and retains that binding for repair.

The existing activation-wide32 preparation admissions and4096 work transitions
remain enforced. Every process carries its actual remaining guest IRQ allowance
across Suspend; the child inherits its parent's remaining allowance at creation.
This does not claim wall-clock accounting for kernel work. Deadlock125, policy126
and actual guest Deadline124 retain separate typed causes. Seven child
registrations per activation and depth below4 remain bounded; arbitrary shared
clone/thread/TLS/non-NULL-stack modes remain refused. Only explicit syscall58
adds this shared-VM policy.

## Acceptance evidence

The canonical source compiler remains .325, SHA256
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`.
`/workspace/vfork2-src/freeze-receipt.json` records the initial implementation;
`/workspace/vfork4-src/freeze-receipt.json` records the final shared-quarantine
committed-release fix, explicit constructor-release guard and counted-binding
publication rule. Each checker compiles its own snapshot.
The final handoff records exact production and receipt hashes.

`scripts/check-linux-vm.py --vfork` runs an ordinary host42/Space42 ELF. It checks
child changes to shared data, brk and anonymous mmap, failed ENOENT/EFAULT exec
with unchanged parent progress, genuine SIGILL wait status, and fresh exec data.
The replacement waits on a pipe byte only its resumed parent can send: a parent
that wakes only at child exit would deadlock. Both roots retain21 measured
cycles plus warmup,23 root calls including the existing independent high-source
startup, and two existing actual alias-invariant entries.

`--vfork-deadline` is a distinct declared resource profile. Its host child
intentionally loops; the host oracle records nontermination and kills the owned
process group. Space uses ten delivered guest IRQ ticks, captures actual native
Deadline, records remaining0/waitSIGKILL9, reclaims the child and resumes the
parent to exit42. This is not claimed as equal host/Space termination behavior.

Both new profiles also run trusted real-CPU ownership checks: genuine vfork
Suspend, shared clone binding, child exit, surviving parent exit, independent
binding tokens, exact native refs and one constructor release. Foreign/revoked
authority and readonly copy targets refuse without unblocking the parent.
Actual huge-PDE final teardown failure retains quarantine until explicit repair.
A second control forces native domain-reference decrement refusal while the
parent is blocked; neither binding is abandoned, launch stays closed, and
repair/recovery reclaims both process rows with stable resource witnesses.
A refused native binding creation publishes no child VM token: only the counted
source retains quarantine. Actual reference-add refusal proves source-only
ownership and stable repair/recovery, without an uncounted alias row.
These twelve direct CPU entries are counted separately from the root corpus.

Original application acceptance uses the separately reproducible upstream
BusyBox1.36.1 xargs profile from commit f90ec18, binary SHA256
`b1c758ba922f7c06a741f3d5e77a2d6ef6baba226bda04c56385244f457ab727`.
The existing completed BusyBox ELF/case arrays are not replaced. The generic
corpus runner's explicit `--manifest` records the selected profile bytes/hash.
After acceptance, only `coverage_goal` metadata in that manifest was updated;
the acceptance manifest hash remains recorded there and in each receipt.
Source/configuration/binary provenance and all three case arrays are unchanged.
The unchanged three cases compare actual host and Space output/exit: echo
control, xargs vfork+self-exec printing `vfork`, and missing-command exec with the
genuine diagnostic/127. Both roots repeat21 cycles with47 application launches.

Final receipt directories, each ending in `/report.json`:

| Gate | Standard and minimal directories | Counts per root |
| --- | --- | ---: |
| Shared ELF | `/workspace/vfork4-shared-*` | 23 roots +12 ownership +2 invariant entries |
| Deadline profile | `/workspace/vfork4-deadline-*` | 23 roots +12 ownership +2 invariant entries |
| Separate vfork FD/admission profile | `/workspace/vfork4-fd-*` | 44 roots, explicit subset |
| Original upstream xargs | `/workspace/vfork4-upstream-*` | 47 application launches |
| Copied child23 regression | `/workspace/vfork4-children-*` | 506 roots |
| Blocking14 regression | `/workspace/vfork4-blocking-*` | 308 roots |
| Original BusyBox child9 | `/workspace/vfork4-busybox-child-*` | 53 application launches |

The earlier vfork2 freeze also passes both-root native pipe110 plus two upstream
launches, original BusyBox12/100, jq81, Lua222, SQLite RAM146 and original blocking
BusyBox12/122. The blocking copies retain the exact110000-byte numbered-line
SHA256. That freeze predates the final shared-Q release/constructor guards and failed
binding-publication cleanup; the affected child/blocking and upstream cases are
repeated against vfork4. Passing vfork3 repeats are retained as intermediate
evidence, with their exact source hashes.

The separate `check-linux-children.py --vfork-fd-profile` retains the existing
partial-copy and32-attempt witnesses but executes real syscall58. It requires
at least five actual descriptor dup publications before EMFILE, exact rollback,
unchanged parent queues/flags/refs, successful vfork after freeing capacity, and
EAGAIN after32 failed preparation admissions. Its two-case profile adds no host
conformance or upstream-app claim. Test-only overrides are recorded in
`/workspace/vfork4-fd-src/test-only-overrides.json`; all five production files
match the vfork4 freeze. The original three NASM profiles, compiled with the same
source basename, remain whole-ELF byte-identical in
`/workspace/vfork4-default-opcode-control2/report.json`.

The explicit omitted-peer-release control uses a private modified snapshot and
fails the shared recovery assertion as required; its source diff/hashes and
`/workspace/vfork3-no-peer-release-control/control-proof.json` record the exact
private omission and genuine expected0/actual-5 panic. It adds no production hook or application success count. Earlier
vfork-refusal receipts, failed host-fixture initialization, missing helper import
and live-source-drift refusals remain historical evidence, not passing gates.

## Remaining goal

This slice does not support general shared-VM clone flags, threads, vfork from
arbitrary concurrent CPUs, arbitrary executable lookup, installed arbitrary
signal handlers, unbounded xargs jobs or unrestricted applications. Self-image
exec is the established explicit executable profile. The overall desktop and
application goal remains OPEN; this is a bounded native-owned execution slice
for review, not a claim that all applications work.
