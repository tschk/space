# Space OS Design Notes

## Reasoning Path

Space is a true new 64-bit x86_64-first operating system design. It uses `.in` as the native systems and orchestration language through the Inauguration compiler toolchain. Soliloquy and RV8 are references for the browser-facing shell and web/runtime surface, not the kernel substrate.

The design should not assume POSIX, ELF, fork, Unix files, or a traditional userspace/kernel split. Compatibility with Linux, Darwin/XNU, and Windows applications should be implemented as sandboxed personalities on top of native primitives, not as the core contract.

CS: 8/10.

## Non-Negotiable Direction

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
- Integrated AI/runtime orchestration.

## Working Philosophy

Space is closest to a nanokernel, but the center of the system is the `.in` language and compiler rather than a traditional kernel API.

The core foundation should be as small as possible. It exists to get onto bare metal, establish memory safety boundaries, enforce capabilities, schedule execution, and bootstrap the compiler/runtime environment. Everything above that foundation is a separate isolated service. Each service receives only the capabilities it needs, and all authority is explicit.

The goal is not to stack many compatibility or abstraction layers on top of hardware. The goal is to make the compiler, runtime, and capability model the operating system contract. The kernel substrate should expose the minimum hardware-enforced primitives needed for `.in` to express and enforce:

- component boundaries
- authority transfer
- object identity
- scheduling intent
- persistence
- checkpointing
- distributed placement
- deterministic execution
- compatibility containment

This means native Space software should not think in terms of Unix processes, files, users, or inherited descriptors. It should think in terms of compiled components, persistent objects, capability handles, execution graphs, and isolated services.

## Kernel Substrate Options

### Option 1: Capability Microkernel

A capability microkernel keeps the privileged kernel small. The kernel owns CPU scheduling, address spaces, interrupt routing, memory objects, capability tables, channels, timers, and checkpoint hooks. Drivers, object storage, network stacks, GPU services, compatibility layers, and AI/runtime orchestration run as sandboxed components.

Native system calls would operate on typed object handles. There would be no ambient path lookup, global process table, Unix user IDs, inherited file descriptors, or process cloning. Authority is passed by explicit capability transfer.

The core kernel object set would likely include:

- `Task`
- `Thread`
- `AddressSpace`
- `CapabilityTable`
- `Channel`
- `VmObject`
- `Interrupt`
- `Timer`
- `Snapshot`
- `Component`
- `ComputeQueue`

This fits the strongest version of the design. It gives clear isolation, zero-copy IPC through shared VM objects, and a natural place to implement compatibility personalities as isolated services.

The main downside is complexity at the system boundary. A microkernel is only elegant if the service contracts are strong. If the driver model, memory object model, and component lifecycle model are vague, the design turns into a pile of privileged servers with hidden ambient trust.

This is a strong candidate for Space, but it should be paired with a higher-level runtime supervisor so the system does not feel like raw kernel handles everywhere.

### Option 2: Exokernel / Library OS

An exokernel exposes protected hardware resources directly through capabilities and leaves abstractions to library operating systems. Instead of one kernel-defined process/file/socket model, different personalities can define their own runtime contracts.

In this model:

- Native `.in` components use Space object graphs and capability channels.
- Linux compatibility runs as a Linux personality library/runtime.
- Darwin compatibility runs as a Mach/BSD/Cocoa personality.
- Windows compatibility runs as an NT object-manager personality.

This is the most radical and wheel-reinventing option. It makes compatibility layers first-class without letting any one legacy OS define the native platform.

The downside is that it can fragment the platform. If every personality owns too much policy, the native system loses coherence. Debugging can also become difficult because failures happen in the boundary between kernel resource protection, library OS policy, and component runtime behavior.

This option is attractive for research, but risky for a first bootable system.

### Option 3: Nanokernel Plus Managed Runtime

A nanokernel does even less than a microkernel. It provides isolation, CPU entry, memory mapping, interrupts, timers, and low-level capability enforcement. Most OS policy moves into a managed runtime written in `.in`.

The `.in` runtime becomes the real operating system brain:

- component graph supervisor
- persistent object graph manager
- scheduler policy engine
- distributed execution coordinator
- AI orchestration service
- compatibility personality loader
- deterministic execution controller
- snapshot/checkpoint coordinator

This fits the language-aware goal best. The kernel is not where most semantics live. The kernel only enforces the substrate that the `.in` runtime cannot safely enforce itself.

The hard part is bootstrapping. The runtime becomes critical very early. A broken runtime can break the entire system even when the nanokernel is correct. The design therefore needs a tiny rescue path and a deterministic bootstrap image format.

This is likely the best long-term identity for Space if the `.in` language is central.

### Option 4: Monolithic Capability Kernel

A monolithic capability kernel puts drivers, scheduler, object store, network, GPU services, and compatibility code into one kernel image, but still uses internal capability APIs rather than Unix-like global authority.

This is the fastest path to visible progress. Early boot, framebuffer, keyboard, memory allocation, object storage, and a browser shell can be wired without designing a full service graph first.

The downside is architectural drift. It violates the spirit of sandboxed components if treated as the final design. Once drivers and compatibility layers live in-kernel, extracting them later is expensive.

This option is useful only as a temporary bring-up substrate. If used, the rule should be: internal interfaces must already look like the future component contracts.

### Option 5: Single Address Space Runtime Kernel

A single address space operating system maps all components into one global virtual address space. Isolation is enforced by capabilities, language/runtime safety, memory permissions, and typed object access rather than by giving each process an unrelated address space.

This is different from a traditional monolithic kernel. Components can still be sandboxed. The sandbox boundary is capability and object access, not necessarily page-table separation for every component.

Potential benefits:

- Very fast IPC because pointers, object references, and shared buffers can remain meaningful across components.
- Persistent object graphs become easier because object identity can be stable across runtime boundaries.
- Snapshotting and checkpointing can operate over object reachability instead of file/process reconstruction.
- The `.in` runtime can reason about live objects, capabilities, and execution graphs directly.
- GPU and heterogeneous compute queues can share buffers with fewer translation layers.

Major risks:

- A memory safety bug can become catastrophic unless unsafe/native code is tightly confined.
- Revocation is harder because many components may hold references into shared object spaces.
- Compatibility layers for Linux, Darwin, and Windows expect process-local address-space semantics.
- Garbage collection, object pinning, and persistent references become core OS problems.
- Hardware isolation still matters for hostile or legacy code.

A practical version would not be a fully shared raw address space for everything. It would be a hybrid:

- One global object identity space.
- Per-component capability views.
- Per-component memory protection domains for unsafe code.
- Shared immutable and copy-on-write object regions.
- Zero-copy transfer through typed shared memory objects.
- Language-managed components can share more aggressively.
- Legacy compatibility personalities run in stricter isolated address spaces.

This makes the single-address-space idea compatible with sandboxing. Space can expose a single persistent object graph while still using hardware page tables where needed.

## Recommended Direction

The best substrate is a nanokernel plus capability microkernel hybrid with a single-address-space-inspired object runtime.

The kernel should provide:

- CPU bootstrap and x86_64 long mode.
- Physical and virtual memory management.
- Capability tables.
- Typed kernel objects.
- Threads and scheduling.
- Interrupt routing.
- Timers.
- Channels.
- VM objects.
- Snapshot and checkpoint hooks.
- Minimal debug console.
- Component bootstrap.

The `.in` runtime should provide:

- component lifecycle
- object graph storage
- package/build verification
- policy evaluation
- compatibility personality management
- distributed execution
- AI/runtime orchestration
- high-level scheduling policy
- deterministic replay mode

The memory model should provide:

- hardware-isolated domains for unsafe or legacy code
- shared object regions for native safe `.in` components
- stable object IDs instead of pathnames as the main reference model
- typed capabilities for object access
- revocation and lease tracking
- snapshot roots and checkpoint epochs

This avoids becoming just another Unix kernel, but it also avoids betting everything on a pure single-address-space system before the safety model is mature.

## Compatibility Personalities

Compatibility should not be the native contract.

Linux support should run as a Linux personality that translates syscalls into Space objects, channels, sockets, and object-graph storage. It should start with a narrow syscall set for statically linked command-line programs before attempting graphical applications.

Darwin/XNU support should be shaped more like Darling: Mach ports, launch services, dyld behavior, frameworks, and app bundles are translated into Space services. It should not require importing XNU code.

Windows support should be shaped more like ReactOS/Wine at the boundary: NT objects, handles, registry, Win32, and PE loading are personality services. The native kernel should not become NT.

All personalities should be sandboxed components with explicit capabilities. They should not receive global authority just because legacy software expects it.

## Open Decisions

- Native executable/package format to replace ELF.
- Whether `.in` compiles kernel components directly at v0 or first generates Rust/C-compatible low-level artifacts.
- Whether the first graphics path is framebuffer, virtio-gpu, or a minimal software compositor.
- Whether the first object store is in-memory only, append-log-backed, or built over a block device from day one.
- How much of the single-address-space model is safe to expose before the `.in` runtime is mature.
- Whether deterministic execution is default or an opt-in mode for replay/build/test.
- How AI orchestration is represented without giving it ambient authority.

## Native Vocabulary

Space should avoid Unix names when the model is not Unix. Naming should teach the architecture.

Preferred native terms:

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
- syscall as the main abstraction
- root
- global namespace

Compatibility personalities may expose those legacy terms internally, but the native kernel/runtime should not be designed around them.

## Proposed System Stack

The intended stack is:

```text
hardware
nanokernel enforcement substrate
Space loader
minimal supervisor
.in runtime
native service graph
browser/runtime shell
compatibility personalities
distributed execution fabric
AI/runtime orchestration
```

The kernel should remain small enough that most of the OS can be updated, restarted, snapshotted, and verified as components. The compiler should know about the component graph before boot, and the runtime should enforce the graph during boot.

## Boot Flow

The first boot path should be x86_64 in QEMU.

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
supervisor component load
object graph root load
first service graph activation
shell component activation
```

The boot image should contain:

- nanokernel binary
- bootstrap supervisor
- initial object graph
- component manifests
- capability manifests
- debug symbols or deterministic symbol map
- build provenance

The boot image should be deterministic. Given the same source, compiler, inputs, and config, it should produce byte-identical output or at least a verifiable reproducibility record.

## Native Artifact Format

Space should not use ELF as the native executable contract. ELF can still be supported inside Linux compatibility.

The native artifact should be a Space component image. Tentative name: `SCI`, for Space Component Image.

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

The loader should reject artifacts that ask for undeclared authority. The runtime should be able to answer: what can this component do, what can it access, what can it call, what can call it, and what happens if it faults?

Early versions may wrap a simpler machine-code blob, but the metadata contract should be designed first so the temporary encoding does not become the real ABI by accident.

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
- request AI agent action

There should be no ambient authority. A component should not be able to discover global services unless its manifest receives a discovery capability.

## Component Model

A component is the native replacement for an app, service, process, daemon, driver, library, and agent tool.

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

Space should treat persistent object graphs as the native storage model.

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

The object graph replaces files for native components. A compatibility personality may present objects as files, registry keys, bundles, plist data, or other legacy forms.

Early implementation path:

1. in-memory object graph
2. append-only object log
3. checkpointed object graph image
4. block-device-backed object store
5. replicated/distributed object graph

## Snapshot And Checkpoint Model

Snapshots are not backups. They are OS primitives.

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

Not every component is snapshot-safe. Device drivers, network endpoints, GPU queues, and AI agent sessions may need custom checkpoint adapters or may be marked non-checkpointable.

## Scheduling Model

Space should have two scheduling layers.

The nanokernel schedules CPU time and enforces hard isolation.

The `.in` runtime schedules semantic work:

- component priorities
- graph waves
- deterministic replay regions
- AI orchestration jobs
- distributed placement
- GPU/CPU work partitioning
- compatibility personality throttling
- latency-sensitive UI work

The compiler should emit scheduling hints, but the runtime owns final policy. The nanokernel should expose enough hooks for the runtime to express policy without moving all policy into privileged code.

## GPU And Heterogeneous Compute

GPU scheduling should be a native resource model, not a driver afterthought.

The kernel should expose only protected queue, memory, and interrupt primitives where possible. The GPU service should own:

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

Early graphics should likely start with framebuffer or virtio-gpu, then move to a native compositor service.

## Distributed-First Model

Distributed-first does not mean every component is remote. It means the native model does not assume the machine boundary is the trust or execution boundary.

The same component graph should be able to represent:

- local component call
- cross-realm call
- cross-device call
- replicated object update
- migrated compute job
- remote AI agent operation

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

## AI Runtime Orchestration

AI orchestration should be native but not ambiently trusted.

An AI agent is a component or service with capabilities. It can only inspect objects, edit code, invoke tools, or control devices if those capabilities were granted.

AI orchestration should integrate with:

- build graph
- component graph
- object graph
- test graph
- deployment graph
- runtime telemetry
- policy engine

Agent actions should be auditable and replayable where practical. The system should be able to distinguish human actions, compiler actions, runtime actions, and AI agent actions.

## Compatibility Personality Plan

Compatibility support is important, but it should arrive after the native substrate is coherent.

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

Linux personality maps Linux expectations onto Space capabilities. It must not add a global Unix namespace to the native OS.

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

## Inauguration Requirements

Inauguration must mature enough to support Space.

Required compiler/language capabilities:

- stable `.in` syntax for components
- Core IR support for component declarations
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
- error reporting good enough for OS work
- cross-component call model
- restricted unsafe/native escape hatch
- test runner support for `.in` components

Required runtime/compiler outputs:

- component image metadata
- capability manifest
- object schema manifest
- scheduling hints
- checkpoint policy
- deterministic execution flags
- import/export table
- debug map
- provenance map

Space can start before all of this exists, but the first Space implementation should avoid creating a permanent parallel language/runtime that bypasses `.in`.

## First Implementation Roadmap

### Phase 0: Planning Repository

Deliverables:

- this design document
- glossary
- native model diagrams
- boot artifact sketch
- `.in` component examples
- kernel object list
- compatibility non-goals

### Phase 1: Inauguration Readiness

Deliverables in `../inauguration`:

- minimal `.in` component syntax
- capability declaration syntax
- manifest emitter
- deterministic formatting/checking path
- x86_64 freestanding artifact story, even if initially stubbed
- sample Space component in repo root or examples

### Phase 2: Nanokernel Skeleton

Deliverables in Space:

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
- RV8/Soliloquy-inspired browser shell model
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

### Phase 10: Distributed And AI Orchestration

Deliverables:

- remote component graph model
- remote capability attenuation
- AI agent component contract
- audited tool invocation
- build/runtime orchestration integration

## Things Not To Do Early

- Do not build a POSIX clone first.
- Do not make ELF the native artifact format.
- Do not implement `fork()`.
- Do not start with Linux app compatibility before native components exist.
- Do not put the whole OS in a monolithic kernel permanently.
- Do not give AI orchestration broad ambient authority.
- Do not make the object store look like files internally.
- Do not make the browser shell define the kernel architecture.
- Do not import incompatible licensed code into the substrate.

## Immediate Next Work

1. Create and publish the private Space planning repo.
2. Inspect Inauguration's current `.in` syntax, Core IR, native backend, and manifest capabilities.
3. Add a root-level Space-oriented `.in` example or design stub in Inauguration if it matches current syntax.
4. Identify the smallest Inauguration compiler improvement that moves toward component manifests.
5. Keep Space native terms consistent before writing kernel code.

## Current Inauguration Readiness Snapshot

Checked after creating this planning repo.

What exists now:

- `.in` supports imports, capabilities, extern bindings with required capabilities, structs, functions, bounded bodies, annotations, distributed function facts, and parallel regions.
- `in agent` emits machine-readable imports, effects, capabilities, Core IR summaries, call edges, orchestration facts, diagnostics, and timing.
- `in build --parser in` can parse and lower `.in` into the current Core IR/textual SIL path.
- Package reporting already has package capabilities and capability policy validation.
- Native backend work exists, but the public CLI still reports native backend status rather than a complete native object backend.

Space-oriented work landed in Inauguration:

- Root `space.in` declares a first Space boot contract using today's `.in` grammar.
- It declares Space capabilities for boot, capability tables, component loading, object graph access, and snapshots.
- It declares extern Space service bindings for capability grant, component load, object-root creation, and realm checkpointing.
- It verifies through `in build --parser in --path space.in --module-id Space`.
- It reports cleanly through `in agent --parser in --path space.in --module-id Space`.
- It was committed to Inauguration branch `self-hosted-compiler` as `05519e8`.

What is still missing for Space:

- First-class `.in` component declarations rather than modeling components as functions plus capabilities.
- Component image manifest emission.
- Native Space Component Image metadata format.
- Capability type checking beyond string policy facts.
- Capability attenuation, delegation, leases, and revocation semantics.
- Object schema declarations in `.in`.
- Realm declarations in `.in`.
- Checkpoint policy declarations in `.in`.
- Deterministic execution declarations in `.in`.
- Freestanding x86_64 code generation suitable for a nanokernel or early runtime.
- A no-host runtime mode for `.in`.
- A stable ABI/interface model for Space service calls.
- A boot-image emitter or manifest that Space can load directly.

Smallest next compiler improvement:

Add a `component` surface to `.in` that can be parsed into agent/graph/package facts before it lowers to executable code. The first version can be metadata-only and should report:

- component name
- required capabilities
- exported service names
- checkpoint policy
- deterministic policy
- entry function

That keeps the next step aligned with Space without prematurely committing to native codegen or a final image format.
