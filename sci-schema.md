# Space Component Image Schema

`SCI` is the native Space component artifact. ELF, PE, Mach-O, and WASM may exist as compiler internals or compatibility-personality payloads, but they are not the native Space loading contract.

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

Every successfully loaded component also registers its own export table, so
binding composes: a module loaded later may import from earlier modules,
shared libraries, or the kernel. `sci-bind-imports` maps each non-kernel
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

The loader rejects an SCI when:

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
| Loader deny-policy enforcement | ✅ Complete |

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
