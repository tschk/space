# Original QuickJS interactive execution

The full compatibility/desktop goal remains **OPEN**. Frozen runtime
`47037aa19171a6afba575a06463cbb5566510210` passes all eight broader CLI/REPL
gates, with847 source files, compiler and original application hashes unchanged.
[Exact evidence](2026-10-25-quickjs-repl-evidence.json),
[complete cohort receipt](../evidence/2026-10-25-quickjs-repl/cohort-receipt.json).

Original QuickJS2024-01-13 executes its unchanged upstream REPL inside Space.
Actual PS2 input edits an interior expression using Left, Backspace, Delete,
Home, Right and End, evaluates `6*7`, creates `/repl.txt`, and reopens its exact
`saved` bytes in a fresh process. The second process independently evaluates
`typeof f` and JSON serialization. Each root runs two original engine entries
and134 actual keyboard events. Source/binary/license provenance remains in the
[application manifest](../../fixtures/applications/quickjs-2024-01-13.json).

The standard-root profile sends the actual original engine byte stream to the
existing protected SCI terminal client. Two real QEMU scanout captures each match
all294912 terminal pixels against independent pyte/Pillow and the pinned DejaVu
font, including ANSI16 colors. [Captures and provenance](../screenshots/2026-10-25-quickjs-repl/README.md).
The minimal-root profile verifies actual keyboard and file behavior without GUI.

The new Linux terminal edge supports exactly stdin in one readable fd-set word,
actual owned-queue readiness, indefinite input suspension and finite native
counter deadlines. Pending operation14 and private bridge operation4 retry the
saved CPU syscall frame. Empty input never charges guest CPU budget. Optional
OPOST|ONLCR converts LF into complete CRLF pairs while counting logical input
bytes; native queues remain raw. Existing raw launch behavior remains intact.
Other descriptors, temporary signal masks and unsupported disciplines refuse.

Per root,15 separate native CPU controls exercise pointer/shape refusal, real
readiness/deadlines, missing timer grants, cancellation during pending select,
and atomic partial CRLF writes. Sixty idle probes verify unchanged guest CPU
budget/syscall counts. These own controls receive zero original-app credit.
Warm frame/domain/capability/heap counts and supervisor CPU state remain stable.

The complete eight-gate cohort totals367 original entries: the previous363
QuickJS/sed CLI activations plus four real REPL activations across both roots.
The explicit no-HPET profile and compiled-private SCI refusals remain included.
The [earlier frozen CLI foundation](2026-10-25-broader-cli-execution.md) retains
its separately scoped eleven-gate three-OS fasmg cohort and390 original entries.

Eleven affected QEMU regressions pass: blocking I/O on both roots, VM, vfork,
retained terminal, original vi navigation on both roots with independent visible
pixels, native address spaces on both roots, desktop launcher and damage.
Architecture, SCI metadata57 checks and personality ABI86 checks also pass.

This is finite ASCII80x24 terminal integration. Ordinary installed-app desktop
launch, resize/concurrent foreign terminals, Unicode, larger dependencies,
AppKit/Win32/X11 frameworks, browsers and editors such as Pulsar remain open.
Current full-lab definitions total184 cached-artifact gates; no complete184-gate
run is claimed. The full163-gate historical receipt retains its original scope.
Failed descriptor-select and harness candidates remain preserved locally rather
than relabeled as passing runs. Hosted CI remains separately tracked.
