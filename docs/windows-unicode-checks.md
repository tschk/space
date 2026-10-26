# Windows UTF8 startup services

Profile 11 adds six observed original SQLite imports to the composed service
profile: GetACP, GetOEMCP, GetCPInfo, IsValidCodePage, MultiByteToWideChar and
WideCharToMultiByte. Its private native entry is
`windows-command-unicode-run(image,size,config)`, using the same explicit
96-byte descriptor and live grants as [profile 10](windows-composed-checks.md).
Profile 10 retains its 43-name admission; profile 11 admits 49 known names but
still at most 32 imports per executable. Original SQLite, 7za and jq remain
unexecuted, with their existing PE metadata and dependency guards.

## Contract and module boundary

[text-unicode.in](../components/text-unicode.in) implements pure Unicode scalar
steps: UTF8 decoding, malformed maximal-prefix length, UTF16 surrogate decoding,
UTF8 width and output bytes. It accepts byte/code-unit integers and returns
values, never guest addresses or grant handles. It owns no heap or mutable
state. This is a native utility module, not an asserted separate SCI process.
[windows-process-unicode.in](../components/windows-process-unicode.in) owns all
foreign ABI, guest-memory, authority and count/error policy. Its helper prefix
is excluded from the native SCI registry like the previous Windows helpers.

This profile explicitly declares both ANSI and OEM codepages to be UTF8, 65001.
It does not infer a host locale. GetACP/GetOEMCP return 65001 with live memory
authority. GetCPInfo resolves numeric 65001 and aliases CP_ACP 0 / CP_OEMCP 1;
it writes a complete 20-byte CPINFO buffer: MaxCharSize 4, DefaultChar '?'/0,
zero LeadByte ranges and zero padding. Unknown codepages fail 87 without writes.
IsValidCodePage reports 65001 as available and aliases/other numeric tables as
unavailable, preserving LastError. No locale/collation, Windows1252 or arbitrary
codepage table is fabricated. The independent profile oracle is
[unicode-contract.json](../fixtures/windows-protected/unicode-contract.json).

## Conversion behavior

Both conversions accept explicit signed 32-bit source counts or negative counts
for NUL-terminated input. Explicit counts preserve embedded NULs and add no
terminator; terminated counts include the terminator. Win64 argument widths are
normalized from their low 32 bits. The fifth through eighth arguments are read
from the actual callee stack with complete span validation before access.
UTF8 input is bounded to 4096 bytes and UTF16 input to 4096 codeunits. Declared
output capacity is bounded to 16384 bytes. Exceeding these bounded resources
fails 8. NUL scanning is bounded and validates each read before accessing it.

A zero output capacity is a size query and does not access the output pointer.
The result counts UTF16 codeunits or UTF8 bytes respectively. A short destination
fails 122. Strict flags MB_ERR_INVALID_CHARS 8 / WC_ERR_INVALID_CHARS 128 reject
malformed input with 1113; flags zero replace malformed maximal subparts with
U+FFFD. Overlong UTF8, surrogate UTF8, values beyond U+10FFFF, illegal leading
bytes, truncated sequences and unmatched UTF16 surrogates are handled. Valid
surrogate pairs and noncharacters retain their scalar values. This is scalar
conversion, without normalization or locale transformations.

The supported UTF8 flags are zero or the relevant strict flag. Other flags
fail 1004. CP_ACP/CP_OEMCP aliases resolve to the explicitly declared UTF8 table.
WideCharToMultiByte's default-character and used-default pointers must be NULL;
nonnull values fail 87. This deliberately follows the documented restricted
UTF8 parameter contract. Modern Windows/Wine versions allow additional cases;
those variants are outside this first bounded profile and are not reported as
compatible.

The complete source and declared writable destination are validated, then the
first scalar pass computes the required count and checks malformed input before
any output write. The second pass publishes the conversion. There is no guest
interleaving or second guest thread during these synchronous passes. Overlapping
input/output spans are explicitly refused with 87; some Windows versions allow
particular overlaps, which this profile does not claim. Invalid parameters fail
87, inaccessible/nonwritable guest spans 998, and missing or revoked live memory
authority 5. Success and successful size queries preserve LastError. Failure
leaves every output byte unchanged. Unaligned and cross-page UTF16 codeunits use
separate translated byte accesses, so a native physical-page adjacency cannot
bypass guest ownership.

No per-call or per-activation resources are added beyond the composed profile.
Conversion length and destination span checks bound kernel service work; the
existing guest IRQ budget does not claim to measure masked kernel service time.
The new profile uses the existing TEB/FLS context/critical/heap lifecycle and
owned read/write/execute permissions. No CPU/runtime assembly changes were made.

## Executable evidence

Use an explicit source-built compiler, with short evidence directories:

```bash
python scripts/check-windows-unicode.py --in /path/to/in --out /workspace/unicode
python scripts/check-unicode-scalars.py --in /path/to/in --oracles /workspace/unicode/oracles.bin --out /workspace/unicode-scalars
python scripts/check-windows-composed.py --profile 11 --in /path/to/in --out /workspace/unicode-mixed
python scripts/check-windows-composed-dependencies.py --profile 11 --apps /tmp/windows-cli --out /workspace/unicode-dependencies
```

The independent Python oracle generates encoded scalar/count expectations and
malformed replacement results. The actual QEMU gate executes 3,410 pure scalar
vectors, then 4,921 CPL3 activations: 234 distinct regular cases repeated 21
cycles, six actual live-revoke API cases and one fresh activation. The scalar
sample spans Unicode values and all encoding boundaries; it is not an exhaustive
test of every scalar. The separate source model executes the same 3,410 scalar
vectors under default, lean and harden compiler profiles (10,230 model cases),
with no claim that a source model is a CPL3 execution.

The actual API corpus covers ASCII/BMP/supplementary/noncharacter roundtrips,
strict and replacement errors including every maximal-prefix length, terminated
and explicit/embedded-NUL counts, query/short results, aliases and unknown
codepage metadata, invalid flags/default pointers, signed argument widths,
resource bounds, full 4096-unit conversions and complete 16384-byte output
capacity/tail verification, bad/overflow/readonly/overlapping pointers, and unaligned
cross-page source/destination. Adversarial RSP values put the sixth and eighth
stack arguments across the actual mapping end, proving refusal before access.
A trusted observer compares the complete target prefix around every failed API;
the guest independently checks returned counts, exact output and LastError.
All six APIs deny an actually revoked grant, then a fresh activation succeeds.
Heap/free-frame/domain counts and caller authority/FS/GS/PIC restore exactly.

The mixed fixture has exactly 32 imports. Main guest and real CPL3 FLS callback
both check metadata and UTF8↔UTF16 supplementary roundtrip while using the
existing heap, environment, TLS/FLS, recursive critical section and real optional
clocks. Its 773 PC/Q35/noHPET activations retain all composed faults/deadlines,
revocation and exact cold-resource proofs. A valid native SCI import of the new
private Unicode entry is denied before allocation. A clock-free 32-import
variant exercises the validated terminator at slot 32; the scan now distinguishes
this terminator from an unsupported 33rd import without increasing admission.

An earlier mixed rerun is preserved at
`/workspace/wunicode/mfinal/pc/serial.log`: mode 2 intended callback fault 142
instead stopped with terminal 125 before that fault. The unique production
FILETIME failure path identified RTC unavailability; the raw CMOS reason was not
captured, so no particular UIP/rollover cause is asserted. The harness now
positively observes FILETIME's terminal control/status before permitting any
retry, rejects untyped 125, checks cleanup and retries at most 32 times. Deliberate
SET failures are never retried and the intended fault 142 must still execute.
Actual activation/transient counts come from the guest-entry observer rather
than fixed totals. The final mixed receipt has 773 entries and zero natural
125 retries; persistent unavailable service still fails the scenario.

Fresh receipts: `/workspace/wunicode/umax/report.json` (API/scalar QEMU),
`/workspace/wunicode/scalars/report.json` (three model profiles),
`/workspace/wunicode/mfinal2/report.json` (mixed/private SCI), and
`/workspace/wunicode/dependencies/report.json` (static original dependencies).
All 17 previous Windows gates passed under `/workspace/wunicode/reg-*/`,
including old profile 10, six NVMe boots and 504 original-app refusals across 12
profiles. The selected compiler remains frozen source-built 0.9.324; reports
retain hashes, command lines and classifications separately.

## Original application limits and references

Independent hash-checked original SQLite inspection now finds 48 implemented
imports out of 157, with 109 unsupported. The first unknown is still one-based
slot 3, SetCurrentDirectoryW. The structural entry/preferred base, directory mask
0x46c and 32-import execution bound are unchanged. Static original security-cookie
disassembly is not a Space startup trace or original-app execution. Wide file
APIs, module resolution, locale/collation, remaining CRT services and validated
PE metadata remain separate executable work.

Read-only behavior references are Wine commit
`840a939ee526137639665ff5f587224d6a36403f`:
[conversion/metadata implementation](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernelbase/locale.c),
[codepage tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/codepage.c),
and [public flags/layout declarations](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/include/winnls.h).
The bounded UTF8 parameter contract is also documented by Microsoft for
[MultiByteToWideChar](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-multibytetowidechar)
and [WideCharToMultiByte](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-widechartomultibyte).
No Wine source or codepage tables are vendored. These references inform public
edge behavior; they do not add dependencies or original application coverage.
