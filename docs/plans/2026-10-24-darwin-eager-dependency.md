# Darwin eager dependency slice

Build on committed protected startup without changing its existing admission or
execution path. Keep foreign linking in a separate trusted personality module,
using generic owned CPU contexts and existing protected service translation.

## Evidence driving this slice

The checksum-pinned original macOS jq uses `LC_DYLD_CHAINED_FIXUPS`, not classic
dyld bind opcodes. Its fixup header has version0, imports format1, uncompressed
symbols, 136 imports and pointer format6 (`DYLD_CHAINED_PTR_64_OFFSET`), with
4096-byte pages. The dependency is `/usr/lib/libSystem.B.dylib`; only a few of
its imported functions correspond to Space's existing real typed services.
The current finite classic binder also spells `_error`, whereas the actual
Mach-O C symbol for Darwin's `__error` is `___error`. The new profile will use
the genuine symbol without changing that older fixture contract.

Reference-only source inspection at Rosemary commit
`f845f21842c85f6863cfa8a7a749cb945b88994a` covers
`fixups/chained.rs`, `namespace.rs`, `fixups/binder.rs`,
`extensions/initializers.rs` and runtime `startup.rs`. Useful seams are bounded
stream-relative tables, dependency ordinals, named-provider identity, complete
fixup validation before writes, and preparation before entry. No source is
copied or linked. Space will refuse missing imports, including unused declared
ones; it will not copy a host-runtime fallback which writes zero and continues.

## Concrete bounded goal

Add `darwin-eager-dependency.in` with a new section-free LC_MAIN profile:
ordered RX/RW segments, LC_MAIN, LC_DYLD_CHAINED_FIXUPS and exactly one explicit
LC_LOAD_DYLIB. A read-only, code-defined native adapter descriptor identifies
one finite provider revision and its seven existing typed functions: `_write`,
`_exit`, `___error`, `_open`, `_read`, `_close`, `_lseek`. It describes a native
ABI adapter, not a loaded libSystem binary or a general dependency graph.
Caller selection of this descriptor supplies no authority: borrowed native
serial/storage grants remain live-checked by the existing scoped translator.

Implement actual eager import/rebase patching for a strict subset of the
original jq's format: version0, imports format1, uncompressed symbol strings,
ordinal1 without weak import or addends, 4096-byte pages, 64_OFFSET pointers,
one forward chain per RW page and bounded table/link counts. Accept arbitrary
aligned writable slots and repeated symbols, rather than the old fixture's
fixed per-symbol slots. Validate all names, ordinals, bits, file/VM extents,
chain steps and image-relative rebase targets before allocation. Unknown APIs,
other dependencies, weak/self lookup, addends, compression, multi-start pages,
text fixups and unsupported pointer forms are refused.

The runtime builds private user RX typed trampolines, maps the owned image and
startup input, eagerly patches only its private RW copy, zeroes private errno
and then enters main with the established owned argc/argv/envp/apple contract.
Its adapter preparation is real and bounded. No dyld/libSystem executable
initializer, constructor, TLV, atexit or framework routine is inferred from it.
All such metadata remains refused. Keep the old startup module intact.

Use an explicit domain/mapping ledger and generic context handoff under the
existing shared Darwin busy guard. Include exact first-use retained-byte and
frame reserve checks, fault/deadline teardown, caller FS/GS restoration and
bounded scratch reuse. This remains trusted kernel-linked scaffolding; no new
unguarded dynamic imports or declarative SCI binding claims.

## Acceptance

A genuine Mach-O fixture with real chained fixups must call the bound functions
at CPL3, verify rebase data, alias slots, actual serial/file behavior and private
errno, and demonstrate prepare-before-main by checking its IAT before its first
call. Include missing/revoked grants, malformed chains/headers/import tables,
unknown symbol/dependency/descriptor identity and allocation-free refusal.
Run at least21 cycles with stable heap/frames/domains/caps/host descriptor
sentinels; fault and actual IRQ deadline reclaim private state. Keep existing
344 startup,483 protected-process and548 file gates intact. The pinned original
macOS jq remains refused and is never counted as an executed app.
