# Space Kernel In `.in` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `.in` the whole Space kernel implementation language, with only the irreducible CPU reset/boot shim outside `.in`.

**Architecture:** Space owns the OS contracts, examples, SCI profile, and boot plan. Inauguration owns generic compiler capabilities such as freestanding x86_64 output, SCI-like metadata emission, object/schema/capability extraction, and native lowering; those capabilities must not be Space-branded inside Inauguration.

**Tech Stack:** `.in`, Inauguration CLI/Rust compiler implementation, x86_64 freestanding objects, QEMU, Limine or UEFI boot substrate, SCI metadata.

---

## File Ownership

Space repo:

- `AGENTS.md`: repository workflow and boundaries.
- `bootstrap-plan.md`: this implementation plan.
- `sci-schema.md`: Space SCI profile.
- `examples/kernel-root.in`: target kernel-root component contract.
- `examples/bootstrap-supervisor.in`: target supervisor component contract.
- future `kernel/`: Space nanokernel `.in` sources.
- future `boot/`: boot-image config, linker scripts, and QEMU harness.

Inauguration repo:

- `in-cli/src/native_emit/`: generic code emitters and freestanding object writers.
- `in-cli/src/owned_compile.rs`: generic owned compile routing.
- `in-cli/src/in_lang_parse.rs`: generic `.in` syntax support.
- `in-cli/src/core_ir.rs`: generic IR model.
- `in-cli/src/boundary_emit.rs` and `in-cli/src/boundary_ir.rs`: generic ABI/capability/object metadata.
- `scripts/check-target-matrix.sh`: generic target checks.
- future generic script names such as `scripts/check-freestanding-x86_64.sh`.

## Compiler Targets

Space needs two target identities:

- `x86_64-unknown-none`: generic freestanding compiler target implemented in Inauguration.
- Space SCI profile: defined in this repo and consumed by Space tooling.

Do not add `x86_64-space` as an Inauguration target. The compiler should stay generic; Space can map its native profile to generic freestanding compiler outputs and Space-owned SCI metadata.

## Task 1: Keep Space Examples Parse-Visible

**Files:**
- Modify: `examples/kernel-root.in`
- Modify: `examples/bootstrap-supervisor.in`
- Modify in Inauguration later: `in-cli/src/in_lang_parse.rs`
- Test in Inauguration later: parser tests for component declarations

- [x] Step 1: Record unsupported syntax intentionally

Run from Space:

```bash
../inauguration/target/release/in compile --path examples/kernel-root.in --target bytecode --json
```

Expected today: failure with a parser diagnostic, because `component`, `capability`, and `interface` are not implemented syntax yet.

- [x] Step 2: Add generic parser support in Inauguration

Implement generic `.in` component declarations, capability declarations, imports, exports, and interface declarations in `../inauguration/in-cli/src/in_lang_parse.rs`.

The parser output should preserve:

- component name
- target string
- deterministic policy
- checkpoint policy
- import declarations
- export declarations
- capability declarations
- interface method signatures

- [x] Step 3: Add Inauguration parser tests

Run from `../inauguration`:

```bash
cargo test -q in_lang_parse::tests::parse_component_declaration --manifest-path in-cli/Cargo.toml
cargo test -q in_lang_parse::tests::parse_capability_declaration --manifest-path in-cli/Cargo.toml
```

Expected after implementation: both pass.

- [x] Step 4: Re-run Space examples

Run from Space:

```bash
../inauguration/target/release/in compile --path examples/kernel-root.in --target bytecode --json
../inauguration/target/release/in compile --path examples/bootstrap-supervisor.in --target bytecode --json
```

Expected after implementation: successful parse/metadata extraction or an explicit unsupported-lowering diagnostic. A silent host-native fallback is failure.

## Task 2: Add Generic Component Metadata Output In Inauguration

**Files:**
- Modify in Inauguration: `in-cli/src/boundary_ir.rs`
- Modify in Inauguration: `in-cli/src/boundary_emit.rs`
- Modify in Inauguration: `in-cli/src/owned_compile.rs`
- Create in Inauguration: `scripts/check-component-metadata.sh`
- Modify in Space: `sci-schema.md`

- [x] Step 1: Define generic metadata fields in Inauguration

Add generic component metadata structs for:

- component identity
- target
- imports
- exports
- required capabilities
- exported capabilities
- object schemas
- checkpoint policy
- deterministic policy

- [x] Step 2: Emit JSON metadata sidecar

Add a generic compile option or report field that writes component metadata beside existing artifacts. Use generic names such as `component-metadata`, not `space`.

- [x] Step 3: Add Inauguration check script

Create `../inauguration/scripts/check-component-metadata.sh` that compiles a generic `.in` component sample and validates JSON keys.

Run:

```bash
bash scripts/check-component-metadata.sh
```

Expected: metadata contains component identity, capabilities, imports, exports, and target.

- [x] Step 4: Sync Space SCI profile

Update `sci-schema.md` only after the generic metadata shape exists. Space may add stricter loader rules here without requiring Inauguration to know the Space product name.

## Task 3: Add Generic `x86_64-unknown-none` Freestanding Object Output

**Files:**
- Modify in Inauguration: `in-cli/src/native_emit/elf.rs`
- Modify in Inauguration: `in-cli/src/native_emit/object.rs`
- Modify in Inauguration: `in-cli/src/owned_compile.rs`
- Modify in Inauguration: `in-cli/src/native_emit/target.rs`
- Create in Inauguration: `scripts/check-freestanding-x86_64.sh`

- [x] Step 1: Add failing dispatch test

Add a test in `native_emit::object` requiring:

- target triple `x86_64-unknown-none`
- linkage `static-lib`
- artifact kind `elf-relocatable-object`
- runtime level `freestanding-none`
- no Linux syscall bytes

Run:

```bash
cargo test -q native_emit::object::tests::dispatches_x86_64_unknown_none_object --manifest-path in-cli/Cargo.toml
```

Expected before implementation: fail because dispatch is unsupported.

- [x] Step 2: Implement minimal freestanding object dispatch

Route `x86_64-unknown-none` to the existing x86_64 ELF relocatable writer, but report it as freestanding and keep Linux executable support separate.

- [x] Step 3: Add script gate

Create `scripts/check-freestanding-x86_64.sh` that compiles:

```in
fn kernel_entry() -> Int { return 42; }
```

Expected checks:

- ELF magic
- `ET_REL`
- `EM_X86_64`
- exported `kernel_entry`
- no Linux `syscall` instruction requirement

- [x] Step 4: Run gates

Run from Inauguration:

```bash
cargo test -q native_emit::object --manifest-path in-cli/Cargo.toml
bash scripts/check-freestanding-x86_64.sh
bash scripts/check-target-matrix.sh
```

Expected: all pass.

## Task 4: Add Real x86_64 Lowering Slice

**Files:**
- Create in Inauguration: `in-cli/src/native_emit/x86_64.rs`
- Create in Inauguration: `in-cli/src/native_emit/x86_64_lower.rs`
- Modify in Inauguration: `in-cli/src/native_emit/mod.rs`
- Modify in Inauguration: `in-cli/src/native_emit/object.rs`
- Modify in Inauguration: `in-cli/src/owned_compile.rs`

- [x] Step 1: Add instruction encoding tests

Add tests for:

- `ret`
- `push rbp`
- `mov rbp, rsp`
- `sub rsp, imm32`
- `mov rax, imm64`
- `call rel32`
- `add rax, rbx`

Run:

```bash
cargo test -q native_emit::x86_64 --manifest-path in-cli/Cargo.toml
```

Expected before implementation: fail because module does not exist.

- [x] Step 2: Implement instruction encoder

Implement the minimal x86_64 encoder needed for scalar functions.

- [x] Step 3: Add Core IR lowering tests

Support:

- scalar return literal
- scalar params
- local bindings
- direct call
- integer add/sub/mul

Run:

```bash
cargo test -q native_emit::x86_64_lower --manifest-path in-cli/Cargo.toml
```

Expected after implementation: tests pass and unsupported constructs fail closed.

- [x] Step 4: Route freestanding object through real lowering

For `x86_64-unknown-none` static-lib, lower eligible Core IR functions into `.text` rather than const-eval-only stubs.

Run:

```bash
bash scripts/check-freestanding-x86_64.sh
```

Expected: object contains function code for at least one non-const direct call sample.

## Task 5: Add QEMU Boot Harness In Space

**Files:**
- Create in Space: `boot/limine.conf`
- Create in Space: `boot/linker.ld`
- Create in Space: `boot/x86_64-entry.S`
- Create in Space: `scripts/check-qemu-boot.sh`
- Create in Space: `kernel/kernel-root.in`

- [x] Step 1: Choose boot substrate

Use the existing Multiboot1 trampoline. The assembly shim sets long mode state and enters `.in`-compiled `kernel_entry`.

- [x] Step 2: Add QEMU script

Create `scripts/check-qemu-boot.sh` that:

- builds the `.in` freestanding object through Inauguration
- links with `boot/x86_64-entry.S`
- creates a bootable image
- runs QEMU x86_64
- checks serial output for `space: kernel root entered`

- [x] Step 3: Run boot check

Run from Space:

```bash
bash scripts/check-qemu-boot.sh
```

Expected after implementation: QEMU exits after printing the serial marker.

## Task 6: Add SCI Sidecar And Loader Contract

**Files:**
- Modify in Space: `sci-schema.md`
- Create in Space: `scripts/check-sci-contract.sh`
- Modify in Inauguration: generic component metadata emitter from Task 2

- [x] Step 1: Generate generic metadata from Inauguration

Run from Space:

```bash
../inauguration/target/release/in compile --path kernel/kernel-root.in --target native --target-triple x86_64-unknown-none --linkage static-lib --entry kernel_entry --json
```

Expected: object artifact plus generic component metadata sidecar.

- [x] Step 2: Validate Space SCI profile

Create a Space script that validates the generic metadata against `sci-schema.md` rules.

Run:

```bash
bash scripts/check-sci-contract.sh
```

Expected: required capabilities, imports, exports, target, and provenance are present.

## What Is Left

Compiler work left in Inauguration:

- multi-function object relocations beyond the currently verified lowering subset
- deeper service/component entry validation for all non-root Space modules

Space work left here:

- CR3-backed domain isolation beyond the current verified domain metadata and tests
- cross-domain channels between isolated address spaces
- promote proc/time/fs/net/gfx services from compiled contracts to isolated loaded components
- implement nanokernel object/capability table vocabulary
- load one `.in` supervisor component from SCI metadata into its own domain

## Phase After First Boot: Nanokernel In `.in`

Deliverables:

- serial console
- physical memory map parser
- page table setup declarations
- IDT declarations
- trap entry ABI
- root capability table
- bootstrap realm creation

Exit criteria:

- `.in` owns the nanokernel control flow after the assembly boot shim
- QEMU boot creates a root capability table and bootstrap realm

## Phase D: SCI Loader

Deliverables:

- SCI parser
- capability manifest verifier
- component code section mapper
- realm/protection-domain creation
- component entry call

Exit criteria:

- boot image loads one `.in` SCI supervisor and starts it
- undeclared capability access is rejected before execution

## Non-Goals For The First Boot

- Linux compatibility
- filesystems
- users/groups
- dynamic linking
- GPU scheduling
- distributed runtime
- broad `.in` standard library

Those come after the native component model boots.
