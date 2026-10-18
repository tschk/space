# Goal statement for the next agent — Space, Subspace and Inauguration

Develop Space, Subspace and Inauguration together through their distinct native
contracts; follow `2026-10-19-three-repository-architecture.md` for ownership and
cross-repo verification. Build a proper, original, hypermodular Space desktop platform faithful to the
component + capability + object + execution-graph model. Prioritize resolution,
logical/pixel scaling and multiple real typefaces before expanding window-manager
features. Design broadly, then prove the architecture through executable slices.
Use simple niri-like tiling/floating and a Raycast/Rover-like command bar as the
shell interaction model; selectively reuse mature compositor and text technology
rather than assuming a full compositor/font stack must be written from scratch.

Read Space `AGENTS.md`, `architecture.md`, `sci-schema.md`,
`docs/compositor-client-split.md`, the command-desktop design,
`2026-10-19-display-text-architecture.md` and the current handoff before edits.
Respect nanokernel/runtime/service boundaries and preserve existing channel/SPDP
contracts. Keep compiler changes generic in Inauguration and SCI-E separate in
Subspace. Do not publish private reference source or claim hardware isolation,
foreign app compatibility, Unicode or real client execution from narrower demos.

First revalidate the handoff checkout and verification state. Complete any listed
checkpoint failures without hiding assertions. Then compare reuse paths with an
actual Space port spike; implement output/work-area/scale and typography contracts
with a resolution/face test matrix and rendered keyboard/pointer checks. Maintain
independent command, layout, compositor, seat, text and application ownership.
Run appropriate boot/SCI/personality/desktop gates, inspect actual diffs and
publish logical verified commits on main under existing authorization. Patch-bump
Inauguration when publishing compiler changes; no release tags, crate publication,
deployment or hardware flashing is authorized by this goal statement.

Use parallel agents for independent bounded work. The primary retains architecture,
integration, final diff inspection and verification. Preserve concurrent changes
and the parked compiler candidate. Record concrete failures and limits, not just
plans. Keep the full desktop goal active until its acceptance evidence exists.

## Other repository continuity

Subspace: preserve static memory, authoritative `.in` topology, typed ports,
exclusive device ownership, MPU/fault and SCI-E/board contracts. Start from the
actual clean `master` checkout, inspect its current revision and run its own gates;
no desktop policy or binary SCI loader sharing. No hardware flashing is implied.

Inauguration: preserve the active continuation checkout and its parked 0.9.321
callable candidate. Fix its recorded reproducible source/native failures, add
regressions and complete its required checks before publishing that patch. The
published, pinned 0.9.320 compiler is the current desktop verification baseline.
Generic improvements must serve both operating systems without product-specific
compiler policy. Read each repo's AGENTS; do not copy stale status into new claims.
