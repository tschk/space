# Original Mach-O image plan

The next executable-format step targets the checksum-pinned original jq1.8.1
macOS x86_64 binary. Its genuine chained-format6 imports match the direction of
the existing eager adapter, but its17 commands, ten sections, preferred4-GiB
base and209 mapped image pages do not fit the old strict five-command/64-frame
profile. Keep that profile and its eleven-service heap adapter unchanged.

The acquired LuaBinaries lua52 and luac52 both declare libedit3 and libSystem,
even though luac has fewer imports. Both require classic dyld-info streams;
neither is an easier dependency-free alternative. Their inspection remains
separate from the Lua5.4.7 goal.

## First checkpoint: directly consumable validated plan

Add a private allocation-free `darwin-image-plan.in` personality module. Given
an immutable trusted source image and an explicitly owned caller output buffer,
produce a versioned3840-byte image plan: source reference/size, entry,
pagezero reservation, bounded segment/section tables, command index, chained
fixup range, dependency command and exact mapped-page demand. The validator
must not allocate frames/domains/capabilities, mutate input or publish output
on malformed/unsupported input. Validate first, emit second, publish the plan
magic last. This is an internal supervisor contract, not a guest pointer API.

Support the concrete original jq command semantics: PAGEZERO creates no user
mapping; bounded RX/RW/R image segments have nonoverlapping pages and file
ranges; sections stay inside their owning segment and distinguish file-backed
from zerofill data. Deny relocations, constructors, TLS and unknown section
semantics. Check LC_MAIN against a real executable text section. Explicitly
recognize and validate load-dyld, UUID, build-version, source-version, symbol and
indirect-symbol tables, function-start deltas, data-in-code, chained-fixup and
export-trie metadata. Metadata acceptance must have a stated interpretation;
there is no blanket unknown-command ignore path. Unknown required or optional
commands remain refused.

The closed executable does not provide exports to another image, load unwind
state, perform dlsym or execute constructors. Its export/unwind tables are
bounded descriptive data only, not evidence those runtime services exist.
Dependency declarations are recorded/validated as requirements; planning must
not pretend an Apple dylib has been loaded. A separate admission preflight
compares all actual imports with the finite implemented adapter and refuses
unavailable symbols before owned mapping. Original jq should advance from
structural refusal to this explicit import refusal, while remaining unexecuted.

Use independent host Mach-O parsing of the unmodified pinned artifacts, actual
QEMU calls to the owning validator/preflight, malformed bounds/overlap/unknown
command/section/dependency controls and output/input/resource preservation.
Preserve an actual old-profile original-binary refusal before this expansion.

## Next checkpoint: owned mapper consuming this plan

Once reviewed, replace neither the old frame limit nor its cached vectors.
Add a separately owned mapping ledger sized576 entries (maximum512 planned
image pages plus owned stack/heap/RX capsules), with explicit preflight for
ledger/context retained bytes and a conservative704-frame backing/table
reserve. Teardown owns every mapped frame and domain even on failed fixups,
unknown imports, faults and deadlines. Validate the actual table bound before
entry rather than assuming the old65/96 reserves apply.

Honor PAGEZERO: the original jq reserves user addresses below4GiB. Its new
profile must place owned stack, heap and capsules above4GiB in disjoint windows,
not reuse the old low-address helpers. Native domain/context mechanisms already
represent64-bit VAs, but actual high-VA CPL3 execution and denied pagezero reads
must be proved before an execution claim. Resolve all imports and initialization
requirements before entry; missing APIs remain explicit refusal. No CPU/core/
GUI policy changes are part of this checkpoint.

## First checkpoint implemented

The private original-image plan and generalized import preflight are implemented,
with actual QEMU original-layout/oracle/denial evidence. See
[the checked contract](../darwin-image-plan-checks.md). Original jq remains
unexecuted and refuses its first unavailable import; the larger owned mapper
is the next checkpoint, not part of this completed planning slice.
