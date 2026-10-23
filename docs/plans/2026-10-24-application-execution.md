# Full application goal: execution checkpoint

The user explicitly requests continued implementation and real local application
testing until the full goal works. The authoritative destination and completion
matrix are [compatibility-coverage-goal.md](../compatibility-coverage-goal.md).
This checkpoint does not close that goal or narrow its required outcomes.

## Verified implementation

All evidence below comes from local execution, with source-built frozen
Inauguration0.9.324, SHA256
`43b5a2f166efb28ea3123e8030c549d1eac9e90ee7c642d013457ff7ade09168`.
It is not a claim of a single latest whole-tree regression run. Application
provenance and exact binaries live in `fixtures/applications` manifests; no
upstream payload was rewritten into a fixture to count as an application.

| Implementation | Actual evidence |
|---|---|
| Original Linux jq1.8.1 | `/tmp/space-linux-jq-clean-entry21/report.json`:81 app activations,21 repeated cycles, actual private CPL3 execution |
| Unmodified upstream Lua5.4.7 | `/tmp/space-linux-lua-clean-entry21/report.json`:222 app activations; `/tmp/space-linux-positional-lua21/report.json` adds actual pread/pwrite behavior and offset preservation |
| Unmodified upstream BusyBox1.36.1 | `/tmp/space-linux-busybox-clean-entry21/report.json`:100 app activations; echo/cat/wc/printf and basic ash scripts; source-built pinned static configuration |
| Unmodified upstream SQLite3.46.1 | `/tmp/space-linux-sqlite-clean-entry21/report.json`:31 app activations with in-memory SQL, JSON, Unicode, recursive/window queries, transactions, blobs and errors |
| Linux lifetime/security | Each corpus exercises21 cleanup cycles,105 actual guest CPU faults, live authority/pointer denials, same-VA other-domain witness and genuine IRQ-driven infinite-guest cancellation |
| Protected Windows | `/tmp/space-windows-{strict,files,write,application}-sanitize`:507/527/527/317 activations; private mappings and typed ABI/file handling; `/tmp/space-windows-nvme-sanitize`:six independent real NVMe boots |
| Protected Darwin | `/tmp/space-darwin-protected-release-final/report.json`:483 protected Mach-O/import runs; `/tmp/space-darwin-files-names-final/report.json`:464 read-only file/import runs, carry/errno and cleanup; integer-width extension under test |
| Native CLI/storage |11 scenarios; `/tmp/space-native-persistence-storage-final`:three NVMe boots; `/tmp/space-native-large-files-pwrite-final`:57391-byte partial/sparse/truncate/reclaim/remount checks; `/tmp/space-sparkfs-names-final2`:24/25-byte names/deep paths and rollback |
| Native GUI applications | Separate packaged calculator/editor in standard image; `/tmp/space-standard-gui-storage-final`, `/tmp/space-gui-storage-app-final` and `/tmp/space-gui-persistence-eight-byte-boundary`:real input/pixels, exact eight-byte persistence through five NVMe boots, denied storage leaves saved file unchanged |
| Native ephemeral ownership | `/tmp/space-native-lifecycle-private-foreign-2/report.json`:151 normal activations plus136 emitted allocation aborts with stable resources; private registry imports refused |
| Protected initial registers | `/tmp/space-user-initial-state-final/report.json`:16 actual guest activations, GP/XMM/x87/MXCSR sanitization and full kernel restoration; old trampoline independently fails GP/x87/XMM controls |
| Compiler | Full required Rust/native checks,119 conformance cases, Linux differential62 agreements/27 explicit refusals/zero disagreements or crashes, owned native/default CLI tests |
| Integrated lab checkpoint | `/tmp/space-application-lab-review-snapshot/report.json`:all14 then-integrated gates pass with source changes empty; source snapshot recorded separately |

These native SCI apps remain trusted CPL0. Clone page tables and cooperative
capability checks do not provide protection from malicious native code. Foreign
protected process tests run CPL3 with private mappings; they are a separate proof.

## Subsequent verified checkpoint

`/tmp/space-compatibility-expanded-run/report.json` passes all26 compatibility
contract/model/runtime/GUI gates from `/tmp/space-application-expanded-source`,
whose367-file capture has a separate source manifest. The first earlier attempt
lacked NASM in the parent command PATH; the corrected tools run passed25 gates
and exposed a real extracted seat-model dependency missing after the retained
API change. That model now executes the real retained/catalog/context functions
and the new all26 run passes. Failure receipts remain preserved.

Private image/retained ownership is committed in `7b0bcae`; the core gate passes
280 initial/490 resumed entries including70 actual allocation aborts. The GUI
resource observer now passes129 actual sessions, including stale generations
against recycled pages and stable post-warmup resource counts. This repairs the
previous19-session capacity failure. It does not make the tiny proof windows a
usable desktop or protect trusted CPL0 SCI apps. Windows startup now has an
explicit owned TEB/static TLS/CPL3 callback profile (`162c68c`), with171 actual
launches and16 malformed refusals; original Windows jq remains unsupported.
Darwin file/int-width/FS/GS isolation now passes548 activations (`935c460`).
All four Linux corpora pass seeded FS/GS restoration and147 genuine guest CPU
fault probes per21-cycle gate. Canonical SQLite provenance is corrected to a
reproducible relative-input build; its manifest retains the initial absolute-path
artifact and historical receipts separately.

The expanded26-gate application lab passes at
`/tmp/space-application-expanded-run`, with no changed source, compiler or
application artifacts. Added retained/startup/129-session gates increase the
next lab revision to30 mandatory gates, including real SQLite file cases. All30 pass at `/tmp/space-application-thirty-run`, sourced from a separate
383-file snapshot, with source/compiler/application artifacts unchanged. This
receipt predates the later pipe, NVMe, FILETIME and readable-window additions;
it does not claim their integration. A later small successful-only
Volume identity clearing guard is covered by its independent owning-function
gate and is not retroactively included in that snapshot.

## Readable desktop and expanded integration checkpoint

The readable native window profile is now the default (`cf2ccbb`). The final
standard/matrix/persistence/lifetime gates all pass from the same435-file frozen
source at `/workspace/space-application-fiftytwo-source`, with an adjacent source
manifest. Receipts are `/tmp/space-gui-final-{standard,matrix,persistence,lifecycle}`.
The tests cover six output/scale combinations, real keyboard/pointer/focus,
saved eight-byte text and status through resize and five NVMe boots, and129
sessions with stable ownership/resources, peer survival and stale-generation
refusal. These clients still execute trusted CPL0.

The expanded application lab now passes **52/52**, with source changes empty,
compiler unchanged and application artifacts unchanged:
`/workspace/local-evidence/space-application-fiftytwo-run/report.json`.
The snapshot includes the reviewed committed baseline plus37 explicitly captured
GUI/lab paths. Its manifest records that scope; in-flight CPU contexts, native
HPET, Windows environment/QPC and Linux child-process work were excluded rather
than implicitly claimed as integrated. That newer work has separate execution
receipts and needs a subsequent coherent regression run.

Native HPET is committed in `1196fde`, with actual PC/Q35 IRQ-masked progress,
exact hardware frequency and explicit no-HPET refusal. Generic caller-owned CPU
contexts are committed in `d8506fb`;61 actual runs prove separate child/parent
GP/FX state, cold MXCSR validation, typed suspend/exit/fault/deadline and complete
supervisor restoration. These are mechanisms, not general native SCI protection.

## Work continuing now

1. Native private image/global ownership and retained generation handles now
   pass actual same-image/two-live-instance, byte-identical source image,
   interleaved close/reuse and stale-handle checks. Initial and resumed
   compiler-emitted allocation aborts restore exact resources; the latest core
   proof runs350 initial/490 resumed entries with140 emitted aborts. Extend the
   runtime toward protected native execution without weakening these gates.
2. Retained GUI reclamation now passes129 sessions with actual input/pixels,
   peer survival, retired/recycled identity denials and stable resources. The
   old19-session refusal is fixed. The new optional readable profile passes real rendering, pointer focus,
   editing and resize at1024x768/1280x720/1920x1080, at2x/3x scale; high-view
   canvas buffers above4GiB also pass129 sessions and five NVMe boots. Evidence
   is `/tmp/space-gui-readable-highview-{matrix,persistence,lifetime,standard}`.
   The constrained-memory refusal/recovery proof now passes and the readable
   profile is the product default. Protected native execution and broader
   desktop quality remain required.
3. SQLite database files now execute actual transactions,9000-byte blob update/
   rollback and separate-process reopen on RAM SparkFS. Fourteen cases and146
   app activations pass21 cycles with stable lease/descriptor/frame counts at
   `/tmp/space-linux-sqlite-files21-final/report.json`; all prior jq/Lua/BusyBox
   gates still pass. Native identity/mode/range lease APIs and Linux translation
   are committed (`46b4593`, `6017dcb`). Checked native NVMe FLUSH is committed (`08213de`). Original SQLite now
   passes three real NVMe boots with commit/update/rollback and independent
   host `integrity_check` after each boot; its15 actual activations consume
   8/4/0 successful FLUSH completions. The latest ABI-width receipt is
   `/tmp/space-linux-sqlite-nvme-int-width-final/report.json`. Crash atomicity
   and power-loss behavior remain open.
4. BusyBox pipelines. Actual protected pipes now pass220 launches across standard/minimal
   profiles, including partial transfers, descriptor aliases, EOF and SIGPIPE.
   The new copied-process checkpoint passes1012 parent activations across
   standard/minimal roots, including actual partial descriptor-copy rollback
   and retained teardown recovery. Nine original BusyBox child cases pass
   106 additional activations, including pipelines, self-exec and background
   wait. Committed checkpoint `211be9e` bounds preparation retries, preserves
   remaining delivered guest IRQ budget and handles serial CLOEXEC. Its
   omission control proves the cancellation consequence. The larger10902-byte
   pipeline remains a captured failure at4096 bytes; implement genuine blocked
   producer/consumer scheduling without enlarging the ring to hide the gap.
5. Original macOS/Windows startup. Original jq binaries remain refused and
   unexecuted. Windows dependency inspection finds immediate GS/TEB access and
   three TLS callbacks; typed PE fixture success is not UCRT/startup coverage.
   Darwin requires broader Mach-O/dyld/relocation/libc/framework support.
   Windows FILETIME now passes848 protected launches across four real RTC
   boots (`9e7e46e`), with one-second native resolution. Original SQLite/7za
   still fail admission. Actual native HPET-backed QPC and explicit owned
   environment translation are committed in `2de596c`; their gates pass593
   and380 activations respectively. The private process heap (`03fa931`)
   passes485 actual launches and seven admission checks. Real TLS/FLS
   callbacks are under test. A separate Darwin startup profile (`168e01f`) passes344 CPL3
   invocations, exact-memory admission/recovery and old483/548 regressions; this does not supply dyld/libSystem or execute jq.
6. The52-gate lab now passes from the frozen source above. Extend the next
   lab revision to the subsequent native counter/context, Windows environment/
   QPC and Linux process slices after their review checkpoints. Retain exact
   failures; source mutation during a run must invalidate integration evidence.
7. Continue the full matrix: protected native apps, real foreign software GUI,
   display/text/scale/input quality, two-instance independent app behavior,
   clipboard, file roots, process/network services and the named FLTK/NetSurf
   milestones. A fixture window does not complete these application outcomes.

## Review and remote delivery

Local review commits are on `compat/coverage-and-gui-foundation`. Generic compiler
changes are committed separately in Inauguration (`f93ba40d`,0.9.324, and
`0a0a5a2b`,0.9.325). The latter emits generic verified SCI layouts and separates
mutable data on page boundaries. Required checks, including isolated `in update`,
pass; the default Space compiler remains frozen at0.9.324 pending integration. The user
has already authorized opening a draft PR. GitHub currently returns HTTP401
`Bad credentials`; pushing has also failed for missing usable authentication.
No remote draft PR has been created. This delivery blocker does not stop local
implementation or testing. Do not request authorization again or invent a PR URL.

Do not mark the project complete until every required acceptance row has actual
end-to-end evidence. Preserve unsupported behaviors as visible failures and
expand coverage by implementing their owning contracts.


## Expanded integration in progress

The first63-gate candidate uses immutable committed source at
`/workspace/space-application-sixtythree-source` with frozen compiler0.9.325.
It exposed a test-only64KiB artifact-slot bound after compiler page separation;
`4a645dc` reserves nonoverlapping128KiB slots and the complete real GUI action/
pixel check passes at `/workspace/gui-slots325`. A separate persistence harness
failure came from a Unix socket path exceeding its platform limit. The original
run and its exact failures are preserved. The next69-gate candidate uses a short
evidence path and includes committed Linux children, Darwin startup and the
architectural RF context fix (`5fd55cb`). Neither run is claimed passed before
its complete final integrity report exists.

FLTK1.3.9 `fluid` is acquired and source-built without upstream patches. A real
host GUI reference edits/saves/reopens a form. Actual Space protected-loader
admission refuses its dynamic ELF before allocation; this remains blocked,
with no payload execution. See [the workload evidence](../fltk-gui-workload.md).


## Reviewed native protection and Windows local storage

Protected native SCI profiles are committed in `78fdae6`. Independent root
regressions from the exact committed source snapshot pass paged279 and
immutable274 actual invocations plus the32MiB exact-budget refusal/recovery
case. `/workspace/native-core-independent-report.json` links their exact
artifacts/compiler hashes and confirms no snapshot file changed. This does not
switch the trusted shipped CLI/GUI loader. Actual protected GUI clients remain
the next integration step; their staging and accepted presentation buffers have
separate ownership.

Windows TLS/FLS is committed in `66d1290`, after actual callback/context proofs,
3544 activations across eight fresh boots, all14 older regressions and the
reviewed cold-cache admission fix. The final narrow-delta gate passes443 focused
activations plus one cold recovery, with six allocation-free refusals. Original
Windows applications remain unexecuted.

The69-gate run finishes68 passed/1 failed with source/compiler/application
integrity passed at `/workspace/lab69/report.json`. Native GUI interaction,
five-boot persistence and129-session ownership all pass. Minimal Linux children
fail when the fixed-TSC-spin cumulative-budget test returns42 instead of124 on
its eighth measured activation; earlier cycles and the standard counterpart
pass. Preserve that test failure and replace its host-speed assumption with a
robust actual-IRQ witness before claiming complete integration. The69-gate
snapshot predates the native SCI and Windows TLS/FLS commits above.


## Protected GUI and blocking-pipeline checkpoint under review

Protected GUI core3 (`f3e12fd`) separates writable guest staging from immutable
supervisor presentation frames. `/workspace/np-gui-final/report.json` proves
140 protected lifecycle instances, real traps, stale/revoked epochs and hostile
staging writes preserving accepted pixels. Exact low-memory refusal/recovery
passes separately. The frozen-source standard GUI, desktop damage and desktop
launcher regressions also pass; the interrupted launcher attempt is retained,
with the completed rerun in `/workspace/np-gui-launcher-recovered.log`.

The opt-in product calculator/editor use these actual protected services.
`/workspace/local-evidence/gui-protected-readable-standalone/report.json` passes
all six output/scale combinations with actual keyboard/pointer and exact pixels.
`/workspace/local-evidence/gui-protected-readable-129-sixth/report.json` passes
129 sessions/258 instances with exact resource recovery, peer interaction, stale
identity refusal and no remint after revoking the launch grant. Earlier capacity
and ownership failures remain preserved. Persistence and manager fault gates
are being finalized; shipped default clients remain trusted CPL0.

The final blocking scheduler keeps the native ring at4096 bytes and makes the
previously failing upstream10902/110000-byte pipelines work. Standard evidence
is `/tmp/space-linux-busybox-blocking-terminal-standard-final21/report.json`;
minimal evidence is
`/workspace/linux-blocking-app-terminal-minimal325-final21/report.json`.
Each passes122 actual upstream activations. The exact110000-byte numbered output
hash matches the input:
`1c7898d6f3630eeddf65917d04f0a07a421f1192d6a6acd122108b5fc747af57`.
The14-case blocking and23-case child suites pass308 and506 activations per root.
[The focused evidence](../linux-blocking-tests.md) records terminal-priority,
retry authority/mapping and actual IRQ controls. These are separate reviewed
receipts; they do not turn the historical69-gate failure into a passing run.

Windows critical sections (`96ef514`) pass654 focused activations and all15
older gates. Eager Mach-O chained imports (`174d708`) pass254 executions and
complete unused-import validation. Original Darwin/Windows applications still
refuse admission. API composition and the separately owned Darwin heap are the
next active implementation slices.


## Subsequent composition and heap commits

Windows composition is committed in `4327d14`. The explicit owned launch
descriptor combines the verified service groups without widening old profiles.
`/tmp/space-windows-composed-final/report.json` passes773 activations across
PC/Q35/no-HPET; all16 older regression gates pass, with matching owned source
hashes audited separately. Original Windows binaries remain refused.

Darwin heap revision2 is committed in `eef4ea8`.
`/tmp/space-darwin-heap-checkpoint275/report.json` passes275 actual executions
over21 stable cycles, including record exhaustion, coalescing, realloc failure
preservation, live revocation, heap/metadata protection and exact cold recovery.
The old254/344/483/548 gates pass unchanged. `ec6379b` pins inspection-only
Lua5.2.4 artifacts and explicitly records unknown build provenance; neither
artifact was executed and the Lua5.4.7 full-goal row remains unchanged.

The83-gate integrated lab is running from the552-file committed `ceef6f7`
archive at `/workspace/space-application-eightythree-source`, with adjacent
source manifest, frozen0.9.325 and evidence under `/workspace/lab83`. It excludes
the later Windows composition, Darwin heap and in-progress protected GUI
consumers. Independent desktop launcher and damage checks on this exact archive
pass actual PS/2 interaction/pixels and322 fps against the30 fps minimum.
Their logs are `/workspace/desktop-{launcher,damage}83.log`. Full integrated
success is not claimed until the final lab/integrity report exists.


## Completed83-gate integration and subsequent checkpoints

`/workspace/lab83/report.json` finishes83 passed/0 failed, integrity passed:
source changes empty, compiler unchanged and application changes empty. The
552-file committed `ceef6f7` archive remains at
`/workspace/space-application-eightythree-source`, with adjacent manifest.
It includes the committed blocking scheduler, eager imports, Windows TLS/FLS
and critical sections, and protected native SCI/GUI core/package gates. It
excludes later Windows composition/Darwin heap, readable protected consumers,
Unicode and default desktop integration. The earlier69-gate failure stays
preserved; this new complete result does not rewrite its timing-dependent
failed assertion.

Readable protected consumers are committed in `aa16a9e`, with the startup
ownership helper in `8e5c4f6`. All final gates pass from the541-file immutable
`/workspace/gui-protected-consumer-startup-final-source`: six output modes,
five NVMe boots,129 sessions/258 instances, six actual peer-failure recoveries
and140 failed input starts with exact cleanup. Receipts are under
`/workspace/local-evidence/gui-protected-*-startup-final`. Required desktop
launcher and damage checks also pass. Default image/command-bar integration
is a separate active checkpoint with its own actual-image gates.

Windows Unicode is committed in `aeeca40`.
`/workspace/wunicode/umax/report.json` passes4921 actual CPL3 activations and
3410 scalar QEMU vectors; independent source models pass3410 cases each in
default/lean/harden. The mixed-service gate passes773 activations and all17
older gates pass. The final run had zero natural RTC retries; the earlier
125 outcome remains preserved with uncaptured raw CMOS cause. Original Windows
applications remain refused; static supported-import counts are not executions.

Original Mach-O planning is committed in `4b05534`.
`/workspace/di/wired/report.json` compares all3840 plan bytes with an independent
host parser, checks1357 genuine links/136 imports, unknown commands and malformed
metadata, and returns unavailable-import -38 before mapping. Original jq and
Lua are never entered. Native address-space ownership is now being implemented
as a reusable mechanism before the larger high-VA mapper or Linux vfork.
