# Counted Linux initial entry, driven by original fbv

The original fbv1.1 CLI probe exposed a real launcher limitation: the existing
`linux-process-run`/`run-input` always construct argc3. Its help option executes,
but the actual no-argument host case exits1 while Space receives two explicit
empty arguments and enters the viewer path instead. Keep the failed receipt at
`/workspace/fbv-cli-second/report.json`; do not rewrite the host oracle to accept
those different arguments. The earlier `/workspace/fbv-cli-first` is a separate
checker compile failure (incorrect serial helper), with zero guest execution.

Add a trusted kernel caller API `linux-process-run-counted-input`, supporting
explicit argc1..3 with the existing three string slots, grant and borrowed input
contracts. Old entry points retain argc3 and the exact original stack builder.
This is a bounded intermediate API, not arbitrary argv/environment support.

For argc1/2, reuse the process-owned argv/environment buffers and existing exec
vector stack construction. Preserve real argc/NULL/envp/auxv, native checked
startup writes, source string ownership, immutable high-source handling,
remaining budget and all native binding/cleanup invariants. Do not introduce a
second stack layout, backing ledger or raw guest-pointer bridge. Numeric counts
outside1..3 must refuse before allocation or guest entry. Unused string slots are never read (NULL/noncanonical unused sentinels are
explicitly tested). Used strings are trusted
caller C strings with existing bounded length/provenance obligations; this is
not an untrusted SCI pointer API.

Acceptance requires actual host/Space startup ELF checks for argc1/2/3, exact
argv/environment termination and auxiliary vectors on both roots over21 cycles,
invalid-count refusal before resource changes, and unchanged old startup/exec/
child/vfork/real-app gates. Original fbv must then match its unchanged host help
and no-argument output/status through CPL3, with repeated resource checks.
This does not establish framebuffer, terminal/signal or GUI adapter support.
The full application/desktop goal remains OPEN.

## Completed focused evidence

The final runtime source is `/workspace/linux-counted2-source`, committed base
f54a293 plus the six-file adjacent manifest. Source-built compiler0.9.325 SHA
`d2ac79b39f5ea98c5d776e88f550cf4327e89539ceaaf0d9ce591c53aa88ed75`.
Both `/workspace/fbv-counted2-final-{standard,minimal}/report.json` pass44 actual
original fbv CLI activations each, plus66 separately counted startup ELF entries
per root. The fixture checks argc1/2/3, stack alignment, exact argv/env strings
and NULL boundaries, and actual required PHDR/PHENT/PHNUM/PAGESZ/ENTRY/RANDOM/
EXECFN auxiliary entries. Argument strings come from immutable0x13000000 loader
memory with the heap capped at0x10000000. Unused arguments include NULL and
noncanonical sentinels. Invalid counts0/4/INTMAX refuse without allocations.

The final same-source legacy regressions pass both-root copied-child23 cases
(506 parent activations per root), original native-VM migration (23 roots plus
2 invariant entries per root) and shared-vfork (23 roots plus12 ownership and
2 invariant entries per root): `/workspace/counted2-{children,vm,vfork}-*`.
The current full131-gate run predates this argument-count change; a following
integrated source must include it before claiming whole-tree acceptance.

`/workspace/fbv-cli-counted-first` retains a later test-oracle failure: actual
argc/status were correct, but concatenating separately captured stdout/stderr
lost the host's actual stdio write order. The corrected checker uses a genuine
host merged pipe, keeps pinned separate stream hashes, and compares guest serial
bytes exactly. No guest bytes are reordered. `/workspace/fbv-cli-counted-second`
and the first `/workspace/fbv-counted-final-*` are successful intermediate scopes,
superseded by the final unused-pointer contract and exact reports above.
