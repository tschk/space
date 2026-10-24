# Protected client typography continuation

The full desktop/application goal remains OPEN. The native shell and new
terminal use measured DejaVu coverage, while the default protected calculator/
editor still render enlarged8-row strikes. Improve the actual CPL3 clients,
without moving their text or pixels into the supervisor/compositor.

Reuse the existing pinned offline DejaVu atlas, license and mature rasterization
pipeline. Each client owns decoded mono/sans coverage and measured advances in
its existing bounded heap. Keep font parsing/shaping out of the kernel; the
initial profile remains ASCII and does not claim full Unicode text semantics.
At existing configuration scales2/3, select14/21px glyphs with16/24px tiles and
stable10/15px terminal cells. Framebuffer stride, clipping, accepted snapshots
and exact-generation presentation keep their current native contracts.

Share window decoration/content layout independently of the chosen text
provider. Legacy bitmap clients retain their old provider and pixel oracles.
Protected SCI clients select a client-local mature-font provider. This source
library seam is not another IPC fabric or isolated font service; the actual
existing protected SCI domain owns the font state and canvas.

Validate native client startup/allocator refusal, the actual emitted SCI policy,
all six output/text sizes, exact independently rasterized labels/content/caret,
real editing/focus/pointer/resize/close/reopen, persistence and fault lifecycle.
Preserve the old visual baseline and failures; do not weaken pixel assertions
or raise image/heap bounds to fit larger assets. Inspect actual QEMU captures
and keep ordinary desktop launcher/damage behavior passing.

The first actual candidate at`/workspace/protected-font-windows1/report.json`
passes all six output/text sizes with independent Pillow/TTF pixel expectations,
interior edits, caret positions, pointer/keyboard focus, resize preservation,
close/survivor/reopen and shell return. Protected startup/descriptor/allocator
models and legacy window contracts pass all three compiler profiles. These are
candidate receipts; final committed-source regressions are recorded separately.
This does not widen the frozen161-gate run or the older bitmap captures.

Final focused checks at frozen`94799a9` are recorded in
[`2026-10-25-protected-font-evidence.json`](2026-10-25-protected-font-evidence.json).
Protected and distributable default clients pass all six configurations,
independent mature-font pixels, editing/caret/focus/pointer/resize/close/reopen,
malformed peer/fault/abort/deadline recovery, both five-boot NVMe persistence
workflows and both129-session lifetime suites. The old bitmap window suite
also passes all six configurations. Desktop launcher/input/pointer/resize and
133fps damage (minimum30, under concurrent QEMU verification) pass.

The new standard image is2032208 bytes and its protected SCI images remain
inside the existing reserved boot window. The image/heap bounds, capabilities,
native surface protocol and refused-input checks were not widened. Actual
[QEMU captures](../screenshots/2026-10-25/README.md) show the resulting clients.
These are native applications, not original Windows/macOS GUI applications.
