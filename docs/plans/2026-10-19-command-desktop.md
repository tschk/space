# A command desktop for Space

User direction, 2026-10-19: a basic niri-like layout controlled through a Raycast-style bar. Layout mode, window controls, terminal and eventually browser belong in that bar. The finished desktop is original Space software, informed by Alpenglowed and the privately supplied Rover reference. A stock Budgie session is not an acceptance criterion.

## Platform foundations take priority

Resolution, scaling, multiple real typefaces and reusable compositor/text
infrastructure precede broader window-manager features. Follow the
[display/text platform design](2026-10-19-display-text-architecture.md); this
command bar is one client/service boundary within that platform.

## Interaction contract

One summonable bar owns query, results, selected row and confirmation. Results combine live window targets and explicitly registered desktop actions. Keyboard and pointer confirmation pass the same action identifier to one dispatcher. Query editing resets selection; navigation wraps over actual visible results. Empty/no-match confirmation cannot invoke a hidden action. Escape dismisses the bar and preserves the previous live window focus; text typed into the bar never reaches the terminal underneath.

Keep the first implementation bounded to existing input support: Tab/topbar summons, Ctrl-N/P navigates and Enter confirms. A future configurable Super+Space binding needs modifier-aware input across PS/2 and USB; do not claim it from ASCII input alone. No shell interpolation or arbitrary command execution is needed for window actions.

## Module and component boundaries

Hypermodularity is an architectural requirement, not a later cleanup. Keep the
command registry/dispatcher and query state separate from layout policy; layout
owns stable window identities, focus and geometry, not rendering. The compositor
owns surface composition/damage/presentation, while the seat routes authorized
input and applications own their sessions and content. Each module needs explicit
inputs, state ownership and observable results before it becomes a separate SCI
service. Do not extend the existing display monolith with unrelated command,
browser, shell and personality logic.

Use the existing SPDP/channel/shared-page contracts for the service split. Do not
introduce a competing bus. The bar dispatches bounded actions to the service that
owns the relevant authority; a search result never grants a capability. Preserve
SCI loader checks and make declaration-to-grant translation Space packaging
policy, not compiler knowledge. The kernel-linked prototype remains a stepping
stone; extracting source files is not proof of isolation.

## Layout direction

Aim for horizontal columns with a focused column and a viewport that follows focus. Keep a simple floating mode for windows that need free placement. Layout actions are searchable alongside windows: tile, float, focus left/right, close and minimize. The first executable slice can establish shared action dispatch and real tile/float geometry; it must be labeled as groundwork until overflow scrolling and per-window floating state are implemented and tested.

Preserve window identity across close/reindex, minimize/restore and mode changes. Geometry changes damage both old and new bounds, account for title bars and preserve terminal content. Closing the final window must leave the bar accessible. A mode label or serial message alone does not prove layout behavior.

## Command and application boundary

Terminal commands must operate the existing real terminal renderer or an actual launched component. Existing terminal buffers are bounded; opening another terminal must allocate an independent session or refuse honestly, never alias a live buffer while claiming a new terminal. Window focus is labeled as focus, not app launch.

Browser is part of the desired product. It becomes an enabled launch action only when an actual browser component renders content and accepts input on Space. Rover's macOS WebKit integration is a reference, not a portable browser engine. Do not add a decorative browser window as compatibility evidence.

Native desktop commands are Space-owned and must eventually target capability-checked SCI objects through the display/input contracts. The current kernel-linked desktop is a prototype, not an isolated component session. Compatibility plumbing for upstream Wayland clients is an independent vertical slice; keep its acceptance separate from shell interaction tests.

## References inspected

- Alpenglowed local revision `2bdb63e0207b91ebf6ccb7b162a0f504b8adf8c7`: `src/runner.rs` query/action routing, `src/main.rs` selection and confirmation, `src/layout.rs` model operations. Its dark surfaces, cyan focus and compact status row are reference ideas, not a prescribed skin. Surface-to-pane integration is explicitly unfinished in its README.
- Authorized private Rover clone, local revision `55a4b8089c12d0b5588c4bf5b1d04325d31e99e1`: picker delegates separate matching, selection and confirmation; the command registry distinguishes app launch, URLs and built-in actions. This inspection imports no private source into Space.
- Space `components/display.in`: existing prefix-filtered four-row window switcher, terminal rendering, focus/close/minimize/restore and damage handling. These working primitives are the initial integration surface.

## Acceptance evidence

Require actual QEMU input and rendered inspection: select commands by keyboard and pointer; verify equivalent results; tile/float roundtrip geometry and retained terminal content; focus after close/minimize; unmatched search and dismissal; terminal input after a transition; shell return. Extend existing desktop launcher checks rather than replacing their assertions. For scrolling columns, additionally prove overflow, viewport panning and accessible offscreen windows. Preserve affected boot, desktop damage, SCI and personality gates.

Current baseline rerun is not green: launcher-panel pixels were absent after an opened serial marker. See the handoff for the exact command and artifacts. Repair or explain that failure before using it as acceptance for new behavior.

## Implemented groundwork checkpoint

The current checkpoint extracts command state/filtering/dispatch into
`components/display-commandbar.in` and tiling geometry into
`components/display-layout.in`. Existing window targets and five bounded actions
share one lookup: tile, close focused, minimize focused, and focus either existing
terminal. The display backend retains drawing and device adapters. This remains
kernel-linked; it is not the SCI service separation described above.

Tiling accounts for taskbars, margins, gaps, title bars and minimum content size,
and refuses insufficient space before mutation. Layout/close/minimize cancel
stale drag state; hidden/removed windows reject keyboard input. Command labels use
the existing raw title-address ABI through an initialized immutable-label table.
The model checker adapts literal pointers into modeled memory; the real boot/SCI
checks remain necessary to catch representation/ABI differences.

Floating restore, scrolling columns, new independent terminal sessions, browser
launch and the output/text architecture remain unfinished. Resolution and multiple
typefaces now take priority over expanding this command set. See the current
handoff for exact evidence, including the standalone SCI baseline compiler failure.
