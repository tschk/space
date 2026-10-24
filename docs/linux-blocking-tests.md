# Blocking-pipe acceptance fixtures

The next execution goal is defined in
[the blocking plan](plans/2026-10-24-linux-blocking-pipes.md). These fixtures are
separate from the completed 23-case child suite and unchanged nine-case BusyBox
child corpus. Passing Linux-host behavior alone does not establish Space support.

## Unmodified upstream BusyBox

`scripts/check-linux-blocking-pipeline.py` expands
`fixtures/applications/busybox-1.36.1-blocking-cases.json`, then uses the existing
protected Linux application runner with the exact pinned BusyBox ELF. The config
retains all nine child cases and adds:

- The original 10902-byte `cat @FILE@ | wc -c` goal, requiring `10902\n`.
- A 110000-byte numbered-line file through the same pipeline, requiring
  `110000\n`.
- The same numbered-line file through `cat @FILE@ | cat`, requiring every byte
  in its original order. The expected output SHA256 equals the input SHA256,
  `1c7898d6f3630eeddf65917d04f0a07a421f1192d6a6acd122108b5fc747af57`.

Numbered lines are generated from indices 0 through 9999 as ten decimal digits plus
a newline. Their unique contents prevent reordered/missing ring chunks from
passing because the test input repeats. The two 110000-byte cases share a real
filesystem file slot, without fabricating application reads. The generated case
config is preserved by the application runner. `blocking-contract.json` records
declared input/output hashes and observed combined serial-output hashes; stderr
is required empty for the transfer cases. No new checksum applet or modified
BusyBox build is introduced.

The actual initial baseline in
`/tmp/space-linux-blocking-110k-baseline/report.json` and its
`blocking-contract.json` retains the older repetitive 110000-byte input hash.
All original nine cases pass, but all three new transfer cases fail. Cat reports
an unimplemented write; wc sees only 4096 bytes and exact-copy output is truncated.
That historical receipt is not rewritten to describe the later stronger input.

## Synthetic blocking graphs

`scripts/check-linux-blocking.py` assembles ordinary static Linux ELF fixtures
and runs the same binaries on the host and under strict Space CPL3. Its separate
14-case suite covers:

- One 11000-byte write spanning the 4096-byte ring, with exact unique LE32 sequence
  comparison, partial reads and EOF.
- Two writers publishing 3000-byte records twice each; every record remains
  contiguous across scheduler handoffs.
- A reader waking on final writer closure, and a writer fault causing real EOF.
- Default, ignored and blocked SIGPIPE after a large write publishes a real
  prefix and the final reader closes. Partial progress must be positive and
  shorter than the full request; ignored SIGPIPE subsequently returns EPIPE.
- Any-child wait selecting a completed second child while the earlier child is
  blocked, followed by a real wake and wait of that first child.
- Cyclic and retained-writer no-runnable graphs, with an explicit Space edge
  deadlock cause/status 125; their host process groups time out.
- An actually runnable root exhausting its IRQ budget while its child is
  blocked: native DEADLINE/status 124, zero remaining budget and delivered ticks.
- A real root UD2 while a writer is retained, plus the existing nonblocking pipe
  ABI probe.
- A finite two-pipe ping-pong that completes 10000 rounds on Linux, but must reach
  Space's actual 4096 admitted-work limit first: typed edge policy cancellation 126
  with IRQ budget still positive. This is distinct from no-runnable deadlock 125
  and genuine hardware deadline 124.

The runner classifies finite Linux contracts separately from Space-specific
typed fault/budget/deadlock policy. Kernel checks require all registered family
records to retire, primary/spare mappings and backing to release, both supervisor
contexts to invalidate, and FS/GS, authority, frames/domains/native descriptors
and an unrelated buffered native pair to remain correct. A fresh next activation
must still work after each fault or cancellation. External harness timeouts are
never treated as successful guest IRQ/deadlock execution.

Host evidence currently includes
`/tmp/space-linux-blocking-host-first/report.json`,
`/tmp/space-linux-blocking-childfault-host/report.json` and the strengthened
sequence fixture in `/tmp/space-linux-blocking-transfer-host-v2/report.json`.
The completed repeated Space gates are recorded below; host-only evidence is not substituted for them.

## Repeated Space evidence

All runs below use the frozen source-built .325 compiler, SHA256
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`.

- Standard 14, 308 actual parent activations over warmup plus 21 cycles:
  `/tmp/space-linux-blocking-terminal-standard14-final21/report.json`.
- Minimal 14, 308 activations including the final extra wake-entry guard:
  `/workspace/linux-blocking-terminal-guard-minimal325-final21/report.json`.
- Standard 14 extra guard follow-up, 28 actual activations:
  `/tmp/space-linux-blocking-terminal-standard-guard14/report.json`.

Trusted supervisor negatives supplement those actual CPL3 binaries. Six retry
scenarios run twice against real registered domains/native pipes: revoked memory
grants and removed mappings must fail before any new queued-byte transfer;
already published 4096-byte prefixes return exactly that progress without
publishing another byte. Canary bytes and the complete native queued payload
remain unchanged. Close works after grant revocation, and ownership is reclaimed.

The root-terminal priority proof uses a real CPL3 clone request to obtain a
genuinely suspended context, then production private-page/native-reference copy.
A root blocked writer loses its final reader while another child remains blocked.
At the last work token, root SIGPIPE must remain 141 with typed signal cause -13,
not be overwritten by quota 126. A second wake must do no work or child retry;
the manager then cancels that child and reclaims every owned reference/domain.

The unchanged 23 child tests also pass 506 activations per profile after the
scheduler fix:

- `/tmp/space-linux-children-terminal-standard23-final21/report.json`.
- `/workspace/linux-children-terminal-minimal325-final21/report.json`.

The cumulative-IRQ child fixture now waits for real delivered IRQs, observed only
in a recorded private test snapshot. Its old fixed-RDTSC calibration failed in a
later laboratory run and remains historical evidence. The isolated no-carry
causal control passes 22 normal completions after 32 genuine IRQ-driven stages in
`/tmp/space-linux-irq-observer-no-carry-final21/report.json`; it records both
source deltas/hashes and is not compatibility coverage or production test hooks.

The final unmodified BusyBox blocking corpus passes all 12 cases and 122 actual
upstream activations per root, including 21 hardware-fault/authority/cleanup
cycles:

- `/tmp/space-linux-busybox-blocking-terminal-standard-final21/report.json`.
- `/workspace/linux-blocking-app-terminal-minimal325-final21/report.json`.

Each adjacent `blocking-contract.json` records acceptance status and exact
input/expected/observed hashes. Both 110000-byte count and complete unique numbered
output pass while the native ring remains 4096. The twelve-case acceptance status
is passed; the overall application/desktop goal remains OPEN.

Unchanged pipe and original applet/builtin regressions also pass on .325:

- `/tmp/space-linux-pipes-terminal-standard-final21/report.json`: 110 synthetic
  activations, plus two actual pinned upstream pipeline probes.
- `/tmp/space-linux-pipes-terminal-minimal-final21/report.json`: the same 110+2.
- `/tmp/space-linux-busybox12-terminal-standard-final21/report.json`: all original
  twelve cases, 100 actual activations.
- `/tmp/space-linux-busybox12-terminal-minimal-final21/report.json`: the same 100.

The optional real-app pipe probe declares 100 guest IRQ ticks, matching the other
application corpora; synthetic pipe fixtures retain ten. Every optional app run
records actual per-record stop kinds, wait causes and remaining ticks. A previous
minimal warmup at ten ticks exited 137 while its second probe passed; that failed
receipt remains `/tmp/space-linux-pipes-blocking-minimal-final21/report.json`.
A later ten-tick diagnostic run passed both and recorded normal exits with
remaining budget in `/tmp/space-linux-pipes-busybox10-diagnostics/report.json`.
The earlier unclassified 137 is not retroactively called a proven deadline or a
passing ten-tick contract. The declared 100-tick acceptance is reported separately.

These prove a bounded cooperative private process graph, not a generally fair
Unix scheduler, arbitrary executable paths, shared-VM/vfork, arbitrary signal
handlers or every ash program. Those and broader desktop acceptance remain open.
