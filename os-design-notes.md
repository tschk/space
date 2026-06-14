# Space OS Design Notes

## Direction

Space is a true new 64-bit x86_64-first operating system centered on `.in` as the native systems and orchestration language.

Space is not a POSIX clone, not an ELF-first system, and not a Unix-like kernel with a different shell. The native model is:

```text
component + capability + object + execution graph
```

The traditional model is explicitly not the native contract:

```text
process + file + syscall + user
```

Compatibility with Linux, Darwin/XNU, and Windows applications should exist as sandboxed personalities on top of Space primitives. Those personalities may expose legacy concepts internally, but they must not define the native OS.

## Non-Negotiables

- 64-bit only.
- x86_64 first.
- No POSIX as the native contract.
- No ELF as the native executable/package contract.
- No `fork()` as a process primitive.
- No traditional userspace/kernel split as the main programming model.
- Capability security everywhere.
- Sandboxed components only.
- Language-aware runtime.
- Distributed-first architecture.
- GPU and heterogeneous compute scheduling.
- Persistent object graphs instead of files as the primary storage model.
- Snapshotting and checkpointing as primitives.
- Deterministic builds and deterministic execution modes.
- Zero-copy IPC.
- Integrated runtime orchestration.

## Chosen Architecture

Space uses a nanokernel plus capability microkernel hybrid with a single-object-space runtime.

The nanokernel is the smallest hardware enforcement layer that makes `.in` capability semantics real on bare metal. It should not contain filesystems, Unix processes, users, package managers, desktop sessions, browser tabs, or compatibility policy.

The kernel substrate owns only what must be hardware-enforced:

- CPU bootstrap and x86_64 long mode.
- Physical memory discovery.
- Virtual memory and page table control.
- Interrupt and exception routing.
- Timers.
- CPU scheduling hooks.
- Typed kernel object IDs.
- Capability tables.
- Memory protection domains.
- Channels.
- VM objects.
- Minimal debug console.
- Fault handling.
- Component bootstrap.
- Snapshot/checkpoint hooks.

Everything else is a sandboxed component above the substrate:

- component supervisor
- object graph store
- network service
- input service
- compositor service
- GPU/compute service
- package/build verifier
- compatibility personalities
- distributed execution fabric
- runtime policy engine
- browser/runtime shell

The guiding rule is simple: if a feature can run as an isolated component with explicit capabilities, it should not live in the nanokernel.

## Compiler-As-OS Contract

Space treats the `.in` language and compiler as the native OS contract.

The compiler should output more than machine code. It should produce a component artifact that describes:

- component code
- required capabilities
- exported interfaces
- imported services
- object schemas
- scheduling hints
- determinism constraints
- snapshot policy
- migration policy
- target architecture
- build provenance

The runtime then loads this artifact and the nanokernel enforces it on hardware.

The flow should become:

```text
.in source
compiled component image
verified capability manifest
runtime loader
nanokernel enforcement
isolated component execution
```

This means native Space development should feel like writing declared components and authority graphs, not calling syscalls.

## Single Object Space

Space should not use a raw single address space for every kind of code. That is too dangerous for drivers, legacy compatibility, and unsafe code.

Instead, Space should use one global object identity space with multiple memory protection domains.

The object model:

- Objects have stable IDs.
- Objects have schemas.
- Objects can reference other objects.
- Object access requires capabilities.
- Object mutation is policy-controlled.
- Object graph roots can be snapshotted.
- Object graph regions can be replicated or migrated later.

The memory model:

- Safe native `.in` components can share object regions more aggressively.
- Unsafe components run in stricter memory domains.
- Legacy compatibility personalities get process-like address-space isolation.
- Large data moves through typed VM objects for zero-copy transfer.
- Immutable and copy-on-write regions are preferred for shared state.
- Raw pointers are not the cross-component identity model.

This keeps the benefit of single-address-space systems, especially fast IPC and persistent identity, without trusting every component with every address.

## Native Vocabulary

Space should use names that describe its real model.

Preferred terms:

- `component`: a compiled unit of execution and authority.
- `realm`: an isolation and authority view for one or more components.
- `object`: a persistent typed value with identity.
- `capability`: an unforgeable authority to operate on an object or service.
- `channel`: a typed communication path between components.
- `graph`: a dependency, execution, object, or policy topology.
- `checkpoint`: a consistent capture point for one component, realm, or graph.
- `personality`: a compatibility environment for a legacy platform.
- `image`: a bootable or loadable compiled artifact.

Terms to avoid as native concepts:

- process
- file
- directory
- user
- group
- fork
- executable
- root
- global namespace

## Boot Flow

The first target is x86_64 in QEMU.

Initial boot path:

```text
UEFI or Limine
Space boot image
nanokernel entry
physical memory discovery
page table setup
interrupt setup
timer setup
serial debug console
capability root creation
bootstrap realm creation
minimal supervisor load
object graph root load
first service graph activation
```

The boot image should contain:

- nanokernel binary
- bootstrap supervisor
- initial object graph
- component manifests
- capability manifests
- deterministic symbol map
- build provenance

The boot image should be reproducible. Given the same source, compiler, inputs, and config, the output should be byte-identical or carry a verifiable reproducibility record.

## Native Component Image

Space should not use ELF as its native component contract. ELF can exist inside a Linux personality.

The native artifact should be a Space Component Image. Tentative name: `SCI`.

An SCI should contain:

- code sections
- data sections
- object schema definitions
- capability import list
- capability export list
- service dependency graph
- deterministic build metadata
- target architecture metadata
- memory safety metadata
- snapshot eligibility metadata
- migration eligibility metadata
- GPU/compute requirements
- debug and trace metadata
- compiler version and source hash graph

The loader should reject images that request undeclared authority. The runtime should always be able to answer:

- what can this component do?
- what can it access?
- what can it call?
- what can call it?
- what state does it own?
- what happens if it faults?

Early versions may wrap a simpler machine-code blob, but the metadata contract should be designed first so a temporary encoding does not become the permanent ABI.

## Capability Model

Capabilities are the core security primitive.

Required properties:

- unforgeable
- typed
- delegatable only when policy allows it
- revocable or lease-bound
- attenuable into weaker capabilities
- serializable only through explicit transfer
- inspectable by the runtime for debugging and audit
- invisible to components without authority

Capability examples:

- read object
- mutate object
- call service method
- map VM object
- submit compute queue work
- receive input events
- render to surface
- access network endpoint class
- load compatibility personality
- create checkpoint

There should be no ambient authority. A component should not discover global services unless its manifest receives a discovery capability.

## Component Model

A component is the native replacement for app, service, daemon, driver, library, and runtime module.

A component has:

- compiled code
- declared capabilities
- exported interface
- object state
- scheduling constraints
- isolation requirements
- checkpoint policy
- deterministic execution policy
- dependency list
- fault policy
- update policy

Components communicate through typed channels or object graph transactions. Large data should move through zero-copy VM objects or persistent objects, not byte streams unless the protocol really is a stream.

Components should be restartable where possible. The runtime should know whether restart means:

- restart statelessly
- restart from last checkpoint
- restart from persistent object graph
- restart under degraded capability set
- do not restart automatically

## Object Graph Storage

Persistent object graphs are the native storage model.

An object has:

- stable object ID
- type/schema
- version
- owner realm or authority policy
- references to other objects
- persistence policy
- snapshot policy
- replication policy
- migration policy
- audit metadata

The object graph replaces files for native components. A compatibility personality may present objects as files, registry keys, app bundles, plist data, or other legacy forms.

Early implementation path:

1. in-memory object graph
2. append-only object log
3. checkpointed object graph image
4. block-device-backed object store
5. replicated/distributed object graph

## Snapshot And Checkpoint Model

Snapshots are OS primitives.

Snapshot targets:

- object
- component
- realm
- service graph
- entire boot graph

Checkpoint requirements:

- quiesce or record in-flight messages
- capture capability state
- capture object references
- capture dirty memory or object deltas
- record external nondeterminism
- preserve replay metadata
- define restore authority

Not every component is snapshot-safe. Device drivers, network endpoints, and GPU queues may need custom checkpoint adapters or may be marked non-checkpointable.

## Scheduling Model

Space has two scheduling layers.

The nanokernel schedules CPU time and enforces hard isolation.

The `.in` runtime schedules semantic work:

- component priorities
- graph waves
- deterministic replay regions
- distributed placement
- GPU/CPU work partitioning
- compatibility personality throttling
- latency-sensitive UI work

The compiler may emit scheduling hints, but the runtime owns final policy. The nanokernel should expose enough hooks for policy without moving policy into privileged code.

## GPU And Heterogeneous Compute

GPU scheduling should be a native resource model.

The kernel should expose protected queue, memory, and interrupt primitives where possible.

The GPU service should own:

- command validation
- queue scheduling
- surface ownership
- compute admission
- graphics/compute fairness
- memory residency
- fault recovery

Native components should request compute capabilities, not raw GPU access.

The `.in` compiler should eventually understand:

- GPU-safe kernels
- deterministic compute regions
- data movement costs
- graph batching
- shader/kernel provenance
- fallback CPU execution

Early graphics should start with framebuffer or virtio-gpu, then move to a native compositor service.

## Distributed-First Model

Distributed-first does not mean every component is remote. It means the native model does not assume the machine boundary is the trust or execution boundary.

The same component graph should represent:

- local component call
- cross-realm call
- cross-device call
- replicated object update
- migrated compute job

Distribution must be capability-gated. A component should not become remotely callable merely because networking exists.

Required concepts:

- device identity
- realm trust
- object replication policy
- latency class
- offline behavior
- conflict policy
- remote capability attenuation
- audit trail

## Determinism Model

Space should support deterministic builds by default and deterministic execution where requested.

Deterministic execution needs:

- explicit time source capabilities
- explicit randomness capabilities
- ordered message delivery regions
- recorded external input
- deterministic scheduler mode
- stable object iteration order
- replay log
- compiler-stable codegen

Not all interactive components need deterministic execution all the time. The important design point is that nondeterminism must be visible and capability-mediated.

## Compatibility Personalities

Compatibility support is important, but it must not define the native platform.

### Linux Personality

Start narrow:

- static command-line programs
- basic memory mapping
- basic process-like isolation inside a realm
- read/write/exit/time subset
- object-backed pseudo-files

Then expand:

- dynamic loading
- sockets
- threads
- epoll-like events
- graphics bridge
- package/runtime environments

Linux expectations map onto Space capabilities. The personality must not add a global Unix namespace to the native OS.

### Darwin Personality

Darwin support should be Darling-like in spirit.

Main surfaces:

- Mach ports as Space channels
- launchd-like service graph as Space component graph
- app bundles as object graph packages
- dyld behavior through personality loader
- framework calls through service shims

Do not import XNU. Mirror useful behavior, not code.

### Windows Personality

Windows support should be NT-object-manager-like in spirit, with ReactOS/Wine as conceptual references.

Main surfaces:

- NT handles as Space capabilities
- registry as object graph view
- PE loader inside personality
- Win32 surface mapped to Space UI/compositor services
- named objects mapped to scoped realm objects

The native kernel should not become NT.

## `.in` Language Requirements

The `.in` language must become strong enough to describe native Space components directly.

Required language/compiler capabilities:

- stable component declarations
- capability declaration syntax
- capability type checking
- deterministic AST and formatting
- stable serialization of component metadata
- native code generation path for x86_64
- freestanding/no-host runtime mode
- build graph output
- dependency graph output
- object schema output
- interface/ABI output
- cross-component call model
- restricted unsafe/native escape hatch
- test runner support for native components

Required compiler outputs:

- component image metadata
- capability manifest
- object schema manifest
- scheduling hints
- checkpoint policy
- deterministic execution flags
- import/export table
- debug map
- provenance map

Space can start before all of this exists, but Space-specific source, examples, and manifests should live in the Space repo.

## Implementation Roadmap

### Phase 0: Planning Repository

Deliverables:

- this design document
- glossary
- native model diagrams
- boot artifact sketch
- `.in` component examples
- kernel object list
- compatibility non-goals

### Phase 1: `.in` Component Surface

Deliverables:

- component declaration syntax
- capability metadata
- export/import metadata
- object schema syntax
- checkpoint policy syntax
- deterministic policy syntax
- sample Space components in this repo

### Phase 2: Nanokernel Skeleton

Deliverables:

- x86_64 boot in QEMU
- serial logging
- physical memory map
- page tables
- interrupt descriptor table
- timer
- panic/fault path
- minimal allocator
- kernel object IDs
- capability table skeleton

### Phase 3: Component Loader

Deliverables:

- load one component image
- parse manifest
- create realm
- grant declared capabilities
- start component entry
- fault and restart policy

### Phase 4: Channels And VM Objects

Deliverables:

- typed channel primitive
- message send/receive
- zero-copy VM object creation
- capability transfer
- channel tests in emulator

### Phase 5: Object Graph V0

Deliverables:

- in-memory object graph
- object IDs
- typed object records
- object capabilities
- append-only log prototype
- checkpoint root object

### Phase 6: `.in` Runtime Supervisor

Deliverables:

- supervisor component mostly or entirely in `.in`
- component graph activation
- policy evaluation
- restart handling
- runtime telemetry
- debug inspection

### Phase 7: Shell And UI Surface

Deliverables:

- basic framebuffer or virtio-gpu path
- compositor component
- input component
- browser/runtime shell model
- native object-backed shell state

### Phase 8: Compatibility Experiments

Deliverables:

- Linux personality for tiny static programs
- no dynamic linking at first
- syscall translation through capability services
- object-backed pseudo-file view

### Phase 9: Determinism And Snapshotting

Deliverables:

- component checkpoint
- object graph checkpoint
- replay log
- deterministic scheduler mode
- restore test

### Phase 10: Distributed Runtime

Deliverables:

- remote component graph model
- remote capability attenuation
- replicated object graph path
- migration policy checks

## Things Not To Do Early

- Do not build a POSIX clone first.
- Do not make ELF the native artifact format.
- Do not implement `fork()`.
- Do not start with Linux app compatibility before native components exist.
- Do not put the whole OS in a monolithic kernel permanently.
- Do not make the object store look like files internally.
- Do not make the browser shell define the kernel architecture.
- Do not import incompatible licensed code into the substrate.

## Immediate Next Work

1. Keep all Space-specific source, examples, and planning inside this repo.
2. Add a small `examples/` directory with proposed `.in` component syntax.
3. Define the first `SCI` metadata schema on paper.
4. Define the initial nanokernel object list and capability table layout.
5. Decide the bootloader path for x86_64 QEMU.

Current artifacts:

- `bootstrap-plan.md`
- `sci-schema.md`
- `examples/kernel-root.in`
- `examples/bootstrap-supervisor.in`
