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
| Loader validates SCI metadata against granted capabilities before entry | ✅ Complete |

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
