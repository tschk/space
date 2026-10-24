# Interactive vi durability continuation

Close the interactive persistence gap with three independent QEMU/NVMe boots.
Create a new owned64 MiB disk; format only that disk. Install the pinned original
BusyBox vi executable and initial text through Space's native filesystem on the
first boot. Later boots must have no ELF staging device: obtain the original
bytes through the existing native immutable file observation and retain its loan
until the protected CPU activation is fully retired.

Use actual PS/2 interior editing/navigation, the existing private terminal/seat,
retained Linux context and protected SCI screen. Save and close, flush native
NVMe, cold boot, verify the old bytes before editing, save again, then cold boot
a read-only verifier. Independently inspect both the persisted ELF and exact
text from host read-only disk parsing. The third boot must preserve disk hash.
Repeat both filesystem schemas and retain all failures and provenance.

This is an explicit integration cohort over existing native providers, not a
new mapping ledger, native kernel file-exec API, installed desktop action or
isolated terminal service. Captured executable labels remain distinct from
argv[0] and do not claim live inode/rename identity. Ordinary product launch,
resize and concurrent foreign terminals remain open.

The initial disk oracle incorrectly excluded valid root inode0 and was corrected
to the actual native ABI with inode/range/type guards retained. The first
completed edit/reopen boots then exposed a verifier mistake: ordinary file
reads update atime, and schema2 correctly requires a bound TimeSource for that
write. The third boot now uses native immutable observations for both text and
ELF, with no clock binding. Whole-disk hash equality remains required; the
failed disk-change/clock probes are preserved rather than weakening that check.

The corrected candidates at`/workspace/vi-durable-nvme3/report.json` and
`/workspace/vi-durable-nvme-utc2/report.json` pass both schemas. Each runs two
original protected vi processes over three cold boots,38 real PS/2 key events,
exact17-/24-byte text, two294912-pixel oracles and whole-disk equality on the
last boot. The later QEMU commands contain no executable staging device; both
native FNV and independent host SHA256 verify the installed ELF. The active
CPU retains its source observation loan through pending-close and releases it
only after CPU retirement. These remain integration-cohort results, not a
general installed-app launcher or source-service isolation claim.
