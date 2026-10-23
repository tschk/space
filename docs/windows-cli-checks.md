# Official Windows CLI corpus and process parameters

The [Windows CLI manifest](../fixtures/applications/windows-cli-2024.json) pins
unmodified official SQLite 3.46.1 and 7-Zip 24.09 x64 executables. Both remain
refused before allocation. A real Windows version/help/database/archive scenario
has not executed on Space. This checkpoint records actual acquisition and
refusal, then an executable startup API group needed by the selected SQLite CRT.

## Provenance and target selection

| Artifact | Upstream archive | Executable SHA256 |
| --- | --- | --- |
| SQLite 3.46.1 `sqlite3.exe`, 3,773,952 bytes | [Official 2024 Windows tools](https://www.sqlite.org/2024/sqlite-tools-win-x64-3460100.zip), SHA256 `c86c0fe0b0b46cfaac40812a26c958bbf2378b6ef9d784d6354d9f5bd66e566b` | `0e56e76eed7efaaf74884cf7c5337ebc65bf1c22eef2f513f4c4b7c8e8dfbb07` |
| 7-Zip 24.09 `x64/7za.exe` | [Official maintainer release](https://github.com/ip7z/7zip/releases/download/24.09/7z2409-extra.7z), SHA256 `43ae97658d0fc5b4eec4d409d85f7bed74a80945fd5704333a3599e0bd79b5fc` | `fbb3dadcc29bcbc5460484d858c5f33f99e5317f5f6cd8d9c83f4dd8c39b3e30` |

These are hashes pinned after primary-upstream HTTPS acquisition, without an
independent published-signature claim. The older `7-zip.org/a/7z2409-extra.7z`
URL returned 404; the upstream maintainer's versioned GitHub release supplied the
archive. The unversioned current `7zr.exe` download was not admitted as 24.09.
No executable bytes are added to this repository or changed to fit the loader.
The SQLite embedded source ID matches the 3.46.1 release identity; the 7za banner
identifies 24.09 x64 dated 2024-11-29. Acquisition verifies these embedded strings.

SQLite is dedicated to the public domain; use its upstream copyright statement
and review separately attributed packaged components if redistributing binaries.
The 7-Zip archive's full `License.txt` states LGPL-2.1-or-later and BSD-2/3-clause
portions for `7za.exe`; binary redistribution must preserve its license
information. The acquisition helper extracts and hash-checks that complete file.
This work inspects binaries and public contracts and vendors no Wine/ReactOS code.

```sh
python3 scripts/acquire-windows-cli.py --out /tmp/space-windows-cli-acquisition
python3 scripts/inspect-windows-application.py /tmp/space-windows-cli-acquisition/sqlite3.exe
```

Acquisition uses the host's generic libarchive reader for two named 7-Zip archive
members and Python's ZIP reader for SQLite. It never runs either executable.
The existing Linux SQLite manifest and its canonical `apps[0]` ordering are
unchanged.

SQLite is the next original-app priority: its CRT is linked into the executable,
with **157 named KERNEL32 imports and no other imported DLL**. 7za has 143 imports
across KERNEL32 (88), MSVCRT (38), ADVAPI32 (9), USER32 (2), and six OLEAUT32
ordinals. Thus fewer total 7za imports still require a larger dependency graph.

SQLite's current loader blockers include PE header offset 256, nine sections,
946 pages under the existing mapping formula (limit 480), a raw text section
larger than 2 MiB, DLL characteristics 0x8160, 157 import slots (limit 32), and
resource/exception/relocation/debug/load-configuration directories. 7za has
PE header offset 248, preferred base 0x400000, multiple DLLs and ordinal imports,
plus unsupported directories. Neither has a static TLS directory. None of
these constraints was bypassed to claim original application execution.

## Required startup group

Read-only disassembly of the pinned SQLite executable gives direct evidence:

- `0x1402349a8` calls `GetStartupInfoW` after initializing a 104-byte structure.
- `0x1402349e6` calls `GetModuleHandleW(NULL)` and inspects its PE headers.
- `0x1402b0f68` / `0x1402b0f75` call `GetCommandLineA` / `GetCommandLineW`.

`components/windows-process-parameters.in` implements this bounded group behind
`windows-command-run(image,size,serial,storage,line,bytes)`. The wrapper accepts
an explicitly supplied ASCII command line of 1–1024 bytes including its sole
terminal null. Empty content, spaces and quoted arguments are preserved exactly;
non-ASCII bytes, embedded nulls, unterminated data and out-of-bound lengths refuse
with `-22` before activation. It copies ASCII and UTF16 strings into one private
RO/NX page at `0x4e004000`. Both APIs return guest addresses into that owned page.
No host environment, pointer or argument parser is substituted for the app's CRT.

`GetStartupInfoW` prevalidates the entire writable 104-byte guest span, then
populates `cb=104` and the current adapter's standard handle tokens (stdin
unavailable, stdout 1, stderr 2). Reserved fields, flags and geometry are zero:
there is no `STARTF_USESTDHANDLES`, inherited console/window configuration or
fake desktop startup state. Tokens carry no new capability; operations keep the
existing live borrowed-grant checks. Invalid output spans yield adapter error 998
without partial writes; this bounded refusal is not Windows SEH emulation.

`GetModuleHandleW(NULL)` returns this activation's preferred image base.
Non-null valid module strings return null/error 126 because named module lookup
and dependency activation are not implemented. Bad pointers yield 998 and
unterminated strings beyond 260 UTF16 code units yield 206. It never reads a
native kernel string on behalf of the guest. Successful APIs preserve LastError.

Only this explicit fourth profile admits these additional four names. Existing
strict/general/TEB-startup profiles retain their previous import refusal. Each
activation keeps existing budget/fault teardown and FS/GS restoration; the
parameter page is tracked in the same frame ledger. New supervisor helpers
`windows-parameters-*` and `windows-command-*` must remain private to SCI lookup.
The TEB/PEB remain partial as described in [startup checks](windows-startup-checks.md).

## Executable evidence and next gate

```sh
PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-cli-admission.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --apps /tmp/space-windows-cli-acquisition --out /tmp/space-windows-cli-refusal-final

PATH=/workspace/toolchain/bin:/workspace/toolchain/usr/bin:$PATH \
python3 scripts/check-windows-parameters.py \
  --in /workspace/toolchain/inauguration-0.9.324/in-cli/target/release/in \
  --out /tmp/space-windows-parameters-final-evidence
```

The original-app admission gate proves 168 refusals (two applications, four
profiles, 21 repeats) with exact heap/free-list/domain/owned-tree preservation.
Its report explicitly records `executed:false`. The parameter gate exercises 275
actual CPL3 launches, including exact ASCII/UTF16 command lines, empty and 1024-byte
boundaries, actual 104-byte startup info with a post-structure canary, successful
module base lookup, missing module/error cases, read-only output and crossing
pointer refusals without partial writes, RO/NX hardware denials, infinite-loop
cancellation 124, FS/GS restoration, and 21-cycle exact heap/frame/domain stability.
Six malformed native command-line inputs refuse before activation. The earlier
171-launch TEB/TLS gate remains a regression.

The next loader slice should replace hardcoded PE-header/section offsets with a
validated bounded image view and an explicit larger-image resource plan, before
admitting this original SQLite layout. Then complete real startup timing/heap,
thread-local data, encoding, file and synchronization contracts required by its
actual linked CRT. Unknown imports continue to refuse. Do not erase them or add
zero-success UCRT/Win32 shims to obtain a version marker.
