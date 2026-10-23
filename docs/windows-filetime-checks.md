# Windows FILETIME from the coherent native RTC

`windows-command-time-run(image,size,serial,storage,timer,line,bytes)` adds one
explicit, timer-authorized startup profile. It binds `GetSystemTimeAsFileTime`
to the [native UTC RTC service](../components/time.in), without supplying QPC,
PIT-based elapsed time, cached success or an invented timestamp. Earlier
strict/general/TLS/command profiles keep refusing this import. The original
Windows SQLite and 7za still do not execute.

## Authority and failure contract

The new private `components/windows-process-time.in` edge translates a borrowed
`TimeSource(read)` to the existing native `cap-timer()` grant. The caller owns
that capability; this activation neither mints nor revokes it. The wrapper
checks image/import admission, the bounded native command line, the timer grant
and any supplied serial/storage grants before the first RTC call. Native timer
rights are the existing flat capability vocabulary; this does not claim a new
per-symbol SCI capability refinement. All helper and launch names retain the
filtered `windows-parameters-*` / `windows-command-*` prefixes.

A coherent pre-entry RTC sample is mandatory. Invalid authority yields `-13`,
invalid arguments `-22`, invalid images `-8`, and unavailable RTC `-11`, before
allocating an activation or setting borrowed execution state. Unix epoch zero
is a valid sample. An earlier validated native RTC value is not reused as a
successful sample when the service returns `-1`.

At the void guest API, the edge rechecks the live timer grant and validates the
**entire writable eight-byte span** before any RTC call. It then requests a new
coherent native sample and writes a DWORD-low/DWORD-high FILETIME only on success:

```
FILETIME = (UnixSeconds + 11644473600) * 10000000
```

The supported native calendar range, 1970–9999, is checked before conversion and
fits signed 64-bit arithmetic. Resolution is **one second**, expressed in 100ns
units. The service supplies UTC; no time-zone conversion is guessed.

The API has no BOOL/error return. This bounded profile therefore stops the
activation on a runtime failure, leaving every guest output byte untouched:

| Condition | Activation status |
| --- | --- |
| Borrowed timer grant revoked | 126 |
| Invalid/nonwritable/crossing-unmapped output span | 142 |
| RTC unavailable or native timestamp outside the admitted range | 125 |

These are explicit Space activation outcomes, not successful Windows API
returns, Win32 LastError values or SEH emulation. A valid unaligned span and a
valid span crossing two mapped writable pages both succeed. LastError is
preserved on success. Resource teardown, FS/GS restoration and borrowed-grant
release follow the existing protected process scope; the caller's still-live
grant remains usable by the next launch.

## Actual hardware and protected execution proof

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-filetime.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-filetime-coherent-final
```

The gate boots four independent QEMU UTC RTCs: 1970-01-01, leap-day 2000-02-29,
nonleap-century 2100-03-01, and 2026-12-31 rollover. Each performs 212 required
CPL3 execution cases, 848 total in the final receipt. The host independently
converts observed native Unix
samples from a datetime 1601 epoch and compares exact FILETIME values; observed
hardware time also advances. A bounded test-supervisor retry records legitimate
transient pre-entry `-11`
refusals (and, if observed, natural runtime 125 terminations with untouched output)
separately; it retries at most 32 times and never converts refusal to fake success.
The final run observed one pre-entry transient and no natural runtime terminal
failures; actual guest launches remain 848. The receipt contains actual samples,
QEMU commands,
source/compiler/kernel/fixture hashes and source-stability checks.

The generated test kernel adds two clearly test-only controls: a supervisor
hook can revoke the borrowed timer or set the actual RTC SET bit while the guest
is paused. An observer counts calls from the real Windows edge to the real
native provider and examines owned guest frames before teardown. It supplies no
fake RTC data. Production source has neither guest control operation.

Coverage includes initial missing/weak/revoked timer grants, invalid image/line,
pre-entry actual SET refusal, live revocation, runtime actual SET failure,
null/kernel/read-only/unmapped-crossing pointers, unaligned and mapped-crossing
outputs, canaries/no partial writes, successful LastError preservation, fresh
zero LastError after terminal failures, budget cancellation and 21-cycle exact
heap/frame/domain invariants. Denied pointer/grant calls make no runtime RTC
request. A bad pointer while actual SET is active still fails before requesting
the clock. SET mode is restored by the test supervisor after every case.

The [original-app refusal gate](../scripts/check-windows-cli-admission.py) now
checks both official binaries through all five profiles, 210 refusals with
`executed:false`. SQLite still structurally validates its unchanged entry
`0x140003a8a` and 946 pages, while unsupported directory mask `0x46c` and first
unknown import 2=`GetEnvironmentVariableA` remain. QPC in its actual CRT cookie
initializer at `0x140234e9e` requires a real monotonic counter/frequency provider;
masked IRQ time cannot be replaced by the delivered PIT interrupt count.

Fresh regression reports are `/tmp/space-windows-*-filetime-regression/report.json`:
strict 507, files 527, write 527, general 317, TLS 171, parameters 275, identity 126,
large PE 81, plus six independent NVMe boots. Original-app refusal evidence is
`/tmp/space-windows-cli-filetime-refusal/report.json` (210 allocation-free
refusals; both originals remain unexecuted). The selected source-built 0.9.324
compiler SHA256 is `43b5a2f166efb28ea3123e8030c549d1eac9e90ee7c642d013457ff7ade09168`.

Public ABI reference: the pinned [ReactOS time implementation](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/dll/win32/kernel32/client/time.c)
confirms a void call writing the low/high DWORD pair from coherent system time.
[Microsoft's FILETIME contract](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-filetime)
defines 100ns intervals from 1601-01-01 UTC. These were read as contract references;
no implementation source was copied. This RTC backend has the explicitly narrower
one-second resolution described above.
