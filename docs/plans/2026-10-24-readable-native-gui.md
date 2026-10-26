# Readable independently executing native GUI applications

The retained GUI lifetime checkpoint058fd15 passed129 real sessions, ownership/
ABA checks and unchanged five-boot persistence. Its64×16 surfaces remain a useful
protocol fixture but are too small for usable applications. This slice keeps
those fixtures independent and builds readable product applications over the
existing SCI, SPDP, output and font contracts.

## Owned canvas and artifact contract

New native `GuiWindowCalc` and `GuiWindowEditor` components explicitly request
`GuiDisplay(present, window)`, with unchanged exact grants20 and52. Existing
`GuiCalc`/`GuiEditor` stay one-page fixtures. The standard product image switches
its kinds20/21 only after named packaging and actual application checks pass.

The Space packager validates those exact declarations and appends a64-byte
canvas trailer to the generic SCI v2 artifact, updating its manifest size:
magic, version1, maximum width768, height384, BGRA stride3072, bytes1179648,
flags1 and reserved0. `protocol/gui-canvas.in` names those constants. Recognized
canvas trailers with unknown versions, malformed bounds, missing authority or
non-retained lifetime must refuse before allocation/mapping/entry. Unmarked
ordinary images retain the legacy profile. This is Space deployment policy; Inauguration
does not gain knowledge of these app names or grants.

The runtime owns288 individual pixel frames, a page ledger and the guest mapping
at0x70001000. Physical contiguity is not assumed. A reserved kernel server view
at0x100000000 + domain×0x40000000 provides contiguous virtual access to those
same frames, above the physical identity window. Its private PD/PT and backing
are bound to the exact retained ledger/generation. Release clears the still-owned
kernel parent entry after the GUI consumer fence, then frees private tables and
frames. Observers inspect that parent, never a freed PD pointer. This does not
use or restore a predecessor's fixed pixel alias. Legacy one-page mappings
remain unchanged.

The runtime owner implements trailer parsing, allocation/mapping/release and
capinfo/snapshot size. The GUI owner implements the protocol constants, strict
named packager, manager/client rendering and the compositor's explicit stride
bounds. The existing compositor remains the renderer; its server surface record
gets an explicit optional stride rather than reinterpreting old wire geometry.

## Client content, layout and output configuration

Each application renders its own window background, title, labels, text, status
and visible caret/focus state into its canvas. Reuse existing Space UI Sans and
Space Term Mono assets and metrics. Share calculator/editor model operations
with the tiny fixtures instead of forking application logic. The editor keeps
its explicit eight-byte persistence boundary during this visual improvement.

The supervisor owns output-relative tiling, focus and coordinate transforms.
Window width is bounded by both256×scale and half the available physical output;
height is bounded by128×scale and available output height. Two3× windows must
remain reachable at1024×768. Client content receives explicit dimensions,
scale, output generation and focus through versioned configuration, and uses
the fixed granted backing stride. The existing32-byte SPDP frame remains the
transport. New configuration/acknowledgement opcodes must be distinct from old
surface/seat opcodes, and the supervisor validates acknowledgements before
changing visible geometry. Resize preserves owned text, answer and saved state.

Current trusted CPL0 startup passes a borrowed supervisor-owned48-byte visual
configuration through `cap-info+64`. The client reads/copies its scalar magic,
generation, extent, scale and focus during startup and retains no pointer.
Post-start configuration uses scalar SPDP events. This borrow is a convention
inside the existing shared identity-map execution model, not an isolation
boundary or a safe protected-client ABI. A later protected startup must copy
validated configuration into an owned bounded client buffer. No manager record,
private capability or runtime instance handle is passed to either client.

The implemented configuration frame uses surface opcode16 and ACK17. Its arg0
is the positive configuration generation; arg1 packs16-bit physical width,
height, raster scale and version1. The client refuses stale generations and
malformed dimensions before changing state. Focus uses a distinct seat opcode16
with exact configuration generation and boolean state. The supervisor validates
the entire reply batch before any compositor mutation.

Ctrl+G changes between2×/3× text; Ctrl+O cycles supported output modes through the
existing validated hardware mode transaction. Both actions have visible hints
inside each window. Calculator/editor logic is shared with the original tiny
clients; their profile and protocol remain unchanged. The default build selects
the readable profile after the high-view rendering/lifetime/storage gates and
core32MiB frame-admission refusal/peer-recovery proof passed.
`GUI_PROFILE=legacy` explicitly selects the original one-page test profile.

The retained input service also receives an optional bounded version1 scalar
output-size argument on each poll. Zero preserves the old descriptor behavior.
Unknown encodings refuse before hardware/state mutation. This keeps pointer
coordinates reachable across resize; the old fixed800×600 input bounds could
not reach the right product window at1920×1080. Actual motion updates the visible
cursor, and full-frame compositing does not erase its old location afterward.

## Actual acceptance

Test1024×768,1280×720 and1920×1080 at2× and3×; assert configured bounds and actual
framebuffer mode/pitch. Exercise real PS/2 input and inverse pointer hit testing,
both typefaces, visible labels/caret/status, calculator results, editing and
Ctrl-S, focus/close/survivor/reopen, and resizing/scale changes with content
preservation. Inspect rendered images as well as checking exact pixels.

Keep tiny protocol/app fixtures,129-session resource/ABA lifetime checks and
actual five-boot NVMe persistence. New canvas release tests must cover every
owned page, stale generation refusal, partial allocation/entry failure and
stable resource counts across repeated window sessions. These remain trusted
CPL0 native applications; no protected or foreign GUI claim follows.

## Executed checkpoints before default promotion

With frozen source-built Inauguration0.9.324:

- `/tmp/space-gui-readable-matrix/report.json` passed all six output/text sizes,
  live state-preserving resize, real pointer focus on both windows, exact two-face
  labels/content/caret/status/shortcut hints, close/survivor/reopen and ordinary
  calculator execution afterward. Source snapshot:
  `/tmp/space-gui-readable-matrix-source.source.json`.
- `/tmp/space-gui-readable-lifetime/report.json` passed129 actual new-window
  sessions with private resource/ABA observer, every pixel page reclaimed,
  server mapping removed, zero remaining GUI/input ledgers and stable resource
  counts after warmup. `/tmp/space-gui-readable-persistence/report.json` passed
  the unchanged actual fiveboot eight-byte NVMe save/shorten/empty/denied-inode
  checks on the new windows. Source snapshot:
  `/tmp/space-gui-readable-lifetime-source.source.json`.
- The actual layout, input poll, client configure/focus/seat parser and server
  reply-batch models pass default/lean/harden. Named artifact policy tests compile
  all four legacy/window SCI declarations and refuse mismatched/widened metadata.
  The original SPDP lifetime model retains its cases and adds stride overflow,
  bounds, reattach and teardown checks.

The initial results above used the low server view. Revised high-view runtime
receipts passed at `/tmp/space-gui-readable-highview-matrix`,
`/tmp/space-gui-readable-highview-lifetime`,
`/tmp/space-gui-readable-highview-persistence` and
`/tmp/space-gui-readable-highview-standard`. Actual compositor/input,129-session
ownership and fiveboot storage all passed with above4GiB server pointers.
Independent desktop launcher, standard/minimal CLI variants and303fps damage
checks passed from the same frozen434-file source. Core OOM proof passed on an
actual32MiB VM with2864 available frames against2865 required, retaining peer
and shell operation. The final default-profile rerun additionally covers saved
content/status through resize, immediate cursor clamp and strict heap extent.
