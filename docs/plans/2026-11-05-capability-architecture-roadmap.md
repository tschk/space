# Capability architecture: audit and roadmap

This is a source audit of the current Space checkout, not a claim of fresh
end-to-end verification. The five layers are `.in`, Inauguration, SCI, the
Space runtime and the nanokernel. Their purpose is not just smaller modules:
together they should let people compose useful systems with explicit,
delegable authority and recover them without granting ambient machine access.
Existing plans remain authoritative for their respective boundaries. In
particular, see [architecture](../../architecture.md), [SCI](../../sci-schema.md),
[desktop ownership](../compositor-client-split.md) and the
[three-repository plan](2026-10-19-three-repository-architecture.md).

## What the implementation actually establishes

| Layer | Evidence in this checkout | Gap that matters |
|---|---|---|
| `.in` source | Components declare capabilities and interfaces; Space examples are consumed by the compiler and packagers. | A declaration alone is not a live, attenuated authority or proof that a call is permitted. |
| Inauguration | The documented path produces native code and component metadata; the SCI schema distinguishes metadata sidecars from executable manifests. | Space-specific translations must not be hardcoded in the compiler; neither a sidecar nor an untested analysis is enforcement. Audit actual compiler output and provenance per slice rather than assuming every schema field is emitted or checked. |
| SCI | v2 contains a mask, imports and exports ([schema](../../sci-schema.md)); the loader resolves names in a flat registry. | A symbol match says nothing about the authority of its caller. Loader input bounds and lifetime must be validated before any patch, registration or entry. |
| Space runtime | `component-register` and `supervisor-activate` in [supervisor.in](../../components/supervisor.in) allocate a component and compare its requested mask with realm grants. | This is not yet a general dependency solver, transactional lifecycle or service replacement protocol. Failure after allocation needs explicit ownership and cleanup, not just an activation result. |
| Nanokernel | [domain.in](../../components/domain.in) has distinct kernel-linked and CPL3 user-domain creation paths; [syscall.in](../../components/syscall.in) gates selected calls. | Kernel-linked domains clone the identity map and run at CPL0. Separation of source files or registry entries does not isolate them; a direct privileged import is not equivalent to a checked syscall. |

The capability table in [object.in](../../components/object.in) stores a target
pointer and rights mask. `cap-check` checks the mask and that the target is
nonzero; the generic check does not compare a requested object identity.
Userspace mint and revoke currently return failure in `syscall.in`. The object
arena checkpoint copies arena bytes and records `cap-count`; it does not copy
capability-slot contents, device state, channels or external filesystem effects.
It is therefore not a general rollback facility. The documentation's aspirational
execution graphs and deterministic behavior should not be read as proof of
replay across those effects.

The abstraction gaps have concrete consequences:

- `sys-chan-send`, `sys-chan-recv` and `sys-chan-close` check the broad
  `cap-graph` right and pass the caller's integer to the channel code. In
  [channel.in](../../components/channel.in), `chan-valid` examines fields at
  that address; it is not an ownership or generation lookup. A valid-looking
  channel header is not proof that this caller owns the endpoint. The SPDP
  shared-page path has separate provenance and frame checks; do not replace
  those with this generic pointer interface.
- [pack-spdp-sci.py](../../scripts/pack-spdp-sci.py) is an intentionally
  narrow example of source-to-policy translation: it checks one component's
  named interfaces and operations, then converts compiler ordinal bits to
  Space rights. This shows how to reject mismatches, not a general packager
  for arbitrary declarations. A scalable policy must retain identity and
  provenance and reject unsupported rights rather than equating ordinal bits
  from unrelated components.
- The flat import registry supports useful code reuse, but the historical
  [dynamic nanokernel plan](2026-09-18-dynamic-nanokernel.md) explicitly leaves
  per-symbol refinement as a non-goal. A service graph must distinguish
  provider discovery, interface compatibility and permission to invoke; it
  must also unregister or invalidate providers when their owner terminates.
- `checkpoint-save` retains the arena and the number of caps, while
  `cap-revoke` mutates the separate capability table in place. Restoring the
  count cannot reconstruct an earlier revoked slot. A future replay design
  needs an atomic ownership and external-effect protocol, not just another
  copy operation.

## Build capability, not only structure

1. **Object-scoped delegated authority.** Introduce an explicit handle for a
   particular object and operation set, with generation/lifetime checks and
   attenuation. A parent may delegate only a subset; revoking a parent must
   make descendants unusable. First slice: two CPL3 clients receive distinct
   channel endpoints; each can use only its own endpoint, and a revoked or
   recycled handle cannot address the other's object. Verify denial on the real
   trap path and after teardown, not by inspecting a bit mask.
2. **Service graphs that can explain themselves.** Let a deployment describe
   named interfaces, versions, providers, dependencies and requested authority;
   the supervisor resolves the graph before activation and presents the exact
   provider/grant chain behind a desktop action. First slice: replace a single
   display or input provider with a compatible implementation, retain the
   existing SPDP ownership rules, and show a missing or unauthorized provider
   failing before either client enters. A name lookup is not a grant.
3. **Rehearsal and recovery with explicit effects.** Extend the object model
   toward a checkpointable component graph, but partition effects into
   snapshot-owned state, replayable inputs and externally committed effects.
   First slice: a deterministic worker consumes a recorded input stream and
   writes to a private transactional object; restart and replay reproduce the
   output, while a denied external write remains absent. Device and filesystem
   rollback are separate contracts, not consequences of copying arena bytes.
4. **User-directed, temporary delegation.** A command can request a narrowly
   scoped object, such as one chosen document or one window surface, for one
   operation and lifetime. The shell explains and delegates the authority; the
   application never receives global storage or seat authority. First slice:
   open a chosen document through an explicitly granted object and prove that
   another document and a stale grant are denied. No fake application launch.
5. **Replaceable personalities as capability clients.** Move one bounded
   foreign ABI operation across an actual service boundary and translate a
   foreign handle into a native object capability. Prove a foreign guest cannot
   obtain an unrelated native object and that service restart revokes its
   handles. Existing kernel-linked translators and finite foreign-app receipts
   are useful baselines, not evidence of this isolation.

## Sequencing and acceptance

First secure SCI admission and define immutable binding inputs and teardown on
every refusal. Then prove object-specific handles and revocation through a real
CPL3 boundary before building delegation UI on top. In parallel, specify a
generic compiler metadata contract and Space-owned policy translation; test
emitter, packager and loader together with malformed and mismatched inputs.
Only then promote one service graph slice and one user-visible delegation slice.
The checkpoint/replay and personality slices should follow once their resources
have explicit owners and revocation semantics. Each slice needs success, denial,
failure cleanup, restart and cross-client tests on the actual path; source-level
module splits or historical screenshots alone do not meet the gate.

PR [#101](https://github.com/tschk/space/pull/101) contains substantial finite
compatibility and desktop work but is a conflicting draft, and its compiler
dependency [Inauguration #446](https://github.com/tschk/inauguration/pull/446)
is being handled separately. Integrate independently verifiable slices without
assuming that dependency has landed; retain the remainder until its compiler,
ownership and integration gates are satisfied.
