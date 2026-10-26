# Bounded Windows UTF8 startup profile

The next executable checkpoint is profile11, explicitly opted into through
`windows-command-unicode-run`. Profile10 retains its existing43-name union.
The six additional observed original SQLite imports are GetACP, GetOEMCP,
GetCPInfo, IsValidCodePage, MultiByteToWideChar and WideCharToMultiByte. The
32-import execution limit and unsupported PE directory guards remain unchanged.
Neither original SQLite, 7za nor jq execution is claimed.

The profile declares UTF8 ANSI/OEM codepages65001. Conversion and GetCPInfo
resolve CP_ACP0 and CP_OEMCP1 to this declared codepage. IsValidCodePage reports
actual supported numeric tables, so65001 succeeds and aliases0/1 do not.
CPINFO reports real UTF8 maxwidth4, '?' default bytes and zero lead-byte ranges.
No Windows1252 table, locale/collation or Unicode normalization is invented.

Pure scalar decoding/encoding belongs in a separate native module accepting
bytes/codeunits, never guest addresses or capability handles. The Windows edge
owns live borrowed memory authority, Win64 stack arguments5–8, guest span checks,
bounded counts and error translation. Source counts are signed32bit; negative
means bounded NUL-terminated input, explicit positive counts include embedded
NULs and need not produce a terminator. Count-only queries return needed units;
short output fails122. Successful conversions preserve LastError.

The input bound is4096 bytes or UTF16 codeunits; declared output is bounded at
16384 bytes. Failures are atomic: validate full input, full declared writable
output, non-overlap and encoding/count before writing. Cross-page unaligned
codeunits use separate translated-byte accesses. Query output is not written.
Malformed strict input yields1113; unsupported flags1004; invalid parameters87;
bad guest spans998; bounded resource excess8; missing/revoked authority5.
Strict flags are MB_ERR_INVALID_CHARS8 and WC_ERR_INVALID_CHARS128. Flags0 use
Unicode maximal-subpart U+FFFD replacement. UTF8 default/used pointers must be
NULL, matching the documented restricted UTF8 API contract; some newer Windows
versions permit more and are outside this first bounded profile.

Acceptance requires independent Python Unicode scalar/count oracles; actual
CPL3 query/roundtrip/embeddedNUL/supplementary/noncharacter/boundary cases;
malformed/overlong/surrogate/truncated byte sequences; malformed UTF16; query,
short, readonly/cross-page/overflow/overlap and live revoke denial with unchanged
output; all four stack-passed arguments; full mixed heap/env/TLS/FLS/critical/
clock integration; exact cleanup and oldprofile/original-app refusals. Existing
composition and earlier Windows gates remain regressions. Runtime evidence and
implemented limits will be recorded after these gates pass.

Behavior references are read-only pinned Wine840a939ee526137639665ff5f587224d6a36403f
`dlls/kernelbase/locale.c`, `dlls/kernel32/tests/codepage.c`, and `include/winnls.h`.
No Wine source is copied or vendored; the pure scalar algorithm follows Unicode
scalar-value and maximal-subpart rules. Locale and general codepage tables
remain separate work.

The implementation and separately classified runtime/model receipts are now
recorded in [Windows Unicode checks](../windows-unicode-checks.md). The pure
scalar models cover default/lean/harden; actual guest conversions and mixed
callback services run atCPL3. These results do not widen original PE admission.
