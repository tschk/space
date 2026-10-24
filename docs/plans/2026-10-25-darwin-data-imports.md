# Darwin typed data-import continuation

The full application goal remains OPEN. The visible Linux vi milestone does not
complete macOS/Windows support. Original macOS jq currently refuses before entry
at`__DefaultRuneLocale`; it must never bind that object to a function stub or a
host libc pointer merely to advance admission.

Rosemary at`f845f21842c85f6863cfa8a7a749cb945b88994a` identifies the key ABI seam:
Darwin ctype headers compile direct loads from a3208-byte rune object with
cached classes atoffset60 and case maps at1084/2108. Its hosted allocator/libc
implementation is not a Space dependency. No Rosemary implementation is copied.

Check those interoperability facts against Apple's public Libc source at
`71bbe350ab79eef58113991d817ccc6165061a64`. The BSD-licensed
`locale/FreeBSD/table.c` supplies the default C-locale cache, including null
deprecated callbacks and the actual`RuneMagA` header. Retain exact source,
permission notice, revision and hashes for deliberately reused table data.
Header declarations/ctype masks are ABI references; do not import their runtime.

Separate structural chained-fixup validation from each personality profile's
closed symbol policy. Preserve the old image/heap acceptance API and tests.
The high-address mapper may bind `_DefaultRuneLocale` as a read-only object and
`_CurrentRuneLocale` as a read-only pointer to it, with no claim of mutable locale
selection, multibyte conversion or general libSystem support. Functions keep
their RX capsules; objects must resolve to separate non-executable guest data.

Reuse the native owned address space: bounded extra page budget, population
through the existing owned bounce, RO/NX mapping, retained binding and identical
cleanup/quarantine rules. No host/kernel pointer, second mapping ledger, global
allocator or new native object class. Unknown remaining imports still refuse
before creating a native VM. Keep source immutability, counted context entry and
authority/resource assertions.

Test the exact three cache arrays against the pinned upstream table, C ABI
offsets/size with an independent host compiler, genuine modern chained data
bindings at CPL3, actual write/execute faults, successive activation isolation,
failure cleanup and unchanged old mapper/image behavior on both roots. Track
original jq's actual next unavailable import honestly; a data fixture is not an
original application entry. Do not widen its historical admission receipt.

The initial original-image cache model passes all4096 bytes against an actual
host-C evaluation of the upstream initializer, including its implicit zero
classes128..255 and all256 case-map entries. The native model repeats22 times
in all3 compiler profiles with guard bytes and invalid-call no-write checks.
`/workspace/darwin-rune-qemu2/report.json` additionally passes184 actual CPL3
fixtures: direct chained data pointers, full-cache digest, private current-locale
pointer, real RO/NX/out-of-range/fixup page faults and23 lifetime cycles. Native
heap/free-page/domain/cap and supervisor TLS/hook state stabilize after warmup.

The first failed probe remains preserved. The existing low-address helper's
16-byte symbol spelling bound refused these longer object names, so the new
data symbols use the already bounded256-byte image-string helper. The older
profile matcher is unchanged. Original jq's next unavailable high-address
profile import is`____chkstk_darwin`; it still has zero application entries.
The lower image/heap profile intentionally retains its old symbol policy.

Final frozen evidence is recorded in
[`2026-10-25-darwin-data-evidence.json`](2026-10-25-darwin-data-evidence.json).
Both`d75525d` roots pass184 own CPL3 entries and69 forced setup failures each,
including failures before/after actual rune-object population and before native
context attachment. Production source is unchanged by these snapshot-only
injections. Both`072169e` original mapper suites also pass318 own entries and147
setup refusals each; original jq's supported data import and next unavailable
name are checked by the actual native matcher. These are not original macOS
application entries. The desktop launcher/input/pointer/resize regression and
243fps damage test pass at`d75525d`. No new complete163-gate run is claimed.
