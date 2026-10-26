# Composed Windows startup services

Profile 10 composes the previously executable command/identity, environment,
FILETIME, QPC, heap, TLS/FLS and critical-section services. It resolves the union
of API IDs 0–42 without admitting unknown names or changing profiles 0–9.
`windows-command-composed-run(image,size,config)` is a private synchronous native
supervisor interface, not a guest pointer-taking syscall or public SCI export.
Original Windows SQLite, 7za and jq remain unexecuted.

## Explicit configuration and authority

The native caller owns a readable eight-byte-aligned 96-byte descriptor and its
line/environment inputs for the synchronous call. Descriptor version is 1;
size is 96 and the reserved word is zero. Validated fields are copied to local
values before activation state changes. A distinct execution-owned native-only
frame retains the validated configuration. It is never mapped into the guest.
The public test oracle is [composed-contract.json](../fixtures/windows-protected/composed-contract.json).

| Offset | Native descriptor field |
| --- | --- |
| 0, 8 | Version 1; descriptor bytes 96 |
| 16, 24 | Borrowed serial/storage grants, or -1 when absent |
| 32 | Mandatory borrowed live native memory grant |
| 40 | Borrowed timer grant, or -1 when clocks are disabled |
| 48, 56 | Command-line input address and bytes including NUL |
| 64, 72 | Explicit environment block address and bytes |
| 80, 88 | Flags; reserved zero |

Flag 1 enables TimeSource services and requires a live timer grant plus a
coherent pre-entry RTC sample. Flag 2 additionally requires a real available
native counter; it is invalid without flag 1. Required-counter absence returns
-38 before allocating process resources. With flag 1 alone, unavailable HPET
makes QPC/QPF return FALSE/error 31 with unchanged output while RTC and the other
services remain usable. With flags zero, a timer must be absent and clock imports
are refused before activation. A separate memory-only fixture proves this case;
its import table explicitly contains no clock names.

Serial and storage remain independently optional. Memory is live-checked by
heap, TLS/FLS, critical sections and, in this new profile, environment APIs.
Revoking memory does not revoke the independent TimeSource grant. Revoking the
latter does not disable owned memory services. Revocation does not retract the
existing mappings; it denies subsequent service operations. Neither a registry
address nor a copied configuration value creates authority.

The line is copied into the existing owned RO page. Environment input is copied
into the private canonical store; snapshots remain RO/NX and immutable through
later mutations. Heap records, FLS contexts, critical records, environment
canonical/scratch and configuration each have distinct private backing. Native
policy uses its own validated state, never a guest-writable PEB pointer.

## Composition and lifecycle

The guest retains profile 8's two-page TEB and PEB at `0x4e005000`, the real
TlsSlots offset `0x1480`, private callback stack and owned entry shadow space.
A callback executes at CPL3 against the same heap, live grants, environment,
thread-local slots and critical-section ownership as its suspended caller.
The shared IRQ quantum and finite callback-transition bound still apply;
kernel syscall service time is not claimed as wall-clock deadline coverage.
No cross-thread waiting, locale, general module resolution or additional API
success is invented by composition.

Normal return/ExitProcess performs actual FLS rundown. Faults and deadlines
terminate with the existing bounded statuses. A terminal void-service failure
must also remain terminal when the FLS context runner is active: profile 10
propagates the service's status (for example RTC unavailable 125) without
resuming the guest or pretending callbacks completed. The prior profile 8
contract is unchanged. Unsupported callback ExitProcess still returns 127.
Cleanup releases all owned state regardless of which borrowed grants remain.

The guest backing ledger is bounded by 1,100 pages for the largest admitted
image, below its capacity 1,152. The mixed fixture owns exactly 87 guest pages.
The conservative reservation is image pages + 80 + 67 heap + 14 composition
frames. The latter includes six TLS/FLS, six environment, one critical ledger
and one configuration frame. The retained first-use bump cache is independently
reserved: exactly 26,912 bytes, never funded by free frames. All ledgers and
activation resources return to the measured warm baseline; no per-call native
heap allocation is added.

## Executable evidence

Run with the explicitly source-built frozen compiler:

```bash
python scripts/check-windows-composed.py --in /path/to/in --out /tmp/windows-composed
python scripts/check-windows-composed-dependencies.py --apps /tmp/windows-cli --out /tmp/windows-composed-dependencies
python scripts/check-windows-cli-admission.py --in /path/to/in --apps /tmp/windows-cli --out /tmp/windows-cli-admission
```

The actual CPL3 scenario holds a critical section on a zeroed owned heap block,
sets TLS and FLS, mutates an explicit environment, reads real RTC/QPC, then frees
FLS through a callback. The callback recursively acquires the same critical
section, allocates/frees from the same heap, reads and updates TLS/environment,
and reads the real optional counter. The caller resumes with its preserved
nonvolatile state and XMM15 and observes those updates while its old immutable
environment snapshot retains the original bytes. Entry writes all four x64
home slots; callback stack alignment and TEB bounds are checked.

The focused gate uses PC, Q35 and HPET-disabled machines. It includes actual
private native SCI import denial before allocation; malformed descriptor/input
and authority refusal; caller descriptor/input mutation after entry; native
configuration alias checks and a guest read fault; readonly snapshot and NX heap
faults; callback/main deadlines; callback ExitProcess refusal; main/callback RTC
SET-mode terminal failure; invalid QPC pointer before provider side effects;
independent live timer/memory revocation; fresh activation after termination;
and exact heap/free-frame/domain/current-capability/FS/GS/PIC cleanup over 21
cycles. The cold test refuses 171 frames unchanged and recovers with the 172nd
frame and exactly the retained bump bytes.

The fresh focused receipt is `/tmp/space-windows-composed-final/report.json`:
773 actual activations (258 PC, 258 Q35, 257 without HPET), including one cold
recovery per machine. Required counter admission is refused without HPET;
optional and clock-disabled scenarios still execute. All 16 older Windows
gates passed again under `/tmp/space-windows-*-composed-regression/`, including
six NVMe boots and 462 unchanged original SQLite/7za refusals across 11 profiles.
Evidence paths are local receipts, not committed executable artifacts.

## Original application boundary and next slice

The independent static inspector checks unchanged official artifact hashes and
all imports against the declared 43-name union. SQLite imports 157 names;
42 now have composed implementations and 115 remain unsupported. Its first
unsupported composed import is one-based slot 3, SetCurrentDirectoryW. The older
command-only diagnostic remains slot 2, GetEnvironmentVariableA. These are
independent import diagnostics, not evidence that SQLite reached either call.

The actual native refusal gate also retains structural entry `0x140003a8a`,
946 mapped image pages, preferred base `0x140000000`, unsupported directory mask
`0x46c`, and the execution import limit 32. Resource/exception/relocation/debug/
load-config semantics remain barriers; zero-slide policy does not silently
validate or execute those directories. Original security-cookie disassembly
observes calls to FILETIME, thread/process identity and QPC; it is static
startup evidence, not a runtime SQLite trace. No original version/help output
has been obtained.

After this composition checkpoint, implement bounded UTF-8/UTF-16 conversion,
count/error behavior and truthful code-page metadata with negative and lifecycle
tests. Locale/collation, arbitrary code pages, dynamic resolution, wide file
APIs and the original PE admission barriers remain explicit separate work.
