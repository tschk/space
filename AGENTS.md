# AGENTS

Space is a separate OS repository. Keep Space-specific source, examples, schemas, boot plans, and component contracts here.

## Architecture priority: hypermodular Space

The architecture is the priority, including during desktop work. Space's native
model is **component + capability + object + execution graph**. Do not grow a
Unix kernel, a monolithic desktop, or a collection of shell-command facades in
place of that model. Prefer cohesive modules with explicit ownership and small,
typed contracts; adding files alone does not establish a runtime boundary.

Read the relevant canonical documents before changing a boundary:

- [`architecture.md`](architecture.md): layer ownership, current runtime and isolation limits.
- [`sci-schema.md`](sci-schema.md): artifact layout, metadata, linking and loader rules.
- [`docs/plans/2026-09-18-dynamic-nanokernel.md`](docs/plans/2026-09-18-dynamic-nanokernel.md): provider registry and chained modules; historical plan, verify implementation before relying on status.
- [`docs/compositor-client-split.md`](docs/compositor-client-split.md): surface ownership, SPDP, shared pages and seat/input proof boundaries.
- [`docs/personalities.md`](docs/personalities.md) and [`docs/personalities-roadmap.md`](docs/personalities-roadmap.md): foreign ABI boundaries and executable coverage.
- [`docs/plans/2026-10-19-command-desktop.md`](docs/plans/2026-10-19-command-desktop.md): original command desktop and acceptance criteria.
- [`docs/plans/2026-10-16-working-os.md`](docs/plans/2026-10-16-working-os.md): integration work; distinguish historical results from fresh verification.

These documents describe both destination and current implementation. When they
disagree, inspect source and runtime evidence, repair the affected documents,
and retain the intended architecture unless the user changes it. Do not silently
turn a prototype limitation into the desired design.

### Layer and authority contract

- **`.in`** expresses native code, component/interface declarations and source
  authority. Move expressible service and policy logic above assembly. Keep
  assembly for CPU entry, traps, register/context handoff and instruction
  sequences the language cannot yet express; implement missing generic language
  support in Inauguration rather than adding a second Space compiler.
- **Inauguration** owns reusable parsing, Core IR → MIR → native emit/JIT,
  freestanding/native ABI support and generic component metadata/artifact
  emission. No LLVM/bytecode runtime substitution. It must not hardcode Space's
  capability names, grant masks, app names, boot policy or desktop semantics.
- **SCI** is the native component boundary. Code, imports/exports, declared
  authority, memory requirements and available provenance travel through the
  compiler/artifact/packager/loader contract. Preserve the distinction between
  metadata sidecars, executable image manifests and actual runtime checks.
  Space packaging translates generic compiler metadata into its concrete
  capability vocabulary and image policy; it must reject unknown/mismatched
  declarations rather than silently widening grants.
- **Nanokernel** owns hardware enforcement: domain/page-table transitions,
  trap/interrupt/context entry, capability enforcement and minimal execution/IPC
  mechanisms. Drivers, filesystems, networking, personalities, shell, layout and
  application policy belong in separable components/services. Current root
  imports are boot scaffolding, not permission to keep adding those policies to
  the trusted core. Preserve working boot while extracting explicit contracts.
- **Space runtime/supervisor/loader** owns activation, dependencies, grants,
  object lifecycle and service binding. Validate image bounds and authority
  before entry, reject unresolved imports, preserve ABI/error propagation and
  clean up denied/terminated instances according to the implemented lifecycle.
  Registry membership or a function address is not authority by itself.
- **Components** own their mutable state, resources and interfaces. Reuse
  existing channels/shared-page mechanisms for cross-domain work. Document who
  allocates, maps, writes, releases and revokes a shared buffer. Do not expose
  raw privileged pointers as an application interface or invent a second IPC
  fabric to avoid the existing contracts.
- **Personalities** translate legacy Linux/Darwin/Windows concepts at the edge.
  Keep foreign process/file/handle semantics out of the native kernel contract.
  Fixtures and kernel-linked translators do not prove arbitrary foreign apps.
- **Subspace** remains a separate embedded runtime/repository. Share generic
  compiler capabilities, not Space desktop policy or an assumed common image
  loader. SCI-E and SCI have distinct contracts and acceptance gates.

### Compiler, linking and isolation invariants

SCI is not ELF; ELF/PE/Mach-O may be intermediates or personality payloads only.
Follow the canonical schema for manifest offsets and versions, rather than
copying byte layouts into new services. Test emitter and loader together for
artifact changes, including malformed-image/import/grant refusal before entry.
Keep source, emitted artifact, selected compiler and runtime evidence traceable.

A source-level capability declaration or loader mask is not hardware isolation.
Current kernel-linked services run at CPL0 with the identity-map clone. SCI user
guests have a separate CPL3 path; prove the specific mapping, syscall and denial
behavior being claimed. Shared text executes with the caller's authority; a
kernel export must not become an unrestricted userspace privilege bypass.
Per-symbol capability refinement is not established by the current flat registry.

Keep ordinary language calls and explicitly owned raw native-ABI calls distinct.
Do not bypass language exception/error propagation to make a boot fixture pass.
Architecture wrappers belong in Space; their calling-convention implementation
and regressions belong generically in Inauguration.

### Hypermodular desktop contract

Build an original Space desktop: a basic niri-like tiling model with a
Raycast-style bar for window targets, layout/window controls, terminal and
ultimately browser launch. Alpenglowed and the privately supplied Rover project
are references, not dependencies or permission to publish private source.
Wayland/Budgie may supply useful infrastructure; a stock session is not the goal.

Separate responsibilities in code and in the eventual component graph:

1. **Command model/dispatcher:** registered typed actions, query/result state,
   availability and one confirmation path for keyboard/pointer. An action asks
   the authorized service to act; it does not gain ambient kernel authority.
2. **Layout policy:** window identities, tiled columns, floating state, focus
   and viewport geometry; independent of pixel rendering and application code.
3. **Compositor/display backend:** surfaces, clipping, bounded damage and
   presentation. Clients own content; shell decorations are not client pixels.
4. **Input/seat routing:** device events, focus and dispatch; preserve the SPDP
   ownership and denial rules, do not grant arbitrary clients global input.
5. **Applications and adapters:** terminal/browser and foreign-client support
   behind explicit service contracts. Do not embed a browser engine, foreign
   loader or generic shell execution in the bar's selection logic.

The kernel-linked framebuffer desktop is an integration prototype. New command
and layout logic should have independently testable modules, not accumulate in
`components/display.in` or the kernel root. Source extraction alone does not
prove SCI process separation. Reuse existing display/channel contracts and
advance actual SCI ownership through tested slices. Keep the existing desktop
as a regression baseline until its replacement passes equivalent interactions.

Never offer fake launch actions. Restoring an existing terminal is window focus;
a new terminal needs an independent session. Browser launch requires a working
browser component. Unsupported actions remain unavailable with honest limits.

## Relationship To Inauguration

Use `../inauguration` as the compiler/toolchain repository. Do not add Space-branded targets, Space product policy, or Space-only source trees to `../inauguration`.

Allowed Inauguration work:

- generic freestanding target support such as `x86_64-unknown-none`
- generic SCI or component-image emitters when they are not Space-branded
- generic capability/interface/object-schema metadata extraction from `.in`
- generic x86_64 native lowering, object emission, relocations, linker support, and QEMU harnesses
- generic compiler tests under `in-cli`, `scripts`, `docs`, or `apps` when they are not named after Space

Space-owned work:

- Space design notes
- Space component examples
- Space SCI profile and loader policy
- Space nanokernel object/capability vocabulary
- Space boot-image layout and QEMU expectations
- Space-specific runtime services and component graphs

## Workflow

When a Space task needs compiler work:

1. Update the Space plan or example first.
2. Implement the generic compiler capability in `../inauguration`.
3. Verify the generic compiler behavior with Inauguration tests.
4. Return to Space and update the Space-facing plan or artifact.

Do not make Inauguration depend on this repository.

Update architecture/SCI/protocol/desktop documents alongside any affected
contract. Record implemented behavior, intended next boundary and acceptance
evidence separately. Maintain the current handoff when work changes ownership.

## Required Checks

For Space-only documentation or examples (also inspect referenced contracts for consistency):

```bash
git diff --check
```

For desktop/runtime changes, run focused model/contract checks, affected QEMU
boot/SCI/personality gates and the desktop launcher/damage checks. Use an
explicit source-built compiler. For visual changes inspect rendered output and
exercise keyboard, pointer, focus, dismissal and actual action effects; serial
markers or screenshots alone are insufficient. Record baseline failures and
keep their assertions rather than hiding them with reduced checks.

For Inauguration compiler changes, run from its active checkout:

```bash
cargo fmt --check --manifest-path in-cli/Cargo.toml
cargo check -q --manifest-path in-cli/Cargo.toml
bash scripts/check-target-matrix.sh
in update
in test --owned-native
in test
git diff --check
```

If a change only touches a narrow compiler area, run the focused tests first, then the full gates before push.

## Boundaries

- Do not claim the kernel is implemented in `.in` until QEMU enters `.in`-compiled code.
- Do not claim SCI is implemented until there is an emitted artifact and loader-side validation.
- Do not use ELF as the native Space contract. ELF may be an intermediate or boot substrate only.
- Do not add POSIX compatibility before the native component model boots.
- Do not add placeholders or TODO prose as a substitute for an executable plan.
