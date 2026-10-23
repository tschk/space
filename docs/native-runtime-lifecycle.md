# Ephemeral native SCI activation lifecycle

The current native `runapp` path is trusted CPL0, despite its clone page tables.
A fresh-boot test is insufficient to certify its lifecycle: the retained baseline
at `/tmp/space-native-lifecycle-baseline/` exhausted the 64-slot capability table
after the standard application scenarios and 23 additional calculator/checksum
pairs. The next calculator activation was refused. The shell survived, but the
requested same-boot run could not complete.

Ordinary synchronous mode 1 activations are now ephemeral. Mode 0
remains asynchronous; an explicit kernel-only retained wrapper uses mode 2 for
GUI/SPDP/input instances. The retained wrapper is excluded from the flat SCI
symbol registry. Ephemeral instances publish no exports or resumable GUI state.

Each ephemeral instance owns a metadata/cap-info frame and a 512-entry heap
frame ledger. Its record tracks its clone tree, private component record and
capability slot, shared/pixel backing frames, prior kernel alias PTE values and
prior root-realm edge. Cleanup first revokes its authority and removes/restores
aliases, then releases its explicitly clone-owned private table tree and owned
backing frames. Boot images, library providers, persistent filesystem state and
retained components are outside that ledger.

Global capability allocation/revocation stays monotonic: arbitrary revoked raw
indices must never regain new authority. The runtime may recycle only its own
private ephemeral slots, never exposed by the supported application ABI, never
published as retained or delegated handles. Private component records obey the
same scope. The app receives grant bits and a domain identifier, while the
capability slot field remains zero. This is a trusted CPL0 lifecycle contract,
not opaque-handle hardware enforcement; CPL0 code can still inspect kernel
memory. General escaped capability reuse requires generation-bearing tokens.

The production loader now binds canonical `malloc`, `calloc`, `realloc` and
`free` imports to the activation's tracked allocator. Its reusable blocks are
separate from the raw application file-buffer heap. Explicit free, normal exit,
import refusal and scoped allocation abort all preserve ownership. Retained
mode2 and asynchronous mode0 keep their existing lifetime until their own
retirement contract is implemented.

The observed production-loader check at
`/tmp/space-native-lifecycle-final-allocator/report.json` passed151 normal real
application activations and136 emitted allocation aborts in one boot. It checks
stable free-frame count, heap high water, domain/capability counts, object arena,
clone ownership and export count after warmup. It also exercises actual allocator
ABI behavior, malformed private imports, refusal to recycle a generic revoked
capability, and refusal to destroy kernel or user trees through the clone API.
The normal driver reports81 application scenarios, including70 additional real
calculator/checksum pairs. Retained GUI regression checks continue to pass.

The bounded4096-entry export registry admits whole providers before writing any
entries. Capacity refusal emits an explicit diagnostic and leaves library-ready
state and registration count unchanged. Exact-fit and full/partial-provider
refusal are exercised by the same gate. Supervisor runtime, foreign-process and
GUI-manager helpers are omitted from the flat registry; checked public
`gui-note-read` and `gui-note-write` remain available.

Run `scripts/check-native-lifecycle.py --in /path/to/in --out /new/output` to
repeat the real same-boot resource proof. The harness observes the production
loader after return; it does not replace its teardown implementation. These are
trusted CPL0 lifecycle tests, not protection against malicious native code.
