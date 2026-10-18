# Space display and text platform

## Purpose and priority

User direction, 2026-10-19: think beyond a framebuffer demo. Resolution,
scaling and multiple typefaces are the immediate foundations. Build a proper,
original desktop faithful to Space's component/capability/object/execution-graph
model. A simple niri-like tiling experience and Raycast/Rover-like command bar
are the shell, not the whole platform. This document specifies the destination
and a migration plan; it does not claim these capabilities exist today.

## Observed baseline

`components/display.in` requests 1920×1080×32 through BGA, reads back dimensions
and virtual width, and has a Multiboot framebuffer fallback. Pitch is available
but substantial chrome and tests assume one resolution. The utilities view even
prints a literal resolution. `components/font.in` supplies a bounded 8×8 ASCII
bitmap face; the anti-aliased path derives coverage for that face. Enlarging a
bitmap or smoothing its pixels is not another typeface, shaping or a font engine.
SPDP uses fixed 32-byte frames and packed 16-bit geometry. Existing SCI proofs
are bounded and do not establish a fully isolated interactive desktop. These are
migration inputs, not permanent product constraints.

## End-state service graph

The names below describe responsibilities, not new implemented SCI interfaces.
Do not freeze their wire encoding until native ownership and versioning are
specified against the existing contracts.

| Service | Owns | Receives | Must not own |
|---|---|---|---|
| Output/device backend | mode discovery, physical scanout, pitch/format, presentation | validated output configuration and frame work | shell policy, app launching, font parsing |
| Compositor | surface tree, transforms, clipping, damage, buffer synchronization | committed surfaces and layout transactions | foreign process models, command query state |
| Seat/input | device normalization, keymaps, focused delivery, routing authority | device events and authorized focus changes | application text buffers or unrestricted global input for clients |
| Layout | stable window identities, columns, viewport, floating geometry | window lifecycle, logical work areas, bounded actions | pixel memory or privileged device addresses |
| Shell/bar | query, result providers, selection, action confirmation, status | registry/object views permitted by its grants | arbitrary privileged code execution |
| Text/font service or library | face catalog, immutable font assets, shaping/measurement/raster cache | text/style requests and permitted assets | input capture, app lifecycle, display ownership |
| Application/session supervisor | SCI launch, dependencies, grants and failure lifecycle | explicit launch requests | window geometry policy |
| Clients and compatibility adapters | client content and translated protocol state | granted surfaces, input, text APIs | ambient kernel/other-client authority |

A service graph does not require every tiny helper to become an IPC service.
Keep pure geometry and text operations composable; choose shared library versus
service based on ownership, failure containment and measured cost. The nanokernel
provides enforcement and execution/IPC mechanisms. It does not become a desktop,
a font engine or a foreign graphics kernel. Build with `.in` and general compiler
capabilities; do not move product policy into Inauguration.

## Output and coordinate contract

An output description needs stable identity, current/supported pixel modes,
physical pixel dimensions, pitch, pixel format, transform, logical extent,
scale and a configuration generation. Optional physical-size/refresh metadata
must be marked unknown when unavailable. Distinguish output identity from its
current mode. A surface is not permanently tied to one output or scale.

Use logical coordinates for shell/layout/hit testing and explicit transforms at
the compositor/backend boundary. Define scale as a rational value and specify
rounding centrally: outward bounds for damage, consistent shared edges for tiles,
and the inverse transform for pointer hit testing. Fractional scale cannot mean
independently truncating each client rectangle. Cursor, glyph baseline and input
must agree on the same transform. Include rotations and negative multi-output
origins in the design, even when the first backend supports one unrotated output.

Validate mode/configuration as a transaction before changing the live output:
overflow-safe buffer size, format/pitch, memory limits, supported mode and logical
work area. Prepare replacement resources, switch at an observable presentation
boundary, and retain/recover the last valid configuration on failure. A stale
commit from an earlier output generation cannot reuse freed scanout buffers.
Resize clamps floating windows and recomputes tiled layout without losing window
identity, focus or content. Output removal relocates reachable windows and keeps
the bar usable; it must not silently destroy application sessions.

SPDP packed geometry is a current wire constraint. Larger coordinates, signed
origins and scale/output events require an explicit versioned extension or
validated coordinate translation. Do not silently reinterpret existing fields or
introduce a second native bus. Add emitter/packager/client/server tests when an
artifact/interface contract changes.

## Multiple typefaces and text correctness

Separate face identity, font asset, family/style/weight, size, logical metrics,
glyph coverage and output raster scale. Product text roles should select faces
through a theme contract: interface/body, command/query, terminal/monospace,
symbols and fallback. At least two genuinely distinct permissively distributable
faces must render simultaneously in the first typeface acceptance slice, with
license and provenance recorded. A scale multiplier or copied bitmap is not a
second face. Terminal cell metrics must remain stable when the UI face changes.

A text request includes encoding, direction/language where relevant, role/style,
size and width constraints. The architecture must account for UTF-8 validation,
Unicode fallback, combining marks, grapheme boundaries, bidirectional text and
script shaping. Font lookup, shaping, measurement and rasterization are separate
steps. Layout measures the same shaped run that rendering paints. Selection,
caret movement, deletion and hit testing operate on text boundaries rather than
bytes or guessed fixed-width cells. Initial ASCII-only milestones must say so;
do not present them as the final text contract.

Font assets are untrusted input. Validate supported formats and bounds; use
bounded caches keyed by asset/face/glyph/size/scale/render mode with explicit
lifetime/invalidation. Fallback must be deterministic and visibly handle a missing
glyph. Support grayscale coverage first; do not assume subpixel order on unknown
panels. Decide color-font/emoji support explicitly instead of accepting a format
that is silently misrendered. Maintain accessibility through legible contrast,
configurable text size, visible focus and keyboard-complete actions.

The dependency decision must evaluate mature shaping/rasterization libraries
before hand-writing a font parser or Unicode shaper. Verify upstream licenses,
portable runtime needs, memory/allocator/error ABI, target build and actual
Space execution. Existing local GPUI/Crepuscularity code may inform reusable
abstractions, but host rendering is not proof of a freestanding Space backend.
No particular dependency is selected or imported by this plan.

## Buffer, resource and authority contract

Keep clients' content buffers owned by their domains. The compositor receives a
bounded, provenance-checked shared mapping, not a client-writable physical pointer.
Define attach/commit/damage/presentation/release and disconnect behavior before
adding asynchronous rendering. A producer must not mutate an in-flight buffer;
a consumer must not read beyond a validated stride/extent. Specify who releases
mapping, backing pages, surface IDs, caches and output resources on each failure.
The existing synchronous SCI pixel proof is not buffer synchronization evidence.

Shell actions reference authorized objects and stable generations. Close/reindex
must not redirect an outstanding command to a different window. A result label
is not launch authority. Font access, input routing, output control and application
launch use distinct responsibilities and least necessary grants. Preserve the
compiler → SCI → packaging → loader boundary and existing denial tests.

## Reuse decision before compositor expansion

Compare three concrete implementation paths against these contracts: retain the
software framebuffer backend while extracting services; port a mature compositor
core/backend through native adapters; or run an upstream stack through a proven
compatibility runtime. Evaluate portability, required syscalls/libraries,
render/text support, protocol coverage, license, maintenance and isolation cost.
A dependency name is not a port plan. Require a minimal client/presentation proof
on Space for the chosen path, preserve fallback boot, and document why alternatives
were rejected. Reuse proven rendering/text code where it fits; do not turn a large
from-scratch compositor into an unexamined prerequisite for the original shell.

## Delivery sequence and acceptance

1. **Architecture and baseline:** document current ownership and failures, inspect
   reference implementations, preserve boot/SCI/personality gates, and record an
   upstream reuse decision with an executable port spike. Current command-bar
   extraction is groundwork, not a completed compositor.
2. **Resolution foundation:** eliminate false fixed-resolution labels; introduce a
   bounded output/work-area contract and test at 1024×768, 1280×720 and 1920×1080,
   plus a portrait logical geometry fixture and invalid/overflow cases. Prove
   nontrivial pitch/format handling, clipping, pointer alignment, resize refusal
   preserving the old state, and reachable controls. State which modes the actual
   backend can present; model fixtures alone do not prove them.
3. **Typeface foundation:** measure and render two distinct faces concurrently;
   verify role selection, terminal cell invariants, baseline/alignment, missing
   glyphs, bounded assets/cache failure and text-size changes. Include real
   screenshots and input/caret interaction at two supported scales. Add Unicode
   shaping/fallback cases as the selected text stack is brought up.
4. **Native interactive services:** migrate surface/seat ownership beyond the
   bounded SCI proof; verify two clients, independent input, buffer release,
   disconnect cleanup and denied cross-client operations. Preserve boot recovery.
5. **Original shell and compatibility:** complete tiled columns/viewport and
   floating roundtrips, command registry/session launch and real browser strategy.
   Add Wayland or other clients through adapters without replacing native policy.
   Test multi-output attach/remove and mixed scale once the backend supports them.

Each step records source/compiler/artifact identity, actual output dimensions,
fonts/scales, memory limits, measured presentation behavior and denied operations.
Do not replace rendered interaction checks with green model tests or version
strings. Physical hardware, GPU acceleration, full Unicode and foreign app support
remain separate proof levels. Update this design and the handoff as decisions
become executable evidence.
