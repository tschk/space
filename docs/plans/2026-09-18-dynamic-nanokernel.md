# Dynamic nanokernel + dynamic modules (Space)

**Status:** In progress (P0) — extends 2026-09-18 SCI v2 dynamic linking.

## Problem

The first dynamic-linking increment (SCI v2 export/import tables, `libspace`
registry, load-time call-site binding) still binds only against boot-kind-7
shared libraries. The nanokernel itself — the largest service provider in the
system — is not a dynamic-link participant: components that want kernel
services (serial, PCI, channels, scheduler) must embed copies of them
(`components/display-standalone.in` carries ~200 lines of duplicated
serial/PCI/input stubs), exactly the pattern `docs/kernel-audit.md` flags.
And loaded components cannot serve each other: the registry is populated only
from libraries, not from successfully loaded modules.

## Design

### 1. The nanokernel is a dynamic-link provider

The boot emitter (`in compile --emit boot`) appends a **kernel export table**
to the boot image and records its absolute virtual address in the SCI boot
header (field `[40..48]`, previously zero). The table lists every function
lowered into the kernel image: `[count(8)]` then entries
`[name offset(8, relative to table start)][code offset(8)]`; names are
NUL-terminated in a trailing string block. Absolute function address =
`KERNEL-CODE-BASE (0x101100) + code offset`.

At boot, `dyn-register-kernel-exports` reads header field `[40..48]` at
`0x101028` and registers every symbol into the dynamic-link registry with
provider = kernel (no extra mapping needed: kernel text is present in every
kernel-clone domain). This is a generic Inauguration capability — boot images
carry their own symbol table — not a Space-branded compiler feature.

### 2. Chained dynamic modules

Every successfully loaded component registers its own export table into the
same registry. Registry entries become provider records:

```
[name][fn virtual address][provider phys][provider virt base][provider size]
```

`sci-bind-imports` maps each provider's image pages (RX, page-aligned phys)
into the importing domain at the provider's fixed virtual base before
patching call sites. Kernel-provider entries carry zero provider fields
(no mapping required). Bind order therefore composes: a module loaded later
may import from earlier modules, libraries, or the kernel — the registry is
one flat, grant-checked namespace.

### 3. Modules (boot kinds 8+)

A *dynamic module* is a component that imports most of its behavior and is
loaded at boot from the boot image by kind. Demo set:

- kind 8 `dyn-mod` — imports `serial-write-cstr`, `serial-write-hex`,
  `serial-nl` from **kernel exports** and prints markers; its own exported
  symbol is then importable by later modules.
- A deny variant imports `no-such-service` — the loader must deny with
  `SCI: DENIED unresolved import` and the boot must continue.

### 4. Standalone shims dissolve

`components/display-standalone.in` drops its duplicated serial/PCI/input
function copies and declares them as imports (empty-body `interrupt fn`
stubs); the standalone display SCI binds against the kernel's exports at
load time. Component-local state (heap mirror, input stubs used before the
input component exists) stays component-owned — only stateless kernel
services become imports.

## Loader rules (unchanged from sci-schema.md)

- required capability mask must be a subset of realm grants (before binding);
- every import must have a registered provider (else deny);
- v1 (32-byte manifest) images remain statically self-contained.

## Acceptance

- `scripts/check-dynamic-modules.sh`: good image boots, kernel-export
  binding prints module markers via kernel serial; bad image denies the
  unresolved import and boots to shell.
- `scripts/check-user-sci.sh` still proves libspace binding.
- `scripts/check-runtime-components.sh` compiles the standalone display with
  kernel imports (previously failed at the verifier on an undeclared
  `pci-bar-mmio` call).
- Inauguration `cargo test` green; boot-image export table unit-tested.

## Non-goals

- No runtime loading from disk changes (execve path already binds v2).
- No per-symbol capability refinement (component-grant mask remains the
  authority gate this round; documented as next step).
