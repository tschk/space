# Original Darwin image planning

`darwin-image-plan.in` is a private supervisor contract for the actual pinned
macOS jq1.8.1 image layout. It advances that original binary from immediate
format refusal to a validated image plan followed by explicit unavailable-import
refusal. It does not map or enter the application, load Apple's libraries, or
implement a complete dyld. Existing startup/eager/owned-heap profiles remain
unchanged. See [the implementation plan](plans/2026-10-24-darwin-original-image-plan.md).

The supported closed profile has the original image's17 command kinds/order
constraints, five named segments and section semantics. Source order is indexed
rather than assumed by the consumer. No unknown optional/required command is
ignored. Malformed supported structures return-8; recognized unavailable
features/commands/dependencies return-38; invalid numeric output bounds or source
output overlap return-14. These are internal admission results, not a Darwin
syscall errno mapping.

## Ownership and consumable plan

The caller supplies trusted, mapped supervisor source/output buffers. Numeric
checks do not establish ownership or make arbitrary CPL0 pointers safe. Source
bytes must remain immutable until the trusted consumer has finished. The plan
contains a privileged source reference and is never a guest interface. All
`darwin-image-*` helpers are excluded from the dynamic kernel registry. This is
kernel-linked personality scaffolding, not an isolated SCI service or a declared
component-capability translation mechanism.

`darwin-image-plan(image,size,out,bytes)` accepts source files up to2MiB and an
output extent3840..4096 bytes. A complete validation pass precedes output writes;
a second pass emits the plan and publishes its magic last. Failure of initial
validation preserves the caller output. Success writes exactly3840 bytes,
preserving the caller tail. Caller status must be checked: failure does not
invalidate an older plan already present in the output. There is no allocation,
domain creation, capability mint or user entry in this contract.

The version1 plan is3840 bytes, little endian64-bit fields:

| Region | Fields |
|---|---|
| Header0..127 | magic `0x4457504C414E0001`, version, source size/reference, preferred base, entry VA, segment/section/command counts, chained-fixup file offset/size, dependency command offset, exact image page count, PAGEZERO upper bound, image flags, plan bytes |
| Segments128..767 | Up to8 records of80 bytes: source command offset, VA, VM bytes, file offset/bytes, maximum/initial protection, first section index/count, semantic segment kind |
| Sections768..3327 | Up to32 records of80 bytes: source section offset, VA/bytes, file offset, attributes, alignment, segment index, reserved1/2, semantic section kind |
| Commands3328..3839 | Up to32 records of16 bytes: source command offset and kind |

The semantic segment kinds1..5 are PAGEZERO, TEXT, DATA_CONST, DATA and LINKEDIT.
Section kinds1..9 are text, stubs, const, cstring, ustring, unwind_info, got, data
and bss. Unused records are zero. The actual original jq plan describes209 image
pages, entry `0x100000860`, ten sections and a4GiB preferred base.

A plan proves layout validation only. Before any mapping, its consumer must
require `darwin-image-import-preflight(plan)==0`; the original jq currently
returns-38. The trusted consumer must not fabricate descriptors or mutate source
or plan between these stages. Import preflight rechecks source layout, plan
identity and source fixup range. The diagnostic helper returns the first missing
import only for a successfully planned immutable image whose dependency
preflight reported unavailable imports.

## Explicit format semantics

PAGEZERO reserves user addresses below4GiB and produces no user mapping. Real
image ranges are page-aligned, bounded to2MiB above the preferred base,
nonoverlapping in VA and file, with RX TEXT, RW DATA and R LINKEDIT. DATA_CONST's
read-only-after-fixups flag is recorded; a future mapper must seal it read-only
before entry. No writable executable mapping is permitted. Section ownership,
alignment, VA/file correspondence, overlap and indirect-symbol ranges are
checked. Bss is explicitly zerofill; a future mapper must zero it even if file
padding covers the same VA range. Constructors, TLS, relocations, unknown
section names/types and unknown segment protections/flags are refused.

LC_MAIN must name an executable text-section byte. LC_LOAD_DYLINKER records the
specific `/usr/lib/dyld` requirement; LC_LOAD_DYLIB records the libSystem path
and compatibility requirement. This does not assert those libraries have been
loaded or that this adapter implements Apple's library version. Other
libraries, including libedit, remain unavailable. The finite adapter's actual
symbols are checked independently from these declarations.

UUID is opaque descriptive identity, not authenticated provenance. The
macOS14 build-version/tool descriptor is checked as supported metadata;
source-version is supported only when empty. Symbol/string and dynamic symbol
partitions, indirect entries, function-start ULEB deltas and export-trie bounds
are checked. The supported export trie has bounded, ordered forward children,
regular exports with mapped targets and zero padding; reexports/resolvers are
refused. The closed image's export/unwind data remain descriptive: no other
image imports its exports, no dlsym or unwinding service is promised. Nonempty
data-in-code is unavailable. There is no blanket metadata ignore path.

Generalized preflight validates the original five-segment chained-format6 /
imports-format1 layout, all136 import entries and all1357 actual chain links.
Each page link remains in its segment/page, rebases target mapped image ranges,
and bind ordinals/reserved fields are checked. Traversal is bounded to4096
links; multi-start pages and nonzero bind addends are unavailable. It checks the
finite existing eleven-service adapter; first missing original import is
`__DefaultRuneLocale`. No success stubs or fake locale/data objects are supplied.

Both acquired LuaBinaries5.2.4 executables declare libedit and libSystem. Their
subtype capability mask `0x80000003`, classic dyld-info fixups and broader legacy
protection profile are not this profile. The current validator first stops at the subtype capability mask with-38
before output publication. Classic fixups/libedit are independently inspected
additional barriers, not later native checks reached by that call. Inspection does not replace Lua5.4.7 or count
as executed application coverage.

## Actual evidence

Reproduce with explicit frozen source-built compiler and toolchain NASM/QEMU:

```bash
python3 scripts/check-darwin-image-plan.py --in /path/to/in --out /workspace/di/new --jq /path/to/jq-macos-amd64 --lua-dir /path/to/lua-5.2.4-macos
```

The runner checksum-pins all three original binaries. Its independent host
parser decodes actual segments, sections, commands, imports and chains; a
separately loaded3840-byte oracle is compared byte-for-byte with each actual
native plan. Twenty-one cycles assert unchanged source, heap/free-list head,
domain and capability counts, inactive user context and untouched caller tail.
The old profile is first called on the three original binaries and returns-8.
Original jq now validates its real layout, then refuses imports with-38. Original
application executions remain zero.

Thirty-four malformed layout/metadata cases and ten malformed chain cases retain
bounds, overlap, unsupported constructor/TLS/protection/dependency, symbol and
metadata refusal assertions. Appended unknown required and optional commands
are refused. A generated-source negative control removes only unknown-command
rejection: the actual native validator admits the appended command and the gate
catches that admission. A separate owning-function positive control rewrites
only import table names to the real implemented `___error`, preserving original
chain geometry; preflight must return0. That control is never entered and never
counted as original application execution.

Frozen .324 receipts are under `/workspace/di`:

- `review`, `review-lean`, `review-harden`: all three native profiles passed
  final provider validation and the actual original-image refusal boundary.
- `review-control`: generated missing-unknown-rejection control caught.
- `wired`: integrated hub import, positive import-table control, invalid plan
  headers and complete actual runtime gate.

All receipts retain compiler/source hashes, full commands, serial logs and
unchanged-source checks. Early failed receipts `first` and `second` are retained:
Lua's valid subtype capability was initially classified malformed rather than
unsupported, and two mutation coordinates/expectations needed correction.
No original image was modified on disk or counted as executed.

The next mapper must consume this exact plan using separately owned larger
ledgers and high-address stack/heap/capsules. It must preserve PAGEZERO and
implement the required dependency APIs before any original binary entry claim.
