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
         ┌──────────────────▼──────────────────┘
         │              .in                     │
         │  native language — describes         │
         │  components, capabilities, objects,  │
         │  effects, execution graphs,          │
         │  distributed facts, scheduling       │
         └──────────────────────────────────────┘
```

Each layer exists to make the layer above possible.

---

## .in

.in is the native language.

It is not primarily trying to be:

- a better Rust
- a better Go
- a better Swift

Its job is to describe:

- components
- capabilities
- objects
- effects
- execution graphs
- distributed facts
- scheduling facts

### Language-Level Concepts

```in
// A component with declared capabilities and effects
component "space.renderer/video-pipeline" {
  target "x86_64-unknown-none"
  deterministic true
  checkpoint "on-request"

  capability gpu.compute
  capability network.send
  capability fs.read("media/*.h264")
}

// A distributed function — the compiler understands this has
// orchestration implications before the runtime sees it
@gpu
distributed render_frame(frame: Frame) -> Frame {
  return process_frame(frame)
}

// An effect — the compiler tracks what each function can do
fn write_log(msg: String) -> void
  effect: io.write(serial)

// A scheduling fact
@latency-critical
fn handle_input(event: InputEvent) -> void
```

The compiler immediately understands:

- this uses GPU resources
- this may be distributed
- this has orchestration implications
- this has latency requirements
- what capabilities are needed

Those are language-level concepts, not runtime annotations.

### What .in Describes

| Concept | Language Form | Compiler Action |
|---------|--------------|-----------------|
| Component | `component "name" { ... }` | Emits component declaration in SCI |
| Capability | `capability gpu.compute` | Added to capability manifest |
| Object | `struct VideoFrame { ... }` | Schema in object manifest |
| Effect | `effect: io.write(serial)` | Tracks side effects through graph |
| Execution graph | `fn a() -> void` / `fn b() -> void` | Call graph → execution graph |
| Distributed fact | `distributed fn foo()` | Marks for distributed scheduling |
| Scheduling fact | `@latency-critical` | Emitted as scheduling hint |
| Determinism | `deterministic true` | Checkpoint/replay policy |
| Checkpoint | `checkpoint "on-request"` | Snapshot policy |

---

## Inauguration

Inauguration is the compiler.

The compiler is the real operating system contract.

### Pipeline

```
  .in source
       │
       ▼
  frontend (parser, typechecker, verifier)
       │
       ▼
  Core IR (UnifiedModule — all frontends converge here)
       │
       ▼
  analysis passes:
    ├── capability graph extraction
    ├── execution graph construction
    ├── object schema extraction
    ├── effect tracking
    ├── scheduling analysis
    ├── determinism analysis
    └── dependency resolution
       │
       ▼
  optimization passes (Core IR level)
       │
       ▼
  SCI emission:
    ├── code sections (machine code)
    ├── data sections
    ├── capability manifest
    ├── object schema manifest
    ├── import/export table
    ├── scheduling hints
    ├── checkpoint policy
    ├── determinism flags
    ├── migration metadata
    ├── GPU requirements
    ├── debug metadata
    └── provenance
```

The compiler doesn't just generate machine code.

It generates:

- authority
- ownership
- scheduling
- imports
- exports
- checkpoint policy
- determinism policy
- migration policy

The compiler knows what a component is allowed to do before it runs.

### Multi-Language Support

Core IR is the shared semantic representation.

Everything eventually becomes:

```
UnifiedModule
```

Whether it came from:

- .in
- Rust
- Go
- Swift
- V
- OCaml
- C

Each frontend lowers into the same Core IR. This means:

- Capability analysis works across languages
- Execution graphs are language-agnostic
- Optimization passes benefit all frontends
- SCI emission is language-independent

The language becomes less important than the semantic graph.

### Core IR Is Where

- types
- effects
- capabilities
- dependencies
- execution facts

become unified.

### What Inauguration Generates

| Artifact | Contents | Consumer |
|----------|----------|----------|
| SCI code | Machine code (x86_64, ARM, etc.) | Space runtime |
| Capability manifest | Required capabilities, exports | SCI loader |
| Object schema manifest | Struct/object definitions | Object graph store |
| Import/export table | Service dependencies | Component supervisor |
| Execution graph | Call graph, component graph | Scheduler |
| Scheduling hints | Priority, latency, affinity | Scheduler |
| Checkpoint policy | Eligibility, frequency | Checkpoint service |
| Determinism flags | Execution mode requirements | Determinism runtime |
| Migration metadata | Migration eligibility, size | Migrator |
| GPU requirements | Compute/memory/bandwidth | GPU service |
| Debug metadata | Source maps, symbols | Debugger |
| Provenance | Compiler version, source hash | Audit |

---

## SCI (Space Component Image)

SCI replaces ELF.

### Today

```
source
  ↓
ELF
  ↓
process
```

### Space

```
source
  ↓
SCI
  ↓
component
```

### SCI Contents

| Section | Description |
|---------|-------------|
| Code | Machine code (.text) |
| Data | Initialized data (.data, .rodata) |
| Capabilities | Required and exported capabilities |
| Imports | Required service interfaces |
| Exports | Provided service interfaces |
| Schemas | Object/struct type definitions |
| Scheduling hints | Priority, latency class, CPU affinity |
| Checkpoint policy | None, on-request, periodic, always |
| Determinism flags | None, deterministic, replay-safe |
| Migration metadata | Migratable, pinned, size estimate |
| GPU requirements | Compute units, memory, extensions |
| Debug metadata | Source maps, DWARF-like info |
| Provenance | Compiler version, source hashes, timestamps |

### What The Runtime Can Inspect

Before execution begins, the runtime can answer:

- what can this component do?
- what can it access?
- what does it own?
- can it be checkpointed?
- can it migrate?
- can it use GPUs?
- what is its scheduling class?
- can it run deterministically?
- what interfaces does it provide?
- what interfaces does it require?
- what objects does it define?
- what provenance does it have?

### Loader Rule

The loader rejects an SCI when:

- a capability is used by code but absent from the manifest
- an import has no granted provider
- the target architecture does not match the boot target
- checkpoint policy conflicts with the placement
- determinism metadata conflicts with the component graph
- provenance verification fails

---

## Space

Space is the operating system.

### Native Concepts

| Concept | Description |
|---------|-------------|
| Component | A compiled unit of execution and authority |
| Realm | An isolation boundary (components + objects + capabilities) |
| Object | A typed value with identity and references |
| Capability | An unforgeable authority over a resource |
| Channel | A typed communication path between components |
| Graph | An execution, object, or dependency topology |
| Checkpoint | A consistent capture of state |
| Image | A bootable or loadable artifact (SCI) |
| Personality | A compatibility environment for a legacy platform |

### Not Native Concepts

These only exist inside compatibility layers:

| Concept | Why Not Native |
|---------|---------------|
| Process | Replaced by component + realm |
| File | Replaced by object graph node |
| Directory | Replaced by object graph hierarchy |
| User | Replaced by capability grants |
| Group | Replaced by capability classes |
| Fork | Replaced by checkpoint + realm creation |
| Root | No global root — capability is authority |
| Global namespace | Every realm has its own view |
| PID | Replaced by capability reference |

### Architecture

```
                  ┌─────────────────────────────────────┐
                  │         Compatibility Layers          │
                  │  Linux personality   Darwin persona   │
                  │  Windows personality                 │
                  └──────────────────┬──────────────────┘
                                     │
                  ┌──────────────────▼──────────────────┐
                  │         Component Graph              │
                  │  fs.in  net.in  gfx.in  proc.in      │
                  │  loader.in  time.in  rand.in         │
                  └──────────────────┬──────────────────┘
                                     │
                  ┌──────────────────▼──────────────────┐
                  │         Object Graph Store           │
                  │  persistent typed objects            │
                  │  schema registry                     │
                  │  reference management                │
                  └──────────────────┬──────────────────┘
                                     │
                  ┌──────────────────▼──────────────────┐
                  │         Component Supervisor          │
                  │  lifecycle, policy, restart          │
                  │  capability grant, SCI loading       │
                  └──────────────────┬──────────────────┘
                                     │
                  ┌──────────────────▼──────────────────┐
                  │         Capability Fabric            │
                  │  minting, delegation, revocation     │
                  │  attenuation, audit                  │
                  └──────────────────┬──────────────────┘
                                     │
                  ┌──────────────────▼──────────────────┐
                  │         Channel Fabric               │
                  │  cross-domain IPC                    │
                  │  zero-copy VM object transfer        │
                  └──────────────────┬──────────────────┘
                                     │
                  ┌──────────────────▼──────────────────┐
                  │         Nanokernel                   │
                  │  memory, paging, interrupts, timers  │
                  │  scheduling hooks, fault handling    │
                  │  bootstrap                           │
                  └──────────────────────────────────────┘
```

---

## Nanokernel

The nanokernel is intentionally tiny.

### It Owns Only

| Responsibility | Description |
|---------------|-------------|
| Memory | Physical memory discovery, frame allocation |
| Paging | Page table creation, domain switching, TLB management |
| Interrupts | IDT, PIC/APIC, exception dispatch |
| Timers | PIT/HPET/APIC timer, clock sources |
| Scheduling hooks | Timer-based preemption, thread primitives |
| Capability tables | Kernel-level capability storage |
| Kernel objects | Typed object IDs, reference counting |
| Channels | Cross-domain channel primitives |
| VM objects | Large memory region transfer between domains |
| Fault handling | Page faults, divide errors, #GP, triple fault |
| Bootstrap | Multiboot/Limine entry, long mode setup |

### Nothing Else

The nanokernel explicitly does NOT contain:

| Feature | Belongs In |
|---------|-----------|
| Filesystem | fs.in component |
| Network stack | net.in component |
| Desktop environment | compositor + shell components |
| Package manager | package.in component |
| Browser | browser component |
| GPU driver | gpu-service.in component |
| Audio stack | audio.in component |
| Device manager | devfs.in component |
| User authentication | auth.in component |
| Logging | log.in component |
| Debugger | debug.in component |
| Compatibility layers | linux-compat.in, etc. |

### Guiding Rule

If a feature can run as an isolated component with explicit capabilities,
it should not live in the nanokernel.

---

## Components

Everything is a component.

### Examples

| Component | Responsibilities |
|-----------|-----------------|
| fs.in | File I/O, directories, mounts, permissions |
| net.in | Sockets, DNS, TLS, HTTP |
| gfx.in | Compositor, surfaces, input routing |
| proc.in | Spawn, exit, signals, thread lifecycle |
| time.in | Clocks, timers, sleep |
| mem.in | mmap, brk, shared memory |
| rand.in | Entropy, random number generation |
| loader.in | ELF/PE/Mach-O parsing, memory domain setup |
| objstore.in | Persistent object graph storage |
| policy.in | Capability grant policy evaluation |
| log.in | Structured logging, tracing |
| debug.in | Breakpoints, memory inspection |
| linux-compat.in | Linux ABI → microservice dispatch |
| darwin-compat.in | Darwin ABI → microservice dispatch |
| win-compat.in | Windows ABI → microservice dispatch |
| audio.in | Audio device management, mixing |
| gpu-service.in | GPU command queue, memory management |

### A Component Contains

- code
- capabilities
- interfaces
- state
- policies

Instead of:

- process
- PID
- filesystem access
- ambient permissions

### Component Manifest

```in
component "space.services/fs" {
  target "x86_64-unknown-none"
  deterministic true
  checkpoint "on-request"

  import "core.channel"
  import "core.block-device"

  capability block-device: read-sectors(dev: Int, buf: Int, lba: Int, count: Int) -> Int
  capability channel: accept-request() -> Request
  capability channel: send-response(resp: Response) -> void
}
```

---

## Realms

A realm is an isolation boundary.

Somewhere between:

- container
- VM
- process
- security domain

but capability-native.

### A Realm Owns

- components
- objects
- capabilities
- policies

### Properties

- Each realm has its own page table tree (memory domain)
- Each realm has its own capability table
- Each realm has its own object graph view
- Realms cannot access each other's memory without explicit channel mapping
- Realms communicate through channels only
- Capabilities can be delegated across realm boundaries
- Different realms can have completely different views of the system

### Realm Hierarchy

```
  ┌────────────────────────────────────────────┐
  │         System Realm (kernel)              │
  │  nanokernel, core services                 │
  │  owns hardware, creates subordinate realms │
  └────────────────┬───────────────────────────┘
                   │
          ┌────────┴────────┐
          │                  │
  ┌───────▼───────┐  ┌──────▼───────┐
  │ Service Realm │  │ Service Realm│
  │ fs.in, net.in │  │ gfx.in, etc  │
  │ owned by sys  │  │ owned by sys │
  └───────┬───────┘  └──────┬───────┘
          │                  │
  ┌───────▼───────┐  ┌──────▼───────┐
  │  Guest Realm  │  │  Guest Realm │
  │  Linux app    │  │  Windows app │
  │  owned by user│  │  owned by user│
  └───────────────┘  └──────────────┘
```

---

## Capabilities

Capabilities are the security model.

Instead of:

```
uid=0
```

or:

```
administrator
```

authority is explicit.

### Examples

| Capability | Grants |
|------------|--------|
| `read-object` | Read an object's persisted state |
| `mutate-object` | Modify an object's persisted state |
| `receive-input` | Subscribe to keyboard/mouse input events |
| `render-surface` | Create and present graphical surfaces |
| `submit-gpu-work` | Enqueue GPU compute commands |
| `access-network` | Open sockets to specific endpoints |
| `read-clock` | Read current time |
| `get-random` | Access random number generator |
| `create-realm` | Spawn a new isolated realm |
| `delegate-cap` | Pass a capability to another component |
| `create-checkpoint` | Capture component/realm state |
| `load-sci` | Load a component image into a realm |

### Properties

- unforgeable
- typed
- delegatable only when policy allows
- revocable or lease-bound
- attenuable into weaker capabilities
- inspectable by the runtime for audit
- invisible to components without authority

No ambient authority.
No global root.
No "everything can see everything."

---

## Objects

Objects replace files as the native storage abstraction.

Instead of:

```
/home/max/config.json
```

you have:

```
Object#1234
```

with:

- identity
- schema
- references
- ownership
- policies
- capabilities

### An Object Has

| Field | Description |
|-------|-------------|
| ID | Stable, unique identifier |
| Schema | Type definition from component manifest |
| References | Links to other objects (typed edges) |
| Owner | Realm or component that created it |
| Policy | Read/mutate/delegate capability rules |
| Version | Monotonic version counter |
| Timestamps | Creation, last modification |

### Object Graph

Objects form graphs.

```
  Object#1 (root realm)
    ├── Object#2 (capability table)
    ├── Object#3 (service graph root)
    │     ├── Object#4 (fs.in service state)
    │     ├── Object#5 (net.in service state)
    │     └── Object#6 (gfx.in service state)
    └── Object#7 (guest realm)
          ├── Object#8 (guest capability table)
          └── Object#9 (guest file handle table)
```

Components operate on object graphs.

Files become a compatibility view.

---

## Channels

Channels replace most IPC.

Instead of:

- pipes
- signals
- sockets

native communication becomes:

```
typed channel
```

### Channel Properties

- Typed (protocol defined by endpoint)
- Capability-gated (who can send and receive)
- Cross-domain (connect components in different realms)
- Zero-copy for large data (VM object transfer)

### Large Data

Large data moves through:

```
VM objects
```

for zero-copy transfer between domains.

---

## Checkpoints

Checkpointing is native.

The OS can capture:

- object
- component
- realm
- graph
- whole system

### State Can Be

- saved
- replayed
- restored
- migrated

without treating it as an application-specific feature.

### Checkpoint Model

1. Quiesce the target (drain in-flight channel messages)
2. Capture object graph state
3. Capture capability state
4. Capture dirty memory pages
5. Record external nondeterminism (timestamps, random values)
6. Store as a checkpoint object

---

## Determinism

Space makes nondeterminism explicit.

| Source | Mechanism |
|--------|-----------|
| Time | Time capability (must be granted) |
| Randomness | Random capability (must be granted) |
| External inputs | Recorded in replay log |
| Scheduling | Deterministic scheduler mode |
| Object iteration | Stable order guaranteed |
| Codegen | Deterministic compiler passes |

### Execution Modes

- Normal mode
- Deterministic replay mode

The runtime switches modes depending on policy.

---

## GPU Model

GPU is a first-class resource.

### Not

```
application → driver → GPU
```

### Instead

```
component → compute capability → GPU service
```

### Compiler Awareness

The compiler can emit:

- GPU eligibility
- memory costs
- fallback paths
- determinism metadata

The runtime schedules placement.

---

## Compatibility Personalities

Linux, Darwin, and Windows are personalities.

They sit above Space.

### Personality Architecture

```
  Legacy binary (ELF, Mach-O, PE)
       │
       ▼
  loader.in — parses binary, creates realm, loads shim
       │
       ▼
  compat shim (guest libc replacement)
       │  channel messages
       ▼
  compat service (linux-compat.in, darwin-compat.in, win-compat.in)
       │  translates legacy model → Space primitives
       ▼
  Core microservices (fs.in, net.in, gfx.in, proc.in, ...)
```

### Linux Personality

Maps:

- processes → components + realms
- files → objects
- syscalls → channel messages

### Darwin Personality

Maps:

- Mach ports → channel endpoints
- launchd → component supervisor
- XPC → typed channels
- IOKit → device capabilities

### Windows Personality

Maps:

- NT handles → capabilities
- Registry → object graph view
- Win32 → compositor + input channels
- COM → capability dispatch

Space never becomes Linux internally.

---

## The Core Thesis

The entire system is built around one idea:

**compiler-defined execution**

The compiler describes:

- authority
- objects
- dependencies
- execution
- placement
- policies

The runtime executes those graphs.

The nanokernel enforces them.

### Fundamental Flow

```
  .in source
       │
       ▼
  Inauguration (compiler)
       │
       ▼
  Core IR
       │
       ▼
  SCI (component image)
       │
       ▼
  Space runtime
       │
       ▼
  Nanokernel enforcement
       │
       ▼
  Execution
```

The compiler is the constitutional layer of the operating system.

The nanokernel is the hardware enforcement layer underneath it.

### Summary

| Layer | Role | Analogy |
|-------|------|---------|
| .in | Describe what should exist | Constitution |
| Inauguration | Prove it's valid and compile it | Legislature |
| SCI | Package it with its authority | Passport |
| Space | Execute it within its bounds | Executive |
| Nanokernel | Enforce the boundaries | Police |
