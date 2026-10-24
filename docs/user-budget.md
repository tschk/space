# Synchronous CPL3 execution budget

The next bounded runtime slice gives a caller-owned CPL3 activation a budget of
PIT timer interrupts. A separate IOPL0/IF1 CPU entry makes a noncooperating loop
interruptible; existing strict IOPL0/IF0 entry remains available. This is scoped
activation cancellation, not a scheduler, wall-clock syscall timeout or a
termination mechanism for trusted CPL0 components.

The domain wrapper validates and prepares the same caller-owned mappings and
context as strict entry, saves caller interrupt flags, PIC mask, syscall hook
and capability, then installs a scoped tick budget. It preserves the existing
PIT divisor. A CPU-confirmed CPL3 IRQ0 path saves GP and floating-point state,
switches to kernel CR3 and invokes `.in` policy. Policy acknowledges the timer
and consumes one budget unit; exhaustion returns status 124 through the user
continuation. Normal completion, faults and deadline expiry restore the scoped
configuration before returning. Interrupts that arrived in kernel code continue
through the kernel timer path.

Acceptance requires actual CPL3 infinite-loop cancellation, a finite workload,
exact IF1/IOPL0 observations, real IRQ delivery with user GP/x87/SSE/MXCSR state
preserved, repeated domain teardown and a surviving shell/other activation.
Existing strict entry, syscall, failure, native application and protected guest
gates remain required. Preemptive FPU scheduling is outside this contract.

Implemented API:

```text
domain-enter-user-budgeted(entry, argument, domain, user_stack, context, budget_ticks) -> Int
```

The first five parameters match `domain-enter-user-prepared`. The shared helper
validates executable code, NX writable stack, domain state and kernel CR3 before
entry. Budget counts must be 1 through 10000; invalid input returns -1 and a
nested budget returns -16. Status 124 means the activation exhausted its budget;
normal and exception statuses otherwise retain their existing meanings. A
100-tick budget is about one second at the current 100 Hz PIT configuration.
Time spent inside interrupt-disabled kernel syscall policy does not consume
user IRQ ticks, so this does not bound a blocking or defective kernel service.

The wrapper performs no heap allocation. It temporarily unmasks PIC IRQ0,
restores the caller's original mask and IF state, and refuses activation while
the trusted preemptive scheduler is active. It preserves the caller's syscall
hook and capability. The personality still owns FS-base restoration and backing
frame/page-table teardown after every result, including deadline expiry.

Internal CPU publications: `0x4190` interruptible IOPL0/IF1 entry,
`0x4198` read-RFLAGS capsule, and `0x41a0` the `.in` user timer dispatcher.
The CPU first verifies saved CS is CPL3; all other IRQs retain the kernel path.
The interruptible raw entry alone installs no deadline; callers use the scoped
`.in` API to obtain cancellation policy.

Fresh QEMU evidence: `/tmp/space-user-budget-restore-final/report.json` passes
26 activations: eight infinite loops cancelled after ten real timer IRQs,
eight finite workloads that observe three IRQs while preserving GP/x87/SSE and
MXCSR state, eight UD2 terminations, one initially masked IRQ0 case and one IF0
caller case. Repeated entries allocate no additional heap after initial mapping
warmup. The fixture checks actual user IF1/IOPL0, exact result statuses, restored
PIC/hook/capability/IF state and a surviving interactive shell. Existing strict
syscall/FPU checks, runtime failure 5/5 and legacy user SCI hello/echo also pass
with this path installed.

```sh
python3 scripts/check-user-budget.py --in /path/to/in --out /tmp/user-budget
```
