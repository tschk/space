# Space Component Image Schema

`SCI` is the native Space component artifact. ELF, PE, Mach-O, and WASM may exist as compiler internals or compatibility-personality payloads, but they are not the native Space loading contract.

## Version 0 Fields

| Field | Purpose |
|-------|---------|
| `magic` | `SCI0` |
| `target` | Target identity such as `x86_64-space` |
| `component` | Package and component name |
| `entry` | Exported entry interface and function |
| `code` | Machine-code section descriptors |
| `data` | Data section descriptors |
| `imports` | Required service interfaces |
| `exports` | Provided interfaces |
| `capabilities_required` | Capabilities the loader must grant |
| `capabilities_exported` | Capabilities this component may create or delegate |
| `object_schemas` | Persistent object schemas used by the component |
| `memory` | Stack, heap, static memory, and VM object requirements |
| `isolation` | Required protection domain and unsafe/native restrictions |
| `checkpoint` | Checkpoint eligibility and restore policy |
| `determinism` | Time, randomness, scheduling, and replay requirements |
| `provenance` | Compiler version, source hash graph, and build inputs |

## Loader Rule

The loader rejects an SCI when:

- a capability is used by code but absent from `capabilities_required`
- an import has no granted provider
- the target does not match the boot image target
- unsafe/native sections request more authority than the realm policy allows
- checkpoint or determinism metadata conflicts with the component placement

## First Compiler Milestone

The first `.in` compiler milestone is an `SCI` metadata sidecar for `x86_64-space` with no executable machine-code claim. The second milestone is a freestanding x86_64 code section for a scalar `start` entry. The third milestone is a boot image that loads one SCI and enters its component entry under QEMU.
