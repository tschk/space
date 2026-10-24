# NVMe FLUSH and native sync

`fs-sync-path` now supports the mounted direct SparkFS NVMe backend through an
actual controller namespace FLUSH. The filesystem checks its file/directory
object, writes any allocation bitmap metadata, submits the FLUSH and returns
success only when the checked completion status is zero. RAM remains
synchronous; asynchronous Volume remains unsupported and returns an error.

The native NVMe forwarder sends a distinct `STORAGE-OP-FLUSH` mailbox operation
to the storage component. The driver builds an NVM opcode 0 command for namespace 1
with a nonzero command ID. PRP1, PRP2, SLBA and NLB remain zero: FLUSH has no data
transfer. Read/write commands independently reject count outside 1..8 sectors
before publishing a command or copying the shared page. This replaces silent
count truncation, which could previously disagree with a caller's copy length.

The driver polls the actual completion queue. A completion must have the correct
phase, matching command ID and submission queue ID 1. It preserves a real
controller error status for the caller; the filesystem maps every nonzero result
to failure. Wrong completion identity or timeout marks the storage backend
unready until recovery/reinitialization rather than trusting subsequent queued
operations. Normal controller command refusal leaves the backend ready, and a
later valid FLUSH can succeed. Command IDs skip zero when wrapping, including
the phase-zero case where an all-zero CQ word must not count as completion.

`nvme-flush-completions` is a provider-owned witness incremented only after a
matching FLUSH completion with status 0. A submitted command, a failed command
and a timeout cannot increment it. The witness supports real application
consumption checks; the command/completion tests remain the evidence behind it.

The mailbox wait is bounded. Busy refusal preserves the existing outstanding
operation. Successful or failed service invocation restores logical caller
identity, actual CR3 and capability context separately; completion clears the
mailbox operation. Pure FLUSH neither copies nor changes the shared data page.

```sh
python3 scripts/check-native-file-services.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/native-flush
python3 scripts/check-nvme-flush.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/nvme-command-owner
```

The native file-services gate runs a RAM boot and three separate QEMU processes
sharing an owned blank 64 MiB raw NVMe disk. It checks the actual submitted SQE,
130 FLUSH completions across queue phase wraps, zero data-page mutation, and
the successful-completion witness. A generated test-only provider can change
only FLUSH's namespace to 2. The actual emulated controller returns status 16386;
file and directory sync must propagate failure without increasing the witness.
The gate checks caller context and mailbox cleanup, removes the injected error,
and requires successful recovery. No fake CQ result substitutes for that
hardware response. An out-of-device read also produces a real completion error
and leaves the caller buffer unchanged. Missing/unready backends, invalid
FLUSH arguments and a busy mailbox produce truthful bounded errors.

The same gate retains metadata identity, persisted 0600 permissions, lease
capacity/splitting and stable-resource tests. Each NVMe process ends with real
file and directory sync; a host read-only parser verifies exact file contents
and inode mode after every boot, including both remounts.

The command-owner gate executes the actual `nvme-io-submit` function in default,
lean and harden compiler profiles with bounded doorbell/CQ fixtures. These
focused tests verify timeout/offline behavior, wrong CID/SQID, CID rollover,
controller error propagation, nonzero-witness refusal, invalid argument/no-SQ
publication and unchanged valid eight-sector write encoding. They model CQ
behavior explicitly and complement the real-controller QEMU gate.

Fresh 2026-10-24 (Australia/Melbourne), frozen Inauguration 0.9.324:

- `/tmp/space-native-flush-final/report.json`: RAM and three NVMe boots pass,
  `source_changed_during_run: []`; serial logs retain actual error status 16386.
- `/tmp/space-nvme-flush-owner/report.json`: all three compiler profiles pass.
- `/tmp/space-nvme-unmatched-cq-control/report.json`: removing only the matching
  completion check makes the focused gate fail with result 110.
- `/tmp/space-kernel-contracts-flush.log`: all 24 source contracts pass, including
  distinct FLUSH encoding and strict read/write DMA bounds.
- `/tmp/space-sparkfs-init-flush.log` and
  `/tmp/space-volume-preservation-flush.log`: existing preservation gates pass.

The Linux application owner independently ran original SQLite across three
NVMe QEMU boots at `/tmp/space-linux-sqlite-nvme-second/report.json`. The commit
consumed eight checked FLUSH completions, the next process/boot update consumed
four, and the final reopen/rollback consumed zero. Raw 16 KiB database contents
passed `integrity_check`; the update and rollback disk hashes matched and no
journal remained. This is paired original-application evidence; see that
application receipt for its commands and activation/resource counts.

A virtual controller FLUSH is the implemented barrier. These tests do not claim
physical SSD power-cut behavior, a journaled native filesystem, arbitrary
hardware recovery after timeout, or asynchronous Volume durability. Earlier
RAM-sync/NVMe-refusal receipts remain valid historical evidence for checkpoint
`46b4593`; they are superseded by the explicit FLUSH path for current NVMe sync.
