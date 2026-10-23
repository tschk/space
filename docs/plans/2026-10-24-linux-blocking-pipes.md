# Protected Linux blocking-pipe execution

Goal: the unchanged pinned BusyBox 1.36.1 ELF must transfer the complete 10,902-byte
fixture through `cat @FILE@ | wc -c`, match host stdout `10902\n`, and reclaim
every process/domain/backing/native-reference resource afterward on both roots.
Keep the existing 9 child cases, 20 synthetic child contracts, original 12-case
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
