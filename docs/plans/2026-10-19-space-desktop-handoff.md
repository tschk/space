# Space desktop handoff — 2026-10-19

## User direction and active goal

Build a new, creative desktop tailored to Space. `tschk/alpenglowed` is the visual and interaction reference. Wayland and Budgie are potential sources of reusable plumbing and ideas, not a one-to-one implementation target or required finished session. This supersedes the earlier stock Wayland + Budgie port target in the working-OS plan.

The active thread goal covers an executable native desktop prototype, selective compatibility integration, preserved boot/personality regressions, generic compiler support when needed, parallel investigation and verified logical commits. Existing commit/push authorization persists. No deployment, release tags or crate publication is authorized by this handoff.

## Verified scope and limitations

Current repository inspection finds a framebuffer desktop, display/input services, fixed-size SPDP messages and initial bounded local stream transport. Read `docs/plans/2026-10-16-working-os.md`, `docs/compositor-client-split.md`, `architecture.md` and repository AGENTS before implementation. Historical QEMU evidence is recorded in the working-OS plan; those tests were not rerun for this handoff. No upstream Wayland client, labwc, GTK or Budgie execution on Space is established. Foreign fixtures do not establish arbitrary Linux/macOS/Windows application compatibility.

Reference inspection now completed: local Alpenglowed at `2bdb63e0207b91ebf6ccb7b162a0f504b8adf8c7` and an authorized local clone of the private Rover reference at `55a4b8089c12d0b5588c4bf5b1d04325d31e99e1`. Reuse their query/result/selection/action separation as an idea; no code was imported. Rover is a macOS launcher, not an OS compositor. Its WebKit and platform integrations do not run on Space. See `2026-10-19-command-desktop.md` for the clarified niri-like layout and command-bar direction.

## Next executable slices

1. Reference inspection and the command-desktop specification are recorded. Next diagnose the baseline launcher-render failure, then implement shared window/action dispatch; preserve working input and focus behavior.
2. Prototype one coherent launcher/workspace/window interaction on the existing framebuffer path. Render it under QEMU and exercise keyboard, pointer, focus, dismissal and client launch. Inspect actual output, not just a saved screenshot.
3. Independently investigate reusable compatibility plumbing: descriptor transfer, shared memory, event waits, library loading and a software display/input backend. Require a real upstream shared-memory Wayland client with pixels, frame/release callbacks, input and clean teardown before claiming support.
4. Review actual diffs, run affected desktop/SCI/boot/personality gates and publish logical verified changes. Keep OS product policy in Space; compiler changes must remain general in Inauguration. Check dependency licensing before importing code; this handoff adds no upstream dependency.

## Checkouts and concurrent compiler work

Space checkout: `/Users/undivisible/projects/space`. At handoff start it had only untracked `vendor/`; preserve it. This handoff changes documentation only.

Compiler continuation checkout: `/Users/undivisible/.codex/worktrees/compiler-loop-continuation/inauguration`, branch `main`. Preserve the separate original `/Users/undivisible/projects/inauguration` checkout and untracked `in-cli/vendor/`. Last locally verified commit is `67d01e15` (0.9.320); the preceding compiler handoff records full publication evidence in `target/verification/scoped-value320-published-r1.json`. Do not infer remote state without checking it.

Uncommitted 0.9.321 implements exact Rust function-item/pointer source evidence, alias provenance, general indirect calls, shared source validation and C invoke fixes. It is NOT ready to publish. Source snapshot `nested-alias321-source-r7.json` predates the latest operator guard. Immutable debug-r2 binary SHA256: `432865116c0405c04da65a5b2f29c0cd8106dc30518507038e2335775f671e26`.

Observed verification:

- `nested-alias321-runtime-r3/results.json`: all 60 candidate checks and 22 fresh Rust references passed.
- `callable321-runtime-r1/results.json`: 84 candidate checks completed against 28 Rust references; 24 failures remain across conditional item joins and dynamic selector calls with zero/one/two arguments, on both JIT/native and all three profiles. Do not weaken those checks.
- `callable321-focused-r5.json`: codec, scoped, ordinary source context, generics and alias-origin groups passed. C group failed 1/4: generated global function-address initializer precedes the function declaration (`safe_target` undeclared). Scratch repair is ready at `target/verification/callable321-c-declaration-order-proposal/candidate.patch`, SHA256 `7181ec311a23be1f98a6d207a20fd193a40e0fc23fde82f6907a2eb415d9321d`; not integrated or tested.
- Operator guard scratch patch was reviewed and applied to actual source. It rejects invalid callable scalar operations before integer erasure and uses existing unsigned comparison lowering. Its focused Cargo test (session `85940`) is terminal: 8 passed, 2 failed; log `target/verification/callable321-operator-focused-r1.log`. The high-bit test assumes recursive folding that `fold_expr` does not provide; `item_not` still lacks Invalid proof.

Compiler work is parked for the desktop goal. Generic alias evidence is retained in `target/verification/callable321-generic-alias-origin-r1/results.json`: 18 candidate checks against 6 fresh Rust references confirm unresolved specialization provenance. Dynamic selector diagnosis remains unfinished. Desktop workers are scratch-only: `review_hotfix` investigates the baseline screenshot failure; `harden_init_review` prepares shared command dispatch and bounded tiling; `count_type_review` completed reference inspection. Source modifications while Cargo is compiling are prohibited by the current verification procedure.

Compiler commands use `AR=$(xcrun --find ar)`, `CARGO_TARGET_DIR=/Users/undivisible/projects/inauguration/in-cli/target`, `CARGO_BUILD_JOBS=1`, `CARGO_NET_OFFLINE=true`. Read compiler AGENTS. Before publication require focused regressions, fmt/check/strict all-target Clippy/full Cargo, source-built `in update`, target matrix, owned-native, default `in test` including exact-source selfhost, protocol check, actual diff inspection and fresh optimized acceptance. Run `in bench` for runtime timing/performance changes. Freeze and hash each candidate; retain failing receipts.

## Handoff validation

Documentation-only: run `git diff --check`. No OS execution or new desktop behavior is claimed by this handoff. The goal remains active.

## New baseline evidence after reference inspection

Ran `python3 scripts/check-desktop-launcher.py --in /Users/undivisible/.codex/worktrees/compiler-loop-continuation/inauguration/target/verification/scoped-value320-installed-release-r3/in --build-dir /tmp/space-original-desktop-baseline-20261019`. Kernel built and booted. Keyboard next/previous/filter/reset selection reached expected serial focus markers. The run FAILED at launcher panel pixel assertion (`launcher panel absent`); primary visual inspection of `launcher-util.png` confirmed the bar absent despite the last serial marker saying opened. This needs diagnosis before claiming a clean baseline. QEMU was cleaned up by the runner. Keep this failure receipt; do not weaken the assertion.

Compiler operator focused test has now terminated: 8 passed, 2 failed. The high-bit comparison test incorrectly expects shallow `fold_expr` to recursively fold its children; `item_not` still lacks Invalid evidence and requires investigation. Uncommitted compiler candidate remains unpublished. The live-session note above is historical; do not restart it without checking current state.

## Architecture priority clarified by user

Hypermodularity and respect for the existing nanokernel/compiler/SCI design take
priority over adding desktop features to the current monolith. `AGENTS.md` now
records the layer/authority contract, current isolation limitations, native-call
ABI boundary, desktop module responsibilities and verification requirements.
Canonical architecture, README, command-desktop and compositor/client documents
are updated consistently. New action/layout work must be independently testable
and module-owned, reuse SPDP/channels and retain a path to actual SCI services;
file extraction alone is not an isolation claim.

## Baseline replay and proposed implementation

Unchanged-kernel replay completed all existing desktop interaction and pixel
assertions successfully in `/tmp/space-desktop-settle-20261019/`. Four launcher
samples at 0/1/3/6 seconds each measured 150324 panel pixels and 792 accent
pixels. The original failure remains preserved; timing is a hypothesis, not a
proven root cause. No production assertions were removed or reduced.

A modular first-slice proposal is ready, not applied:
`target/verification/commandbar-proposal/commandbar.delta.patch` SHA256
`67860e1231e460872ecb127a65bbe6d47ca89d5189ba1dfaf789434e342349ef`.
Consult the actual `ready.json`/hash before use (the patch SHA should be verified,
not trusted from prose). Command state/filter/dispatch is in
`display-commandbar.in`, geometry in `display-layout.in`; display keeps rendering
and device input. Five actions cover tiling, close/minimize and existing-terminal
focus. Shared lookup serves keyboard, pointer and rendering. A 54-case checker
and QEMU extension plan are prepared but unrun. Floating, scrolling columns and
new terminal/browser component launch remain required later work. Primary must
review the proposal against updated AGENTS before applying it.
