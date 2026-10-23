# Full goal and first real-application checkpoint — 2026-10-24

Historical checkpoint: see the newer [execution checkpoint](2026-10-24-application-execution.md)
for implemented compiler/protected-runtime fixes and current application results.
The full goal remains active.


User date: Australia/Melbourne. The active [full goal](../compatibility-coverage-goal.md)
now covers the complete protected Linux/Darwin/Windows application platform,
native desktop and real CLI/GUI corpus, with file persistence, independent
instances, focus/input/buffer ownership, crash recovery and repeated cleanup.
The goal remains incomplete. This checkpoint reports actual local tests and
implementation, not completion of the larger platform.

## Implemented from application testing

- The native hex viewer rendered nibble values 0–9 as punctuation/letters. Its
  formatter now uses decimal digits for those values and lowercase a–f for
  10–15. All 256 bytes pass an independent Python formatting oracle over default,
  lean and harden profiles. The old source fails at byte 0. Actual QEMU output
  now includes the correct `72 65 61 6c` for the saved text's initial `real`.
- The native system-info xorshift algorithm expected logical right shift on a
  64-bit word, while `Int >>` sign-extends. An explicit unsigned mask now preserves
  the established `0x308662a96818da74` result. Generic signed shift semantics and
  the original expected result are unchanged. The old artifact's mismatch was
  captured before the rebuilt app passed in QEMU.
- A native application runner drives shipped SCI apps with fresh-output waits,
  interactive editor pacing, expected values, admission/fault detection and
  per-scenario serial spans. It preserves failures while recovering to the shell
  after completed/refused applications. It is separate from foreign compatibility.
- Image builds accept `--variant standard|minimal|all`; default remains `all`.
  Standard-only builds let native workflows run reproducibly without ignoring
  the minimal build failure. The full build's standard artifact was byte-identical
  to the explicitly requested standard image.
- The pinned real-app corpus starts with original jq 1.8.1 x86_64 release binaries
  for Linux, macOS and Windows. The manifest verifies upstream SHA256 values and
  sizes; binaries stay outside git. The admission runner supplies every original
  byte and the true image size to the actual Space loader functions in QEMU,
  before heap initialization, then checks continued kernel boot. It never invokes
  ordinary foreign application code through the trusted CPL0 fixture path.

## Fresh local results

Source-built compiler: Inauguration `0.9.322`, source
`7d152155cbcd5aad683976ef2303e6b4e62b969e`, at
`/workspace/inauguration/in-cli/target/release/in`. QEMU `10.0.13`, NASM `2.16.03`.
Native standard image SHA256:
`c48f87d746e09c7f8189bf3d00876046b16472b308b79bb74ba3afbe65254fcf`.

| Local test | Observed result | Evidence |
|---|---|---|
| Native calculator | Arithmetic precedence, parentheses and divide-by-zero recovery pass | Actual SCI app in QEMU |
| Native notes | Type, save, close and reopen text in the same boot pass | Actual editor input and rendered reopened content; reboot persistence not tested |
| Native hex viewer | Opens notes file and prints correct hex digits | Actual app output plus all-256-byte formatter checks |
| Native files, manual, clock | Write/read-back/delete, manual output and calendar/uptime pass | Actual SCI apps |
| Native system info, monitor, benchmark | Established self-check, interactive quit and 9592 primes pass | Actual SCI apps |
| Unknown native app | Refused; shell remains usable | Negative application lifecycle case |
| Native checksum app (`sum notes.txt`) | Refused by loader: unresolved import `abort` | Failure retained; checksum workflow did not execute |
| jq 1.8.1 Linux host reference | Version matches; `-nc '[range(10)] \| add'` prints `45`, exit 0 | Host oracle only; not execution inside Space |
| jq Linux ELF inside Space | Refused with `-8`, twice in fresh QEMU boots | 2,255,816 bytes, 10 program headers and 4 load segments; exceeds current 2 MiB fixture bound and single-segment profile |
| jq macOS Mach-O inside Space | Refused with `-8`, twice | 855,272 bytes, 17 load commands, multiple segments and PIE/dyld startup beyond the fixture profile |
| jq Windows PE inside Space | Refused with `-8`, twice | 1,026,560 bytes, 10 sections beyond the fixed single-section/import profile |
| Corrupt-artifact control | All three hashes refused before host execution or QEMU app admission | Intentional checksum mismatch; no application execution |
| Full/default image build | Still fails compiling minimal: unresolved `GDT-TSS-SEL` in `domain-init` | Original failure retained; adding cpu alone exposed further display/loader coupling and was reverted |

Native total: **10 scenarios passed, 1 failed, 0 not run**. This is nine actual
apps passing, one actual app refused, and one passing unknown-app refusal. It is
not ten successful applications. Foreign total: **0 application passes, 3 blocked**;
all six admission probes produced repeatable refusal. No foreign GUI app ran.

The ordinary native-app and foreign-app commands intentionally return 1 while
these blockers remain. The valid refusal probes do not make application status
pass. Current outcomes are not inferred from screenshots or manufactured output.

## Reproduction and artifacts

Use the environment's local QEMU/NASM tools on PATH and the source-built compiler:

```sh
export INAUGURATION_DIR=/workspace/inauguration
BUILD_DIR=/tmp/space-real-native-standard-final \
  bash scripts/build-images.sh --variant standard
python3 scripts/check-native-applications.py \
  --image /tmp/space-real-native-standard-final/standard.bin \
  --out /tmp/space-real-native-another-run
python3 scripts/check-hd-byte.py \
  --in /workspace/inauguration/in-cli/target/release/in
python3 scripts/check-real-app-admission.py \
  --in /workspace/inauguration/in-cli/target/release/in \
  --apps-dir /workspace/real-apps/jq-1.8.1 \
  --out /tmp/space-real-jq-another-run --download
```

Actual receipts/logs:

- `/tmp/space-real-native-final/report.json` and `serial.log`: final native workflows.
- `/tmp/space-real-native-standard-final-build.log`: successful standard build.
- `/tmp/space-real-native-standard-final/build-receipt.json`: runtime/test source, compiler and image hashes.
- `/tmp/space-real-native-all-check.log`: full build's retained minimal failure.
- `/tmp/space-real-jq-final/report.json`: manifests, loader/compiler/kernel hashes,
  host reference output, exact binary descriptions and both QEMU probe results.
- `/tmp/space-real-jq-download/report.json`: clean automatic acquisition and repeatable admission results.
- `/tmp/space-real-jq-checksum-control/report.json`: artifact-integrity negative control.
- `/tmp/space-hd-regression-control.log`: old formatter fails the new oracle.

The expanded model tier passed 8 suites and retained the existing Linux native
writable-globals compiler failure as its one failure; receipt:
`/tmp/space-real-app-models/report.json`. The new formatter gate is included in
that tier and CI.

ABI contracts (86 assertions), architecture boundaries, Python/shell syntax,
document links and `git diff --check` passed. These tests do not replace the
prior [desktop/personality checkpoint](2026-10-23-compatibility-gui-handoff.md)
or mark its native compiler baseline failure fixed.

## Next work toward the full goal

1. Resolve the emitted native `abort` failure contract through the owning
   compiler/runtime layers. It must terminate/report the affected instance safely;
   no dummy export, no returning success, and no unchecked-index rewrite to hide
   language errors. Run positive and actual failure-path app cases afterward.
2. Repair minimal-root dependencies by separating display-specific SCI proof
   ownership from the core loader/shell path. Importing the complete desktop to
   make a core-only image compile is not the intended architecture.
3. Implement protected native Mach-O startup/mappings/lifecycle, share generic
   process machinery with ELF/PE, then support real multi-segment images and
   required imports. Raising the fixture size limit alone cannot run jq.
4. Advance sustained SCI clients, buffer release and authenticated focus/input,
   then test the real toolkit/application matrix in the full goal. Native terminal
   sessions, reboot persistence and foreign GUI workflows remain required outcomes.

Continue on `compat/coverage-and-gui-foundation`. GitHub credentials still fail;
no draft PR exists remotely. The prepared PR contents can be pushed/opened once
credentials work, while local implementation and testing remain authorized.
