# Fixture boot layout repair

The expanded151-gate integration at `/workspace/lab151/report.json`, source
`34239e7`, finishes136 passed/15 failed, with source/compiler/application integrity
passed. It preserves failures from old injected-fixture reservations. The kernel
grew past the old1.5MiB reservation; for example the protected Windows probe's
kernel has1,613,208 bytes and ends at physical `0x289d98`, overlapping the old
`0x280000` fixture slot. The guard correctly stopped execution. This is not a
successful application/guest run and the original receipt is not rewritten.

The fixtures now occupy explicit free slots below the unchanged `0x300000`
kernel heap. `scripts/boot_fixture_layout.py` checks page alignment, the whole
kernel extent, nonempty payload, and fixture/heap separation before constructing
an output. It preserves all input bytes. Existing individual payload-size limits
remain. No image, import, memory, IRQ, lifetime or performance limit is raised.

| Fixture cohort | Physical staging |
|---|---|
| Single PE, legacy hand-authored foreign image, input or surface SCI | `0x2f0000` |
| Raw CPU/context fixture | `0x2e0000`; a separate private SCI stays at `0x2f0000` |
| Input plus two small SCI clients | `0x2d0000`, `0x2e0000`, `0x2f0000`, existing64KiB slot limits |
| Input plus calculator/editor SCI applications | `0x2b0000` input64KiB; `0x2c0000` and `0x2e0000` retain128KiB application slots |

The native shell's legacy fixture entrypoints and the hand-authored ELF/Mach-O/
PE headers move together. Kernel IRQ helper origins and physical callback offsets
move together. Protected guest virtual addresses stay unchanged. No acquired
original application bytes, preferred bases, ELF/Mach-O/PE rules or32-import
execution bound were altered. These physical addresses are test-image placement,
not a new foreign ABI or component transport.

Twelve host packing controls check exact input/padding/payload preservation and
refusal for overlap, heap overflow, empty payload and invalid/unaligned addresses.
The same oversized kernel must still fail at the old slot and succeed only when
the fixture moves to a safe slot. Focused QEMU repeats pass protected Windows
process/environment behavior, native IRQ preservation, actual CPU context
suspend/resume, legacy native GUI input/content/close checks and all trusted
foreign output/file/stream fixtures. The first context repeat caught two old
physical FPU-helper offsets and remains preserved separately from its passing
corrected repeat.

Space CI first advanced to the tested Inauguration 0.9.325 implementation
`0a0a5a2baf8ebe105df73f93820a72048da164d1`, published for review in
[compiler draft PR446](https://github.com/tschk/inauguration/pull/446).
The previous 0.9.251 pin failed at the project-build step in run40091348021;
its failed run remains separate. The 12 layout controls and 99 file-control
model checks are also included in the revised CI recipe. The full application
lab remains separate from that smaller artifact-free CI subset.

The corrected compiler pin builds successfully in hosted run40091839291, which
then fails in its test step. Local recipe replay identifies the stale
`check-local-stream.py` extractor: it copied intervening top-level declarations
twice and omitted the native discard-tag validation now called by `vfs-close`.
The harness now extracts each function through its own closing brace and includes
those actual provider dependencies. All original stream/file-adapter assertions
pass under default, lean and harden at
`/workspace/space-ci-local-stream-corrected2.log`. No provider or assertion is
changed to accommodate the test. The earlier failing outputs remain preserved.

The complete matrix must be rerun from a new frozen source; focused repairs do
not turn the earlier151-gate failure into a passing run. Adding the shared layout
gate makes the next cached-artifact matrix152 gates. This does not complete the
[full application/desktop goal](../compatibility-coverage-goal.md).

One additional failure was the lifecycle probe image exceeding the unchanged
2MiB image allowance by13,168 bytes after appending nine private fixtures. That
instrumented test now explicitly packages its CLI/library/demo cohort (all kinds
5..19) plus all private cases. The unused GUI cohort (kinds20..22) stays in the
ordinary image and dedicated GUI gates. No CLI scenario, repeated cycle, abort,
capacity or resource assertion is removed: the focused repeat passes all81
scenarios, including70 repeated calc/checksum cycles. Its receipt records both
the original standard image hash and the explicitly retained/excluded kinds.

The follow-up address audit found a separate historical diagnostic outside the
application matrix: `check-real-app-admission.py` still appended whole original
applications at the old low fixture address. It now uses separate QEMU raw
loaders at `0x08000000` for the exact original bytes and `0x07ffffe0` for its
32-byte descriptor, with independent kernel/heap, acquisition and RAM guards.
No original image header, preferred address or validator rule is changed.
`/workspace/legacy-admission-relocated/report.json` records two boots each for
the pinned Linux, Darwin and Windows jq artifacts: all six validator calls
refuse, all three applications are **blocked**, and there are zero test errors
or foreign application entries. Its expected exit status is 1. This diagnostic
only measures the old trusted in-place validators; it says nothing about the
newer protected personality execution profiles, where original Linux jq runs.


The fresh frozen `c408746` source now passes **152/152**, including all previously
failing layout gates, with source/compiler/application integrity passed. The
720-file receipt is `/workspace/lab152/report.json`, SHA-256
`8c5227678bbfa5aacb99dcb1ce74f6d5f638cc797c2f91de31faaea4407c4a70`.
The failed 151-gate run remains unchanged. Later diagnostic and CI-harness
repairs above have separate focused evidence.


The final CI pin advances to `8530dd3a99cca7de38db50772ddcbde5d0b77745`
after current-Clippy cleanup in that same compiler draft. Local extended unit
checks pass 2,850 tests with one existing ignored test; all-target extended
Clippy, formatting, cargo check, target matrix, `in update`, owned-native and
default integration suites pass. Existing platform skips and 16 tolerated
polyglot evaluation warnings remain explicit. The rebuilt release compiler is
byte-identical to the frozen binary used for all 152 Space gates. Separate
proof: `/workspace/compiler-ci-fix-proof.json`. Hosted Space run40092713741 passes
both build/test and website jobs at Space source `23eb877`, before the final
compiler-pin/documentation/screenshot commit. Later CI runs retain their own
source scope.
