# Compatibility and GUI coverage checkpoint — 2026-10-23

Continue the user's ongoing [coverage goal](../compatibility-coverage-goal.md):
increase executable Linux/Darwin/Windows behavior and desktop quality so real
GUI clients can be tested. Keep a draft PR reviewable through coherent commits.
This records completed work and next acceptance gates; it schedules no background
work and does not claim general application compatibility.

## Checkout and implemented slice

Space: `/workspace/space`, branch `compat/coverage-and-gui-foundation`, based on
`457bb24b57800ac111d1ec8d12f7af2664afc8f1`. The first commit records pinned
Rosemary, ReactOS, Wine, gVisor and Darling research and the coverage ladder.
No upstream code, library or asset was imported.

- `foreign-exec.in` now dispatches Linux syscall 8 and Darwin Unix-class syscall
  199 to execution-owned, storage-granted file seeking. The shared file fixture
  checks denied host/closed descriptors, invalid whence/negative targets without
  offset mutation, tail reads, CUR advancement, rewind and zero-byte reads.
  Both exit and ordinary-return variants run twice. Existing error conventions,
  denied storage and descriptor cleanup assertions remain.
- Windows PE `ReadFile` fixtures now check a boundary-crossing output-count
  pointer refuses without changing a buffer sentinel or consuming file data,
  and zero-byte read success preserves position. The sentinel is initialized on
  each invocation because trusted fixture image buffers survive repeated runs.
- Shared VFS checks execute the actual foreign seek helper for capability denial,
  unowned/invalid/closed descriptors, unsupported asynchronous backends,
  invalid targets/whence and signed overflow with unchanged offsets. Existing
  Linux/Darwin adapters and Windows duplicate/seek/paired-error coverage remain.
- The desktop seat adapter fixes unreachable bottom-right resizing and retains
  grip offsets to prevent the first-motion jump. Actual click/drag model checks
  cover resize/minimum bounds/content clicks/titlebar movement. Real QEMU PS/2
  shrink/restoration checks inspect exposed background and restored tile pixels.
- `check-compatibility-coverage.py` runs separate contract, model, runtime and
  GUI tiers, retains every gate's status/log/evidence level and writes source /
  compiler hashes to `report.json`. Missing dependencies and failures stay
  nonzero; the runner continues other gates. Output directories must be empty so
  earlier evidence is not overwritten. CI adds explicit JIT command-model checks;
  the default command-model gate still requires both JIT and native targets.

These are trusted CPL0 foreign fixtures and native desktop/SCI proofs, not
protected foreign processes, a foreign GUI adapter or unmodified application
coverage. Existing component, capability and SPDP ownership limits still apply.

## Fresh verification

Source-built Inauguration: `/workspace/inauguration/in-cli/target/release/in`,
version `0.9.322`, source `7d152155cbcd5aad683976ef2303e6b4e62b969e`.
Compiler SHA256:
`a634bf1ffd3ce1907b4440b29f89477b743ea2d80717af646c6150461855dedb`.
QEMU `10.0.13`, NASM `2.16.03`, Linux x86_64 host.

```sh
python3 scripts/check-compatibility-coverage.py \
  --tier all --in /workspace/inauguration/in-cli/target/release/in \
  --out /tmp/space-coverage-final
```

Result: **17 suites passed, 1 failed**. The runner intentionally returns 1.
The retained failure is `command-model-native`: the Linux-hosted compiler says
`writable globals require the macOS executable assembly path`. Reproduced using
Space's pre-change command-model script at `457bb24`; the failure is not hidden
by selecting JIT in the default gate. Baseline log:
`/tmp/space-commandbar-native-baseline.log`.

Passing evidence includes 86 ABI assertions, architecture checks, three-profile
VFS/seek, Darwin pipe, Unix stream, POSIX wait, Windows wait and mapping models;
39 JIT command-model checks; all nine foreign guest variants run twice; Mach-O
validation; Darwin/Windows translators; full desktop keyboard/pointer/pixel
interactions; SCI client pixels, bounded keyboard-driven pixels and seat denials.
Full logs, generated fixtures and screenshots are beneath
`/tmp/space-coverage-final`; the JSON report's source/compiler hashes were checked
against the final runtime/test files. The resize model also fails with the old
handlers as a regression control.

The unchanged compositor performance gate passed on the same kernel:

```sh
KERNEL_BIN=/tmp/space-coverage-final/desktop/kernel.bin \
  BUILD_DIR=/tmp/space-coverage-damage-final bash scripts/check-desktop-damage.sh
```

Measured 100 frames in 31 PIT ticks, 322 fps, against the existing 30 fps minimum.
This host's result is not a cross-machine performance comparison. Python syntax,
local documentation references and `git diff --check` also passed. No hosted
Rosemary build or unmodified foreign application was executed. Local tools were
installed under `/workspace/toolchain`; its QEMU wrapper supplies shared libraries,
BIOS data and `-L`, and its netcat wrapper closes stdin on EOF for Linux monitor
commands. These setup files are outside the Space patch.

## PR state and next work

The draft PR title/body are prepared in `/tmp/space-draft-pr.md`. GitHub API
access returns HTTP 401 for the configured credential; pushing the branch fails
with `could not read Username for 'https://github.com'`. No remote branch or draft
PR was created. Resume push and draft creation once environment credentials work;
do not describe this local branch as an open PR.

Next executable milestone: the [Rosemary plan](../rosemary-macos-reference.md)
protected native x86_64 Mach-O slice with separate RX/RW segments, BSS, startup /
exit, guest-pointer checks, denied kernel/other-domain access and repeatable
fault/exit cleanup. Reuse generic domain/lifecycle machinery for ELF and PE.
Decide loader reuse/licensing and the foreign-library/SCI boundary before copying
or linking `machish`. Keep native compilation owned by Inauguration.

Then expand descriptor operations through actual guest entry paths and typed PE
imports, using ReactOS/Wine/gVisor semantic cases as references. Advance the SCI
client path from synchronous proofs to owned release/focus/lifecycle contracts
before adding a small foreign software GUI client. Keep output/scale/text quality,
real keyboard/pointer interaction, visible pixels and damage performance in the
acceptance gates. Fix the generic Linux native writable-globals gap in Inauguration
as a separate tested compiler slice; do not weaken its current Space assertion.
