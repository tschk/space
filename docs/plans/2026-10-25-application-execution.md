# Real application and desktop continuation

The full compatibility/desktop goal remains **OPEN**. The latest complete frozen
run passes **163/163 gates**, zero failed or blocked, from **782 committed source
files** at `8f70aaf812452ba4d60861fd25b887ab0f52da94`. It finished on 2026-10-25
at 06:22 Australia/Melbourne. Source/compiler/application integrity passes with
no changed inputs. [The scoped receipt](2026-10-25-application-163-evidence.json)
records each gate, original application pins and timing. Full local receipt:
`/workspace/lab163/report.json`, SHA256
`0f47089ddbd877f7bfe71b0f6c2c64c050d2fb4c06cb13068e55f5d56645b82b`.
Workspace paths are local evidence, not hosted artifacts.

The earlier **161/161** run remains separately recorded in
[its unchanged receipt](2026-10-25-application-evidence.json), at `3ac91e0` with
766 source files. It does not inherit the later Darwin data/font changes.

The exact frozen Inauguration0.9.325 binary remains
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`,
built from the pinned compiler dependency8530dd3a99cca7de38db50772ddcbde5d0b77745.
Existing Linux jq/Lua/BusyBox/SQLite, native ownership, NVMe durability, original
fbv pixels and bounded Darwin/Windows fixture behavior remain covered.

## Working original vi

The new terminal gates execute the unchanged pinned BusyBox vi ELF in protected
Linux contexts. Actual PS/2 events drive edit/save and fresh-process reopen on
both roots. A separate protected SCI terminal owns ASCII80x24 cells, DejaVu
glyphs and pixels. Navigation tests use38 real key events, including interior
Left/Backspace/Delete and Home/Right/End, with exact17-/24-byte saved files.
Each live terminal screenshot matches all294912 content pixels against an
independent pyte/Pillow/pinned-font oracle. Native queues, exact seat leases,
retained waits, raw controls/timed poll, cancellation and supervisor restoration
have separate model/native evidence.

[Actual QEMU screenshots](../screenshots/2026-10-25/README.md) are lossless scanout
captures. Original Windows/macOS application entries remain zero. Fixed-size
vi display/input acceptance does not establish resize, concurrent foreign
terminals, normal installed-app launch. The later interactive cold-boot checks below close
the finite reboot-persistence gap.

## Integrated changes and later verification

This complete163-gate run includes
[typed Darwin C-locale data](2026-10-25-darwin-data-imports.md) and
[protected client typography](2026-10-25-protected-client-typography.md), with
both roots'184 own data fixtures/69 setup failures, old318-entry mapper suites,
protected/default GUI configurations, fault/persistence/lifetime checks,
legacy visual preservation and desktop launcher/damage.

The later [interactive durability continuation](2026-10-25-interactive-vi-durability.md)
adds two gates, bringing current definitions to165. Both have separate passing
frozen-source receipts: three cold NVMe boots per schema, two original vi
activations and38 real PS/2 events, exact ELF/text bytes, independent live
pixels and whole-disk equality on the final read-only boot. Later boots have
no ELF staging device. These commits change only the test fixture/harness and
documentation; runtime code matches the frozen163-gate source. A complete165-gate
run is not claimed. Ordinary desktop launch, resize, concurrent terminals and
isolated source/terminal services remain open.

The earlier152/152 run and failed151-gate candidate remain historical evidence.
The corrected import-denial fixture now verifies every staged manifest and all
five exact unresolved-import diagnostics inside the existing reserved window;
the older invalid staging and failed follow-up remain preserved.

The separate compiler dependency's strict macOS ARM self-host job remains
failed on the unsupported borrowed-slice Rust ABI. Passing Space tests/CI do
not establish compiler self-host success or general cross-platform applications.
