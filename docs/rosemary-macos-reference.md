# Rosemary reference for the macOS personality

Source review: 2026-10-23. Space baseline:
`457bb24b57800ac111d1ec8d12f7af2664afc8f1`. Rosemary baseline:
[`f845f21842c85f6863cfa8a7a749cb945b88994a`](https://github.com/microlift/rosemary/tree/f845f21842c85f6863cfa8a7a749cb945b88994a).
This is a source-based integration proposal. No Rosemary code is imported and
no Rosemary build, macOS application execution or new Space runtime gate was run.

That review baseline is historical. Subsequent Space work now provides native
owned address spaces and a separate finite high-address Darwin mapper, with318
actual CPL3 fixture entries and147 setup refusals on each standard/minimal test
root. It validates original Mach-O layout/chains and refuses original jq at
`__DefaultRuneLocale` before native allocation. See the
[mapper checkpoint](plans/2026-10-24-darwin-owned-mapper.md) and
[full application goal](compatibility-coverage-goal.md). These are Space's own
mechanisms; no Rosemary implementation code or host runtime was imported.
Original Darwin applications, Objective-C/framework behavior and foreign GUI
integration remain open. Native protected calculator/editor sessions are the
current local GUI test foundation, with their scope recorded in that full goal.

## Recommendation

Use Rosemary as a reference for the user-space macOS stack: Mach-O loading and
dynamic linking, explicit import ABIs, Objective-C, Foundation and AppKit.
Keep Space's existing BSD translator and native component architecture. Start
with native x86_64 execution on x86_64 Space; evaluate cross-architecture lifting
only after the process and framework contracts work. Microlift is not a
replacement for Inauguration or the native SCI compiler pipeline.

The eventual path is:

`command dispatcher → application supervisor → Darwin runtime → Mach-O guest`

`guest AppKit → personality display adapter → SPDP → Space compositor`

Focused seat events travel back through the adapter into the guest event loop.
These are proposed responsibilities, not interfaces already provided by Space.
SCI remains the deployment/authority boundary for native components; Mach-O is a
foreign payload managed by the personality. Do not treat a Mach-O header as an
SCI capability declaration.

## What the source establishes

Space's [`darwin.in`](../components/darwin.in) implements a BSD-shaped adapter
with Space-local shims and Mach stubs. [`darwin-macho.in`](../components/darwin-macho.in)
accepts a fixed-address, single-RX-segment returning fixture. The hardware
syscall/file fixtures are bounded CPL0 executions with interrupts disabled.
They do not establish process startup, dyld, protected application memory or
ordinary macOS compatibility; see [personalities](personalities.md).

Rosemary combines a Mach-O runtime with reimplemented frameworks and native or
emulated execution. Its Darwin/framework layers depend on hosted facilities
such as Rust `std`, libc, threading, dynamic libraries and SDL3. Linux support
therefore does not imply a freestanding Space port. Its
[`syscall` test](https://github.com/microlift/rosemary/blob/f845f21842c85f6863cfa8a7a749cb945b88994a/crates/rosemary/tests/syscall.rs)
explicitly checks refusal of a guest raw Darwin syscall; do not assume the
import bridge supplies a complete XNU syscall environment.

## Reference map

All Rosemary paths below are relative to the pinned revision linked above.

| Rosemary source | Useful reference | Space integration boundary / missing work |
|---|---|---|
| `crates/machish/src/{fat.rs,loader.rs,fixups/,exports/}` | Slice selection, segment loading, symbol resolution and rebasing | Extend beyond the trusted fixture only with domain-owned memory, bounded parsing and refusal tests. Keep foreign format policy outside the nanokernel. |
| `crates/machish/src/memory/mod.rs`, `resolve/mod.rs` | `AddressSpace`, `ProtectionPolicy`, `SymbolProvider`, synthetic dylibs | Candidate portable loader core; Space must supply real memory/protection and explicit symbol providers. Host addresses cannot be copied into isolated guest import slots. |
| `crates/rosemary/src/abi/{table.rs,marshal.rs,aggregate.rs}` | Declared signatures, register and aggregate marshaling | Define the guest-to-runtime ABI, callbacks, stack alignment and error behavior. Resolve only typed, authorized imports; unknown signatures fail. |
| `crates/darwin/src/`, `crates/starnix/src/`, `crates/server/src/` | Darwin structures, errno/descriptor translation, host/process separation | Map onto granted Space VFS/process/channel objects. Replace host libc, `/proc`, Unix sockets and ambient filesystem access as required by each selected API. |
| `crates/objc/`, `crates/corefoundation/`, `crates/foundation/` | Builtin Objective-C runtime, object lifetime, strings and framework behavior | Bring up a declared subset after callbacks, allocation, TLS, threads and run-loop needs have explicit contracts. Apple runtime passthrough is unavailable. |
| `crates/appkit/src/{window.rs,event.rs,backing.rs,screen.rs}` | NSWindow lifecycle, event translation and software backing stores | Extract a display backend boundary around current SDL3 calls; translate to SPDP and focused seat input. These files are references, not an existing pluggable Space backend. |
| `crates/rosemary/tests/{link.rs,tlv.rs,msgsend.rs,runloop.rs,appkit.rs}` | Behavioral fixtures and failure expectations | Reproduce selected behavior with distributable fixtures; record toolchain skips separately from executed coverage. |

`machish` uses `#![no_std]` plus `alloc`; its default features enable host `std`
and optional loader extensions. A direct reuse spike must select features
explicitly, supply allocation/error behavior and prove a target build. Its
`AddressSpace::protect` permits implementations that do nothing, so satisfying
that trait alone is not memory isolation. `ProtectionPolicy::Strict` is the
candidate for a native protected guest; verify actual page permissions.
Successful mappings also need supervisor-owned rollback and teardown; the
loader trait alone does not establish resource reclamation.

## Staged executable slices

1. **Protected Mach-O execution before frameworks.** Add a separately gated
   personality runtime slice, preserving the trusted fixture gates. Run one
   import-free native x86_64 Mach-O in a private CPL3 address space with explicit
   stack/startup/exit contracts. Prove BSS zeroing, entry/segment bounds, actual
   RX/RW/NX enforcement, denied kernel access, termination and cleanup. Loading
   arbitrary addresses or invoking guest code at CPL0 is not the acceptance gate.
2. **One typed dynamic import.** Support only the load commands/fixups needed
   by a small fixture importing `_write` and `_exit`. Bind to guest-accessible
   trampolines that cross a checked service boundary; copy/validate buffers and
   maintain per-instance descriptors and Darwin errors. Reject unresolved
   imports, unsupported dylibs/fixups, invalid pointers and unauthorized storage
   before side effects. Repeat launch/exit to prove cleanup. Direct syscalls
   need their own explicitly supported trap path or a clear refusal.
3. **Objective-C and Foundation subset.** Prove message dispatch, a callback
   into guest code, autorelease/retain/release, TLS/errno separation and a bounded
   run-loop source. Expand only from fixture-observed API requirements. Keep
   unsupported Mach ports, exceptions or concurrency behavior explicit.
4. **One software-rendered macOS client.** Launch a tiny AppKit guest that
   draws an asymmetric opaque pattern and changes it on one real key event.
   Its personality adapter owns the surface/pool identities and converts backing
   pixels into the existing SPDP shared-page pipeline. Prove exact visible
   pixels, bounded damage, one input delivery, close and post-close refusal.
   This is a bounded AppKit proof, not general macOS GUI support.
5. **Desktop launch and multiple clients.** After the supervisor and focused
   seat route exist, register a typed launch action in the command model. The
   action carries an application identity and approved grants; the supervisor
   validates the bundle/executable and reports launch or failure. Use stable
   instance/window generations, distinguish launch from focus, and remove stale
   results on exit. Prove two clients, focus changes, pointer input, resize/scale,
   denied cross-client access, crashes and repeated teardown before claiming
   desktop integration. Keep the action unavailable until the executable path
   works; no shell command string or fake launch row.

## Implemented reference-driven slices — 2026-10-24

Space now implements bounded parts of slices1 and2 in original `.in` source:
`darwin-protected.in` admits a fixed-address Mach-O profile, builds private
CPL3 mappings and guest RX import trampolines, validates borrowed service
capabilities and guest buffers, and reclaims execution-owned resources. The
protected process/import gate passes483 activations; the read-only file gate
passes464. Those are fixture counts, not original macOS application coverage.
Original macOS jq remains refused and unexecuted. No Rosemary code or host
runtime has been copied, linked or vendored to obtain these results.

The next application startup contract must distinguish `LC_MAIN` from
`LC_UNIXTHREAD`. Rosemary's pinned
[`image/entry.rs`](https://github.com/microlift/rosemary/blob/f845f21842c85f6863cfa8a7a749cb945b88994a/crates/machish/src/image/entry.rs)
records that LC_MAIN follows dyld/libSystem initialization. Its
[`startup.rs`](https://github.com/microlift/rosemary/blob/f845f21842c85f6863cfa8a7a749cb945b88994a/crates/rosemary/src/startup.rs)
passes argc/argv/envp/apple to initializers, runs them before main and handles
thread-local/process termination afterward. Its TLV reporting distinguishes
per-thread data/BSS from descriptors and initialization callbacks. These are
useful behavioral seams to verify independently; calling the current bounded
entry with zero arguments does not supply them.

Before importing broader framework behavior, implement owned startup strings,
argument vectors, initialization ordering, TLS/errno and bounded callbacks
through the same protected runtime. Keep static layout admission separate from
an executable dependency graph. Then drive a real macOS CLI binary and retain
its unresolved-import/runtime failures. The full app and GUI acceptance rows
remain in [the active coverage goal](compatibility-coverage-goal.md).

The separate [protected startup profile](darwin-startup-checks.md) now proves
owned argc/argv/envp/apple and distinct LC_MAIN/LC_UNIXTHREAD entry conventions
through actual CPL3 fixtures. Its strict no-dependency admission does not run
dyld, libSystem initializers, constructors or TLS/TLV. Original macOS jq remains
refused; a pinned host trace records its 17 commands and 136 undefined symbols.
The existing protected/file profiles remain unchanged.

A separate [eager dependency adapter](darwin-eager-checks.md) now binds genuine
chained Mach-O imports to seven existing typed services, using a finite native
provider identity and private guest trampolines. It proves real calls and
preparation before main, with unknown imports refused before allocation. It
loads no libSystem executable and runs no library constructor or TLV machinery;
original macOS jq remains refused.

## GUI contract to settle before slice 4

Reuse [`protocol/display.in`](../protocol/display.in) and the existing channel /
shared-page mechanisms. The current SCI pixel and keyboard proofs establish
bounded synchronous exchanges, not a general asynchronous multi-client desktop;
see the [compositor/client split](compositor-client-split.md).

- Associate each guest NSWindow with an adapter-owned surface and generation.
  Space layout policy owns placement/focus; foreign AppKit semantics stay in the
  personality. Do not import Rosemary's Aqua decorations as Space shell policy.
- Rosemary's `backing::Store` contains top-row-first, premultiplied BGRA pixels.
  SPDP specifies BGRA with pitch `width * 4`, but does not establish matching
  alpha semantics. Begin opaque; validate orientation, stride, extents and
  logical/pixel scale. Define alpha handling before translucent windows.
- The client owns backing storage. Grant only bounded shared mappings to the
  compositor; validate ownership and arithmetic before attach/commit. Specify
  in-flight immutability, release and disconnect/revocation before asynchronous
  presentation. A comment promising a frame callback is not a working fence.
- Translate only events delivered to the focused authorized surface. The current
  input proof routes selected normalized ASCII/control key presses; it does not
  provide SDL scancodes, full key releases, modifiers, repeat or IME. Name the
  slice's limitation and add protocol coverage before expanding it.
- Reject geometry beyond the current packed 16-bit wire fields. Follow the
  [display/text plan](plans/2026-10-19-display-text-architecture.md) for scale,
  fonts and coordinate conversion. GPU/Metal, WebKit, audio, clipboard and global
  menus remain later independently granted adapters.

## Reuse decision and next work item

Reference-first is the current choice. Rosemary is GPL-3.0-only according to its
workspace manifest; Space carries MPL-2.0. Direct copying, translation or linking
needs an explicit license/distribution decision with attribution and dependency
review. A service boundary alone does not decide those obligations. No vendoring,
submodule or Rust runtime dependency is introduced by this review.

The next implementation extends the protected `.in` loader toward real startup
and application dependencies, retaining the bounded slice1/2 gates. Decide
separately whether to adapt `machish` after checking the foreign-library/SCI
linking path and license. Do not make a complete hosted Rosemary/SDL/Vulkan port a prerequisite.
Keep Space-specific ABI wrappers here and generic compiler/foreign-ABI support
in Inauguration.

For later hosted Rosemary comparisons, pin the revision and use
`ROSEMARY_OBJC=builtin`, `ROSEMARY_STRICT_IMPORTS=1`, and, on non-macOS,
`ROSEMARY_NO_PASSTHROUGH=1`; confirm these against its `docs/usage.md`.
These controls expose missing imports; they do not remove hosted dependencies.

For runtime work, preserve `check-darwin-personality.sh`, `check-darwin-macho.sh`
and `check-foreign-syscalls.sh`; GUI work also needs `check-spdp-sci.py`,
`check-spdp-input.py`, `check-sci-seat.py`, desktop launcher/damage regressions
and real keyboard/pointer/visible-pixel acceptance for the added slice. Use an
explicit source-built Inauguration compiler. This documentation review requires
`git diff --check` and reference consistency checks only.
