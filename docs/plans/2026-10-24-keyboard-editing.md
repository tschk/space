# Native keyboard normalization and cursor editing

The full application/desktop goal remains open. This slice makes the existing
bounded native Notes editor usable for interior edits through the existing
input page and SPDP seat delivery. It adds no renderer, IPC channel, foreign ABI
or authority. The document remains eight printable ASCII bytes; larger and
multiline documents remain required work.

## Contract

`protocol/keyboard.in` preserves desktop arrow values128(up),129(left),130(right),
131(down),132(home),133(end), adds134(delete), and gives PageUp/PageDown distinct
135/136 values. ASCII and control bytes retain their meaning. Both PS/2 decoders
consume E0 framing, ignore extended release/PrintScreen fake shifts, track left
and right Ctrl independently, and consume the six-byte Set1 Pause sequence.
Nonextended legacy keypad translations are unchanged; this is not a complete
NumLock/keypad or international-keymap implementation.

The SCI USB HID usage translation fixes Escape, Backspace, Space, punctuation,
Delete and navigation, refusing unknown/error usages rather than emitting NUL.
US Shift/Ctrl normalization shares the PS/2 helper. USB CapsLock, simultaneous
key delivery/report slot changes and controller/enumeration correctness remain
open; model results must not be presented as real USB input evidence.

The editor owns its cursor at private client memory+136, independently of its
length at+128. Loading places the cursor at the end. Left/Right/Home/End move
within[0,length]; Backspace/Delete remove the preceding/current byte; printable
input inserts only when capacity permits. Invalid private cursor/length state
refuses edits. Saving still uses the existing fixed-file capability, manifest
and bounded supervisor bounce. Status and file layout remain unchanged.
The existing window painter renders the owned cursor; calculator behavior and
legacy end-caret pixel assertions are retained.

## Verification

`scripts/check-keyboard-editing.py` executes actual decoder/editor functions
against independent vectors in default/lean/harden compiler profiles. It checks
E0/E1 framing, overlapping Ctrl releases, fake shifts, all256 HID usages and
501 deterministic editing operations with intermediate string/cursor/save and
out-of-field-write assertions. This is model evidence only.

`scripts/check-gui-protected-windows.py` retains its six output/scale modes,
keyboard/pointer focus, resize, close/survivor/reopen and exact pixel assertions.
It adds real PS/2 Home/End/Left/Right/Delete/Backspace/interior insertion with
independently specified text and caret positions. The pixel oracle accepts an
explicit cursor for those cases; existing two-field expectations still require
an end caret. The launcher/damage and affected persistence checks remain gates.

Frozen source: `/workspace/keyboard-editing-source`, committed base
`eea9cce` plus the explicit adjacent override manifest. Production inputs are
hash-identical to the working checkout. Source-built compiler0.9.325 SHA
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`.

Completed actual checks:

- `/workspace/keyboard-editing-model3/report.json`: all15 model/profile checks,
  49 Set1 bytes per decoder/profile,256 HID usages/profile, actual report
  Shift+8/Ctrl+S/held/release/unknown/Delete,501 editing operations/profile and
  invalid cursor/length refusal controls. Models do not prove USB hardware.
- `/workspace/keyboard-editing-gui1/report.json`: all six modes, real PS/2
  interior edits/boundaries, exact text/status/caret, pointer focus, resizing,
  surviving calculator and reopen. Rendered interior-caret PNG inspected.
- `/workspace/keyboard-editing-persist1/report.json`: five actual NVMe boots,
  saved/shortened/empty field, exact independent disk oracle and denied storage.
- `/workspace/keyboard-editing-lifetime1/report.json`:129 sessions/258 instances,
  ownership/resource/ABA/launch-revocation checks.
- `/workspace/keyboard-editing-faults1/report.json`: six hostile peer modes,
  actual keyboard/peer pixels and input-loader ownership refusal.
- `/workspace/keyboard-editing-launcher1`: real parent-desktop keyboard/pointer,
  selection, taskbar, resize and dismissal pass. Existing window-contract
  models also pass in all three profiles.
- `/workspace/keyboard-editing-damage1.log`:100 moving frames/33 actual PIT
  ticks,303fps against the unchanged30fps threshold.

Ordinary-image default launch also passes six modes and command-bar interaction
at `/workspace/keyboard-editing-default1/report.json`. These focused
receipts do not extend the older frozen122-gate run or establish a larger editor.
