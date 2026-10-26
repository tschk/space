# Windows performance counter from native HPET

`windows-command-counter-run(image,size,serial,storage,timer,line,bytes)` adds
profile 6: the command/identity/FILETIME imports plus `QueryPerformanceCounter`
and `QueryPerformanceFrequency`. Both APIs invoke the
[native MonotonicCounter provider](hardware-counter.md) with the caller's live
borrowed timer grant. Windows policy owns output spans, BOOL and LastError;
the native provider owns ACPI discovery, HPET width, frequency and monotonicity.
No PIT tick, RTC wall clock, guessed frequency or success shim substitutes for
the hardware counter. Original SQLite and 7za still do not execute.

Before allocating an activation, profile 6 validates image/imports, arguments and
all borrowed grants. It requires a positive authorized native frequency and a
valid authorized native sample; unavailable hardware returns `-38`. It then
requires the same coherent RTC anchor as the FILETIME profile (`-11` if RTC is
transiently unavailable). The original FILETIME wrapper still selects profile 4
and continues refusing QPC imports. Environment profile 5 is independent.

At each QPC/QPF call the edge checks the live timer grant and the complete writable
eight-byte guest span before asking the native provider for a sample. Success
writes the exact 64-bit native count/frequency, returns BOOL 1 and preserves
LastError. Failure returns BOOL 0, writes no output bytes, and sets LastError:

| Condition | LastError |
| --- | --- |
| Missing/revoked borrowed authority | 5 (access denied) |
| Invalid/nonwritable/crossing-unmapped span | 998 (no access) |
| Native unavailable/backward/overflow state | 31 (general failure) |

Unaligned and mapped cross-page outputs are valid. The supported native provider
requires a 64-bit HPET and an exactly representable integer frequency derived
from its femtosecond period. Counts above 2^32 retain their high DWORD. Counts
outside nonnegative signed 64-bit range or moving backward make the native
provider unavailable; Windows does not reset or repair it. This is a single
synchronous bounded process profile, without Windows scheduler, UCRT, SEH or
arbitrary PE execution support.

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-counter.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-counter-proof
```

The focused gate performs 296 actual protected executions on PC and another 296
on q35, plus 21 allocation-free admission refusals and one actual protected FILETIME
success with HPET disabled (593 protected executions total). Each
hardware machine proves frequency times actual HPET period equals 10^15, actual
advancement while syscall IF=0 and PIT ticks remain unchanged, full-width counts
above 2^32, exact native-to-guest sample transfer, pointer/grant rejection before
provider calls, no partial/outside writes, live revocation, backward and sign-bit
faults, guest deadline termination, caller FS/GS restoration and fresh activation.
Twenty repeated cycles after warmup preserve heap, frame count and domain count.
The no-HPET machine also executes the original FILETIME profile successfully,
confirming it has no accidental counter prerequisite. Five additional malformed
image/argument/missing/weak/revoked-grant refusals per machine leave provider
call counts and allocation state unchanged.

Test images instrument calls while preserving every actual provider result.
A supervisor-only private syscall hook can revoke the grant or pause the real
HPET and write its main counter for boundary/failure injection. Each backward or
sign-bit test then restores a nonnegative hardware count and invokes trusted
native initialization to establish a **new test epoch**. This destructive test
reset is not production monotonic recovery or an API available to the guest.
Production Windows never calls counter initialization or writes HPET registers.
