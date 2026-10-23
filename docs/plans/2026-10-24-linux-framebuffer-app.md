# Original framebuffer viewer: intermediate foreign GUI workload

The full goal still requires original FLTK applications on Linux, Darwin and
Windows. fbv is an additional small upstream workload for discovering display
and input contracts; its command-line startup does not complete a GUI row.

## Pinned original program

Source: godspeed1989/fbv1.1, commit
`57f26fb104ef5a718fc934006408719f929f6811`. The public commit archive SHA256 is
`1a12eab9063d1bbb3ea17391ad4e77c2538620228215b2f786bb65ad3a040ea0`.
The repository declares GPL version2. Configure selects built-in BMP and disables
optional JPEG/PNG, without C/H implementation patches. Configure legitimately
replaces the tracked Make.conf template and emits config.h.

Three independent clean builds produce the same828736-byte static Linux ELF,
SHA256 `8de38de2f88ede5b276aa4ad4f965e22e139357a5a747b1ab1a87e45717fa984`.
The first used a clean git archive, the second the pinned public archive, and
`/workspace/real-apps/fbv-builder-clean3/report.json` verifies the repeatable
`scripts/build-fbv-corpus.py` recipe. All original files except the generated
Make.conf remain byte-identical. A mistaken first provenance check treated
Make.conf as immutable; its failure is retained separately in build2.

The manifest is `fixtures/applications/fbv-1.1.json`. CLI help/no-argument stdout
and stderr hashes are pinned independently of the Space run. The compiler is
host GCC14.2 for the upstream payload; Space itself still builds through the
source-built Inauguration compiler. This is foreign ELF execution, not a Space
rewrite or a substitute native compiler.

## Actual Space evidence

The launcher initially forced argc3. The resulting real failure is retained,
and the bounded counted-entry repair is documented in
[the counted-entry checkpoint](2026-10-24-linux-counted-entry.md).
Both final roots now pass44 original CLI executions plus66 separately classified
startup-fixture entries over21 measured cycles. Exact merged serial output and
status match real host execution. Resource, authority, domain, hook, budget and
caller FS/GS state checks pass. These original entries execute through CPL3
native owned address spaces. That CLI checkpoint does not prove pixels or GUI
input. The later explicit presentation slice below adds original viewer pixels.

## Intended display/input boundary

Run a known BMP through the original viewer, with an explicitly granted real
file and no host framebuffer access. Record its actual missing calls before
extending the personality. Source inspection identifies `/dev/fb0`, Linux fb
ioctls, shared mmap/munmap, terminal polling and signal/VT calls as seams, not as
already observed successful services. Its skip-tty mode can expose the first
software presentation slice before interactive input is ready.

A framebuffer adapter must own a display capability, an execution-local device
handle and bounded guest buffers through the existing native VM object. Preserve
native RO/RW/NX enforcement and checked stopped copies. Do not map physical
scanout or supervisor memory into a foreign process, add a second backing ledger,
fake successful VT/signal calls, or present partially accepted guest writes.
Translate accepted pixels through existing SPDP/canvas attach/damage/commit and
release contracts. Seat events must be routed to the focused owned instance.

Acceptance advances through actual image decoding/presentation, exact independent
pixel checks, real keyboard/pointer effects, resize/scale, two independent
instances, denial/fault/close cleanup and parent-desktop survival. Keep unavailable
services and incomplete stages explicit. A framebuffer prototype or CLI help run
must never be reported as FLTK, X11, Cocoa, Win32 or full desktop compatibility.

## Observed BMP blocker, separate from accepted CLI coverage

The additive `check-linux-fbv.py --bmp-probe` profile deliberately returns
nonzero/blocked even when its diagnostic assertions hold. A real102-byte4x4 BMP
is written through native filesystem APIs and read by the unmodified viewer.
The original program reaches `open /dev/fb0: No such file or directory`, rather
than its corrupt/unknown-image path. Saved file bytes and runtime ownership are
checked after each invocation. That diagnostic invocation presents no pixels;
it remains a missing-device refusal outside the explicit display session.

The headless host error path is also unhealthy: after the missing framebuffer,
upstream cleanup can abort with an invalid free. The source jumps to cleanup
before initializing its image ownership field. This is retained as an unhealthy
reference, with no application patch or fake successful device call. On Space,
its unsupported abort path reaches a genuine GP fault (vector13), returns141,
and still releases ownership and returns to the shell. Host and Space status/
bytes are explicitly recorded as mismatches rather than a passing GUI scenario.

`/workspace/fbv-bmp-first` retains the initial bad short-option/healthy-host
assumption. `/workspace/fbv-bmp-second` and
`/workspace/fbv-bmp-minimal-first` retain the two-root observed-blocker runs.
The source contains correct short `-cy` flags; the host's optional long-y argument
quirk is not used. The original default CLI gate remains strict and separately
passes44 original entries after adding this diagnostic option at
`/workspace/fbv-cli-probe-regression/report.json`.

A healthy graphical reference requires an actual virtual framebuffer. Preparing
a small Linux reference boot is comparison work only; it will never count as
Space application or GUI execution. Its zero-credit reference receipt remains
separate from the later actual Space adapter below.


## Original viewer presentation — explicit initial profile

`/workspace/linux-framebuffer-verified/report.json` passes22 original unchanged
fbv activations plus88 separately counted synthetic syscall/fault/deadline/
quarantine activations, with21 measured resource cycles after warmup. The pinned
828736-byte ELF runs as CPL3 through native owned VM objects. It reads the real
102-byte BMP from SparkFS and uses its own `-cery` enlargement and RGB conversion.
The entire1024x768 RGB screenshot matches an independent BMP/nearest-neighbor
oracle, including all256x128 client pixels, background and cursor. The actual
rendered frame was inspected. Original fbv exits0; no host viewer supplies Space
pixels or application behavior.

This profile explicitly borrows a caller-owned native canvas and independently
granted Memory/Display owner. One open `/dev/fb0` descriptor and one full
131072-byte RW MAP_SHARED mapping are admitted for a sole process. Native VM
owns all backing; no physical scanout/MMIO is mapped. Actual canvas dimensions,
stride and RGB bitfields populate FBIOGET_VSCREENINFO/FBIOGET_FSCREENINFO.
Successful complete unmap performs checked stopped native upload before page
withdrawal. The descriptor may close while its mapping remains writable; the
actual fixture proves that unmap still presents. A completed mapping retires
this bounded lease: remap and concurrent aliases refuse rather than invent file
backing persistence. Unknown ioctl/flags/offsets, partial unmap/protection,
descriptor duplication/replacement and fork/vfork/exec refuse before effects.
Other device reads/writes/stat remain unsupported, with real errors.

The ordinary Linux runtime imports a small optional private device contract;
only this explicit workload imports the framebuffer/display implementation.
A kernel-owned64-byte serialized request and raw machine-ABI status callback
carry private edge calls, not guest-selected function pointers or a new IPC
service. Neither the provider nor canvas is a public SCI export. The minimal
ordinary CLI regression passes44 original CLI plus66 startup fixture entries at
`/workspace/linux-framebuffer-cli-minimal/report.json`; a display-free root does
not gain GUI capability by importing the ordinary Linux runtime.

Each resource cycle adds three genuine negative execution paths: a mapped guest
writes RX code and faults, a mapped guest reaches a serial barrier then expires
its real10-tick IRQ budget, and a stopped mapping receives an actual malformed
PDE before its complete unmap. The latter native copy quarantines the VM, leaves
accepted epoch0, closes admission and retains the edge/canvas lease. Binding and
constructor retirement are independently verified; only trusted page-table repair,
public Linux/native recovery and explicit edge release reopen admission. No CPU
phase is forged and the quarantined guest is not resumed. The test-only frozen
source changes exactly one callback installation to an interposer that always
calls the real provider; canonical/compiled hashes and replacement are recorded.
The production provider has no test hook. Caller FS/GS/capability, frames, domains,
heap, object arena, grants, hook, VM and budget invariants hold after warmup.

Earlier receipts remain failures: missing initial explicit import/helper caused
compile refusals; the first small-image run exited0 but its second mapping was
correctly refused, so the presentation gate failed. A first minimal-GUI compile
exposed a display dependency and drove the optional-device split; it is not GUI
coverage. A reentrancy guard caught the provider recursively querying its own
adapter during FD allocation, repaired to inspect its owned descriptor state.
The first quarantine interposer injected before a partial unmap and caused a
real CPU fault; its final fault-count assertion failed. Injection now targets
only the exact complete unmap, preserving the original assertion.

These are private kernel-linked prototypes, not isolated SCI display services,
ordinary launcher integration, interactive TTY/seat input, remappable framebuffer
backing, X11, FLTK, Cocoa or Win32 GUI completion. Native source
`482bbb1` separately passed two-producer canvas pixels,132 entries,22 faults,
partial-copy grant revocation, mode changes and retained close. The later native
canvas regression also passes at `/workspace/native-canvas-framebuffer-regression`.
The application lab now adds two mandatory gates (native canvas and original
framebuffer viewer) for135 total; a fresh committed integration run is required.
