# Space Component Image Schema

`SCI` is the native Space component artifact. ELF, PE, Mach-O, and WASM may exist as compiler internals or compatibility-personality payloads, but they are not the native Space loading contract.

## Compiler / packager / runtime authority boundary

Inauguration emits generic code and component metadata. Space owns its concrete
capability names, grant masks, boot graph, provider policy and native SCI profile.
The packager must validate and translate declarations into that profile without
widening authority; the loader validates the actual executable manifest and
available provider bindings before entry. Sidecar metadata alone does not prove
runtime enforcement. Do not put Space-specific capability translation into the
compiler or infer authority from a resolved symbol.

For example, the bounded SCI display producer's packaging validates named memory
and display rights before translating compiler ordinals into Space's mask. Its
shared page is granted and adopted through trusted loader provenance, not a
client-supplied physical pointer. See [compositor/client ownership](docs/compositor-client-split.md).
This is a bounded implemented path, not a claim that all SCI metadata fields or
all desktop services already have equivalent enforcement.

Shared code executes with the caller's authority. The current flat symbol
registry and component-level grants do not establish per-symbol rights or make
privileged kernel exports safe to call from arbitrary guests. Keep kernel-linked
CPL0 and user SCI CPL3 behavior distinct; see [architecture](architecture.md).
Any change to this boundary requires matching generic emitter and Space
packager/loader tests, including malformed-image, missing-import and denied-grant
cases. Source/module separation does not by itself create isolated services.

## Version 0 Fields

The Inauguration compiler emits component metadata as a JSON sidecar
(`<artifact>.component-metadata.json`) alongside compiled freestanding objects.

| Metadata Key | SCI Equivalent | Source |
|---|---|---|
| `component` | Component identity (`package/name`) | `Decl::Component` + package |
| `target` | Target triple/architecture | `Decl::Component.target` |
| `entry` | Entry function name | Compile `--entry` flag |
| `code_sections` | `.text` segment descriptor | Compiler lowering output |
| `data_sections` | Initialized data segment | Struct initializers |
| `imports` | Required service interfaces | `Decl::Component.imports` |
| `exports` | Provided service interfaces | `Decl::Component.exports` |
| `capabilities_required` | Capabilities the loader must grant | `Decl::Component.capabilities` |
| `capabilities_exported` | Capabilities this component may delegate | Derived from `capabilities` |
| `object_schemas` | Struct/object type definitions | `Decl::Struct` from module |
| `memory` | Stack, heap, static data requirements | Compiler default / profile |
| `checkpoint` | Checkpoint eligibility policy | `Decl::Component.checkpoint` |
| `deterministic` | Deterministic execution requirement | `Decl::Component.deterministic` |
| `provenance` | Compiler version and build metadata | `CARGO_PKG_VERSION` + source hash |

## Dynamic linking (SCI v2)

The compiler emits dynamically linked images: every `--emit sci` artifact
carries an export table and an import table in its manifest, so components
bind to shared libraries at load time instead of embedding copies of shared
code.

### v2 image layout

Magic `0x5343490000000002`, 64-byte manifest:

| Offset | Field |
|---|---|
| 0 | magic (v2) |
| 8 | required capabilities mask |
| 16 | entry = virtual base of the code section |
| 24 | image size (manifest + code + data + tables + strings) |
| 32 | export count |
| 40 | export table offset (from image start) |
| 48 | import count |
| 56 | import table offset |

Sections in order: manifest (64 B), code, pad, data, export table, import
table, name strings. Each table entry is 16 bytes:

- **Export**: `[name image offset][code offset]` — the exported symbol's
  absolute address is `entry + code offset`.
- **Import**: `[name image offset][call site offset]` — the call site is a
  `call rel32` instruction; its displacement lives at `site + 1`.

Names are NUL-terminated in a trailing string block; all offsets are relative
to the image start.

### Binding contract

The Space loader (`components/sci-loader.in`) is the binder:

1. **Registration** — a shared-library SCI (boot-image kind `BOOT-IMAGE-LIB`,
   e.g. `components/libspace.in`) is registered at boot via
   `sci-register-library`: the loader validates its capabilities and copies
   its export table into a kernel-side symbol registry.
2. **Import resolution** — when a component whose import count is nonzero is
   loaded, `sci-bind-imports` resolves every imported name against the
   registry and patches the component's `call rel32` displacements with
   `target - (entry + site + 5)`. The library's text pages are mapped
   read-only into the importing component's domain at the library's fixed
   window (`LIB-VIRT-BASE = 0x3F000000`), so the bound calls execute shared
   text in the caller's domain with the caller's capabilities.
3. **Deny rule** — a component with an import that has no registered provider
   is denied before its entry point runs (`an import has no granted provider`).

v1 images (magic `0x5343490000000001`, 32-byte manifest, no symbol tables)
keep loading unchanged; they are statically self-contained.

### Explicit Space GUI canvas profile

The readable native GUI slice adds a Space-owned optional64-byte trailer to
SCI v2, after the compiler's code/data/tables/strings. The manifest image-size
field includes the trailer; existing table offsets and generic v2 format stay
unchanged. `pack-gui-sci.py` emits it only for exact named `GuiWindowCalc` and
`GuiWindowEditor` metadata declaring `GuiDisplay(present, window)`. Their exact
Space grant masks remain20 and52. Existing tiny `GuiCalc`/`GuiEditor` and other
display clients keep their one-page profile and receive no trailer implicitly.

The eight little-endian64-bit fields are magic `0x5350414345434E56`, version1,
maximum width768, maximum height384, BGRA stride3072, bytes1179648, flags1,
reserved0. Constants live in `protocol/gui-canvas.in`. The loader extension is
owned by the runtime; it must validate the exact bounded profile, retained mode
and granted memory/display rights before allocating or mapping. Individual
physical pages are ledger-owned and may be noncontiguous; the server receives
an owned contiguous virtual view, while the client sees its fixed granted pixel
window. See the [readable GUI plan](docs/plans/2026-10-24-readable-native-gui.md)
for implementation and acceptance status; packaging alone is not execution proof.

### Kernel exports and chained modules (dynamic nanokernel)

The nanokernel itself is a dynamic-link provider. The boot emitter
(`in compile --emit boot`) appends a **kernel export table** to the boot
image and records its absolute virtual address in the boot header field
`[40..48]` (zero when absent). Table layout: `[count(8)]`, then entries
`[name offset(8, relative to table start)][code offset(8)]`, followed by a
NUL-terminated name string block. A symbol's absolute address is
`KERNEL-CODE-BASE + code offset`.

At boot `dyn-register-kernel-exports` reads header field `[40..48]` and
registers every kernel symbol into the same registry the library loader
uses. Registry entries are **provider records**:

```
[name][fn virtual address][provider phys][provider virt base][provider size]
```

Provider activation profiles register their complete export tables, so binding
composes: a module loaded later may import from earlier providers, shared
libraries, or the kernel. Ordinary synchronous ephemeral activation and explicit
retained mode2 clients publish no flat exports; their private owned images may
be reclaimed, so an unowned global provider address cannot outlive them.
`sci-bind-imports` maps each non-kernel
provider's image pages RX into the importing domain at the provider's fixed
virtual base before patching call sites; kernel-provider entries carry zero
provider fields (kernel text is already present in every kernel-clone
domain).

A *dynamic module* is a component that imports most of its behavior and is
loaded at boot by boot-image kind (e.g. `BOOT-IMAGE-DYN-MOD`, kind 8;
`components/dyn-mod.in`). A module importing an unregistered symbol is
denied (`SCI: DENIED unresolved import ...`) and boot continues — see
`scripts/check-dynamic-modules.sh`.

## Example

```json
{
  "component": "space.kernel/KernelRoot",
  "target": "x86_64-unknown-none",
  "entry": "start",
  "code_sections": [
    { "name": ".text", "offset": 0, "size": 0, "flags": "rx" }
  ],
  "data_sections": [],
  "imports": [],
  "exports": [
    { "name": "boot", "interface": "BootEntry" }
  ],
  "capabilities_required": [
    { "name": "serial", "capability_type": "DebugConsole", "args": ["write"] },
    { "name": "memory", "capability_type": "PhysicalMemory", "args": ["discover", "map"] },
    { "name": "tables", "capability_type": "PageTables", "args": ["create", "activate"] },
    { "name": "traps", "capability_type": "TrapTable", "args": ["install"] },
    { "name": "caps", "capability_type": "CapabilityTable", "args": ["create_root", "mint_kernel"] }
  ],
  "capabilities_exported": [],
  "object_schemas": [
    {
      "name": "KernelState",
      "fields": [
        { "name": "root_table_id", "type": "Int", "offset": 0, "size": 8 },
        { "name": "realm_id", "type": "Int", "offset": 8, "size": 8 },
        { "name": "cpu_ready", "type": "Bool", "offset": 16, "size": 8 }
      ],
      "size": 24,
      "align": 8
    }
  ],
  "memory": { "stack": 16384, "heap": 0, "static_data": 0 },
  "checkpoint": "none",
  "deterministic": true,
  "provenance": {
    "compiler": "inauguration",
    "compiler_version": "0.2.0",
    "source_hash": ""
  }
}
```

## Loader Rule

The loader rejects an SCI when its self-declared required bitmask is not a
subset of the load-path grant mask (`SCI-GUEST-GRANTS` for packed/file guest
SCI; display/input/volume use their own constants). Packed `boot-image-find`
also bounds physical address and size.

That deny path is metadata. Kernel-linked components (personalities, runtime
components) run at CPL0 on a cloned 4 GiB identity map, so they can still
issue `inb`/`outb` and touch kernel-mapped memory. SCI guests loaded through
`sci-load`/`sci-load-file` instead get an exclusive `domain-create-user` page
table and enter at CPL3 via `domain-enter-user`, with no identity clone.
Syscall `cap-check` gates serial and channel syscalls; for kernel-linked code
it is a contract, not a hardware boundary.

The sidecar JSON still records:

- a capability is used by code but absent from `capabilities_required`
- an import has no granted provider
- the target does not match the boot image target
- unsafe/native sections request more authority than the realm policy allows
- checkpoint or determinism metadata conflicts with the component placement

## Compiler Milestone Status

| Milestone | Status |
|---|---|
| Component declaration parsing | ✅ Complete |
| Component metadata sidecar | ✅ Complete |
| Freestanding x86_64 ELF object | ✅ Complete |
| Real x86_64 function body lowering | ✅ Complete |
| Metadata + code in same artifact | ✅ Complete |
| Boot image enters `.in`-compiled `kernel_entry` in long mode under QEMU | ✅ Complete |
| Loader accepts a binary SCI manifest capability mask before entry | ✅ Complete |
| Loader deny-policy enforcement | bitmask vs grant constant; not isolation |

## Future Version Fields

Future SCI versions may add:

- `isolation`: required protection domain and unsafe/native restrictions
- `scheduling`: priority, latency class, CPU affinity
- `migration`: migration eligibility and policy
- `snapshot`: snapshot eligibility and policy
- `channels`: typed channel endpoint declarations
- `graph`: dependency and execution graph edges
- `compat`: compatibility personality requirements
- `gpu`: GPU/compute requirements and limits

The optional Space boot-image kind25 (`BOOT-IMAGE-RUNTIME-SELFTEST`) carries an
explicit native SCI diagnostic in runtime-component test images. The diagnostic
hub runs it through owned transient admission and checks status42, preserving
the loader regression without creating/overwriting a persistent `test.sci`.
This trusted native SCI check is distinct from protected CPL3 application proof;
ordinary distributable images do not gain that asset or a new application action.
