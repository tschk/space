# Native screen continuation

The original pinned BusyBox vi now accepts real PS/2 editing through native
terminal queues and retained CPU waits, saves exact bytes and reopens in a new
protected process. Its output is still an ANSI stream, not a desktop surface.
The full project goal remains active while this display path is implemented.

## Implemented finite slice

`terminal-screen.in` is a pure client-owned 32 KiB ASCII80x24 model. Parameters
are bounded to32 and decimal values saturate at65535; unknown string payloads
cannot invoke devices or clipboard operations. Cursor motion, J/K erase,
scrolling/margins, deferred wrapping, basic indexed SGR and separate normal/
alternate cells support the actual pinned vi stream. This is not Unicode,
complete terminal emulation or resize support.

`app-terminal-view.in` compiles to a separate profile3 CPL3 SCI image with only
memory/display grants. It owns parser state, cells and staging pixels. Pinned
DejaVuMono14 coverage fits every exercised ASCII glyph in9x16 cells. Its finite
canvas is768x384, with80 columns centered inside720 pixels. The existing GUI
configuration scale2 is admission bookkeeping for this fixed profile; terminal
metrics are physical pixels and no terminal scaling behavior is claimed.

The private supervisor in `terminal-view.in` leases the existing generation-owned
GUI record, private SPDP ring, accepted snapshot and compositor surface. Version1
application frames carry up to15 bytes and an explicit present flag, never a raw
guest pointer. The client validates complete payloads before changing cells.
Only the existing validated ATTACH/DAMAGE/COMMIT reply and exact invocation epoch
publish pixels. Linux is stopped while the native SCI client runs; supervisor
TLS/hook/domain state is checked before the foreign process resumes. Keyboard
authority remains with the native seat rather than the renderer. These supervisor
helpers are denied as SCI imports; this is still a trusted supervisor library,
not an isolated terminal service.

Opening currently requires the existing quiescent GUI scene. It does not yet
install an ordinary launcher action, place foreign clients in the desktop tiling
graph or allow two concurrent foreign terminal processes. Close retires routing,
surface/pool references and owned SCI resources using the existing lifecycle.

## Executed evidence

- `/workspace/terminal-screen-model4/report.json`: all4096 transitions and103
  complete-cell comparisons against independent pyte0.8.2 pass in all3 compiler
  profiles. The original captured vi stream is an oracle input, not new
  application execution. Failed extractor/oversized test-function/oracle-DCS
  diagnostics remain preserved; mature pyte does not implement DCS screen policy.
- `/workspace/vi-terminal-live-view4/report.json`: two actual original protected
  vi processes,27 real PS/2 text events, exact17-/24-byte files, save/reopen,
  supervisor restoration and stable resources afterwarmup pass. Both actual
  QEMU captures match all294912 terminal pixels against an independent
  pyte/Pillow/DejaVu oracle using the captured live stream prefix. Host-generated
  expected pixels are never substituted for QEMU screenshots.
- `/workspace/terminal-view-package1/report.json`:9 emitted SCI policy artifacts
  and222 refusal controls pass; packaging evidence does not claim execution.
- `/workspace/terminal-view-denial-retained1/report.json`:27 own protected Linux
  control activations and2 actual forbidden SCI imports pass. Its third image
  was incorrectly staged at the loader's exclusive0x300000 upper bound, so that
  rejection proves only manifest refusal. It is not renderer-import evidence.
  These are not upstream application entries.

The frozen keyboard commit `2b6c796` separately passes hosted CI and desktop
launcher/input/pointer/resize, both boot-image builds and263fps damage (minimum30).
The terminal-surface continuation needs its own final committed-source checks;
the historical152-gate run retains its old scope. The full goal stays OPEN.

## Extended-key continuation

The native ring now admits a bounded1..8-byte sequence as one producer
transaction: validate payload/header/space first, write cells, publish head
once. Full queues return would-block with unchanged cells/head/epoch. The native
seat checks its exact focus lease and delegates without any foreign key policy.
`linux-terminal-keyboard.in` owns Linux VT encodings for the9 normalized
navigation keys; ASCII/control bytes preserve their identity. These private
kernel-linked helpers are denied as raw SCI imports.

`/workspace/terminal-navigation-model1/report.json` passes147 controls in all3
profiles, including all128 ASCII codes,9 exact navigation sequences, wrapping,
backpressure, stale focus, revocation and overflow. The native queues remain
single-producer/stopped-guest objects, not a concurrent producer API.

`/workspace/vi-terminal-navigation-view1/report.json` and
`/workspace/vi-terminal-navigation-minimal1/report.json` pass2 actual original
vi processes and38 real PS/2 events each. Left, Backspace and Delete correct
`native24` inside the line to`native42`; Home/Right/End move without changing
the expected file. Both exact saved-file oracles and all294912 pixels in each
visible capture pass. This extends the interactive slice, not general input
methods, Unicode, mouse reporting or multi-session acceptance.

The expanded five-import gate exposed that older staging mistake: later images
could also land in live allocator memory. The failed
`/workspace/terminal-navigation-final-controls/report.json` is retained. The
corrected harness packs the five bounded SCI images in8 KiB slots wholly inside
the existing reserved boot window, verifies each manifest before invoking the
loader and requires the exact unresolved-import diagnostic for every symbol.
No allocator/boot reservation, authority or refusal assertion was widened.

Final focused receipts and exact source revisions are recorded in
[`2026-10-25-terminal-evidence.json`](2026-10-25-terminal-evidence.json).
The corrected frozen`35b2bb2` native and retained gates both pass all5 exact
unresolved-import checks before entry/resources change. Frozen`32484b0` passes
147 native models, both38-event vi navigation roots, both294912-pixel visible
oracles, full desktop launcher/input/pointer/resize, both image builds and204fps
damage (minimum30). Frozen`adba514` separately passes all23 affected protected
Linux application/process regressions and the6-output-size protected native
window test. Actual [QEMU captures](../screenshots/2026-10-25/README.md) show the
finite working vi profile. These focused checks do not replace the historical
152-gate complete run or claim a complete new161-gate run.

Use the MIT-licensed VTE 0.13.1 transition rules as reproducible native data,
checked against all 4,096 bytes evaluated by the original upstream Rust macro.
Keep parser state separate from screen policy and rendering. Bound parameters,
intermediates, strings, cell storage, cursor motion, alternate screens and
damage. Unknown sequences cannot become memory addresses or device operations.
The initial real application uses ASCII; Unicode/shaping and complete terminal
compatibility require their own executable evidence.

The client owns its screen and pixels. Present through existing surface/shared
buffer contracts, retaining focused seat ownership and native process lifetime.
Inspect actual QEMU pixels during keyboard edits, independently compare cells
with the original output stream, save/reopen, close and restore the parent
desktop. An image rendered by a host oracle is comparison evidence only.
