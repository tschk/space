# Space, Subspace and Inauguration: shared direction

## Product and architecture goal

Build usable native operating-system platforms above a general compiler, not
three overlapping kernels or a compiler full of product-specific exceptions.
Space is the desktop/runtime platform; Subspace is the bounded embedded runtime;
Inauguration is the reusable language, verification and native emission foundation.
Keep their contracts compatible where semantics genuinely match while preserving
different hardware, memory, artifact and scheduling requirements.

Space's immediate design priorities are resolution/scaling, multiple real
typefaces and an original command desktop. Subspace does not acquire a desktop,
heap or runtime loader because Space needs them. Inauguration must improve
expressiveness and correctness for both without knowing either product's app
names, capability vocabulary, grant policy or board addresses.

## Responsibility and contract map

| Concern | Inauguration | Space | Subspace |
|---|---|---|---|
| Language/IR | fronts, source semantics, Core IR/MIR, verifier | native `.in` service/component use | native `.in` runtime/topology use |
| ABI/native code | general calling conventions, raw native boundary, exception propagation, relocations | x86 hardware wrappers, trap/runtime consumption | Thumb capsules, AAPCS, vector/ISR/context consumption |
| Metadata | general interfaces/capabilities/object schemas and available provenance | validate/translate to native SCI policy | validate/translate to SCI-E/resource ledger policy |
| Artifacts | generic object/raw/component emit and linker support | SCI profile, loader and service bindings | SCI-E record, linked-entry validation, UF2 board boundaries |
| Runtime authority | correctness of emitted code/metadata, not runtime grant decisions | domains, capability checks, shared mappings and lifecycle | static grants, exclusive peripheral owners, MPU/task/port boundaries |
| Product policy | none | desktop, output/text/session/services, foreign adapters | board resource budgets, bounded startup, embedded drivers/fault policy |
| Native loading | generic emitter contracts | dynamic SCI and grant-checked provider composition | no runtime component loading in MVP |

Semantic capability/interface identifiers and rejection-rule corpus may be shared.
Do not unify binary SCI/SCI-E layouts, share x86 loaders with Cortex-M or introduce
mutual OS repository dependencies. The compiler must not depend on either OS.

## End-to-end workflow

Begin with the consuming OS contract/fixture and identify the missing generic
capability. Implement it in Inauguration with source/IR/native regressions, using
the common pipeline and preserving ABI/error semantics. Run its required gates,
freeze the source-built compiler and record its identity. Return to each affected
OS, compile the real artifact and test loader/board/runtime behavior. Compiler
tests alone do not prove an OS boots; QEMU alone does not prove physical hardware.

Prefer typed structures and explicit ownership over raw offset arithmetic where
supported, retaining assembly only for necessary hardware/ABI capsules. Keep
startup data, alignment, initialized globals, relocation and ownership invariants
visible in both emitted artifacts and runtime tests. Never use a permissive
prototype shortcut to silently widen the native capability contract.

## Space workstream

Follow `AGENTS.md`, `architecture.md`, `sci-schema.md`,
`docs/compositor-client-split.md`, the command-desktop plan and the display/text
platform design. Extract command/layout policy from rendering, then establish
output coordinate/scale and font/text contracts before more window-manager
features. Evaluate mature compositor/text reuse with a real Space port spike.
Keep SCI ownership, buffer release, seat routing, authority and application launch
separate. Test supported resolutions/scales, multiple genuine faces and rendered
keyboard/pointer interaction. Broaden foreign-client support through adapters
without turning native semantics into POSIX/Win32/Darwin kernel policy.

## Subspace workstream

Read its own `AGENTS.md`, `docs/vertical-slice.md`,
`docs/contracts/inauguration-foundation.md`, `docs/contracts/sci-e-v1.md`, board
profiles and `systems/vertical-slice.in`. The `.in` topology is authoritative;
regenerate JSON/Zig mirrors rather than editing generated representations as
independent designs. Keep no general heap, no filesystem in the first preview,
no MVP runtime component loader and exclusive-by-default peripheral ownership.
Nonowners communicate through typed ports, not duplicate MMIO grants.

Protect the actual AN521 vertical slice: UART, tasks, preemption/cooperative yield,
mailbox ordering, IRQ stack ABI, MPU/unprivileged domains and denial/fail-stop
behavior. Verify warm reset and initialized data, static RAM budgets, SCI-E linked
entry/CRC and malformed records, and UF2 board-family refusal. Hardware flashing
remains a separate explicitly authorized gate, never implied by a QEMU image.
Space typography requirements do not justify breaking deterministic embedded
resource bounds. Share pure algorithms only when proven useful to both runtimes.

## Inauguration workstream

Use the active continuation checkout recorded in the handoff, not the separate
dirty original checkout. Read its AGENTS and use one Core IR → MIR → native/JIT
pipeline. Improve general object-oriented/C-type and `.in` expressiveness, source
semantic proof preservation, native address/call/return ABI, freestanding data and
relocations, and diagnostics. Keep target requirements general; no Space-branded
compiler paths or Subspace board policy. Crepuscularity is a separate GUI framework,
not a frontend or automatic freestanding display stack.

The uncommitted 0.9.321 Rust callable candidate is not a released toolchain. Its
known failures and exact receipts are in the handoff; preserve it for repair rather
than using it as the verified Space/Subspace baseline. A generic correction must
keep language calls distinct from explicitly owned raw native-ABI calls, maintain
source failure priority and refuse unowned semantics before executing/emitting.
Do not accept a successful fixture by bypassing verifier or exception propagation.

## Verification and publication

- **Space:** focused model/contract tests; actual QEMU desktop actions and pixel
  inspection; affected smoke/hardening, compositor damage, SCI and personality
  checks. Pin the selected source-built compiler; retain failing artifacts.
- **Subspace:** `bun test`, `bun run check:all` with an explicit compatible compiler,
  and affected negative fault/MPU/entry/board fixtures. Report HIL as skipped when
  it was not run; never call a soft probe a hardware-isolation result.
- **Inauguration:** focused regressions, fmt/check, strict Clippy/full Cargo and
  source-built `in update`, target matrix, `in test --owned-native`, default
  `in test`, protocol and relevant performance/architecture checks per AGENTS.
  A parked failing candidate does not gain publication readiness from this plan.

Review actual staged diffs and preserve concurrent work. Publish logical verified
commits to each repository's existing authorized branch; do not create branches
merely for this plan. Compiler code releases need a patch bump and complete gates.
This goal authorizes no release tags, crate publication, deployments, remote
configuration changes or device flashing. Maintain a cross-repo handoff containing
source/artifact/compiler identities, observed tests, unresolved failures and exact
next actions. Keep the full objective active beyond any single green demo.
