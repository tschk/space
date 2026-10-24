# Original BusyBox vi workload

The separate [vi manifest](../fixtures/applications/busybox-vi-1.36.1.json)
adds upstream vi Kconfig options to the existing static BusyBox 1.36.1 build.
It does not replace the pinned CLI or xargs binaries. No upstream source was
patched: 752 C/header/assembly files match the acquired official archive.
Builds in two clean directories have identical binary bytes. The retained
`/workspace/busybox-vi-build4/report.json` matches the new profile and its config
hash; the first new build intentionally differed from the older CLI artifact
pin and remains recorded separately. The vi ELF SHA-256 is
`22e06756b81d069041080e5582854a7cd0bbf63e50f3002703d2b9a1035d8c5e`.

## Executed scope

The host PTY reference really inserts text, saves, exits and reopens in another
process. It passes at `/workspace/vi-host-reference/report.json`. It contributes
zero Space compatibility credit.

Space executes the original vi binary through the existing protected Linux
process path. Its native EX-command profile reads `original\n`, replaces and
saves `SpaceTUI42original\n`, then starts a separate vi process which reopens,
replaces and saves `Reopened42\n`. Independent native file reads verify both
intermediate and final bytes. Each RAM profile runs 44 original processes over
22 cycles. The two-boot NVMe profiles run 88 original processes each; boot two
verifies the prior saved bytes before resetting the test. An independent raw
disk oracle checks size, inline payload, zero retired tail and schema2 UTC
mtime. The binary is still explicitly staged at boot; this is not ordinary
installation or desktop launch.

The owning ABI fixture is separately counted: 22 CPL3 entries per boot check
regular-file readiness including EOF, descriptor/event masks, unchanged offsets,
invalid/ignored handles, unsupported waits, partial-output refusal, null/RO
pointers, shrink, zero extension and extent/access refusals. Three actual SCI
import fixtures per boot must fail before entry or resource allocation; a marker
detects accidental entry. Their staging must fit inside the existing bounded
boot window. The initial high-address staging attempt exercised a different
trusted loader path and failed its cold-resource assertion; that receipt is
preserved and is not a successful preflight proof.

`/workspace/vi-file-controls-model2/report.json` passes 99 owning-function
model checks across default/lean/harden, including live grant revocation during
readiness queries, stale identities, missing clock and unchanged refusals.
Model checks are not application or guest-fixture entries.

```sh
python3 scripts/check-linux-tui.py --in /path/to/source-built/in \
  --app /path/to/pinned/vi-busybox --batch-ex --out /tmp/vi-ram
python3 scripts/check-linux-tui.py --in /path/to/source-built/in \
  --app /path/to/pinned/vi-busybox --batch-ex --root minimal --out /tmp/vi-minimal
python3 scripts/check-linux-tui.py --in /path/to/source-built/in \
  --app /path/to/pinned/vi-busybox --batch-ex --nvme --utc --out /tmp/vi-utc
```

The runner freezes its source inputs, checks original payload bytes before every
cycle, retains compiler/image/source/application identities, and checks native
page/domain/descriptor and authority cleanup. New evidence directories are
required. Source/compiler/application changes invalidate a run. The main lab
includes standard/minimal RAM and both NVMe schema profiles.

## Native contracts and limits

`vfs-readiness.in` owns synchronous regular-file readiness. `linux-process-poll.in`
translates Linux syscall7 and eight-byte pollfd rows, with at most16 rows.
Negative descriptors are ignored, invalid descriptors report POLLNVAL, ordinary
file readiness includes EOF, and requested IN/OUT/RDNORM/WRNORM bits are mapped.
Unknown event bits do not invent readiness. All outputs are staged until the
whole query passes. Real waits and unsupported terminal/pipe/device profiles
refuse -95 without committing partial revents. Live Memory/Storage grants and
the existing file inode/mount identities are checked. Existing path-backed VFS
limitations remain; this is not a new general unlinked-file object model.

The shorter vi save exposed syscall77 returning -38 and leaving trailing bytes.
`filesystem-inline-resize.in` now owns zero fill, shrink and metadata updates
for existing native inline files of at most96 bytes. The Linux descriptor edge
checks live grants, access and identity, preserves offsets and maps errors.
Non-inline files, larger extents and asynchronous Volume backing remain refused.
Schema2 mutations require the real existing TimeSource lease. This does not
claim a filesystem journal, crash atomicity or rollback after an I/O failure.

These helpers are private trusted kernel-linked prototypes, explicitly denied
in the SCI export registry. They do not establish an isolated Storage or
TerminalSession SCI service. No foreign backing-block ledger, raw guest pointer
into VFS, alternate IPC fabric or terminal policy in the nanokernel was added.

## Real keyboard continuation, 2026-10-25 Australia/Melbourne

The original pinned vi now runs through the optional native terminal backend on
both standard and minimal roots. Two successive protected processes receive 27
actual PS/2 text events, save `native42original\n`, then reopen and save
`again42native42original\n`. The test verifies exact 17- and 24-byte files,
the unchanged upstream ELF, restored supervisor state and stable resources
after warmup. `scripts/check-linux-terminal-vi.py` preserves the original ANSI
output separately; this is keyboard/file evidence, not a desktop screenshot.

The native backend retains CPU/VM state while input or output would block.
Its bounded raw termios, single-descriptor poll, descriptor flags and native
geometry support this application without changing regular-file readiness.
Finite poll uses the authorized hardware counter. An executable negative
control caught an expired poll deadline leaking into a subsequent blocking
read; the corrected backend retires that deadline on poll completion.
Canonical disciplines, signals, multiple-descriptor terminal poll and concurrent
foreign terminal processes remain unsupported in this optional profile.

The PS/2 controller and keyboard decoder were extracted unchanged from the
mouse module so minimal-root keyboard testing needs no framebuffer/mouse
geometry. These are native libraries, not new SCI isolation boundaries.

## Historical startup limitations and remaining display work

Before the native terminal continuation, an original vi startup with no terminal input correctly opened the file and emitted
its ANSI screen, then fails reading input. Feeding key bytes from a regular file
also remains a failed scenario: vi's Escape decoder needs actual timed input
availability, while Linux correctly reports a regular file readable at EOF.
Changing that readiness to make the application pass would be incorrect.

The EX scenario proves original application editing/file behavior. The newer
keyboard scenario additionally proves real input and retained waits. ANSI output
rendered by Space, resize events, two concurrent terminal clients and general
TUI support remain open. Those stay in
the [full goal](compatibility-coverage-goal.md), with the next native session
boundary explained in the [console/GUI reference review](terminal-gui-reference.md).
