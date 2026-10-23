# Native monotonic hardware counter

`components/counter.in` declares a native `Counter` provider with a
`MonotonicCounter(read, frequency)` timer capability and provider-owned memory
mapping authority. It supplies a free-running hardware count and exact integer
counts per second. The existing RTC `Time` service remains independent and
continues to supply coherent whole-second UTC timestamps.

The current standard boot root initializes this provider once, immediately
after memory discovery. This is boot-linked service scaffolding, not evidence
of an independently activated or isolated hardware component. Physical firmware
and MMIO access remain internal to the provider; native clients receive neither
physical pointers nor discovery/mapping entrypoints.

| Native entrypoint | Result and scope |
| --- | --- |
| `counter-init(mb-info)` | Trusted boot initialization, 0 or -1; never a guest import |
| `counter-frequency()` | Provider-internal exact positive Hz, or -1 unavailable |
| `counter-read()` | Provider-internal nonnegative monotonic count, or -1 unavailable |
| `counter-frequency-authorized(timer)` | Live borrowed `cap-timer` check; -13 denied |
| `counter-read-authorized(timer)` | Live borrowed `cap-timer` check; -13 denied |
| `counter-service-frequency()` | Native import, checks the actual activation's `current-cap` |
| `counter-service-read()` | Native import, checks the actual activation's `current-cap` |

Only the two `counter-service-*` functions enter the dynamic native registry.
All other `counter-*` helpers are excluded. In particular a native client cannot
supply or guess another realm's capability-table index through an exported
handle-taking helper. The personality supervisor may call the hidden authorized
functions with an explicitly borrowed, live timer grant. Windows retains its
own complete output-pointer checks and BOOL/error translation at that edge.

This registry gateway checks the native `cap-timer()` vocabulary. Generic SCI
compiler manifests encode component-local ordinal bits; this checkpoint does
not translate those ordinals into native timer rights or implement a provider
graph binding. The component/interface declarations record the intended service
authority. The registry test lends controlled native kernel grant objects and
calls their resident bindings; it does not prove ordinary declarative SCI Timer
binding. Windows's explicit borrowed native capability route is separate and
can use the validated provider without claiming that missing translation.

## Implemented hardware profile

Discovery consumes the Multiboot memory map, bounded to 8 KiB and 128 entries,
with checked descriptor lengths and nonwrapping ranges. RSDP candidates are
16-byte aligned in the advertised EBDA window or the defined legacy BIOS search
window. The provider validates the legacy checksum and extended checksum when
present, follows an RSDT or XSDT through validated below 4-GiB firmware ranges,
limits the root to 128 pointers, and requires a unique checksum-valid HPET table
with the supported 56-byte/revision 1 layout. It never guesses a device from a
hardcoded MMIO address when firmware does not advertise one.

The HPET GAS must describe aligned system-memory registers, zero bit offset and
an unspecified or 64-bit access width/size. This explicitly accepts SeaBIOS's
zero width/access fields. The supported MMIO address lies in the upper PCI/MMIO
window below 4 GiB and cannot overlap usable RAM, ACPI reclaim or NVS. The
provider maps one supervisor-only UC/NX page, checks that the hardware ID matches
the firmware block ID, validates vendor/revision and requires the 64-bit counter
capability. A 32-bit counter is refused: arbitrary IF0 sampling gaps cannot
truthfully extend all missed wraps.

The hardware femtosecond period must be positive, no more than 100, 000, 000 fs,
and divide 10^15 exactly. Frequency is exactly 10^15/period; there is no guessed,
rounded or IRQ-derived frequency. Unsupported periods return unavailable.

Initialization refuses legacy routing or already enabled timer comparators/FSB
interrupt delivery. It enables only the general counter, without resetting the
main count or installing interrupt routes. A bounded 100, 000-read probe must
observe actual forward progress. If a previously disabled counter does not
advance, the provider restores its prior general configuration and refuses it.

A read serializes the MMIO sample and last-value publication against native
client preemption. It uses the existing CPU flags capsule and preserves the
caller's IF0/IF1 state; no CPU/protected-runtime source or new assembly is needed.
Equal consecutive counts are permitted, backward values are not. A backward
sample or signed 64 overflow invalidates the provider rather than fabricating a
wrap extension or clamping a timestamp. Count and frequency then report
unavailable. There is no production reset/recalibration fallback.

Initialization failure is not an allocation-free rollback guarantee. Hardware
capabilities are inspected after mapping: failed hardware validation may retain
a supervisor UC/NX mapping and page-table allocation. A failed enable/progress
probe attempts to restore its original counter configuration. The mapping is
not exposed to a guest, and the boot provider is not a repeated guest request.

## Executed verification

```sh
python3 scripts/check-hardware-counter.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/hardware-counter
python3 scripts/check-counter-owner.py \
  --in /path/to/inauguration/in-cli/target/release/in \
  --out /tmp/counter-owner
```

The hardware gate compiles the actual standard root and boots QEMU PC and Q35.
For each, 10, 000 native reads must advance monotonically while IF is zero and
PIT-delivered `ticks` remains unchanged. Frequency must equal the actual HPET
period's exact quotient. It checks live timer authority/revocation, unchanged
read resource counts, the actual dynamic registry's two public bindings and
absence of private helpers, registered calls with correct/incorrect activation
grants, and restoration for a native IF1 caller. A separate `hpet=off` boot must
report unavailable and retain the RTC service. No IRQ-driven PIT counter
substitutes for any hardware sample.

The owner gate executes the unchanged discovery/read functions in actual
default, lean and harden compiler profiles against explicit byte-level ACPI and
MMIO models. It covers RSDT and XSDT, bad/extended checksums, invalid map lengths,
unsafe table pointers, root count/alignment/duplicate tables, GAS address space,
width/offset/alignment, RAM aliases, invalid periods and inexact quotients,
32-bit refusal, active timer/routing conflicts, bounded stalled/backward startup,
configuration restoration, runtime backward/signed overflow, IF state and live
authority. The model labels are not hardware evidence; the QEMU gate supplies
that independently.

Fresh 2026-10-24 (Australia/Melbourne), frozen Inauguration 0.9.324:

- `/tmp/space-counter-hardware-checkpoint/report.json`: PC, Q35 and no-HPET boots.
  PC/Q35 hardware exposes period 10, 000, 000 fs and exactly 100, 000, 000 Hz.
- `/tmp/space-counter-owner-checkpoint/report.json`: all three compiler profiles.
- `/tmp/space-counter-frequency-control/report.json`: removing only exact period
  divisibility causes the owning-function gate to fail with result 125.
- `/tmp/space-hpet-firmware-inspect`: separate physical firmware inspection of
  the default QEMU machine, including the actual ACPI HPET descriptor and MMIO
  capabilities. This inspection informed GAS validation; it does not replace
  the IRQ-masked hardware execution gate.

Receipts retain source/compiler/kernel hashes and commands. The first hardware
harness attempt and first owner harness attempt had unspaced subtraction
expressions parsed as identifiers; those compile failures are preserved at
`/tmp/space-counter-hardware-first` and `/tmp/space-counter-owner-first`.
The production provider compiled on its first standard-image build.

This profile does not support 32-bit HPET extension, arbitrary ACPI/MMIO outside
the supported physical window, multicore synchronization, sleep/suspend reset,
physical oscillator calibration, or a fallback to CPU/PIT frequency guesses.
Trusted tests may deliberately pause and rewrite HPET to inject backward or
overflow faults, then establish a new test epoch through boot-only reinitialization;
that destructive setup is not a production monotonic recovery guarantee.
