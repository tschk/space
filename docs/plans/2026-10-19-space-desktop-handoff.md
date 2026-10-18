# Space / Subspace / Inauguration handoff — 2026-10-19

## Start here

Read [the next-agent goal statement](2026-10-19-next-agent-goal.md) and
[the cross-repository architecture](2026-10-19-three-repository-architecture.md).
The user's priority is a proper hypermodular OS platform, substantial architecture
planning, resolution/scaling and multiple genuine typefaces. Build an original
command desktop inspired by basic niri tiling and Raycast/Rover interactions.
Evaluate mature compositor/text infrastructure before expanding a from-scratch
renderer. Do not redefine the destination around the current framebuffer demo.

Space `AGENTS.md`, `architecture.md`, `sci-schema.md` and the existing compositor
and personality contracts remain authoritative. The
[display/text architecture](2026-10-19-display-text-architecture.md) specifies
output transactions, coordinate transforms, typeface roles/fallback/shaping,
buffer ownership and the service graph. The
[command desktop plan](2026-10-19-command-desktop.md) defines the shell boundary.
No compositor dependency, new font asset or private source was imported.

## Current checkouts

- **Space:** `/Users/undivisible/projects/space`, `main`. Previously published
  `ccc1f44` defines direction and `f59757a` records the hypermodular contracts.
  Command-bar checkpoint `fcdbdf2` extracts the modules and carries the verified
  action/model changes. The expanded architecture accompanies this handoff.
  Preserve untracked `vendor/`.
- **Subspace:** `/Users/undivisible/projects/subspace`, existing `master`, clean
  at inspection; local revision `ea1ac5d` validates system/board IRQ ranges.
  This checkpoint does not edit or publish Subspace code. Follow its own AGENTS.
- **Inauguration:** active continuation checkout
  `/Users/undivisible/.codex/worktrees/compiler-loop-continuation/inauguration`,
  `main`, last local commit `67d01e15` (0.9.320). Preserve its uncommitted
  0.9.321 callable work and `in-cli/vendor/`. Do not substitute the separate
  dirty `/Users/undivisible/projects/inauguration` checkout for editing.

Existing authorization covers logical verified commits/pushes and compiler patch
bumps, with parallel agents and primary integration. No new branches, tags,
crate publication, deployment or device flashing. Never use Grok/Oracle. Native
agents were the available fallback for bounded work; preserve scratch proposals.

## Implemented desktop checkpoint

`components/display-commandbar.in` owns bounded query/selection, candidate
availability and one dispatch path for keyboard/pointer. Existing windows precede
five actions: tile windows, close focused, minimize focused, focus terminal1/2.
Filtering remains prefix ASCII with four visible rows; typing finds commands
beyond those rows. Terminal focus restores an existing session; it does not launch
a new terminal. Browser, floating and scrolling commands are not faked.

`components/display-layout.in` owns titlebar-aware horizontal tiling over the
current window geometry. It validates minimum size before mutation, includes
margins/gaps/taskbars, preserves content and damages old/new frames. Tiling and
close/minimize cancel stale drag state. Minimize selects a visible focus or none;
hidden/out-of-range targets reject key input. The display backend retains drawing
and input adapters. These modules are still kernel-linked, not isolated services.

Command labels use an initialized table of immutable image-string addresses and
a typed setter, matching the existing window-title address ABI. This was necessary
because direct String returns from an Int function passed boot emission but failed
standalone SCI verification. Do not undo that distinction or bypass the verifier.

## Verification evidence

Pinned final compiler:
`/Users/undivisible/.codex/worktrees/compiler-loop-continuation/inauguration/target/verification/scoped-value320-installed-release-r3/in`,
SHA256 `432b167183a7ab94d61c1dd26e48dce58324e70aeebd5118a2c7f4f2a9609d04`.

- `python3 scripts/check-commandbar.py --in <pinned-in> --out <fresh-dir>`:
  **72 checks passed**, actual JIT evaluation/native execution across default,
  lean and harden. Receipt `/tmp/space-command-model-final-r5/results.json`
  pins source/compiler/runner/generated artifacts. Model adapters intern ASCII
  pointer bytes into bounded memory; they do not prove the real SCI ABI.
- `python3 scripts/check-desktop-launcher.py --in <pinned-in> --build-dir <fresh-dir>`:
  **final fresh-kernel QEMU pass**, receipt
  `/tmp/space-command-desktop-final-r7/receipt.json`. Tests retain original PS/2,
  query/focus/no-match, pointer, close/reindex and Escape coverage; add keyboard
  and pointer tiling, exact frame geometry, minimize/restore, terminal input and
  stale-action refusal. Primary inspected command-bar and tiled screenshots.
  Final kernel SHA256 `c9ce3a65b1b698d2ad009dba6f75f3bea2dd065e3e03a2af165c506f37d00b51`.
- QEMU smoke/hardening **passed** using the pre-label-storage checkpoint kernel;
  final fresh QEMU boot also passed. Kernel contracts **22 passed**; SPDP contract
  **41 passed**; SCI metadata contract **57 passed**. Artifacts/logs are
  `/tmp/space-command-smoke-r1.log`, `/tmp/space-command-spdp-r1.log`,
  `/tmp/space-command-sci-r1.log` and `/tmp/space-command-contracts-r1.log`.
- `check-personalities.sh` **passed** with pinned compiler via
  `/tmp/space-compiler-320-shim`: Windows/Darwin demos, 22 Mach-O refusal/return
  scenarios, foreign Linux/Darwin/Windows serial/file fixtures and Linux streams.
  Final-source log `/tmp/space-command-personalities-final-r2.log`; this is scoped
  regression evidence, not arbitrary app compatibility.
- Subspace `bun test`: **70 passed, 0 failed**, 317 assertions; log
  `/tmp/subspace-handoff-bun-test-20261019.log`. Full embedded QEMU/MPU/SCI-E/UF2
  gates were not rerun in this desktop checkpoint; hardware flashing was not run.

## Known failures and scope limits

`check-runtime-components.sh` with the final label representation reaches
`in: missing return value in pci-read32`. An isolated **unchanged HEAD baseline**
with the same pinned compiler fails identically:
`/tmp/space-runtime-baseline-320-r1/compile.log`; changed runtime attempt is
`/tmp/space-command-runtime-r3.log`. The empty imported native stub is a general
compiler compatibility issue, not proof the runtime components work. Repair it
with a generic regression in Inauguration before claiming this gate passes.
Do not copy kernel implementations into standalone components to hide it.

The damage-rendering gate **fails its unchanged 30 fps threshold on both images**:
final kernel 100 frames/1387 ticks = 7 fps, unchanged baseline 100 frames/1683
ticks = 5 fps in sequential runs. Logs are
`/tmp/space-command-damage-final-r2.log` and
`/tmp/space-command-damage-baseline-r2.log`. These host runs do not establish an
improvement or a root cause; both miss the gate. Preserve the threshold and
investigate compiler/backend/presentation cost before a performance claim.

The benchmark script previously leaked QEMU when its threshold check failed under
set -e. Its EXIT cleanup is repaired without changing the threshold or failure
status; both final negative runs exited1 and left no owned test QEMU processes.
Earlier leak-affected measurements remain in r1 logs and are not the comparison.

Earlier QEMU runs exposed timing-dependent stale captures/dropped paced input.
The updated runner waits for bounded observable frame/selection/query transitions
and retains the original assertions. Failed artifacts under
`/tmp/space-command-desktop-full-r*` and the original baseline are preserved.
This does not establish a responsive production event/presentation pipeline.

Still absent: multi-resolution/scale runtime support, multiple real faces,
Unicode shaping/fallback, stable generation-keyed window handles, floating restore,
scrolling columns, independently launched terminal sessions, real browser,
Wayland client execution and fully isolated interactive SCI desktop services.
See the display/text plan for prioritized evidence, not just feature names.

## Parked compiler work

0.9.321 remains unpublished and must not be used as the verified OS baseline.
It adds exact function-item/pointer source facts, alias provenance, indirect calls
and shared validation/C backend work. Existing receipts live under that checkout's
`target/verification/`:

- `scoped-value320-published-r1.json`: preceding 0.9.320 publication/gates.
- `nested-alias321-runtime-r3/results.json`: 60 candidate checks +22 references
  passed with immutable debug-r2.
- `callable321-runtime-r1/results.json`: 84 checks +28 Rust references; 24 failures
  remain for conditional joins/dynamic selectors across JIT/native/profiles.
- `callable321-operator-focused-r1.log`: 8 passed, 2 failed. `item_not` lacks Invalid
  proof; high-bit test assumes recursive folding that shallow fold_expr lacks.
- `callable321-generic-alias-origin-r1/results.json`: generic forwarding aliases
  lose exact specialization origin (18 checks, 6 Rust references).
- C declaration-order patch remains scratch-only at
  `callable321-c-declaration-order-proposal/candidate.patch`, SHA256
  `7181ec311a23be1f98a6d207a20fd193a40e0fc23fde82f6907a2eb415d9321d`.

Collect current source and revalidate receipts before editing. Compiler commands
use `AR=$(xcrun --find ar)`, target dir
`/Users/undivisible/projects/inauguration/in-cli/target`, jobs1 and offline Cargo.
Follow its AGENTS: focused tests, fmt/check/strict Clippy/full Cargo, source-built
update, matrix/owned-native/default integration/selfhost/protocol and relevant
benchmark gates before publishing a patch bump. Do not weaken source proofs or
ordinary language exception propagation to pass OS boot fixtures.

Final checkpoint receipt: `target/verification/command-desktop-checkpoint-final/receipt.json`
pins logs and source identities, including known failures. These local artifacts
may need regeneration on another machine; commands and tests are checked in.

## Next actions for another agent

1. Read the goal/architecture documents and revalidate checkouts, receipts and
   published revisions. Resolve the recorded compiler/runtime and damage-gate
   failures as appropriate; keep their baseline evidence intact.
2. Make the reuse decision with a bounded Space port spike, then implement output
   mode/work-area/logical-to-pixel contracts and a real multi-typeface text path.
   Test resolutions/scales, pitch/format, metrics, fallback and rendered input.
3. Advance the actual SCI surface/seat/client lifecycle and capability boundaries;
   keep shell, layout, compositor, text, input and app ownership modular.
4. In Subspace preserve static memory, authoritative .in topology, exclusive
   peripheral grants, typed ports, MPU denial, fault fail-stop and SCI-E/board
   boundaries; run its affected gates before any embedded claim/publication.
5. Repair Inauguration's concrete general correctness gaps and publish only with
   full compiler gates. Preserve the broad OS goal; this checkpoint is groundwork.

The overall goal remains active. No completion, isolation or compatibility claim
is implied by this handoff.
