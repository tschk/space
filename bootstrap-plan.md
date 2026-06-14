# Space Bootstrap Plan

## Goal

Make `.in` the whole Space kernel implementation language by moving the kernel from contract-first `.in` components to freestanding `.in` machine code in small bootable slices.

## Compiler Targets

Space needs two target identities:

- `x86_64-space`: native Space component target, freestanding, SCI-first
- `x86_64-unknown-none`: lower-level freestanding object target used while SCI and boot-image tooling mature

`x86_64-space` must not mean Linux, POSIX, ELF-as-contract, or host syscalls. Early compiler artifacts may contain ELF sections while the loader and boot image are being built, but SCI is the native contract.

## Phase A: Contract-First Components

Deliverables:

- proposed `.in` kernel root component
- proposed `.in` bootstrap supervisor component
- SCI v0 metadata schema
- capability and object vocabulary in examples
- compiler target identity in `inauguration`

Exit criteria:

- Space examples compile far enough to produce parse/manifest diagnostics, or fail with explicit unsupported syntax diagnostics
- `in backend --target native --target-triple x86_64-space --json` reports contract-only, not host fallback

## Phase B: Freestanding Codegen Slice

Deliverables:

- x86_64 freestanding object for a scalar `_space_start`
- no libc, no Linux syscall, no dynamic loader
- explicit stack and calling convention contract
- linker script or boot image section map
- QEMU test harness that reaches the entry and writes serial output

Exit criteria:

- QEMU x86_64 boots and prints a line produced by `.in`-compiled code
- unsupported `.in` features fail closed

## Phase C: Nanokernel In `.in`

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
