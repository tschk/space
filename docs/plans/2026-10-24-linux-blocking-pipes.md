# Protected Linux blocking-pipe execution

Goal: the unchanged pinned BusyBox 1.36.1 ELF must transfer the complete 10,902-byte
fixture through `cat @FILE@ | wc -c`, match host stdout `10902\n`, then transfer
110,000 uniquely numbered bytes through count and exact-output pipelines, and reclaim
every process/domain/backing/native-reference resource afterward on both roots.
Keep the existing 9 child cases, 23 synthetic child contracts, original 12-case
BusyBox baseline, jq/Lua/SQLite and native persistence checks passing.

The current observed failure is retained in
`/tmp/space-linux-busybox-blocking-next/report.json`: its original 9 cases pass,
but the new pipeline emits `cat: write error: Function not implemented` and
`4096\n`. The native ring capacity stays 4,096. A real producer must suspend when
its ring fills so the parent can spawn and execute its consumer.

## Ownership and execution

Native CPU contexts already capture real GP/IRET/FX/FS/GS and distinguish
suspend, exit, fault and IRQ deadline. Native VFS owns buffered bytes, endpoint
references and EOF. Linux edge process records own runnable/blocked state,
foreign syscall arguments and progress, guest descriptor names, PIDs and wait
results. The kernel assembly receives no Linux syscall or scheduler policy.

Replace the recursive child-first call with a bounded runnable-record loop.
Clone makes its child runnable and records the actual parent return PID. Prefer
the new child until it suspends or terminates; retain its runnable parent so a
blocked producer cannot prevent consumer creation. Completed children remain
zombies until a real wait reaps them. A blocking wait suspends its owner while
other owned records remain runnable. Any-child wait must find an eligible
zombie even when an earlier child is still blocked.

A blocked read retains its fd, guest address and count privately. It completes
with actual available bytes, EOF after the final writer closes, or a real
error. It never invents a successful empty read while writers can produce data.

A blocked write retains its original fd/address/count and the number of bytes
already published. Writes at most 4,096 bytes remain atomic. Larger writes may
publish a real prefix, suspend, and continue from exactly that prefix offset.
The scheduler must never repeat a published prefix or return a fabricated full
count. If a reader disappears, generate the actual SIGPIPE/EPIPE policy already
implemented, respecting blocked/ignored signals and previously transferred
bytes. Descriptor status changes and live capability checks apply on retries.

Use native `user-context-remaining` to retain delivered guest IRQ accounting
across suspended slices. Remaining ticks describe actual guest IRQ delivery;
wall-clock harness time and kernel-service work have separate bounds. Fixed
process/depth/exec limits continue to bound preparation work.

An activation-wide 4,096-unit policy quota admits each syscall service,
scheduler turn and blocked-operation retry. Exhaustion cancels the owned job
with explicit edge cause -7/status 126, separately from deadlock 125 and actual
IRQ deadline 124. This bounds admitted kernel work; it does not measure elapsed
kernel time. Cleanup always runs after the quota is exhausted.

If every retained process is blocked and no owned runnable process can change
the condition, terminate the bounded job with an explicit edge deadlock cause
and status 125. Genuine hardware IRQ deadline remains 124. Both paths must close
all retained references, invalidate supervisor contexts before domain teardown,
and reclaim all backing. Closing the root activation also tears down any
remaining owned children. Record these lifetime limits in the coverage report.

## Acceptance evidence

1. Capture the current real BusyBox failure, including original ELF hash, host
   output, all syscall markers and actual Space output.
2. Execute synthetic ordinary Linux ELFs for cross-capacity producer/consumer
   transfer, exact byte order and checksums, atomic short writes, partial large
   progress, EOF wakeup, read/write access errors, invalid full ranges, nonblock
   behavior, descriptor closure and blocked SIGPIPE delivery.
3. Exercise two waiting children and wait selection, finite owned graphs,
   infinite runnable work with real IRQ deadline, cyclic no-runnable deadlock,
   fault/close wakeup and resource recovery followed by a fresh real query.
4. Run the unchanged BusyBox 10,902-byte pipeline and existing positive suites on
   standard/minimal roots over 21 measured cycles plus warmup. Record failed
   attempts as failures and retain independent native-pair/resource witnesses.
5. Re-run original jq/Lua/BusyBox12/SQLite RAM, protected pipe and original
   SQLite NVMe transaction/reboot checks against the final source snapshot.

True shared-VM vfork remains a subsequent goal requiring an owned native VM
object with reference-counted page/domain lifetime. Current unsupported
CLONE_VM/vfork requests continue to return explicit refusal.

## Completed bounded milestone

The original pinned BusyBox ELF passes all twelve declared child/blocking cases
on both roots, including the unchanged nine child cases, 10,902-byte count,
110,000-byte count and exact 110,000-byte copy. Each final run performs 122 root
application launches over warmup and 21 measured cleanup/authority cycles:

- Standard: `/tmp/space-linux-busybox-blocking-terminal-standard-final21/report.json`.
- Minimal: `/workspace/linux-blocking-app-terminal-minimal325-final21/report.json`.

The input and exact-copy output both have SHA256
`1c7898d6f3630eeddf65917d04f0a07a421f1192d6a6acd122108b5fc747af57`.
The native ring remains 4,096 bytes. These are original ELF executions, with
additional descendant execution not included in the root-launch count.

The final .325 compiler is pinned by SHA256
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`.
Both roots also pass all 23 existing child contracts (506 root launches each)
and all fourteen blocking contracts (308 each). The trusted root-terminal
boundary check proves SIGPIPE at the last policy token stops further retries;
the extra wake-entry assertion passes in the final minimal full run and a
standard 28-launch follow-up. Exact receipts and observer-only IRQ source deltas
are documented in `docs/linux-blocking-tests.md` and `docs/linux-children.md`.

Broader regression evidence on the new scheduler/quota before the narrow
terminal-priority correction uses frozen .324: original jq 81 root launches,
Lua 222, SQLite RAM 146, and SQLite NVMe fifteen launches across three real
QEMU boots. Receipts are `/workspace/linux-jq-blocking-regression21/report.json`,
`/workspace/linux-lua-blocking-regression21/report.json`,
`/workspace/linux-sqlite-blocking-regression21/report.json` and
`/workspace/linux-sqlite-blocking-nvme/report.json`. The NVMe boots consume
8/4/0 actual successful controller FLUSH completions, respectively; the final
rollback/read-only boot makes no fabricated durability claim. The terminal
correction is covered afterward by both child suites, both blocking suites,
both real BusyBox blocking corpora and unchanged pipe/application baselines.

This milestone establishes cooperative execution for the declared bounded
process family. General preemptive scheduling, orphan/background lifetime,
shared-VM vfork, arbitrary executable lookup, unrestricted signal handlers and
full desktop application compatibility remain separate work.
