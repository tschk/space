# Protected native SCI profiles

`native-protected-*` is an explicit supervisor-owned native component runner.
It does not change the trusted CPL0 CLI/GUI loader default. Its component object,
private capability slot and generation-bearing retained handle use the existing
runtime ownership model; execution kind 2 selects an owned CPL3 domain. Kind 0
continues to select a trusted clone. Catalog lookup, resume and destruction check
both the discriminator and the actual user/clone ownership bitmaps. Unknown or
mismatched kinds refuse before destructive cleanup.

The supervisor calls `native-protected-open(port, image, available, name, grants,
arguments)`, where `available` is an independently known readable extent and
`arguments` is zero or a trusted `{pointer,length}` descriptor. Arguments are at
most 1023 bytes, copied into owned supervisor storage and then the user capinfo
page. The returned handle contains no pointer or raw capability index.
`native-protected-run(handle,budget)` performs one native entry invocation and
returns its status. `native-protected-stop(handle)` reports 1 normal exit, 2 CPU
fault, 3 deadline or 5 compiler abort. Normal return leaves the component live;
abort, fault and deadline mark it retiring. Explicit retire/release completes
teardown. Released and recycled handles refuse before entering another instance.

## Artifact and permissions

Both profiles require native SCI v2 at base `0x60000000`, a memory declaration
mapped to grant 4, optional console grant 1, at most 128 import call sites and an
exact bounded execution trailer. The caller must actually hold the requested
authority. Structural validation uses the actual extent before private image
allocation or import binding. A finite native import table replaces flat kernel
symbol lookup; unsupported imports refuse before lifecycle allocation.

`pack-native-protected-sci.py --immutable-image` explicitly selects profile 1.
The private image is RX; mutable image globals fault. This supports the old
compiler without claiming general mutable native application support.

Profile 2 consumes truthful generic `sci_layout` from frozen Inauguration .325.
The packer verifies the exact raw artifact SHA256, size, base and section ranges
before applying Space capability/header/trailer transformations. Packaging checks
component identity, target/entry, unique capability declarations, exported authority
and the raw compiler ordinal mask for both profiles. The paged profile also
cross-checks section/static-data metadata, zero padding and actual binding tables
against the hash-bound layout. Both profiles check actual bounded symbol names,
entry export and raw import call sites. The loader
validates the bounded in-image descriptor again. Header/text are RX; initialized
mutable data is RW/NX; independently page-aligned bindings are RO/NX. Data cannot
overlap text or binding pages. SHA binding establishes which artifact the
sidecar describes, not authenticated producer provenance. Original source image
bytes never receive import patches or instance-global writes.

## Owned memory and native services

| User address | Ownership and permission |
| --- | --- |
| `0x60000000` | Private image; profile-specific permissions above |
| `0x68000000` | 64 KiB private stack, RW/NX |
| `0x69000000` | 2 MiB APP-API scratch heap, RW/NX |
| `0x6a000000` | Separate 2 MiB malloc arena, RW/NX |
| `0x6b000000` | Private capinfo/argument page, RW/NX |
| `0x6c000000` | Owned native SYSCALL stubs and return capsule, RX |

The malloc arena is separate from the APP-API scratch heap, so compiler-created
arrays cannot overwrite an app's raw scratch buffer. Its 128 allocation records
remain supervisor-owned. Malloc/calloc/realloc return only owned user addresses;
free and copies check exact allocation/range ownership. Null allocation failure
is real and compiler abort never resumes the failed expression. Missing memory
authority returns null from allocation services. Capinfo field 8 stays zero;
fields 16/24 describe the scratch heap and field 64 points only to the user copy
of arguments. It contains no kernel physical pointers.

The finite service group is abort, malloc/calloc/realloc/free, bounded console
write/decimal/hex/newline/character and APP-API argument/heap helpers. Each admitted
call patches to an instance-owned stub. The kernel checks saved user RIP, the
instance's admitted-service bitmap, current domain/capability/object ownership
and method authority. Unknown IDs do not fall through to native kernel or foreign
ABI syscall dispatch. Console buffers are translated through the calling
instance's physical ledgers, with a complete bounded NUL scan before output.
Kernel/peer pointers, invalid ports and missing rights refuse without output.
Legacy shared libraries containing IN/OUT are not mapped as a substitute.

State offset 120 selects the execution kind. Protected extra state at offset 112
owns the 768-byte user context, trap frame, allocator metadata, sixteen stack
frames, argument copy and allocator-backing ledger. The shared image/scratch
ledgers and capinfo frame remain explicit. Destruction removes the owned user
page tables before backing, and never interprets user malloc pointers as kernel
allocator headers. The trusted runner refuses protected handles and the protected
runner refuses trusted handles.

Admission holds local interrupts off through the fixed allocation stream. Its
conservative frame budget is `3120 + ceil(image_bytes/4096)`: up to 2054 user table
frames across the first four GiB, 1024 scratch/allocator backing frames, sixteen
user stack frames, sixteen frames of conservative kernel TSS headroom, two capinfo/trap frames
and eight state/ledger/pool frames. Admission also checks object/catalog/domain/
capability capacity and refuses an active preemptor. Entry uses generic owned user
contexts with IOPL0/IF1 and a bounded delivered-IRQ0 quantum. This is not a wall
clock bound on kernel service time or arbitrary CPL0 allocation recovery.

## Actual evidence

- `/tmp/space-native-protected-package-checkpoint/report.json`: six fresh compiled
  .324/.325 artifacts across default/lean/harden, 315 metadata/artifact tamper
  refusals and CLI failure preserving an existing output. Valid packed bytes
  match the artifacts used in the QEMU checkpoints below.

- `/tmp/space-native-protected-paged-checkpoint/report.json`: .325 profile 2,
  279 actual protected SCI invocations, 70 mixed trusted/protected lifecycle
  cycles, 140 protected lifecycle instances, independent initialized globals,
  exact source-byte preservation and 16 preallocation refusals.
- `/tmp/space-native-protected-immutable-checkpoint/report.json`: .324 profile 1,
  274 protected invocations and the same mixed lifecycle/resource proof, with
  mutable-image writes explicitly faulting and 15 preallocation refusals.
- `/tmp/space-native-protected-oom-checkpoint/report.json`: 32 MiB VM, available
  frames exactly one below the conservative budget, IF0/IF1 refusal with exact
  cap/domain/resource bytes unchanged, live peer and later fresh launch surviving.

The real compiled client exercises allocation, checked console traps, direct
text writes, NX stack/heap/data execution, read-only binding writes, kernel/peer
reads and writes, privileged OUT, forged service/capability/port/pointer requests,
compiler-emitted allocation abort 134 and a genuine infinite-loop deadline 124.
The mixed test alternates close order, resumes both kinds after failure, rejects
stale generations after actual slot recycling and checks stable frame count,
heap/object/cap/domain/export high water plus exact cap/domain bytes. All source
image bytes remain unchanged. The shell survives. Trusted retained-native and
distributable standard/minimal GUI regression gates also pass.

Repeat with `scripts/check-native-protected.py --in /path/to/in --out /new/output`.
Use `--profile paged` with explicit .325, or add `--mode oom` for the 32 MiB gate.
The default compiler remains .324. These are bounded compiled fixture profiles;
real native CLI service coverage and protected readable GUI execution are next
capability groups. No filesystem, display, networking, general scheduler or
POSIX process support is implied by this checkpoint.
