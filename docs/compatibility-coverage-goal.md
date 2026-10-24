# Compatibility coverage and GUI application goal

User direction, expanded 2026-10-24 (UTC): build a usable native
Space desktop and protected Linux, Darwin/macOS and Windows application
personalities; keep implementing and locally testing real CLI and GUI applications
until the acceptance matrix below works end to end. This is the full project
goal. The fixture lab is an early checkpoint, not the completion target.

Latest actual local results: [execution checkpoint](plans/2026-10-24-application-execution.md).
The earlier [real-application checkpoint](plans/2026-10-24-real-applications.md)
is historical; its compiler and protected-execution blockers have since advanced.

Status: **active; full goal incomplete**. Current shipped behavior and local test
results must be recorded separately from this destination. Work proceeds through
reviewable implementation/test commits on the requested draft PR branch. This
file does not create a scheduled or unattended background task.

Continuation, 2026-10-25 Australia/Melbourne: the full goal was never completed.
Native owned terminal queues and separate seat focus leases now pass 99 modeled
controls and actual QEMU keyboard/lifetime/import-denial checks. Retained foreign
activation waits and interactive original vi are the active implementation work;
see the [native terminal continuation](plans/2026-10-25-native-terminal-session.md).
These focused checks do not widen the historical 152-gate receipt below.

## Active local execution checkpoint — 2026-10-24

Latest complete passing checkpoint: **152/152 passed**, zero failed or blocked,
from **720 committed source files at `c408746`**. The receipt is
`/workspace/lab152/report.json`, SHA-256
`8c5227678bbfa5aacb99dcb1ce74f6d5f638cc797c2f91de31faaea4407c4a70`.
Source, compiler and original application integrity checks pass, with no changed
inputs. The run finished on 2026-10-24 at 23:13 Australia/Melbourne.

This integrates the measured DejaVu font advances, terminal cells and baselines,
dark desktop palette, exact font/framebuffer oracles and real desktop keyboard,
pointer, focus, resize, close/reopen, persistence and performance checks. Actual
[QEMU screenshots](screenshots/2026-10-24/README.md) show both the native shell
and the protected native calculator/editor; those clients retain their own
bitmap text and the editor's eight-ASCII-byte limit.

Original BusyBox vi now performs EX-command edit/save and separate-process
reopen/edit/save. Each RAM root passes 44 original vi activations; each two-boot
NVMe schema profile passes 88, with exact persisted bytes and stable lifetime
checks. Native regular-file readiness and inline resize are bounded prerequisites.
**Interactive keyboard/PTY/ANSI TUI acceptance remains OPEN**, as do original
Windows/macOS applications and foreign GUI acceptance. The denied private SCI
imports, own CPU fixtures and modeled provider controls remain separately counted.
See [vi scope](linux-vi-workload.md), [desktop evidence](plans/2026-10-24-desktop-fonts.md)
and the [Wine/ReactOS/Rosemary/terminal review](terminal-gui-reference.md).

The first expanded 151-gate run at `34239e7` finished **136 passed / 15 failed**,
with integrity passed. Its unchanged receipt remains `/workspace/lab151/report.json`.
The [layout repair](plans/2026-10-24-fixture-boot-layout.md) preserves all exercised
assertions and the unchanged heap boundary; the fresh 152-gate run passes those
previously failing gates. The earlier 144/144 result at `5b54e1e` retains its
separate 695-file scope. No percentage of general OS compatibility is inferred.

Later legacy admission diagnostics and CI-harness repairs have separate focused
receipts. They do not rewrite the frozen integration source or turn rejected
applications into execution coverage. The full project goal remains active.

An earlier whole-tree checkpoint passes all131 gates at
`/workspace/lab131/report.json`, from657 committed files at f54a293, with source,
compiler and application integrity passed. It includes shared vfork/xargs,
keyboard/cursor editing and the repaired compiler/Windows test harnesses. The
later663-file133-gate source (3af6ad4) also passes all133 gates at
`/workspace/lab133/report.json`, including integrity checks. It adds counted
startup and original fbv CLI entry; it does not retroactively extend131.

The next committed checkpoint passes all135 gates from672 files at9a014c2,
`/workspace/lab135/report.json`, with source/compiler/application integrity
passed. It includes the native owned canvas and actual original fbv BMP pixels,
plus the previous CLI/process, Windows/Darwin and desktop regressions. Later
UTC metadata work is a separate in-progress source; it does not extend135.

The independent679-file UTC/Volume source1ffaa65 passes all137 gates at
`/workspace/lab137/report.json`, including source/compiler/application integrity.
It adds schema2 UTC metadata, actual NVMe persistence and malformed backing
refusal while preserving original Linux workloads and desktop behavior.
Windows Find work proceeds separately: a finite root adapter now passes624
actual CPL3 fixture activations on RAM and1248 across two actual NVMe boots,
with complete record oracles, revocation, fault/deadline and lifetime checks.
Original Windows application entries remain zero. See the
[Find boundary and evidence](plans/2026-10-24-windows-find.md).

The later686-file sourcead0a0be passes all139 gates at
`/workspace/lab139-retry/report.json`, including source/compiler/application
integrity and both new Windows Find gates. Its interrupted first attempt at
`/workspace/lab139` is retained separately and has no final all-pass claim.

The next native file-observation slice has separate focused acceptance: original
fbv pixels come from a native filesystem snapshot on RAM and across v1/UTC NVMe
boots. Original fbv, BusyBox and Lua also run132 times per filesystem profile
across two boots, with no application ELF staging on reopen, exact output and an
unchanged read-only disk. Captured executable identity is separate from argv0.
See [the native Storage boundary](plans/2026-10-24-native-file-observations.md).
Its five new integration gates do not retroactively extend the139-gate source.

The full goal remains active. Four unmodified upstream Linux applications now
execute through private CPL3 mappings: original jq1.8.1, source-built Lua5.4.7,
BusyBox1.36.1 and SQLite3.46.1. The sanitized-entry checkpoint passes81 jq,
222 Lua,100 BusyBox and31 SQLite activations, each with21 measured cycles,
actual CPU faults, timer cancellation, authority denial and resource checks.
Actual owned pipes pass220 protected launches across standard/minimal images;
the original BusyBox child corpus now passes nine cases on both standard and
minimal images (106 upstream activations), including two/three-stage pipelines,
self-exec, subshells and background wait. The new bounded blocking scheduler
passes the original10902-byte pipeline and110000-byte count/exact-output
pipelines on both roots, keeping the native ring at4096 bytes. Each root passes
122 actual upstream BusyBox activations; original failure receipts remain
preserved. SQLite now also completes
real RAM-backed database transactions and separate-process reopen:14 cases,
146 activations and21 repeated fault/cleanup cycles pass, including a9000-byte
blob and rollback preserving its contents. Original SQLite also passes three actual NVMe boots, checked FLUSH and
independent host database integrity checks after commit/update/rollback.
General process scheduling, crash atomicity and the broader database acceptance
rows remain open.

Copied Linux processes now use the shared native `UserAddressSpace` mechanism
(`d9d1db9`); the foreign edge has no backing-frame ledger or raw physical I/O.
All28 final migration gates pass from a frozen source, including both-root
original app/process/pipe regressions and three SQLite NVMe boots. Mandatory
controls cover failed exec staging, retained teardown, mismatched process-row
refusal before guest entry, IF restoration and immutable high-source startup
arguments. Bounded syscall58 vfork is now committed separately:14 final both-root gates
pass, including47 actual upstream xargs launches per root, blocked-parent/exec
ordering, shared mappings, failed-exec continuation and retained-owner recovery.
Arbitrary shared clone/thread flags remain refused. See the [vfork contract](linux-vfork.md)
and
[Linux owned VM evidence](linux-owned-vm.md) for exact profiles and counts.

Original fbv1.1 adds a smaller intermediate GUI-program startup corpus:44 real
protected CLI activations per root now pass with unchanged host help/no-argument
output and status. Its initial argc mismatch drove an explicit argc1..3 launcher;
66 separately counted startup ELF entries per root check argv/envp/auxv, high
immutable sources and unused-pointer refusal. Three clean unmodified-source
builds are byte-identical. A later explicit native-canvas framebuffer profile now renders the original
viewer BMP:22 original launches and88 separately counted syscall/fault/deadline/
quarantine controls pass with exact pixels and21 measured resource cycles. It
does not provide interactive input, ordinary launcher integration or complete
any FLTK/framework row. See the
[framebuffer workload checkpoint](plans/2026-10-24-linux-framebuffer-app.md).

Protected Mach-O supports checked raw Darwin calls and finite typed libSystem
imports, including a separate eleven-service allocator revision. Protected PE
has a composed43-name KERNEL32 service profile while retaining the32-import
execution bound and explicit unknown-directory refusal. Windows strict507/read527/write527/general317 activation gates and six
NVMe boots pass after register sanitization. Original macOS/Windows jq remain
explicitly refused and unexecuted; general dyld/UCRT/framework support is open.

The separate high-address Darwin mapper now consumes the generic native owned
address-space object. Its finite three-import fixture passes318 actual CPL3
entries and147 forced setup refusals over21 measured cycles, including exact
RO/NX faults, real deadlines, source/plan checks and retained-owner recovery.
The original pinned macOS jq still refuses-38 at `__DefaultRuneLocale` before
native VM creation; it has zero executed entries. See the
[mapper checkpoint](plans/2026-10-24-darwin-owned-mapper.md). Original Darwin
applications and framework/GUI support remain required full-goal work.

Windows profile12 separately adds real owned UTF16/UTF8 file paths and directory
state:1326 CPL3 activations and63 activations across three independent NVMe boots
pass, with19 older Windows regressions preserved. Original apps still refuse;
directory iteration is the next missing provider contract. The new private
native directory snapshot prototype checks1698 real entries, tombstones and
indirect blocks across21 RAM-backed kernel observations. It has no foreign Find
API or original-application execution claim. The same provider now passes63
observations through three actual NVMe boots, with independent raw-disk entry/
inode/content checks and byte-unchanged read-only reopens. Foreign enumeration
integration remains open. See [Windows paths](windows-path-checks.md) and the
[native snapshot checkpoint](plans/2026-10-24-native-directory-snapshots.md).

All11 native CLI scenarios pass. Native notes persists edited bytes across three
NVMe boots. Filesystem repairs now pass actual57391-byte multi-block, sparse,
partial-overwrite, truncate, reclaim and remount checks, plus24-byte filename
boundaries. This proves the tested completed-write/remount behavior; crash
atomicity and journaling remain open.

Ordinary persistent-volume boot now preserves user files: its diagnostic SCI
write is restricted to the disposable RAM filesystem. Three actual NVMe boots
retain a user-owned `test.sci` sentinel and byte-unchanged read-only reopens; the
old root fails that same oracle. RAM/file-loader and filename/remount regressions
pass. See the [boot preservation checkpoint](plans/2026-10-24-boot-storage-preservation.md).

The standard image now defaults to protected CPL3 calculator/editor clients
(`f09df34`), launched through `gui apps` or the real command bar. Six display
modes, five NVMe boots,129 sessions, hostile-peer recovery and parent desktop
restoration pass. Launch errors visibly render and can be dismissed. The input
driver remains trusted SCI and the supervisor/compositors remain kernel-linked.
The bounded two-app session temporarily owns scanout; concurrent integration
into the desktop tiling model and a larger editor remain full-goal work.

Native keyboard/cursor editing now passes real PS/2 interior insertion,
Backspace/Delete and Home/End/Left/Right with exact caret pixels across six modes.
Five NVMe boots,129-session lifecycle, hostile-peer recovery, ordinary default
launch and parent-desktop launcher/damage regressions remain passing. USB HID
usage/Shift/Ctrl corrections have model evidence only; USB hardware and full
keyboard/report handling remain open. The editor still holds eight ASCII bytes.
See the [keyboard/editing checkpoint](plans/2026-10-24-keyboard-editing.md).

The earlier distributable standard-image checkpoint includes separate native SCI GUI calculator
and editor applications. Actual keyboard, shifted operators, pointer focus,
close-one/keep-other-running and exact client glyph checks pass. The editor's
explicit storage capability saves at most eight bytes and reopens them across
five real NVMe boots; a stripped-grant image cannot change the file. These
earlier native clients run trusted CPL0 in explicit legacy/window profiles. The old retained lifecycle failed on
session20 after19 completed sessions. Private image/global ownership and
physical close reclamation now pass129 sessions with real input/pixels and
resource/ABA checks; capability/domain/page/surface identities are withdrawn
before reuse. An optional readable-window profile now passes six output/scale combinations,
real pointer/edit/resize checks,129 resource/ABA sessions and five NVMe boots,
including server canvas views above4GiB. Low-memory refusal/recovery also passes, and this profile is now the product
default (`cf2ccbb`). Final real tests pass129 sessions, six output/scale modes
and saved-text resize plus five NVMe boots from one435-file snapshot. Broader
desktop quality remains open. The current protected default described above
supersedes this historical trusted-profile checkpoint.

Source-built Inauguration0.9.324 passes its required compiler checks, including
119 conformance cases and Linux differential62 agreements/27 explicit refusals
with zero disagreements/crashes. A new frozen Space snapshot passes all26 compatibility gates. Its separate
expanded26-gate application lab also passes with no changed source, compiler or
application artifacts. The30-gate revision also passes from a separate immutable383-file snapshot,
with compiler and application artifacts unchanged. It predates the subsequent
pipe/NVMe/FILETIME/readable-window features; a new integrated run must include
those gates. That subsequent52-gate run now passes in full at
`/workspace/local-evidence/space-application-fiftytwo-run/report.json`, with
unchanged source/compiler/application artifacts. Its435-file scoped snapshot
explicitly excludes newer CPU/context, native HPET, Windows environment/QPC and
Linux child-process work; their separate proofs do not retroactively extend it.
General foreign GUI applications, full
desktop text/layout behavior and the rest of the acceptance matrix below remain
open. The current default integration has separate later receipts.


## New slices and integration work

Linux copied process families now pass1012 parent activations across the standard
and minimal roots, including partial descriptor-copy rollback and retained
teardown recovery. The original BusyBox child corpus passes106 additional
activations. These are separate checkpoint receipts, not an extension of the
52-gate frozen integration result. Review identified repeated preparation and
suspend-budget accounting gaps; the committed fix (`211be9e`) bounds activation
preparations to32, carries the actual remaining delivered IRQ budget, and closes
serial descriptors marked CLOEXEC on self-exec. A generated omission control
proves the budget fix changes actual cancellation behavior. The subsequent
blocking scheduler passes14 synthetic cases/308 activations per root, including
actual suspension, EOF/SIGPIPE wakeup, atomic short writes and exact partial
progress. It separately bounds kernel policy work at4096 units; policy
cancellation126, deadlock125 and actual IRQ deadline124 remain distinct. The
23-case child regression passes506 activations per root. The robust cumulative
budget fixture now observes real delivered IRQs in an explicitly recorded
test-only source profile; the earlier timing-dependent failure is retained.

Windows environment and native hardware-counter translation are committed in
`2de596c`; the private process heap is committed in `03fa931`. Their actual
protected checks pass380 environment,593 counter/clock and485 heap launches,
with explicit unavailable-counter and allocation/admission refusals. TLS/FLS
callbacks are committed in `66d1290`, with3544 activations across eight fresh
boots, all14 older regressions and exact cold-cache admission/recovery checks. Recursive critical sections are committed in `96ef514`, with654 focused
activations and all15 older regressions. Original Windows applications remain
refused. Composition is now committed in `4327d14`:773 protected activations
across PC/Q35/no-HPET and all16 older regression gates pass. Unknown original
imports, PE directories and the32-import execution bound remain explicit
barriers. Unicode profile11 is committed in `aeeca40`, with4921 actual CPL3
conversion executions,773 mixed-service activations and independent3410-case
scalar models in each of three profiles. Original Windows applications remain
unexecuted; execution-local wide paths/cwd are the next slice.

Generic SCI layout metadata and page-separated mutable data are committed in
Inauguration `0a0a5a2b` (0.9.325). Required compiler checks and the isolated
self-update pass. Historical CLI receipts retain their0.9.324 compiler; the
new protected default requires valid0.9.325+ layout metadata. No compiler
publication or toolchain-symlink change is implied. Darwin startup is committed in `168e01f`, with344 actual CPL3 executions,
exact first-cache memory admission/recovery and unchanged483/548 old gates.
Protected native SCI profiles are committed in `78fdae6`, with separate
paged279/immutable274 actual invocation proofs,140 protected lifecycle
instances per profile and exact32MiB refusal/recovery. The shipped native GUI
loader has a historical trusted profile; the protected default is now verified
and committed separately in `f09df34`. Protected GUI core3 is committed in `f3e12fd`: owned read-only input rings,
writable staging and separate immutable accepted presentation frames pass
actual hostile-write, lifetime and low-memory checks. The opt-in real calculator
and editor now pass all six output/scale modes and129 sessions/258 instances.
The consumer checkpoint is committed in `aa16a9e`, with final six-mode,
five-boot persistence,129-session and six-fault recovery gates passing from one
frozen541-file source. The separate startup ownership fix (`8e5c4f6`) passes140
failed starts with exact cleanup and a surviving peer. Default launch
integration is committed in `f09df34`, with actual ordinary-image and
command-bar interaction, persistence, lifecycle, faults and visible errors. Original Darwin/Windows applications and foreign GUI
workloads remain open. Eager Mach-O chained imports are committed in `174d708`
with254 actual executions and malformed/unused-import refusal controls; the new
Darwin heap adapter is committed separately in `eef4ea8`:275 actual CPL3
executions over21 stable cycles, allocator failure preservation, live-grant
revocation, exact pressure recovery and unchanged254/344/483/548 regressions.
Original macOS jq still refuses admission. Inspection-only Lua5.2.4 artifacts
do not replace the full Lua5.4.7 acceptance target.

The subsequent69-gate immutable run passes68 and fails one cumulative-budget
test on the minimal image; source/compiler/application integrity passes. This
is retained as an integration failure while its fixed-TSC timing assumption is
repaired. It does not invalidate the52-gate historical checkpoint or silently
remove the failed assertion.

The next committed552-file snapshot (`ceef6f7`) passes all83 integrated gates
with unchanged source/compiler/application hashes at `/workspace/lab83/report.json`.
It includes both real BusyBox blocking pipelines, Windows TLS/FLS/critical
sections, eager Mach-O imports and protected native SCI/GUI runtime ownership.
It excludes the later composition/heap, readable protected consumers, Unicode
and default-launch work; their focused receipts remain separately scoped.

Original Mach-O image planning is committed in `4b05534`: the original jq image
produces an independently verified209-page plan and validates1357 chained links
and136 imports. It still refuses its first unavailable import before mapping
or entry. This is loader progress, with zero original application executions.

## Full completion goal

From a clean checkout, build Space and its source-built compiler, boot locally
under QEMU, install the pinned application corpus, and use the original Space
desktop to launch native and foreign applications as separate protected
instances. A user can open/edit/save/reopen files, run CLI pipelines, switch
between independent GUI windows, resize/tile/minimize/restore them, and close or
recover a crashed application without losing another application's work. Reboot
preserves saved files. Denied authority and unsupported APIs produce bounded,
useful failures. No supported scenario depends on executing a foreign payload at
CPL0, faking its output, or forwarding the workload to the development host.

Completion means all required scenarios in the versioned corpus pass through
Space's own runtime in fresh repeatable local runs, with isolation, persistence,
interaction, visible output and cleanup evidence. It does not mean every API or
every application ever released for the three operating systems is implemented.
Expand the supported application/profile matrix after each completed checkpoint;
a narrowed matrix must never silently redefine the full destination.

### Required platform outcomes

| Workstream | Completion evidence |
|---|---|
| Native platform and compiler | Source → Inauguration → SCI packaging → loader → granted objects is reproducible; generic ABI/native/JIT fixes live in Inauguration. Native compiler model gates pass on the actual development host rather than being skipped. |
| Protected process runtime | ELF, Mach-O and PE images have validated mappings, startup stack/arguments/environment, RX/RW/NX permissions, guest-pointer checks, per-instance descriptors/handles/TLS/errno and bounded exit/fault cleanup. Two instances cannot read/write each other or kernel memory; repeated launch/fault/exit reclaims owned resources. |
| Linux personality | The pinned corpus exercises real Linux startup, dynamic/static loading as selected, file metadata/offsets, process creation/wait/signals, pipes/polling, terminal/session behavior, threads/futexes, time and required sockets. Unsupported structures/flags/syscalls fail before unintended side effects. |
| Darwin/macOS personality | The pinned Mach-O corpus exercises segment/fixup/import and dyld behavior, Darwin error conventions, BSD descriptors/process behavior, required Mach task/port/VM contracts, Objective-C/blocks, Foundation/CoreFoundation, run loops and the AppKit/graphics subset its GUI workloads use. |
| Windows personality | The pinned PE corpus exercises imports/relocations/TLS and callbacks, declared x64 calling conventions, process/thread/synchronization and file semantics, NTSTATUS versus Win32 BOOL/count/LastError, message loops and the Win32/GDI or equivalent GUI subset its workloads require. Space-local translator IDs do not stand in for a real binary ABI. |
| Native desktop | Separately owned command, layout, compositor, seat, text and application-supervisor services work together. Real independent terminal/editor/file sessions launch; focus/layout/command actions refer to stable identities and display actual launch failures. Preserve the original niri-like layout and command-bar direction. |
| Display/text/input | Supported resolutions/scales work with multiple real typefaces, measured text/caret/hit testing, fallback and declared Unicode/shaping support. Keyboard releases/modifiers/repeat, pointer capture/focus, clipboard and text input have explicit recipient/authority contracts; extend to IME with actual tested input before claiming it. |
| GUI adapters and buffers | Native SCI clients and foreign software-rendered windows present their own bounded buffers. Attach/damage/commit/release, resize/scale, stale identities, disconnect and crash recovery are tested; clients cannot modify in-flight buffers or receive another client's input. Shell decorations remain Space policy. |
| Files, network and resources | App file access follows granted roots, saved content survives close/relaunch/reboot, denial does not mutate files, and network/DNS/TLS scenarios use explicit service grants. Audio/GPU capabilities enter only through owned service/backends and actual corpus cases; software presentation remains a working fallback. |
| Continuous application lab | One command acquires/verifies corpus artifacts, builds/boots the tested Space image, drives scenarios with bounded timeouts, captures status/logs/screenshots and compares outputs/content. CI runs redistributable gates; local GUI evidence includes actual keyboard/pointer effects and keeps failure artifacts. |

### Real application acceptance matrix

The following are concrete initial targets, not claims of current support or
verified downloadable artifacts. Start with native x86_64 for all three foreign
formats. Pin the exact upstream archive/revision, source/build recipe, target
triple, binary SHA256 and distribution license in the executable corpus before
counting a scenario. Source-built applications retain unmodified upstream source;
record build/configuration choices. A special Space rewrite is a native port and
must be reported separately from foreign compatibility.

| Target/profile | Initial named upstream version | Required scenario and oracle |
|---|---|---|
| Native Space | Repository `calc`, `notes`, `files`, terminal and their SCI artifacts, pinned to the tested Space commit | Calculate a known result, edit/save/reopen exact text, list/create/read files, launch two independent terminal sessions, switch focus, close one and keep the other responsive. Reboot and verify saved bytes. |
| Linux ELF TUI | BusyBox 1.36.1 vi, separate [pinned profile](../fixtures/applications/busybox-vi-1.36.1.json) | Type/edit through real focused terminal input, display actual ANSI output, save/reopen after reboot, resize, two independent clients and close/crash recovery. Current EX-command file workflow passes; interactive acceptance remains open. |
| Darwin x86_64 Mach-O TUI | Microsoft Edit source commit `cb6de0a8966aecd01d19a3541dab1829d0e679ca`; native artifact acquisition/build still required | The same focused edit/save/reopen/resize/two-client workflow through actual Darwin startup, descriptors and termios. Source review only; zero Space application entries. |
| Windows x86_64 PE TUI | Microsoft Edit at the same pinned source commit; native artifact acquisition/build still required | The same workflow through real Win32 console records/modes/output and file handles, with focused input, independent sessions and cleanup. Source review only; zero Space application entries. |
| Linux ELF CLI | BusyBox 1.36.1, [upstream](https://busybox.net/downloads/); Lua 5.4.7, [upstream](https://www.lua.org/ftp/); SQLite 3.46.1, [upstream](https://www.sqlite.org/2024/) | BusyBox `echo`/`cat`/`wc` and shell pipeline operate on known files with exact stdout/status; Lua computes and reads/writes a file; SQLite creates a database, commits/query rows and reopens it after restart. |
| Darwin x86_64 Mach-O CLI | Lua 5.4.7 and SQLite 3.46.1, built for the declared macOS deployment target | Execute the same Lua/file and SQLite transaction/reopen scenarios through the Darwin process/import path. Capture imports/startup requirements; a hosted Rosemary run is comparison evidence only. |
| Windows x86_64 PE CLI | 7-Zip 24.09 standalone command-line tool, [upstream](https://www.7-zip.org/); SQLite 3.46.1 for Windows | Create/list/extract a known archive, compare extracted hashes and failure exit codes; run the database transaction/reopen scenario with real Win32 file/handle behavior. |
| Linux software GUI | FLTK 1.3.9 `fluid`, [upstream](https://www.fltk.org/software.php) | Launch the actual designer through its Linux GUI backend, type/edit a form, resize, save/reopen its project, open a second instance and prove focused input and independent content. |
| Darwin Cocoa GUI | FLTK 1.3.9 `fluid` built as an x86_64 macOS application | Drive the actual Cocoa/AppKit application: launch, edit, resize/scale, save/reopen, second instance, close and crash cleanup. Use actual client pixels and input delivery. |
| Windows Win32 GUI | FLTK 1.3.9 `fluid` built as an x86_64 Windows application | Drive the actual Win32 message loop and software drawing backend with the same edit/save/reopen/two-instance scenario; verify buffer and handle cleanup. |
| Expanded desktop/browser milestone | NetSurf 3.11, [upstream](https://www.netsurf-browser.org/downloads/), with a declared port/profile | A real browser action launches a live browser instance, renders a bundled HTML/CSS page, accepts link/input/scroll interaction and retrieves a controlled HTTP page; add HTTPS only with certificate/error tests. This is a later workload with its own dependency gate, not a decorative browser window. |

The acquired Linux FLTK workload now has a [pinned artifact, real host edit/save/
reopen reference and actual protected-loader refusal](fltk-gui-workload.md). It
has not executed on Space.

Before a larger GUI toolkit is ready, add a tiny upstream software GUI workload
to expose missing contracts. Keep it as an intermediate checkpoint; neither a
hand-authored surface fixture nor a toolkit demo completes the real-application
rows above. Higher-level text/framework/network/GPU work is driven by the actual
application's observed imports and behavior, not by adding success stubs.

### Local testing and evidence rules

Record each run as one of: artifact/build failure, loader refusal, runtime
failure, scenario mismatch, or scenario pass. Keep `execution_started` separate
from artifact inspection. A loader refusing a real binary is useful evidence of
a gap, but is not a successful application run. Native host execution, Wine,
Rosemary, a stock Linux VM or a reference OS may establish expected output; only
execution through the tested Space image counts toward Space compatibility.

For each app scenario, retain the artifact origin/hash, license/build provenance,
Space/compiler/image hashes, boot/backend configuration, command/inputs, exact
stdout/stderr/exit status, file-content hashes, serial logs and screenshots.
GUI scenarios must include keyboard and pointer interactions, focus changes,
resize/scale, close/reopen and post-close refusal; screenshots alone cannot prove
input routing. Pin reference outputs and allowed rendering tolerances explicitly.
Never run an ordinary acquired foreign app through the trusted CPL0 fixture
invoker to obtain an apparent success; complete its protected process path first.

Run every required scenario from a fresh boot and again in the same session.
Run at least 20 repeated launch/exit cycles and a two-instance interaction/fault
case while checking owned page/descriptor/handle/surface counts return to their
expected baseline. For saves, verify data in a separate process and after reboot.
A timeout, skip, missing toolchain or unsupported API remains a visible failure
or blocker and does not reduce the required acceptance set.

### Delivery order and completion gate

1. Establish versioned real-app acquisition/provenance and attempt/diagnostic
   records now; run existing native applications locally and retain foreign
   loader refusals without calling them successful executions.
2. Implement protected native x86_64 Mach-O execution and generic instance /
   lifecycle primitives; apply those primitives to ELF and PE. Keep the existing
   bounded fixtures as fast semantic regressions.
3. Bring up the three CLI corpus rows through real startup, imports, files,
   terminal and process paths. Use actual missing calls to choose each next
   coherent implementation slice; fix generic compiler blockers in Inauguration.
4. Complete sustained native SCI desktop clients, independent app sessions,
   authenticated focus/seat routing, buffer release and teardown. Verify native
   terminal/editor/files workflows and persistence before relying on them as
   the foreign GUI test platform.
5. Implement each personality's software GUI adapter and bring up real FLTK
   `fluid` applications. Complete edit/save/reopen, two instances, focus, resize,
   scale and failure recovery through the native desktop.
6. Complete browser/network/text requirements, then add audio/GPU and more
   demanding apps with explicit service ownership and new executable scenarios.
   Keep software rendering, original native shell behavior and prior apps green.
7. Run the whole matrix from clean builds and fresh/repeated local boots with
   retained artifacts and no unexplained required failures. Review portability,
   isolation, resource lifetime, license and distribution requirements for the
   exact shipped dependencies. Publish the supported profile/version matrix.

The full goal is complete only when these outcomes and required application rows
are supported and reproducible. Each checkpoint updates the handoff, executable
manifest and draft PR evidence; a passed fixture subset or a plan document is
not completion. Beyond that milestone, keep adding named application scenarios
and fixing the coherent gaps they expose while preserving the supported matrix.

## Completion target for the next milestone

Establish a reproducible compatibility lab on Space:

- Run small ELF, Mach-O and PE fixtures through their actual ABI entry paths,
  record exact results and errors, and repeat runs to detect lifecycle leaks.
- Add executable positive, invalid-input, denied-authority and cleanup checks
  with each supported behavior. Preserve previous assertions and refuse unknown
  operations instead of returning invented success.
- Display one client-owned software surface that changes in response to real
  focused keyboard input, then prove close and post-close refusal. Follow with
  two independently owned clients, focus changes and pointer interaction.
- Keep desktop resolution, scaling, typography, query/selection, layout and
  damage performance gates green. Foreign GUI adapters must not become a reason
  to regress the native desktop or move policy into the nanokernel.
- Record source/compiler identities, commands, results, logs and screenshots.
  State which tests actually executed and which were skipped or blocked.

Each PR should close one behavioral gap with observable evidence. A larger API
count without executed behavior does not satisfy the goal. Do not use a single
percentage of all Linux/Windows/macOS APIs as a coverage metric: the denominator,
ABI version and dependencies would be misleading.

## Immediate pinned application baseline

jq **1.8.1** is the first acquired upstream comparison program for x86_64 Linux,
macOS and Windows. The [manifest](../fixtures/applications/jq-1.8.1.json) pins
official release URLs, byte sizes, upstream SHA256 values and the actual scenario
`jq -nc '[range(10)] | add'` (stdout `45`, exit 0). Binaries remain outside git.
The [local admission runner](../scripts/check-real-app-admission.py) validates
these original binaries with actual Space loader functions in QEMU, twice per
personality, before any heap initialization can overwrite the injected payload.
It never invokes a foreign payload in the trusted CPL0 runner. Host reference
output is labeled separately. A blocked or merely admitted app keeps this
application gate nonzero; loader acceptance alone is not application coverage.

```sh
python3 scripts/check-real-app-admission.py \
  --in /workspace/inauguration/in-cli/target/release/in \
  --apps-dir /workspace/real-apps/jq-1.8.1 \
  --out /tmp/space-real-jq-new --download
```

The larger candidate matrix below remains the full delivery target. Add pinned
manifests and actual workflows as each application is acquired, then replace
admission-only evidence with protected launch, application output and lifecycle
evidence as the runtime becomes capable. Do not alter a real binary into the
special fixture layout and call that unmodified-app compatibility.

## Source-reviewed baseline

The current source supplies kernel-linked translators, bounded trusted foreign
execution fixtures and native SCI display/input proofs. These are different
levels of coverage; preserve that distinction in results. The source baseline
and limitations are described in [personalities](personalities.md), the
[roadmap](personalities-roadmap.md), the [compositor/client contract](compositor-client-split.md)
and the [Rosemary review](rosemary-macos-reference.md).

| Area | Present source coverage | Next evidence needed |
|---|---|---|
| Linux | BSD/POSIX-shaped service calls; bounded ELF serial/read-only file fixtures; a bounded Unix stream-pair fixture and model checks | Broader descriptor operations through actual ELF calls, real process startup/lifecycle, private guest mappings and Linux structures |
| Darwin | BSD-shaped translator, errno mapping and Mach stubs; thin fixed-address Mach-O serial/read-only file fixtures | Private process memory and startup, supported mapping/fixups/imports, Objective-C/framework subset, real Mach contracts where required |
| Windows | Space-local call table, typed bounded handles, paired NTSTATUS/LastError; PE fixture with selected KERNEL32 imports | Additional typed imports with Win32 error/output semantics, process/domain lifecycle, ntdll/Win32 separation and user/window APIs |
| Native desktop | Kernel-linked desktop, command/layout/output/text modules and bounded SPDP/SCI pixel/input proofs | Sustained independent client lifecycle, focused multi-client seat routing, buffer release, resize/scale and fault/disconnect recovery |

This table records source inspection, not a fresh all-green test run. Trusted
CPL0 fixtures do not prove isolated foreign applications. Existing source-level
module extraction does not establish a separately enforced SCI service boundary.

## Upstream research anchors

Reviewed 2026-10-23, pinned to the revisions below. No source was copied into
Space as part of this research. Follow per-file licenses before reusing code or
test bodies; an algorithm or behavior reference is not a dependency decision.

| Project / revision | Inspected source | Takeaway for Space |
|---|---|---|
| ReactOS `e81244349554c4f98a97fdd7fb67d7a1b450eec5` | [ReadFile API tests](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/modules/rostests/apitests/kernel32/ReadFile.c), [NtReadFile tests](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/modules/rostests/apitests/ntdll/NtReadFile.c), [user message queues](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/win32ss/user/ntuser/msgqueue.c) | Keep Win32 BOOL/count/LastError distinct from NTSTATUS/IO_STATUS_BLOCK. Test invalid handles, EOF, zero lengths and output-pointer effects. Message queues and focus are real subsystem work, not a drawing shortcut. |
| Wine `840a939ee526137639665ff5f587224d6a36403f` | [kernel32 file tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/file.c), [ntdll file tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/ntdll/tests/file.c), [win32u driver](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/win32u/driver.c), [Wayland surface adapter](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/winewayland.drv/wayland_surface.c) | Separate foreign API implementation from display backend. Its SHM attach path marks buffers busy until commit and compositor release; borrow the ownership discipline when defining SPDP release, not assumptions that Space already speaks Wayland. |
| gVisor `8938ebcf1c12a6266bdf5a650088e1360777aa94` | [read tests](https://github.com/google/gvisor/blob/8938ebcf1c12a6266bdf5a650088e1360777aa94/test/syscalls/linux/read.cc), [pipe tests](https://github.com/google/gvisor/blob/8938ebcf1c12a6266bdf5a650088e1360777aa94/test/syscalls/linux/pipe.cc), [file syscalls](https://github.com/google/gvisor/blob/8938ebcf1c12a6266bdf5a650088e1360777aa94/pkg/sentry/syscalls/linux/sys_file.go) | Measure observable Linux semantics: partial transfers, nonblocking state, drain-before-EOF, closed peers, descriptor flags and offsets. Keep emulated kernel concepts inside the personality rather than adopting gVisor as Space's kernel. |
| Darling `60ba801decee7a00782f74f6be4c8ffb013f79ff` | [project overview](https://github.com/darlinghq/darling/blob/60ba801decee7a00782f74f6be4c8ffb013f79ff/README.md) | Distinguish Darwin syscall/framework coverage from GUI maturity. Darling describes Linux-hosted runtime and syscall translation with GUI support in active development; it is a comparison target, not a demonstrated freestanding Space dependency. |
| Rosemary `f845f21842c85f6863cfa8a7a749cb945b88994a` | [loader, ABI, framework and GUI review](rosemary-macos-reference.md) | Start native x86_64; explicit imports and software backing stores are useful reference seams. Host libc/SDL/Rust std and raw host pointers must be replaced or constrained by Space contracts. |

The ReactOS ReadFile test carries MIT, while the inspected NtReadFile test
carries LGPLv2.1+. ReactOS is a mixed-license tree, so its project name is not a
license identifier. The inspected Wine files carry LGPLv2.1-or-later headers;
gVisor's inspected tests carry Apache-2.0. Darling's top-level license is GPLv3
and its overview notes separately licensed submodules. Rosemary declares
GPL-3.0-only, while Space has MPL-2.0. Evaluate actual copied/linked components,
not an assumed exemption from placing them in a separate service.

## Executable coverage ladder

Use two independent axes when recording coverage: the entry path and the tested
behavior. A source constant check can guard an ABI number, but cannot stand in
for a guest calling it.

| Evidence level | Required observation |
|---|---|
| Contract | ABI numbers, structure/layout and unsupported-value policy are checked |
| Behavior model | Actual owning functions execute against a controlled model, including refusal and unchanged state |
| Guest fixture | ELF/Mach-O/PE code invokes the real hardware/import path in QEMU and checks return/output/error conventions |
| Protected process | Private CPL3 mappings, startup/exit/fault behavior, guest-pointer validation, denied access and resource lifetime are exercised |
| GUI client | Client-owned pixels visibly change after real authorized input; focus, buffer and close behavior are checked |
| Application | A named unmodified application/version works for a documented scenario through the established contracts |

A named fixture belongs to its actual level. Repeated execution is part of
acceptance, not evidence that a fixed CPL0 runner became a process environment.
When behavior needs blocking waits, interrupts, threads or asynchronous I/O,
first add the corresponding runtime/process contract; do not spin indefinitely
inside the interrupts-disabled trusted runner.

For every added behavior, retain a small evidence record containing personality,
ABI entry, supported arguments, explicit refusals, expected outputs/errors,
required capabilities, positive/negative cases, compiler revision, test command
and artifact location. Report pass/fail/skip counts per suite and evidence level.
Add new cases without weakening old assertions to make the totals rise.

## First implementation sequence

1. **Descriptor semantics across all three personalities.** Keep common VFS
   ownership and bounded buffers, but test each foreign ABI separately. Prioritize
   EOF/count behavior, zero-length transfers, invalid handles/pointers, duplicate
   lifetime, offset/seek and cleanup on exit/return. Linux uses negative errno;
   Darwin hardware calls use carry/positive errno; Windows imports use their
   declared BOOL/handle/count/error conventions. Unsupported modes must fail
   without backend side effects. Add a guest fixture when extending a model.
2. **Protected foreign execution.** Follow the Mach-O slice in the Rosemary
   review, then reuse generic domain/startup/lifecycle machinery for ELF and PE.
   Keep each format's validation, relocation/import and startup rules explicit.
   Add denied kernel/other-client memory cases and repeated fault/exit cleanup.
   Keep generic ABI/compiler fixes in Inauguration and Space policy here.
3. **Software GUI adapter proof.** Make the existing native SCI surface/input
   path sustained and ownership-safe, then translate one tiny guest's software
   backing surface and input events. Do not require a complete Wine, Darling,
   SDL, X11 or Wayland environment before this bounded proof works.
4. **Application-driven expansion.** Choose a small redistributable program per
   personality and record its exact import/syscall/framework requirements. Add
   the smallest coherent missing contract with differential/reference tests,
   rerun the supported scenario and retain previous fixtures. Only then choose
   a larger CLI or GUI application. Metal/Vulkan, browsers and broad desktop
   frameworks remain separate service/backend workstreams.

## Desktop acceptance needed for foreign GUI testing

Keep command dispatch, layout, compositor, seat and application supervisor
separate. Follow the [display/text plan](plans/2026-10-19-display-text-architecture.md)
and [command desktop plan](plans/2026-10-19-command-desktop.md).

- Exercise the supported output modes and scales with two real typefaces,
  legible controls, correct caret/text hit testing and unchanged logical/pixel
  coordinate rules. Add Unicode/shaping support only with actual rendering and
  input coverage; an unknown-glyph box is not full Unicode typography.
- Present client-owned opaque software pixels through bounded SPDP shared
  mappings. Specify stride, extents, orientation, damage, in-flight immutability,
  release and disconnect/revocation before asynchronous rendering. Match alpha
  semantics explicitly before testing transparent windows.
- Prove keyboard and pointer input reach only the focused authorized client.
  Test focus changes, command bar capture/dismissal, close/reindex, stale surface
  identities, two independent client streams and post-close refusal. Extend the
  present selected-ASCII key proof before claiming modifiers, repeats or IME.
- Prove resize/scale transitions preserve content and invalidate only valid
  regions. Inspect actual rendered output as well as geometry/state, and keep
  the existing damage/performance threshold. Test failures and teardown while
  another client remains interactive.
- Enable a launch action only after the supervisor really starts that executable
  with validated grants and reports failure/exit. Focusing an existing terminal
  is focus; a second terminal needs a distinct live session. A decorative window
  or an unavailable browser entry is not foreign GUI compatibility.

## Gates and continuation

Run focused owning-function checks first, then relevant QEMU fixture, SCI and
personality gates. Existing starting points are `check-personality-abi.sh`,
`check-local-stream.py`, `check-darwin-pipe-lifetime.py`,
`check-vfs-shared-offset.py`, `check-posix-wait-status.py`,
`check-windows-wait-result.py`, `check-mmap-lifetime.py`,
`check-darwin-personality.sh`, `check-windows-personality.sh`,
`check-darwin-macho.sh` and `check-foreign-syscalls.sh`.

Desktop work also retains `check-display-output-text.py`, `check-commandbar.py`,
`check-desktop-launcher.py`, `check-desktop-damage.sh`, `check-spdp-sci.py`,
`check-spdp-input.py`, `check-sci-seat.py` and affected boot/runtime gates. Use an
explicit source-built compiler and keep failure artifacts. Update this goal's
linked behavior documents and the working handoff when a slice is verified;
record baseline failures separately from regressions. Keep a draft PR reviewable
through small coherent commits while expanding the next executable gap.
