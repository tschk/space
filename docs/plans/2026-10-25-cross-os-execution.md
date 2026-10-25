# Original cross-OS compiler execution

The full application/desktop goal remains **OPEN**. The frozen cross-OS cohort
at `db1676f967aec7f4a86951a0bb46d4253a76f68e` passes all11 gates, with zero
failed or blocked. All819 source-file hashes, the source-built compiler and the
three original executable hashes remain unchanged through the complete run.
[Full cohort receipt](../evidence/2026-10-25-cross-os/cohort-receipt.json).
[Per-application and regression hashes](2026-10-25-cross-os-evidence.json).

These are three shipped builds of **one upstream application**, flat assembler g
at `905f6791f6777e35baec182e6843e2ada30cedd0`; not three unrelated applications.
No upstream executable or source is patched. Both offline acquisition and a fresh
GitHub archive download verify the pinned archive, binaries and BSD notice.

| Original executable | CPU profiles | Actual original activations | Result |
|---|---|---:|---|
| Linux x86_64 ELF | `max`, `qemu64,+rdrand` | 65 each | Exact macro/arithmetic file; real `%t` output matches native RTC |
| macOS x86_64 Mach-O | `max`, plain `qemu64` | 65 each | Complete original low-address image and BSS; exact output |
| Windows i386 PE32 | `max`, plain `qemu64` | 65 each | Genuine compatibility-mode CPL3 execution; exact output |

That is390 original activations. Each profile includes42 expected compiler-error
exits and21 steady ownership cycles. The source-derived macro output is exactly
`53706163650a0101020203030404` in Space's filesystem. Real app diagnostics,
file accesses, status, denied metadata and cleanup are asserted inside Space.
The six malformed-image controls per profile use a separate copy. Native CPU,
VM and provider controls receive no original-application credit.

Complete real Space serial logs for the max CPU profiles:
[Linux](../evidence/2026-10-25-cross-os/linux-max.serial.txt),
[macOS](../evidence/2026-10-25-cross-os/darwin-max.serial.txt),
[Windows](../evidence/2026-10-25-cross-os/windows-max.serial.txt).
These are serial workflows; they are not graphical app screenshots.

The separately imported classic C ABI edge ignores unspecified high register
bits for32-bit integer parameters; owned provider controls verify this case.
Anonymous mapping, zeroing, RO denial, hints, unmap, file item/EOF/seek behavior
and actual RTC all retain independent controls. Native32 and low-view suites
pass on both plain CPU profiles, including4103 owned pages, former supervisor
address shadows, faults, IRQ budgets and repeated teardown.

Additional frozen Linux-runtime regressions at `e2ee4b1` pass10 checks: original
jq/Lua/SQLite suites, standard/minimal native address spaces, desktop launcher
and damage, Linux VM ownership, real vi navigation on the minimal root, and the
visible original vi with independent pixels on the standard root. Both vi
profiles drive38 real PS/2 events across two processes and verify exact saved
bytes. Damage reaches250 fps against the unchanged30 fps minimum. The older
[21-check native/macOS/Windows checkpoint](2026-10-25-classic-execution.md) has
its own frozen scope and includes both318-entry modern Darwin mapper roots.

Plain qemu64 fails the Linux launch with-38 because it lacks the required
RDRAND source for genuine AT_RANDOM. Its failed receipt remains preserved. The
second Linux profile explicitly enables RDRAND; no timestamp/seed fallback is
introduced. An initial clock-control fixture also failed because it reused a
cleared process grant; the corrected fixture preserves the original assertions.
Hosted CI is tracked separately from these local QEMU receipts.

Reproduce this cohort with the command in the
[cross-OS continuation](2026-10-25-original-cross-os-execution.md). Default lab
`all` now defines176 gates; a complete176-gate run is not claimed. The historical
163-gate receipt keeps its original runtime/compiler/source scope.

Normal installed-app/desktop launch, broader dynamic dependencies and threads,
Windows PE32+, dyld/Objective-C/AppKit, Win32 message/graphics APIs and actual
browser/Electron/Pulsar execution remain unfinished. The classic import shims
do not execute Apple's dyld/libSystem or Microsoft's kernel32 binaries. Every
finite result here leaves the full real CLI/TUI/GUI application goal open.
