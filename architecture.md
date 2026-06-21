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

SCI replaces ELF as the native Space runtime contract.

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

---

## Implementation Roadmap

### Dependency Graph

```
Phase 0: Domains ──────────────────────────────────────┐
  creates: domain_create, domain_switch, domain_map     │
  unlocks: isolated memory for microservices            │
                                                        │
Phase 1: Cross-Domain Channels ─────────────────────────┤
  creates: chan_connect, chan_send_cross, VM object xfer│
  unlocks: IPC between isolated components              │
                                                        │
Phase 2: Component Loader ──────────────────────────────┤
  creates: loader.in (parse + place SCI into domain)    │
  unlocks: loading any .in component into its own realm │
                                                        │
Phase 3: Core Microservices ─────────┬──────────────────┘
  proc.in mem.in time.in rand.in     │
  (first .in services in own domains)│
                                     ▼
Phase 4: fs.in ───────────── Phase 5: net.in ───────────┐
  file I/O, dirs, mounts     sockets, DNS, TLS          │
                                                        │
Phase 6: gfx.in ──────────── Phase 7: audio.in ─────────┤
  compositor, surfaces      PCM, mixing, streams        │
                                                        │
Phase 8: Compatibility ─────────────────────────────────┤
  loader.in (ELF/PE/Mach-O)  linux/darwin/win compat    │
                                                        │
Phase 9: Distribution ──────────────────────────────────┘
  remote components, replicated objects, migration
```

---

## Phase 0: Domain Subsystem

**What**: Multiple memory domains (page table trees).
**Why**: The #1 blocker. Without domains, every component shares one
         address space — no isolation, no microservices, no compat.
**Where**: `kernel/kernel-root.in` + new `kernel/domain.in`

### Primitives To Add

```in
fn domain_create() -> Int
  // Allocates a new PML4 (4K frame)
  // Copies kernel mappings (code, data, stack, MMIO)
  // Returns a domain ID

fn domain_switch(id: Int) -> void
  // Writes CR3 with the domain's PML4 physical address
  // Executes INVPG for all pages (or uses PCID if available)

fn domain_map(domain: Int, virt: Int, phys: Int, flags: Int) -> void
  // Walks the domain's page table hierarchy
  // Creates intermediate tables as needed
  // Installs a leaf PTE mapping virt → phys with flags
  // Does NOT affect the current address space

fn domain_unmap(domain: Int, virt: Int) -> void
  // Removes a mapping from the domain's page table

fn domain_destroy(id: Int) -> void
  // Frees all frames in the domain's page table tree
  // Does NOT free the domain's memory (caller must free)
```

### Data Structures

```in
// In kernel-root.in or kernel/domain.in
const MAX_DOMAINS = 64
var domain_count = 0
var domain_table: Int  // array of { cr3, state, owner_cap } per domain
  // allocated during domain_init

// Domain state
const DOMAIN_FREE = 0
const DOMAIN_ACTIVE = 1
const DOMAIN_SUSPENDED = 2
const DOMAIN_DESTROYED = 3
```

### Channel Shared Page Protocol

Cross-domain communication requires a page mapped into both domains.

```in
fn domain_create_shared_page(dom_a: Int, dom_b: Int, virt_a: Int, virt_b: Int) -> Int
  // Allocates a physical frame
  // Maps it into dom_a at virt_a
  // Maps it into dom_b at virt_b
  // Returns the physical address (for capability tracking)
```

The shared page holds a simple ring buffer:

```in
// Layout of a shared channel page (4096 bytes)
// offset 0:     head (write index, owned by sender)
// offset 8:     tail (read index, owned by receiver)
// offset 16:    capacity (max messages)
// offset 24:    message_size (bytes per slot)
// offset 4096:  message data (ring buffer)
```

### Verification

```in
fn test_domain_create() -> void {
  let d = domain_create()
  // d should be 1 (first non-kernel domain)
  // CR3 should point to new PML4, not kernel's PML4
}

fn test_domain_isolation() -> void {
  let d1 = domain_create()
  let d2 = domain_create()
  let page = domain_create_shared_page(d1, d2, 0xFFFF8000, 0xFFFF8000)
  // d1 can write 0xFFFF8000, d2 can read it
  // d1 CANNOT read d2's private pages
  // d2 CANNOT read d1's private pages
}
```

### Files
- `kernel/kernel-root.in` — add domain_create, domain_switch, domain_map
- `kernel/domain.in` — domain data structures, channel shared page protocol
- `tests/test-domain.in` — verification tests

---

## Phase 1: Cross-Domain Channel Fabric

**What**: Channels that work across domains, with capability transfer.
**Why**: Microservices need to communicate. Current channels are
         single-address-space only.
**Where**: `kernel/channel.in`

### Primitives To Add

```in
fn chan_connect(local_domain: Int, remote_domain: Int, shared_page: Int) -> Int
  // Creates a cross-domain channel endpoint
  // Returns a channel handle

fn chan_send_cross(ch: Int, msg: Int, cap: Int) -> void
  // Writes message to shared page ring buffer
  // Optionally transfers a capability
  // Notifies remote domain (scheduling hint)

fn chan_recv_cross(ch: Int) -> (Int, Int)
  // Reads message from shared page ring buffer
  // Returns (message, transferred_capability)

fn chan_transfer_cap(ch: Int, cap: Int) -> void
  // Tags a capability for transfer across domains
  // Receiver gets a minted copy with attenuated rights
```

### Capability Transfer Protocol

1. Sender calls `chan_transfer_cap(ch, cap_handle)`
2. Kernel validates sender has `delegate-cap` right on the cap
3. Kernel creates a minted copy in receiver's capability table
4. Next message on the channel carries the new cap handle
5. Receiver gets the attenuated capability

### Files
- `kernel/channel.in` — cross-domain extensions
- `kernel/cap-table.in` — capability delegation, minting, revocation

---

## Phase 2: Core Microservices

**What**: First .in components that run in their own domains.
**Why**: Prove the domain + channel fabric works with real services.
**Where**: `services/proc.in`, `services/mem.in`, `services/time.in`, `services/rand.in`

### Service: proc.in

```in
// Process lifecycle service
// Runs in its own domain, accepts channel requests

fn proc_main() -> void {
  let ch = channel_accept_bootstrap()
  while true {
    let (req, cap) = chan_recv_cross(ch)
    match req.op {
      "spawn" => proc_spawn(req.binary_id, req.caps)
      "exit"  => proc_exit(req.code)
      "wait"  => proc_wait(req.pid)
      "signal" => proc_signal(req.pid, req.sig)
    }
  }
}
```

### Service: mem.in

```in
// Memory management service
// Manages virtual memory within a realm

fn mem_map(domain: Int, virt: Int, size: Int, flags: Int) -> Int
fn mem_unmap(domain: Int, virt: Int, size: Int) -> void
fn mem_brk(domain: Int, new_brk: Int) -> Int
fn mem_shm_create(domain_a: Int, domain_b: Int, size: Int) -> Int
```

### Service: time.in

```in
// Clock and timer service

fn time_now() -> Int     // nanosecond timestamp
fn time_sleep(us: Int) -> void  // yield for microseconds
fn time_timer_create(interval_us: Int) -> Int  // periodic timer handle
```

### Service: rand.in

```in
// Entropy service
// Capability-gated — components without the capability get zeroes

fn rand_bytes(buf: Int, len: Int) -> void
fn rand_u64() -> Int
```

### Files
- `services/proc.in`
- `services/mem.in`
- `services/time.in`
- `services/rand.in`
- `services/manifest.in` — component declarations for each service

---

## Phase 3: Component Loader / SCI Runtime

**What**: Load an SCI into a new domain, validate its manifest, start it.
**Why**: Every .in component needs this to run as an isolated microservice.
**Where**: `kernel/loader.in`

### Loader Flow

```in
fn sci_load(sci_addr: Int, domain: Int) -> Int
  // Parse SCI header
  // Validate capability manifest against grant policy
  // Map code and data sections into domain
  // Set up initial stack
  // Register channels from import table
  // Return component handle (for supervisor tracking)
```

### What The Loader Validates

Before mapping a single page, the loader checks:

- SCI magic and version
- Target architecture matches boot target
- Every required capability has a grant
- Every imported service has a provider channel
- Code section does not exceed size limit
- Checkpoint policy is compatible with domain
- Determinism flags are compatible with realm

### Files
- `kernel/loader.in`
- `kernel/sci-parser.in` — SCI header and section parsing
- `tests/test-loader.in` — load a minimal component

---

## Phase 4: Filesystem (fs.in)

**What**: Directory tree, file I/O, mounts — as a .in microservice.
**Why**: Microservices and guests need to read/write data.
**Where**: `services/fs.in`

### Channel Protocol

```in
// Request types
const FS_OPEN = 1
const FS_READ = 2
const FS_WRITE = 3
const FS_CLOSE = 4
const FS_STAT = 5
const FS_READDIR = 6
const FS_MKDIR = 7
const FS_MOUNT = 8

// Response
struct FSResponse {
  status: Int     // 0 = OK, negative = errno
  data: Int       // depends on operation
  cap: Int        // capability for opened file (if applicable)
}
```

### Backend

Early fs.in uses a simple in-memory object-graph-backed filesystem.
Later it gains block-device mounts through filesystem driver components
(ext4.in, tmpfs.in, devfs.in).

### Files
- `services/fs.in`
- `services/fs-ram.in` — in-memory root filesystem
- `services/fs-dev.in` — device node resolution
- `tests/test-fs.in` — file I/O verification

---

## Phase 5: Networking (net.in)

**What**: Sockets, DNS, TLS — as a .in microservice.
**Why**: Microservices need to communicate with the outside world.
**Where**: `services/net.in`

### Channel Protocol

```in
// Request types
const NET_SOCKET = 1
const NET_BIND = 2
const NET_CONNECT = 3
const NET_LISTEN = 4
const NET_ACCEPT = 5
const NET_SEND = 6
const NET_RECV = 7
const NET_GETADDRINFO = 8

// Socket types
const SOCK_STREAM = 1
const SOCK_DGRAM = 2
```

### Dependencies

- NIC driver (`kernel/net.in` contains the current e1000 path)
- TCP/IP stack (could be a separate .in component: tcpip.in)
- DNS resolver (dns.in)
- TLS handshake (tls.in)

### Files
- `services/net.in`
- `services/tcpip.in`
- `services/dns.in`
- `services/tls.in`
- `kernel/net.in` — current e1000 path; split to a driver domain when domains enforce isolation

---

## Phase 6: Graphics (gfx.in)

**What**: Compositor, surfaces, input routing — as a .in microservice.
**Why**: Native graphics for components and compatibility personalities.
**Where**: `services/gfx.in`

### Pipeline

```
Component
  │  channel: "create_surface 800x600"
  │           "blit x=10 y=20 pixels=..."
  ▼
gfx.in (compositor)
  │  framebuffer blit or virtio-gpu command
  ▼
Hardware (framebuffer / GPU)
```

### Surfaces

- Each surface is a VM object shared between the component and gfx.in
- Components blit by writing to the VM object and sending a damage notification
- gfx.in composites damaged regions and presents to hardware
- Input events flow from gfx.in to the focused component via channel

### Files
- `services/gfx.in`
- `services/gfx-compositor.in`
- `services/gfx-input.in`
- `drivers/framebuffer.in`
- `tests/test-gfx.in`

---

## Phase 7: Compatibility Personalities

**What**: Run Linux, Darwin, and Windows binaries as guest components.
**Why**: The whole point of the microservice architecture.
**Where**: `services/loader.in`, `services/linux-compat.in`,
           `services/darwin-compat.in`, `services/win-compat.in`

### Loader.in (Binary Parser)

```in
fn elf_load(domain: Int, elf_addr: Int) -> Int
  // Parse ELF headers
  // Map LOAD segments into domain
  // Set up TLS, stack, auxiliary vector
  // Return entry point

fn macho_load(domain: Int, macho_addr: Int) -> Int
  // Parse Mach-O headers (FAT + thin)
  // Map segments
  // Set up dyld stub

fn pe_load(domain: Int, pe_addr: Int) -> Int
  // Parse PE headers
  // Map sections
  // Resolve IAT stubs
```

### Linux Compat Service

- Maintains per-guest fd table (maps fd → fs.in channel)
- Translates POSIX calls into channel messages
- Manages signal delivery
- Handles clone/thread creation within guest domain

### Darwin Compat Service

- Maintains Mach port name space
- Translates mach_msg → channel operations
- Manages dyld loading
- Routes IOKit to device capabilities

### Windows Compat Service

- Maintains NT handle table
- Translates NT syscalls → capabilities
- Presents registry view over object graph
- Routes Win32 calls to gfx.in + input channels

### Files
- `services/loader.in`
- `services/linux-compat.in`
- `services/linux-shim.in` — guest libc replacement
- `services/darwin-compat.in`
- `services/darwin-shim.in`
- `services/win-compat.in`
- `services/win-shim.in`

---

## Phase 8: Distribution

**What**: Remote components, replicated objects, component migration.
**Why**: Distributed-first model.
**Where**: `services/dist.in`, `services/objstore.in`

### Remote Components

- Components declare distribution eligibility
- Runtime can instantiate a component on a remote node
- Channel endpoints transparently bridge across the network
- Capabilities are attenuated for remote access

### Replicated Objects

- Object graph regions can be replicated
- Conflict resolution policies (last-writer-wins, CRDT, custom)
- Consistency models (eventual, strong, causal)

### Migration

- Checkpoint component state
- Transfer checkpoint + SCI to remote node
- Resume execution on remote node
- Update routing tables for open channels

### Files
- `services/dist.in`
- `services/objstore.in`
- `services/dist-channel.in` — network channel bridge
- `services/dist-migrate.in` — migration coordinator

---

## Phase Dependency Table

| Phase | Depends On | Effort | Verification |
|-------|-----------|--------|-------------|
| 0: Domains | — | 2-3 weeks | Create domain, write/read isolation test |
| 1: Cross-domain channels | Phase 0 | 1-2 weeks | Two domains communicate over shared page |
| 2: Core microservices | Phase 0, 1 | 1-2 weeks | proc.in spawns a thread in new domain |
| 3: SCI loader | Phase 0, 1 | 2-3 weeks | Load minimal component, verify cap grant |
| 4: fs.in | Phase 2, 3 | 2-3 weeks | Guest reads a file over channel |
| 5: net.in | Phase 2, 3 | 3-4 weeks | Guest sends UDP packet over channel |
| 6: gfx.in | Phase 2, 3 | 3-4 weeks | Surface created, pixel blitted, displayed |
| 7: Compat | Phase 3, 4, 5, 6 | 3-6 months per personality | Run a real binary (busybox, basic CLI) |
| 8: Distribution | Phase 0-7 | Ongoing | Two QEMU instances communicate |

---

## Current Status

### Running Today
- Nanokernel boots x86_64 long mode under QEMU
- Serial console, physical memory discovery, page tables
- Object graph arena, capability table, bootstrap realm
- Cooperative + preemptive multitasking
- Typed channels for inter-component IPC
- SCI loader with capability validation
- Interactive shell (16 commands)
- e1000 NIC driver (UDP transmit, ARP)
- Deterministic execution subsystem

### Next Blockers (Phase 0)
1. `domain_create()` — allocate new PML4, copy kernel mappings
2. `domain_switch()` — CR3 switch with TLB management
3. `domain_map()` — install mapping in a domain's page table
4. Shared page protocol for cross-domain channels
5. Test isolation (write to one domain, read from another)

### Repository Layout

```
/Users/undivisible/projects/space/
  kernel/
    kernel-root.in        nanokernel (1506 lines, 90 declarations)
    domain.in             Phase 0 - multiple memory domains
    channel.in            Phase 1 - cross-domain channels
    loader.in             Phase 3 - SCI loader
  services/
    proc.in               Phase 2 - process lifecycle
    time.in               Phase 2 - clock and timer
    fs.in                 Phase 4 - filesystem
    net.in                Phase 5 - networking
    gfx.in                Phase 6 - graphics
  boot/
    multiboot.asm         x86_64 CPU bring-up
  scripts/
    check-qemu-boot.sh    Full boot verification
    check-sci-contract.sh Metadata validation
  sci-schema.md           SCI format specification
  bootstrap-plan.md       Original bootstrap plan
  compatibility-personalities.md   Microservice compat model
```
