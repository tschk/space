# Working operating systems: integration goal

Develop Space and Subspace through executable vertical slices, using the existing architecture and component contracts. Keep OS policy in `.in`; retain assembly for CPU entry, traps, register/context handoff, and instruction sequences the language cannot express. General compiler and ABI capabilities belong in Inauguration.

## Initial integration evidence (historical snapshot)

- Space is pushed on `main` through `0699c03`: explicit native-call wrappers, initialized boot data and safe heap reservation, capability-binding repair, personality fixes, and the desktop switcher/input changes. The full root passes real QEMU shell/hardening, Darwin and Windows demos, foreign Linux/Darwin/Windows fixtures, user SCI hello/echo, and dynamic-module chaining/refusal. Kernel-linked CPL0 services are not isolation.
- Inauguration `0.9.213` (`0be5933b`) and `0.9.214` (`6e11635a`) are pushed on `main`. The former adds raw native calls and radix literals; the latter retains initialized boot data and pointer fixups. `0.9.215` (`2b68271c`) is also pushed and registers the existing native word-I/O operations in the common checker. Its full ARM/x86 suites, strict Clippy, source-built CLI integration, target matrix, owned-native and protocol gates pass. No crate publication or release tag is implied by these Git checkpoints.
- The actual QEMU desktop passes keyboard search/edit/focus, terminal input, pointer taskbar focus, pointer launcher opening, Escape behavior, and rendered pixel assertions. Primary inspection confirmed separated taskbar labels. The reset protocol is checked in both input implementations, including rejected replies preserving keyboard access. The standalone runtime-components gate passes display/input startup, volume read/write/RPC, SCI loading and Linux file access with the verified `0.9.215` compiler.
- Subspace is pushed on its default branch `master` through `0bd26e5`: linked SCI-E entry validation, UF2/flash boundaries, unprivileged task stacks, and fail-stop unknown MemManage faults. After upstream integration and the final compiler frame fix, 59 Bun tests, normal AN521 QEMU, and the unknown-fault negative image pass. CI passed. Hardware flashing remains skipped.

## Parallel work and acceptance

1. **Boot and language boundary.** Make raw native-ABI calls explicit without weakening exception propagation for language functions. Consume the generic compiler capability through Space-owned architecture wrappers. Prove boot, shell interaction, and clean return after fixtures with `check-qemu-smoke.sh`, `check-kernel-contracts.sh`, and affected runtime gates.
2. **Personalities.** Fix demonstrated translator errors and expand executable coverage. First: clearing one Darwin descriptor's CLOEXEC flag must retain another descriptor's flag. Require the isolated regression and `check-darwin-personality.sh`; retain Windows/Linux/foreign-fixture checks. Fixture execution does not imply arbitrary macOS, Windows, or Linux application compatibility.
3. **Desktop.** Target an upstream Wayland + Budgie session, initially using labwc, with Space-specific runtime and display/input adapters. Keep the existing compositor and SCI-client checks as a boot fallback and regression baseline while the port develops. Retain `tschk/alpenglowed` as an interaction reference for later customization. Prove real Wayland clients and Budgie components on Space before claiming desktop compatibility.
4. **Subspace.** Preserve and review the existing MPU/task/UF2 changes. Bind SCI-E records to the actual linked ARM ELF entry, verify structure and CRC, reject malformed inputs before output, and rerun Bun, SCI-E, and QEMU gates. Keep SCI-E separate from Space's SCI format; no heap, filesystem, or runtime component loader in the MVP.
5. **Integration and publication.** Primary agent reviews each actual diff, runs appropriate repository gates, and makes logical commits/pushes. Record source revision, compiler selection, and actual proof level. Continue through reproducible correctness and coverage gaps rather than treating a green demo as a complete OS.

References: `architecture.md`, `docs/personalities.md`, `docs/personalities-roadmap.md`, `docs/compositor-client-split.md`, `docs/plans/2026-09-18-dynamic-nanokernel.md`, and Subspace's `docs/vertical-slice.md` and `docs/contracts/`.

## Wayland + Budgie desktop port direction

Requested direction: reuse the existing desktop stack first, then refactor the
Space integration and shell incrementally. Keep component domains, capabilities,
and hardware policy in Space; keep generic compiler changes in Inauguration.

Upstream Budgie 10.10 uses Wayland and recommends labwc. Its panel and Raven
need layer-shell, with additional workspace, toplevel and output protocols.
Budgie also depends on GTK/GLib and desktop services. Importing a shell alone
does not supply that runtime. Sources: [Budgie build requirements](https://docs.buddiesofbudgie.org/10.10/developer/workflow/building-budgie-desktop/)
and [labwc build dependencies](https://github.com/labwc/labwc/blob/master/meson.build).

Space currently has a framebuffer compositor, input handling and bounded
SCI-owned pixel/seat proofs. `protocol/display.in` is a fixed 32-byte SPDP
protocol, not the Wayland wire protocol. Current foreign executable fixtures
also do not provide a general dynamically linked Linux desktop userland.

Port boundaries and acceptance:

1. Establish the userspace/runtime contract for libwayland and labwc: local
   stream transport, descriptor/shared-buffer transfer, event readiness,
   memory mappings, libc and required library loading/linking. Validate real
   client/server round trips and malformed/disconnected-client cleanup.
2. Bring up a Space display/input backend for the compositor using existing
   services. Start with software rendering and one output; preserve buffer
   ownership, bounded damage and input focus. Choose and verify the backend
   interface against the selected wlroots release before implementing it.
3. Run an upstream Wayland shared-memory client under Space in QEMU. Require
   visible pixels, frame/release callbacks, keyboard/pointer interaction and
   clean teardown. A Linux-hosted reference session is useful development
   evidence but does not satisfy this Space acceptance check.
4. Add the protocols and session services required by Budgie; bring up its
   panel/menu and launch a real client. Then customize shell behavior and
   replace platform adapters incrementally, retaining interoperability tests.

Licensing must be resolved before importing code: current contributor rules
require permissive dependencies, while Budgie binaries and labwc are GPL-2.0
(Budgie shared libraries use LGPL-2.1). This plan adds no upstream dependency.
See [Budgie licensing](https://github.com/BuddiesOfBudgie/budgie-desktop#license)
and [labwc licensing](https://github.com/labwc/labwc/blob/master/meson.build).
No Wayland client, labwc, GTK or Budgie execution on Space is established yet.

## Next bounded work

- Keep the new personality, heap/input, runtime-component and graphical interaction checks in CI, pinned to the verified compiler revision.
- Repair generic Thumb calls with stack arguments, using the existing failing 5/6/7-argument QEMU fixture. This should allow the RTOS to express MPU parameters directly instead of packing them to work around the compiler.
- Restore a genuinely minimal root dependency boundary. It currently fails on missing `syscall-dispatch`; importing the shared full shell/loader also pulls personality, storage and network dependencies. Do not describe that profile as working or restore it with permissive stubs.
- Expand descriptor redirection/shared-offset and process termination contracts from executable proofs. Current fixture and demo results do not establish arbitrary macOS, Windows or Linux application compatibility. SCI-E remains a validated header plus JSON, not a runtime loader.

Evidence directories on the verification host: `/tmp/space-desktop-launcher-215-primary/`, `/tmp/space-personality-audit-20261016/`, `/tmp/space-host-gates-215/`, and Subspace `target/verification/subspace-review/`. Test images are emulation evidence, not hardware validation.
