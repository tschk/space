# Space Architecture

```
         ┌─────────────────────────────────────┐
         │              Space                   │
         │     operating system, component      │
         │     runtime, capability fabric       │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │              SCI                     │
         │  Space Component Image format       │
         │  replaces ELF as native contract    │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │          Inauguration                │
         │  compiler — the real OS contract     │
         │  generates authority, graphs, SCI   │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │              .in                     │
         │  native language — describes         │
         │  components, capabilities, objects   │
         └──────────────────────────────────────┘
```

Each layer exists to make the layer above possible.

---

## .in

.in is the native language. It describes components, capabilities, objects,
effects, and execution graphs as language-level concepts, not runtime
annotations.

```in
component KernelRoot {
  target "x86_64-unknown-none"
  deterministic true
  checkpoint none

  export boot: BootEntry
  capability serial: DebugConsole(write)
  capability memory: PhysicalMemory(discover, map)
}
```

The compiler extracts capability manifests, object schemas, and execution
graphs from these declarations and emits them into the SCI artifact.

---

## Inauguration

Inauguration is the compiler. It lowers `.in` source through a frontend
(parser, typechecker, verifier) into Core IR, runs analysis passes
(capability graph, execution graph, object schema, effect tracking,
determinism), and emits SCI artifacts containing machine code plus
metadata manifests.

Multi-language support: Rust, Go, Swift, C, and other frontends all
lower into the same Core IR, so capability analysis and SCI emission
work across languages.

---

## SCI (Space Component Image)

SCI is the native binary contract — not ELF. An SCI artifact contains:

- Code sections (x86_64 machine code)
- Capability manifest (declared authority)
- Object schema manifest (struct definitions)
- Import/export table
- Provenance (compiler version, source hash)

The loader validates declared capabilities against the realm's grants
before transferring control. A component requesting undeclared
capabilities is denied before its entry point runs.

---

## Nanokernel

The nanokernel (`kernel-root.in`) is the root component. It runs in
long mode after the boot trampoline (`boot/multiboot.asm`) enters
x86_64. It provides:

- **Serial console** — COM1 UART output and interactive shell
- **Physical memory discovery** — Multiboot1 memory map parsing
- **Virtual memory** — 4 KiB page table walking and mapping
- **Object graph** — arena-allocated objects with checkpoint/restore
- **Capability table** — mint and track authority per realm
- **Interrupts** — IDT, 8259 PIC, PIT timer, exception handlers
- **Component supervisor** — validates and activates components
- **Cooperative scheduler** — M:N threading with ctxsw, blocking, yield
- **Preemptive scheduler** — timer-driven context switching
- **Typed channels** — CSP-style ring buffers with blocking send/recv
- **Cross-domain channels** — shared-page IPC between memory domains
- **Memory domains** — isolated page table trees (Phase 0)
- **SCI loader** — loads and validates external component images
- **e1000 NIC driver** — MMIO register access, TX/RX rings, ARP, UDP
- **Deterministic execution** — xorshift64 PRNG with seeded workloads

---

## Memory Domains

Domains are isolated page table trees. Domain 0 is the kernel domain
(shared PML4 at physical 0x1000). `domain_create()` allocates a new
PML4, copies the kernel's low mappings, and returns an ID.
`domain_switch()` changes CR3. `domain_map()` installs a mapping in
a domain's page table. Shared pages enable cross-domain IPC.

---

## Components

Components are registered as objects in the graph with a name, entry
address, and required capabilities. The supervisor checks required
caps against the realm's grants before invoking the entry point.

The SCI loader extends this to external components: it reads a binary
manifest from memory, validates capabilities, creates a domain, maps
the component image, and transfers control.

---

## Capabilities

Capability slots are 16 bytes: `[target_object_ptr][rights]`. The
kernel mints capabilities into a root table. Capability bits:

| Bit | Capability |
|-----|-----------|
| 1   | serial    |
| 2   | timer     |
| 4   | memory    |
| 8   | graph     |

The loader rule: a component may only activate if its declared
authority is a subset of what its realm grants.

---

## Objects

Objects live in a dedicated arena (32 bytes each:
`[id][type_tag][ref0][ref1]`). The arena can be checkpointed and
restored independently of kernel state.

---

## Channels

In-address-space channels are ring buffers with poll-with-yield
blocking. Cross-domain channels use shared physical pages mapped into
both domains' page tables.

---

## Current Status

### Running Today
- Nanokernel boots x86_64 long mode under QEMU
- Serial console, physical memory discovery, page tables
- Object graph arena, capability table, bootstrap realm
- Cooperative + preemptive multitasking
- Typed in-address-space channel IPC demo
- Cross-domain shared-page channels
- SCI manifest loader with capability-mask validation
- Interactive shell (16 commands)
- e1000 NIC driver (UDP transmit, ARP)
- Deterministic execution subsystem
- Memory domain isolation (Phase 0)

### Repository Layout

```
kernel/
  kernel-root.in        nanokernel root component
  domain.in             memory domain subsystem
  channel.in            cross-domain channel fabric
  net.in                e1000 NIC driver
  pci.in                PCI bus enumeration
  guest-service.in      SCI guest component example
boot/
  multiboot.asm         x86_64 CPU bring-up
scripts/
  check-qemu-boot.sh    Full boot verification
  check-sci-contract.sh SCI metadata validation
  build-multicomponent.sh  Multi-component image build
  check-network.sh      Network driver test
sci-schema.md           SCI format specification
```
