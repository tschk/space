# Serious desktop application trials

The full goal remains **OPEN**. The user explicitly asked for applications such
as Pulsar, Warp and Helium, and a broad set of real editors, terminals and
browsers. vi remains an intermediate milestone. These trials do not change the
earlier 163/163 runtime checkpoint or establish any new working Space GUI app.

Seven official Linux x86_64 distributions are now acquired and pinned in the
[executable corpus](../../fixtures/applications/desktop-corpus.json). Downloads
are extracted into owned directories without installing packages or running
maintainer scripts. The manifest distinguishes published asset hashes from
locally measured CDN hashes. Original binaries and application sources are not
vendored into this repository.

| Application | Pinned version | Direct shared libraries in entry ELF | Undefined dynamic symbols in entry ELF | Space result |
|---|---|---:|---:|---|
| Lite XL | 2.1.8 | 4 | 277 | Admission -8; not entered |
| Pulsar | 1.132.1 | 34 | 1411 | Admission -8; not entered |
| Zed | 1.25.3 | 15 | 651 | Admission -8; not entered |
| WezTerm | 20240203-110809-5046fc22 | 16 | 763 | Admission -8; not entered |
| Warp | 0.2026.06.03.09.49.stable.00 | 11 | 389 | Admission -8; not entered |
| Helium | 0.20.1.1 | 32 | 1388 | Admission -8; not entered |
| Firefox | 158.0.1 | 7 | 176 | Admission -8; not entered |

These counts describe the entry ELF, not the transitive dependency graph or a
count of independent missing APIs. Firefox additionally loads Gecko libraries;
Pulsar bundles Electron, Node and native addons. Each trial preserves readelf
headers, program headers, dynamic entries, undefined symbols and version data.

The actual QEMU admission test checks both repeated validator results and
unchanged heap/free-list/domain/capability counters. Full host SHA256 checks
bind every payload to its pin before and after execution. The separate native
byte oracle checks 64-byte samples at the beginning, end and every MiB; it is
explicitly **not** a full-byte oracle. One GiB guest RAM covers the original
large executable plus its injection address. No payload is entered at CPL0 or
CPL3 and no host service is forwarded into Space. The diagnostic exits nonzero
while applications remain blocked; seven refusals are not seven app passes.

The frozen admission source is `665bf14`. Its complete local receipt is
`/workspace/desktop-corpus-final/report.json`. Native wrong-sample and
oversized-table negative controls stop before validator admission. Their local
receipt is `/workspace/desktop-corpus-negative-controls-fixed/report.json`.
The initial negative-control command failed before guest entry because it
bypassed the local QEMU wrapper and lacked libcapstone; that failure is retained.

## Host references

Host reference results are recorded separately from Space admission. Helium
uses the real Chromium renderer, actual textarea/button input, JavaScript and
localStorage across a full browser process restart. An independent PNG oracle
checks both canvas regions' exact displayed colors. Helium's deliberate canvas
readback noise is recorded rather than disabled; the
[upstream patch](https://github.com/imputnet/helium/blob/0.20.1/patches/helium/core/noise/canvas.patch)
explains why API readback can differ from visible pixels. Firefox's narrower
reference checks an actual Gecko screenshot and both canvas regions; keyboard
and storage restart are not claimed for that scenario.

Pulsar, Zed and Lite XL have actual host edit/save/fresh-process-reopen evidence, with
further input, exact second saves and graceful close. WezTerm's software backend
runs an actual shell command and produces exact output bytes. Warp's host
reference reaches its welcome window only; no terminal or account workflow is
claimed. Lite XL also exercises its actual command palette for graceful quit.

The [scoped evidence](2026-10-25-desktop-app-evidence.json) binds each result to
its frozen source and complete receipt SHA256. Native admission is at `665bf14`;
both browser references are at `53b384b`; the Pulsar/Zed/WezTerm/Warp cases are
at `612e499`; Lite XL's focused final continuation is at `7050284`. The full
`612e499` host candidate is still **failed** because its Lite XL append did not
insert the editor's final logical newline. It is not relabelled green. The
focused correction inserts a real Return before appending; all exact byte,
fresh-process and graceful-quit assertions remain. This is separate case
evidence, not a claim that the whole host suite passed at the final head.

[Actual host screenshots](../screenshots/2026-10-25/host-app-references/README.md)
are explicitly separated from the actual Space/QEMU screenshots. They are not
Space GUI compatibility evidence.

Early host harness failures remain preserved: raw xdotool file typing dropped
line breaks, Pulsar initially focused its changelog, SDL text events could race
Return handling, and Zed's GPU/project prompts consumed input. The corrected
harness sends explicit Return events, waits for key frames, focuses the actual
editor, enables the documented software-GPU option and tests a directory
containing only generated text. It retains exact file assertions. Lite XL's
Linux defaults have no Ctrl+Q binding; use the real `core:quit` command palette
action instead of changing the application.

Browser failures are also retained: the host's policy blocks file URLs, so the
corrected local web-app scenario uses a loopback HTTP server without changing
that policy. A mistaken 72-character expectation was corrected to the actual 74
characters. Canvas API comparisons exposed Helium's documented readback noise;
the final independent oracle checks exact displayed colors instead of disabling
privacy protection or accepting inaccurate rendered pixels.

## Implementation order toward actual Space applications

1. Advance the owned executable/dependency graph over native immutable file
   observations and owned mappings. Add bounded dynamic ELF/interpreter
   initialization, relocations, TLS and library lifetime without moving Unix
   process policy into the nanokernel. Prove startup and cleanup with a real
   dynamic executable before selecting a large GUI binary.
2. Establish an owned software GUI adapter through existing SCI/SPDP surfaces,
   accepted buffers and focused seats. Lite XL's SDL software path is the
   smallest acquired editor candidate. A new native backend is a port and must
   be reported separately from original Linux binary compatibility.
3. Complete real file watching, asynchronous waits, independent processes,
   IPC/shared-memory and terminal session contracts as required by each actual
   workload. Preserve the working original Linux CLI/TUI and ownership gates.
4. Bring up a real browser engine: first the bundled local web app, then
   controlled HTTP/HTTPS, storage, scrolling, multiple windows and cleanup.
   Helium exercises Chromium; Firefox independently exercises Gecko. Browser
   chrome, a host browser, a fake web view or remote screenshots do not count.
5. Expand to Pulsar's Electron/Node/addons and Warp/Zed's rendering/runtime
   requirements. Complete project editing/search/command palettes or real shell
   sessions, resize and independent instances. Raising the 16 MiB guard alone
   cannot supply these services. Avoid implementing success stubs just to pass
   import admission.

Warp's inspected [client README](https://github.com/warpdotdev/warp/blob/1e6c3ae465d6a925a9b97ae03877aaadd159b8f1/README.md#licensing)
states AGPLv3 for the client and MIT for its UI crates. Raycast binary
compatibility is not a target. These references do not import their code into
Space or change the native component/capability/object architecture. The
existing Darwin/Windows acceptance rows remain required; this corpus currently
acquires only Linux artifacts.

## Reproduce

```sh
python3 scripts/acquire-desktop-corpus.py --out /tmp/desktop-corpus
python3 scripts/check-desktop-corpus.py --in "$IN" \
  --index /tmp/desktop-corpus/applications.json --out /tmp/desktop-admission
# The blocked application diagnostic above intentionally exits 1.
python3 scripts/check-browser-host-reference.py \
  --index /tmp/desktop-corpus/applications.json --out /tmp/helium-reference
python3 scripts/check-browser-host-reference.py --browser firefox \
  --index /tmp/desktop-corpus/applications.json --out /tmp/firefox-reference
python3 scripts/check-desktop-host-reference.py --x11-prefix / \
  --index /tmp/desktop-corpus/applications.json --out /tmp/desktop-reference
```

Use an explicit source-built Inauguration for `$IN`, plus nasm/QEMU on PATH.
Host checks need Pillow, Playwright for Helium, and installed Xvfb/xdotool or
`--x11-prefix` pointing to an owned extracted dependency root. They use separate
profiles and a private X11 display, with no account creation. Browser pages are
served from a loopback-only server. Local receipt paths are not hosted artifacts.
