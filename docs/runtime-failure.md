# Runtime failure and synchronous user entry

Space keeps activation policy in `.in`. The bootstrap assembly supplies the CPU
continuations that ordinary calls cannot express. An emitted compiler `abort`
import now resolves to `components/runtime-failure.in`; it cannot return a dummy
success to the failed language expression.

## Trusted synchronous components

`runapp` currently invokes SCI runtime components at CPL0 in identity-map clone
domains. `runtime-invoke-entry` opens one synchronous continuation for the current
domain. `abort` abandons component frames and returns status 134 to that loader
continuation. The loader revokes the activation capability, clears its executable
entry, records the failure and publishes neither its exports nor resumable
activation metadata. The shell remains available. Nested continuations return
-16. An unscoped abort halts, and a CPL0 CPU exception remains fatal.

This boundary supports language allocation failure; it provides neither hardware
isolation for `runapp` nor rollback of a component's earlier writes. Clone-domain
page tables, component records and backing allocations remain retained. Reclaiming
those resources requires explicit clone and backing-frame ownership. Clone
creation now copies mutable leaf tables, repairing the earlier shared page-table
pointer problem. A complete destructor still needs the payload/heap/shared-page
backing ledger, removal of kernel aliases, capability-slot reuse and component
record cleanup; freeing page tables alone does not complete activation teardown.
This limitation also applies to successful legacy activations.

## CPL3 faults and strict entry

The registered exception handlers cover vectors 0, 3, 6, 13, 14, 16 and 19.
They receive the CPU-saved CS. Only a fault from CPL3 with an
active synchronous user continuation returns to its caller. The outcome is
`128 + vector`: invalid opcode gives 134, general protection 141 and page fault
142; integer divide gives 128, breakpoint 131, x87 144 and SIMD 147. A kernel
fault cannot borrow the user recovery path. INT3 has a DPL3 gate and its CPU-saved
RIP advances past the instruction. Other exception vectors are not yet covered
by this recovery contract.

Legacy `domain-enter-user` retains its historical IOPL3 behavior. New prepared
user entry uses IOPL0 with IF clear. The TSS I/O permission map starts beyond the
TSS limit, denying user IN/OUT. Callers own image and stack mappings and the
context descriptor. Parent loaders must revoke their own capabilities, destroy
the user page-table tree and release their backing-frame ledger after return.

The CPU bridge initializes x87/SSE2 state, starts RDX at zero, saves the kernel
FPU state for the synchronous activation and restores it on return. This supports
one synchronous process; it does not establish FPU ownership across preemptive
multitasking. Syscall and fault policy runs with the saved kernel FPU state,
so guest rounding modes or pending floating-point exceptions cannot alter it.
CR0.NE selects native x87 exception delivery. The low entry publications are internal kernel interfaces:

| Address | Value |
| --- | --- |
| `0x4150` | Scoped trusted `runtime_invoke(entry, argument)` |
| `0x4158` | Nonreturning scoped `runtime_abort(status)` |
| `0x4160` | Strict user entry, descriptor `{rip, arg, rsp, cr3}` |
| `0x4168` | Address of the synchronous user-syscall continuation flag |
| `0x4170` | Hardware `runtime_random64(kernel_output_pointer)` |
| `0x4178`, `0x4180`, `0x4188` | Breakpoint, x87 and SIMD exception capsules |
| `0x4190`, `0x4198`, `0x41a0` | Interruptible user entry, read RFLAGS, user timer dispatch |

The entropy capsule checks CPUID.RDRAND, retries at most 16 times, and writes
one 64-bit sample only on success. Outcomes are 0 (success), -38 (unsupported)
and -11 (hardware not ready). There is no fallback seed. Personality startup
must refuse an entropy-dependent process if the hardware cannot provide it.

## Resumable syscalls

Actual user SYSCALL captures user RSP before switching to TSS RSP0 and builds the
same frame as INT80. Both enter the `.in` dispatcher with kernel CR3. A scoped
`domain-user-syscall-hook(frame) -> Int` supplies personality policy: return 1 to
resume the same user frame or 0 to terminate the activation. The handler writes
the result to frame RAX. Without a hook, the existing native first-syscall exit
behavior remains. Unsupported hook actions terminate with -1.

The bridge preserves general registers, user stack/red zone and x87/SSE state
across resumable dispatch, then restores guest CR3 and IRETs. SYSCALL's architectural
RCX/R11 clobbers still apply. A personality may update saved RFLAGS to express
its error convention. Relevant offsets from the frame base:

| Field | Offset |
| --- | ---: |
| R10, R9, R8 | 40, 48, 56 |
| RDI, RSI, RDX | 72, 80, 88 |
| RAX | 112 |
| RIP, CS, RFLAGS | 120, 128, 136 |
| User RSP, SS | 144, 152 |

The hook is a kernel-owned synchronous binding, not an application-granted raw
callback. Personality loaders must install and restore it around their own guest
entry and validate translated user buffers through that guest's mappings.

## Executable checks

Use an explicitly selected source-built compiler and retain the output directory:

```sh
python3 scripts/check-runtime-failure.py --in /path/to/in --out /tmp/failure-check
python3 scripts/check-user-syscall.py --in /path/to/in --out /tmp/syscall-check
python3 scripts/check-user-syscall.py --in /path/to/in --out /tmp/syscall-max --cpu max
```

The failure gate forces the compiler's array-allocation failure path, checks two
nonreturning aborts and calculator recovery, injects real CPL3 UD2/page faults and
checks exact outcomes plus calculator recovery, then verifies a CPL0 UD2 remains
fatal. The syscall gate executes real CPL3 SYSCALL and INT80, checks resume/exit,
argument and result offsets, RDX initialization, preserved GP/SSE/stack state and
carry-flag edits, and confirms the interactive shell survives. It also verifies
RDRAND output on `max` and unchanged output with explicit -38 on `qemu64`.

Fresh QEMU evidence on 2026-10-24: failure gate 5/5 at
`/tmp/space-runtime-failure-syscall/report.json`; syscall bridge gate at
`/tmp/space-user-syscall-random-qemu64/report.json` and
`/tmp/space-user-syscall-random-max/report.json`; nine existing trusted Linux, Darwin
and Windows serial/file/stream syscall fixtures at
`/tmp/space-foreign-syscalls-bridge/`. The actual native checksum app and other
shipped application workflows are separately exercised by
`scripts/check-native-applications.py`; the controlled failure fixture is not a
substitute for those applications.

### Arithmetic exception verification limit

`scripts/check-user-arithmetic.py` defaults to all four independent instruction
triggers: integer DIV by zero, INT3, unmasked x87 divide by zero followed by
FWAIT, and unmasked SSE DIVSS by zero. It retains CPU interrupt traces and a
failure report. `--vector 0`, `--vector 3`, `--vector 16` or `--vector 19` selects
an explicit single-vector check; each runs eight activations and requires its
exact vector outcome and a surviving shell.

Local QEMU 10.0.13 TCG does not deliver the SIMD exception: DIVSS sets MXCSR's
zero-divide flag with its mask cleared (`0x1d84`) and CR4.OSXMMEXCPT set
(`CR4=0x620`), then continues to the deliberately forbidden UD2. The strict SIMD
assertion remains failing; the installed vector-19 capsule has not been proven
by an actual hardware SIMD exception here. `/dev/kvm` is unavailable. A native
host control with the same instruction sequence does receive SIGFPE; that is an
instruction-fixture control, not evidence of Space's handler. Upstream QEMU's
[SSE DIV helper](https://github.com/qemu/qemu/blob/v10.0.0/target/i386/ops_sse.h)
and [MXCSR helper](https://github.com/qemu/qemu/blob/v10.0.0/target/i386/tcg/fpu_helper.c)
update software floating-point flags without raising this mask-based exception.
General preemptive FPU scheduling remains outside this synchronous contract.

Fresh selected arithmetic gates each passed eight real CPL3 executions with an
exact outcome and surviving shell: `/tmp/space-user-arithmetic-divide-final/`,
`/tmp/space-user-arithmetic-breakpoint-final/` and
`/tmp/space-user-arithmetic-x87-final/`. The SIMD gate remains separately
recorded at `/tmp/space-user-arithmetic-simd-final/`. The resumed syscall gate
also checks user x87 stack, MXCSR rounding mode and direction flag preservation
at `/tmp/space-user-syscall-kernelfpu-final/report.json`.

The opt-in [synchronous CPL3 execution budget](user-budget.md) adds IOPL0/IF1
entry and real IRQ0 cancellation. The existing strict IOPL0/IF0 interface retains
its semantics. Budget expiry is status 124 and restores the caller's scoped
configuration before personality cleanup.

### Kernel timer call boundary

The ordinary CPL0 IRQ0 wrapper now reserves aligned native parameter scratch,
keeps original CR3/frame metadata on its own stack, saves/restores x87/SSE state
and clears DF before `.in` dispatch. The interrupted flags return through IRET.
This does not change the separate trusted preemptive scheduler's FPU contract.

`scripts/check-kernel-irq.py` executes a trusted assembly control in CPL0, takes
at least three real PIT interrupts per activation and checks both interrupted
stack alignments. Its callback deliberately uses the native 64-byte parameter
home area and clobbers caller-saved XMM/x87 state. Sixteen workloads verify GP,
x87, SSE, MXCSR, original DF and stack state survive, while callback entry has
DF clear and the required alignment. The original timer wrapper fails this
control; its retained trampoline can be supplied with `--trampoline` to rerun
the negative case. Separate baseline evidence also demonstrates FPU corruption
and DF leakage without the parameter-home stress adapter.

Fresh kernel timer controls: `/tmp/space-kernel-irq-home-fixed/report.json` passes
16 workloads and at least 48 actual IRQs; the retained old-trampoline control at
`/tmp/space-kernel-irq-home-baseline/report.json` fails with R11 overwritten by
parameter-home writes and DF leaked into policy. The independent baseline without
home-area writes is at `/tmp/space-kernel-irq-baseline/`. Latest assembly also
passes 26 budgeted activations, native applications 11/11, runtime failure 5/5 and
strict resumable syscall/FPU checks at the corresponding
`/tmp/space-user-budget-kernelirq-regression/`, `/tmp/space-native-apps-irq-final/`,
`/tmp/space-runtime-failure-irq-final/` and `/tmp/space-user-syscall-irq-final/`
reports.
