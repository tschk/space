# Eager Darwin dependency adapter

`components/darwin-eager-dependency.in` adds a separately admitted executable
profile with real eager chained fixups, owned startup and seven existing typed
services. It leaves committed protected-process, file and startup providers
unchanged. See the [plan](plans/2026-10-24-darwin-eager-dependency.md) and
[Rosemary reference](rosemary-macos-reference.md). No reference source is copied
or linked, and no original macOS application is claimed to run.

## Explicit dependency identity and preparation

The immutable, code-defined native adapter has identity
`DARWIN-EAGER-IDENTITY = 0x4457414249000001` and finite ABI revision 1. An image
must request exactly `/usr/lib/libSystem.B.dylib` through the strict descriptor
layout, with timestamp zero and current/compatibility fields `0x10000`. These
fields identify this fixture adapter contract; they do not assert that an Apple
libSystem executable/version has been loaded. There is no ambient host library
lookup, fallback symbol provider, filesystem dependency search or executable
dependency graph.

| Mach-O import | Real bounded behavior |
| --- | --- |
| `_write` | Borrowed live serial authority, stdout/stderr, complete owned guest span |
| `_exit` | Actual protected process exit; low eight status bits; never returns |
| `___error` | Address of invocation-private errno word, initially zero |
| `_open` | Owned read-only regular-file binding through borrowed live storage authority |
| `_read` | Owned binding, checked complete writable guest span and actual VFS read |
| `_close` | Releases the invocation-owned binding, including after storage revocation |
| `_lseek` | Actual owned shared file position with existing offset/error checks |

The spelling `___error` is the genuine Mach-O symbol for Darwin's C `__error`.
The older fixture's `_error` spelling is refused in this profile; its old tests
remain unchanged. The private errno word does not supply pthread/TLS or TLV.
Calls use the existing user RX syscall capsules: C ABI failures return -1 and
store Darwin errno, while successful calls preserve errno. No privileged native
function address is installed in a guest slot.

Preparation validates descriptor identity, the entire image and every import,
then validates caller-owned startup spans and borrowed authority. Only then
are private mappings allocated. The runtime builds RX capsules, zeroes private
state, eagerly patches the private RW image, copies owned startup vectors and
enters LC_MAIN with the existing argc/argv/envp/apple and return-stub contract.
The fixture checks every IAT slot and errno before its first bound call. No
executable libSystem initializer, constructor, destructor, atexit, TLV or
framework function is inferred or stubbed. Such metadata remains refused.

`darwin-eager-run(image,size,input,bytes,identity,serial,storage,budget)` is a
trusted supervisor interface. The caller keeps image bytes and its startup span
stable/readable throughout the synchronous invocation. The adapter checks span
bounds and copies startup data; it does not validate arbitrary CPL0 caller page
mappings. All `darwin-eager-*` helpers are excluded from dynamic imports, with
actual registry lookup refusal tested. This remains kernel-linked personality
scaffolding, not an isolated SCI service or a declarative component capability
binding. Descriptor selection supplies no authority. The guest domain has no
native capability; each service checks the explicitly borrowed native grants.
A missing grant (-1) permits preparation but its service refuses actual use.
A wrong positive grant is refused before allocation.

## Admitted format

Exactly five commands: ordered section-free RX/RW `LC_SEGMENT_64`, LC_MAIN,
`LC_DYLD_CHAINED_FIXUPS`, and one LC_LOAD_DYLIB. The established fixed image
window, 64-KiB segment limits, entry/file bounds, nonoverlap and W^X checks apply.
No LC_UNIXTHREAD, ASLR, additional segments, constructors or external code are
admitted by this separate profile.

The chained format follows an actual seam in pinned macOS jq:

- Header version 0, imports format 1 and uncompressed symbols; bounded,
  stream-relative tables and exact canonical starts layout.
- At most 16 imports, ordinal 1, no weak import, and zero addends. Every
  declared name must resolve, including unused entries. Duplicate known names
  and multiple slots for one symbol are supported.
- 4096-byte pages and `DYLD_CHAINED_PTR_64_OFFSET` (format 6). The RW segment
  has one forward chain per page or START_NONE. At most 512 links per image.
- Arbitrary eight-byte-aligned slots in file-backed RW bytes, including slots
  beyond byte 127 and later pages. Forward next offsets cannot overlap or leave
  their page. Four-byte alignment, multi-start pages and text fixups are refused.
- Image-relative rebases must resolve into this invocation's RX/RW image.
  High/reserved bits and unsupported pointer forms are refused.

Fixup metadata follows both segments' file bytes, is at most 4096 bytes and is
never itself a writable guest target. Header/table/string/chain extents and all
names are checked before allocation. Applying the already validated chain writes
only through this invocation's physical mapping ledger. Caller image bytes are
preserved; the runtime does not patch its input buffer.

The shared Darwin busy guard prevents concurrent ledger reuse. Exit, CPU fault
and actual IRQ deadline tear down pages/domains and invocation-owned files,
preserving ambient caller descriptors and caller FS/GS. Retained scratch uses
exact first-use bump-byte checks separately from the frame reserve. At most 40
backing pages and 17 conservative page-table frames fit the 65-frame reserve;
the extra import page shares the exit page's leaf table. Missing protected
ledgers, eager CPU context and file scratch require 10160 bump bytes in total.
These are retained once; repeated invocations reuse them.

## Verification

```sh
python3 scripts/check-darwin-eager-owner.py --in "$IN" --out /tmp/eager-owner
python3 scripts/check-darwin-eager.py --in "$IN" --out /tmp/eager-qemu \
  --app /path/to/jq-macos-amd64
```

Both distributable image variants also build successfully from the frozen
integrated source: `/tmp/space-darwin-eager-image-build`, with the exact command
and compiler output retained in `/tmp/space-darwin-eager-image-build.log`.

The actual QEMU gate freezes its complete source tree and uses a genuine Mach-O
fixture with independently decoded host-side chained metadata. It executes 254
CPL3 invocations: 252 across 21 cycles, one real mid-process storage revocation,
and one exact first-use cache recovery. It verifies all seven bound services,
non-fixed slots, write aliases including a second page, an image-relative
pointer, private errno, missing authorities, invalid/crossing/read-only buffers
without moving file offsets, unclosed-file cleanup, typed exit, CPU faults,
actual IRQ deadlines, FS/GS isolation/restoration and stable heap/frame/domain/
capability/descriptor ownership. Every caller image byte is compared against
its saved source except the explicit test mode word. An ambient host descriptor
remains open at its original offset/path throughout.

The pressure control makes 65 real frames available, exhausts bump capacity,
and checks allocation-free refusal, then provides exactly 10160 bytes and runs
actual bound calls successfully. Thirty-six malformed layout/chain/import
cases, wrong descriptor identity and wrong positive authority refuse before
allocation. The scoped test dispatcher only adds a raw request which revokes
the actual borrowed grant; production translation and service behavior are
unchanged.

The owning-function model executes actual validators in default, lean and
harden profiles with 75 malformed cases and exact 512-link acceptance versus
513-link refusal. Native string literals are backed by model bytes and their
pointer parameter is represented as Int; parser branches are preserved. It
models format admission, while QEMU establishes private application and calls.

Receipts:

- `/tmp/space-darwin-eager-final/report.json`: actual QEMU, frozen source unchanged.
- `/tmp/space-darwin-eager-owner-checkpoint/report.json`: all three owner profiles.
- `/tmp/space-darwin-eager-unused-import-control2/report.json`: generated-only
  removal of complete import-table validation, preserving per-used-chain
  lookup. An isolated unused unknown import incorrectly reaches execution,
  and the actual gate catches the regression. Successful sources are untouched.
- `/tmp/space-darwin-eager-startup344/report.json`,
  `/tmp/space-darwin-eager-old483/report.json`, and
  `/tmp/space-darwin-eager-old548/report.json`: unchanged prior profiles rerun
  against the frozen integrated source, all passing with unchanged source.

## Original macOS jq boundary

The inspector now records the original pinned binary's actual chained metadata:
1888 bytes at file offset 839680, version 0, imports format 1, uncompressed
symbols and 136 imports. Its two chained segments use format 6, 4096-byte pages,
and image offsets 802816/819200 with four/five pages. This drives the new format
choice. Original jq also has 17 commands and 10 sections, dyld and libSystem
requirements, and many unknown functions/data imports including heap, stdio,
pthread/TLS, locale and math. The finite adapter supplies none by implication.

With `--app`, the actual runtime checks allocation-free refusal (-8) of that
checksum-pinned original image. It is not entered. Next work is a truthful wider
image/dependency policy and actual implementations of the observed required
services, followed by original application execution; GUI/framework coverage
remains a separate goal.

A separate [owned heap profile](darwin-owned-heap-checks.md) adds four bounded
allocator APIs under a new descriptor revision. This seven-service revision1
profile and its unknown-import refusals remain unchanged.
