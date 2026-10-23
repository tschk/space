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
native owned address spaces. The app has not drawn pixels or received GUI input.

## Next executable boundary

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
