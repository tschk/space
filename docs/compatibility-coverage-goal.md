# Compatibility coverage and GUI application goal

User direction: 2026-10-23. Grow Linux, Darwin/macOS and Windows coverage through
working, tested slices while improving the native desktop enough to exercise
real GUI clients. This is an ongoing engineering goal, not a claim of general
application compatibility or a scheduled background task.

## Completion target for the next milestone

Establish a reproducible compatibility lab on Space:

- Run small ELF, Mach-O and PE fixtures through their actual ABI entry paths,
  record exact results and errors, and repeat runs to detect lifecycle leaks.
- Add executable positive, invalid-input, denied-authority and cleanup checks
  with each supported behavior. Preserve previous assertions and refuse unknown
  operations instead of returning invented success.
- Display one client-owned software surface that changes in response to real
  focused keyboard input, then prove close and post-close refusal. Follow with
  two independently owned clients, focus changes and pointer interaction.
- Keep desktop resolution, scaling, typography, query/selection, layout and
  damage performance gates green. Foreign GUI adapters must not become a reason
  to regress the native desktop or move policy into the nanokernel.
- Record source/compiler identities, commands, results, logs and screenshots.
  State which tests actually executed and which were skipped or blocked.

Each PR should close one behavioral gap with observable evidence. A larger API
count without executed behavior does not satisfy the goal. Do not use a single
percentage of all Linux/Windows/macOS APIs as a coverage metric: the denominator,
ABI version and dependencies would be misleading.

## Source-reviewed baseline

The current source supplies kernel-linked translators, bounded trusted foreign
execution fixtures and native SCI display/input proofs. These are different
levels of coverage; preserve that distinction in results. The source baseline
and limitations are described in [personalities](personalities.md), the
[roadmap](personalities-roadmap.md), the [compositor/client contract](compositor-client-split.md)
and the [Rosemary review](rosemary-macos-reference.md).

| Area | Present source coverage | Next evidence needed |
|---|---|---|
| Linux | BSD/POSIX-shaped service calls; bounded ELF serial/read-only file fixtures; a bounded Unix stream-pair fixture and model checks | Broader descriptor operations through actual ELF calls, real process startup/lifecycle, private guest mappings and Linux structures |
| Darwin | BSD-shaped translator, errno mapping and Mach stubs; thin fixed-address Mach-O serial/read-only file fixtures | Private process memory and startup, supported mapping/fixups/imports, Objective-C/framework subset, real Mach contracts where required |
| Windows | Space-local call table, typed bounded handles, paired NTSTATUS/LastError; PE fixture with selected KERNEL32 imports | Additional typed imports with Win32 error/output semantics, process/domain lifecycle, ntdll/Win32 separation and user/window APIs |
| Native desktop | Kernel-linked desktop, command/layout/output/text modules and bounded SPDP/SCI pixel/input proofs | Sustained independent client lifecycle, focused multi-client seat routing, buffer release, resize/scale and fault/disconnect recovery |

This table records source inspection, not a fresh all-green test run. Trusted
CPL0 fixtures do not prove isolated foreign applications. Existing source-level
module extraction does not establish a separately enforced SCI service boundary.

## Upstream research anchors

Reviewed 2026-10-23, pinned to the revisions below. No source was copied into
Space as part of this research. Follow per-file licenses before reusing code or
test bodies; an algorithm or behavior reference is not a dependency decision.

| Project / revision | Inspected source | Takeaway for Space |
|---|---|---|
| ReactOS `e81244349554c4f98a97fdd7fb67d7a1b450eec5` | [ReadFile API tests](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/modules/rostests/apitests/kernel32/ReadFile.c), [NtReadFile tests](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/modules/rostests/apitests/ntdll/NtReadFile.c), [user message queues](https://github.com/reactos/reactos/blob/e81244349554c4f98a97fdd7fb67d7a1b450eec5/win32ss/user/ntuser/msgqueue.c) | Keep Win32 BOOL/count/LastError distinct from NTSTATUS/IO_STATUS_BLOCK. Test invalid handles, EOF, zero lengths and output-pointer effects. Message queues and focus are real subsystem work, not a drawing shortcut. |
| Wine `840a939ee526137639665ff5f587224d6a36403f` | [kernel32 file tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/kernel32/tests/file.c), [ntdll file tests](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/ntdll/tests/file.c), [win32u driver](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/win32u/driver.c), [Wayland surface adapter](https://github.com/wine-mirror/wine/blob/840a939ee526137639665ff5f587224d6a36403f/dlls/winewayland.drv/wayland_surface.c) | Separate foreign API implementation from display backend. Its SHM attach path marks buffers busy until commit and compositor release; borrow the ownership discipline when defining SPDP release, not assumptions that Space already speaks Wayland. |
| gVisor `8938ebcf1c12a6266bdf5a650088e1360777aa94` | [read tests](https://github.com/google/gvisor/blob/8938ebcf1c12a6266bdf5a650088e1360777aa94/test/syscalls/linux/read.cc), [pipe tests](https://github.com/google/gvisor/blob/8938ebcf1c12a6266bdf5a650088e1360777aa94/test/syscalls/linux/pipe.cc), [file syscalls](https://github.com/google/gvisor/blob/8938ebcf1c12a6266bdf5a650088e1360777aa94/pkg/sentry/syscalls/linux/sys_file.go) | Measure observable Linux semantics: partial transfers, nonblocking state, drain-before-EOF, closed peers, descriptor flags and offsets. Keep emulated kernel concepts inside the personality rather than adopting gVisor as Space's kernel. |
| Darling `60ba801decee7a00782f74f6be4c8ffb013f79ff` | [project overview](https://github.com/darlinghq/darling/blob/60ba801decee7a00782f74f6be4c8ffb013f79ff/README.md) | Distinguish Darwin syscall/framework coverage from GUI maturity. Darling describes Linux-hosted runtime and syscall translation with GUI support in active development; it is a comparison target, not a demonstrated freestanding Space dependency. |
| Rosemary `f845f21842c85f6863cfa8a7a749cb945b88994a` | [loader, ABI, framework and GUI review](rosemary-macos-reference.md) | Start native x86_64; explicit imports and software backing stores are useful reference seams. Host libc/SDL/Rust std and raw host pointers must be replaced or constrained by Space contracts. |

The ReactOS ReadFile test carries MIT, while the inspected NtReadFile test
carries LGPLv2.1+. ReactOS is a mixed-license tree, so its project name is not a
license identifier. The inspected Wine files carry LGPLv2.1-or-later headers;
gVisor's inspected tests carry Apache-2.0. Darling's top-level license is GPLv3
and its overview notes separately licensed submodules. Rosemary declares
GPL-3.0-only, while Space has MPL-2.0. Evaluate actual copied/linked components,
not an assumed exemption from placing them in a separate service.

## Executable coverage ladder

Use two independent axes when recording coverage: the entry path and the tested
behavior. A source constant check can guard an ABI number, but cannot stand in
for a guest calling it.

| Evidence level | Required observation |
|---|---|
| Contract | ABI numbers, structure/layout and unsupported-value policy are checked |
| Behavior model | Actual owning functions execute against a controlled model, including refusal and unchanged state |
| Guest fixture | ELF/Mach-O/PE code invokes the real hardware/import path in QEMU and checks return/output/error conventions |
| Protected process | Private CPL3 mappings, startup/exit/fault behavior, guest-pointer validation, denied access and resource lifetime are exercised |
| GUI client | Client-owned pixels visibly change after real authorized input; focus, buffer and close behavior are checked |
| Application | A named unmodified application/version works for a documented scenario through the established contracts |

A named fixture belongs to its actual level. Repeated execution is part of
acceptance, not evidence that a fixed CPL0 runner became a process environment.
When behavior needs blocking waits, interrupts, threads or asynchronous I/O,
first add the corresponding runtime/process contract; do not spin indefinitely
inside the interrupts-disabled trusted runner.

For every added behavior, retain a small evidence record containing personality,
ABI entry, supported arguments, explicit refusals, expected outputs/errors,
required capabilities, positive/negative cases, compiler revision, test command
and artifact location. Report pass/fail/skip counts per suite and evidence level.
Add new cases without weakening old assertions to make the totals rise.

## First implementation sequence

1. **Descriptor semantics across all three personalities.** Keep common VFS
   ownership and bounded buffers, but test each foreign ABI separately. Prioritize
   EOF/count behavior, zero-length transfers, invalid handles/pointers, duplicate
   lifetime, offset/seek and cleanup on exit/return. Linux uses negative errno;
   Darwin hardware calls use carry/positive errno; Windows imports use their
   declared BOOL/handle/count/error conventions. Unsupported modes must fail
   without backend side effects. Add a guest fixture when extending a model.
2. **Protected foreign execution.** Follow the Mach-O slice in the Rosemary
   review, then reuse generic domain/startup/lifecycle machinery for ELF and PE.
   Keep each format's validation, relocation/import and startup rules explicit.
   Add denied kernel/other-client memory cases and repeated fault/exit cleanup.
   Keep generic ABI/compiler fixes in Inauguration and Space policy here.
3. **Software GUI adapter proof.** Make the existing native SCI surface/input
   path sustained and ownership-safe, then translate one tiny guest's software
   backing surface and input events. Do not require a complete Wine, Darling,
   SDL, X11 or Wayland environment before this bounded proof works.
4. **Application-driven expansion.** Choose a small redistributable program per
   personality and record its exact import/syscall/framework requirements. Add
   the smallest coherent missing contract with differential/reference tests,
   rerun the supported scenario and retain previous fixtures. Only then choose
   a larger CLI or GUI application. Metal/Vulkan, browsers and broad desktop
   frameworks remain separate service/backend workstreams.

## Desktop acceptance needed for foreign GUI testing

Keep command dispatch, layout, compositor, seat and application supervisor
separate. Follow the [display/text plan](plans/2026-10-19-display-text-architecture.md)
and [command desktop plan](plans/2026-10-19-command-desktop.md).

- Exercise the supported output modes and scales with two real typefaces,
  legible controls, correct caret/text hit testing and unchanged logical/pixel
  coordinate rules. Add Unicode/shaping support only with actual rendering and
  input coverage; an unknown-glyph box is not full Unicode typography.
- Present client-owned opaque software pixels through bounded SPDP shared
  mappings. Specify stride, extents, orientation, damage, in-flight immutability,
  release and disconnect/revocation before asynchronous rendering. Match alpha
  semantics explicitly before testing transparent windows.
- Prove keyboard and pointer input reach only the focused authorized client.
  Test focus changes, command bar capture/dismissal, close/reindex, stale surface
  identities, two independent client streams and post-close refusal. Extend the
  present selected-ASCII key proof before claiming modifiers, repeats or IME.
- Prove resize/scale transitions preserve content and invalidate only valid
  regions. Inspect actual rendered output as well as geometry/state, and keep
  the existing damage/performance threshold. Test failures and teardown while
  another client remains interactive.
- Enable a launch action only after the supervisor really starts that executable
  with validated grants and reports failure/exit. Focusing an existing terminal
  is focus; a second terminal needs a distinct live session. A decorative window
  or an unavailable browser entry is not foreign GUI compatibility.

## Gates and continuation

Run focused owning-function checks first, then relevant QEMU fixture, SCI and
personality gates. Existing starting points are `check-personality-abi.sh`,
`check-local-stream.py`, `check-darwin-pipe-lifetime.py`,
`check-vfs-shared-offset.py`, `check-posix-wait-status.py`,
`check-windows-wait-result.py`, `check-mmap-lifetime.py`,
`check-darwin-personality.sh`, `check-windows-personality.sh`,
`check-darwin-macho.sh` and `check-foreign-syscalls.sh`.

Desktop work also retains `check-display-output-text.py`, `check-commandbar.py`,
`check-desktop-launcher.py`, `check-desktop-damage.sh`, `check-spdp-sci.py`,
`check-spdp-input.py`, `check-sci-seat.py` and affected boot/runtime gates. Use an
explicit source-built compiler and keep failure artifacts. Update this goal's
linked behavior documents and the working handoff when a slice is verified;
record baseline failures separately from regressions. Keep a draft PR reviewable
through small coherent commits while expanding the next executable gap.
