# Protected Linux children and self-exec

The Linux personality translates bounded `clone`, `wait4`, `execve` and signal-mask
requests to native owned user contexts. `linux-process-children.in` owns foreign
process policy; `linux-process-state.in` owns process records and their resource
ledgers. CPU context suspension, page-table enforcement and resumption remain
generic native mechanisms. Synthetic ELF fixtures are separate from upstream
BusyBox application coverage.

## Implemented boundary

Children execute first. The suspended parent retains a native context while the
child receives copied private user mappings, inherited register/FX/FS/GS state,
and independently owned references to inherited native open descriptions. File
offsets and pipe endpoint status are shared; guest descriptor flags and mutable
program data are private. Both actual native references and the family's pipe
ownership token must be inherited. Matching a family token alone grants no
access to an endpoint.

The initial profile accepts NULL-stack `clone` with SIGCHLD and optional
CHILD_SETTID/CLEARTID. Shared-VM/thread/TLS modes and non-NULL child stacks return
ENOSYS. A job has eight total registered records including its root and maximum
child depth three. Reaping retains the registration slot until whole-job
cleanup, bounding cumulative copy work. Admission failure leaves no child or
zombie record. PIDs are monotonic identities, independent of reusable CPU domains.
Each activation also admits at most 32 clone/exec preparation attempts, including
resource failures that release their tentative record. Invalid or limit-rejected
requests do not consume admission. This bounds repeated partial-copy work even
when no child registration survives.

Actual remaining IRQ budget is saved across every suspended/resumed slice.
Children inherit the parent's remaining budget and self-exec retains its budget;
neither operation silently replenishes a fresh quantum. Ordinary synthetic cases
use 100 ticks, while the cumulative-budget fixture deliberately uses ten.

`wait4` accepts a positive child PID or -1, options zero or WNOHANG, a nullable
four-byte status destination, and NULL rusage. Invalid status/rusage pointers
return EFAULT before consuming a zombie. A valid non-NULL rusage returns ENOSYS
and also preserves the zombie. A reaped child returns ECHILD.

Wait status uses typed stop causes: normal exit is status shifted eight bits;
UD2 is SIGILL, page/general-protection faults are SIGSEGV, SIGPIPE is signal13,
and the native execution deadline is SIGKILL. Normal exits134 and141 remain
normal exits; they are never inferred to be faults from their numeric values.

The signal-mask subset uses the actual eight-byte kernel mask and excludes
SIGKILL/SIGSTOP. A child inherits its mask and starts without pending signals.
Blocked SIGPIPE queues, then delivers on unblock; ignored SIGPIPE returns EPIPE.
Arbitrary installed signal handlers remain unsupported.

Self-exec prepares a fresh domain, mappings, argument/environment stack and
context before revoking the old image. It preserves PID and inherited open
descriptions, closes CLOEXEC descriptors only in the replaced process, resets
program data/TLS, and retains ignored SIGPIPE and the signal mask. Preparation
failure leaves the old image and descriptors usable. The implemented image path
is `/proc/self/exe`; this does not claim a general executable filesystem loader.

Child-first execution supports small pipelines whose producers complete within
the existing 4096-byte stream capacity. It does not establish a scheduler-backed
blocking stream contract. Larger blocking transfers remain an explicit next goal.

## Verification and remaining goals

`scripts/check-linux-children.py` assembles static ordinary Linux ELF fixtures,
runs declared host contracts, and loads the same bytes under strict Space CPL3.
Space-specific capacity/refusal fixtures are explicitly excluded from Linux host
agreement. Independent kernel witnesses check native pair isolation, reclaimed
frames/domains, descriptor references, FS/GS and authority restoration.

The completed 17-case snapshot passed 374 parent activations per profile in
`/tmp/space-linux-children-standard21/report.json` and
`/tmp/space-linux-children-minimal21-first/report.json`. This includes private
memory/FX, real shared-file offsets, two retained children, three actual CPU fault
types, queued SIGPIPE through a grandchild, self-exec, pointer refusals and record
limits. These receipts predate the added regular-file exec descriptor case;
they do not certify newer cases. The expanded 20-case standard-profile suite
passed 440 actual parent activations in
`/tmp/space-linux-children-standard20-final21/report.json` and independently
440 under the minimal root in
`/tmp/space-linux-children-minimal21-null-first/report.json`. It adds regular-file
exec descriptor lifetime, valid-buffer null-device host agreement, and an
explicit Space-only null checked-buffer profile. Kernel-side null checks revoke
the live memory grant:
read/write, seek, stat and flag queries must fail while close still releases the
owned reference. Invalid-range failures preserve a separate mapped canary.

The pinned unmodified BusyBox child corpus is
`fixtures/applications/busybox-1.36.1-children-cases.json`. Its first actual run
matched eight of nine host cases, including two/three-stage pipelines and real
wc self-exec. The overall first gate failed because background execution needed
a genuine native EOF/discard object exposed as `/dev/null`. After that native
provider and owned descriptor integration, the unchanged nine cases all passed
on the standard profile in
`/tmp/space-linux-busybox-children-standard-final21/report.json`: 53 actual
upstream application activations, 21 cleanup/denial cycles and seven hardware
fault probes per cycle. Background wait produces exactly `child:parent\n`;
the three-stage pipeline produces `6\n`; last-stage exit 23 propagates unchanged.
The minimal-profile counterpart also passes all nine cases and 53 activations
in `/tmp/space-linux-busybox-children-minimal21-null-first/report.json`.
The native object is not a fabricated file or command-specific output substitute.
The original 12-case BusyBox corpus and
completed pipe contracts remain separate regression requirements.

Unchanged focused regressions against the final child/null sources pass:

- `/tmp/space-linux-pipes-child-null-standard21/report.json`: 110 actual pipe
  activations and 21 ownership/capability/capacity cycles.
- `/tmp/space-linux-pipes-child-null-minimal21/report.json`: the same 110/21
  contract under the minimal root.
- `/tmp/space-linux-busybox-child-null-baseline21/report.json`: all original
  12 upstream applet/builtin cases, 100 actual activations and 21 cleanup cycles.

Next acceptance requires genuine blocking transfer scheduling. The full
application and desktop goal remains open.

Lifecycle hardening adds a 21st, explicitly Space-only descriptor
admission case. With an independent native pair already retained, the root owns
three pipe pairs. Clone publishes five real duplicated native descriptors, then
the sixth fails with EMFILE. The fixture requires no child TID publication or
waitable child, unchanged parent flags/buffers/peer references, and successful
clone/wait after releasing one pair. Kernel accounting asserts five published
references and exactly one failed copy, so the proof does not infer partial work
only from pool sizes. Its first focused gate passes two parent activations in
`/tmp/space-linux-partial-fd-first/report.json`.

`fixtures/linux-children/cleanup.in` separately forces native teardown refusal
from a trusted supervisor fixture. Both primary and prepared exec VMs, mappings
and backing frames must remain owned; new user activation returns EIO. After
repair, explicit trusted recovery must reclaim both without losing ownership.
The child runner requires its actual recovery marker, and no failed cleanup may
silently retire a process row or resume its parent.

The final 21-case hardened suite passes 462 actual parent activations per root:

- `/tmp/space-linux-children-cleanup-standard21/report.json`.
- `/tmp/space-linux-children-minimal21-cleanup-final/report.json`.

These include the required retained-cleanup marker and exact partial-copy
diagnostics on every warmup/measured activation. The unchanged nine-case
upstream BusyBox child corpus also passes 53 activations per root in
`/tmp/space-linux-busybox-children-cleanup-standard21/report.json` and
`/tmp/space-linux-busybox-children-cleanup-minimal21/report.json`.

`scripts/check-linux-blocking-pipeline.py` makes that next gate executable. It
retains the completed nine cases and adds a real 10902-byte file piped through
unmodified `cat | wc -c`, requiring exactly `10902\n` and no stderr. The first
actual diagnostic in `/tmp/space-linux-busybox-blocking-next/report.json` fails:
cat reports an unimplemented write and wc counts 4096. Its final exit status is 0
because wc succeeds; stdout/stderr disagreement still correctly fails the gate.
The remedy requires genuine producer suspension and consumer scheduling while
retaining native stream ownership and the 4096-byte capacity contract.

The final boundedness suite has 23 cases. Its retry-admission case forces 32
actual partial native-FD copy failures, requires EMFILE each time, then EAGAIN
on attempt 33 without a waitable child or parent-pipe damage. Kernel diagnostics
require exactly 32 admitted preparations/rollbacks and five copied references on
each failed preparation. Its cumulative-IRQ variant spins for 20 million RDTSC
cycles between attempts and must stop with typed native DEADLINE/status 124 after
at least one completed suspended preparation, at least ten actual IRQ ticks and
zero remaining budget, before 32 preparations complete. This distinguishes IRQ
enforcement from an ordinary program exit 124 or an external wall watchdog.

The causal control in `/tmp/space-linux-budget-no-carry-first3/report.json`
deliberately omits only the budget carry store in an isolated captured source
copy. It records original/modified hashes, is explicitly classified
`negative-control-passed`, and requires the same finite program to finish with
typed normal exit 42 after 32 preparations. It passes two activations. No live
production source is modified, and this control is not compatibility coverage.

The final 23-case gate passes 506 parent activations per root in
`/tmp/space-linux-children-budget-standard23-final21/report.json` and
`/tmp/space-linux-children-minimal23-budget-final21/report.json`. The original
nine-case child application corpus also passes 53 actual upstream activations
per root in `/tmp/space-linux-busybox-children-budget-standard21/report.json`
and `/tmp/space-linux-busybox-children-budget-minimal21/report.json`. These
include serial stderr CLOEXEC preserved in the parent and closed only in the
exec-replaced child.
