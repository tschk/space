# Owned synchronous user contexts

`components/user-context.in` adds a supervisor-owned CPU context for strict CPL3
execution. A syscall hook may return action 2 to suspend its current process.
The CPU captures the post-policy register frame and guest FPU state before
abandoning the TSS stack, then restores the kernel and returns to the supervisor.
Action 1 continues the current user activation; action 0 exits it. No guest syscall
number or Linux process policy is encoded in the CPU mechanism.

The caller supplies at least 768 bytes aligned to 16 bytes and retains ownership
of that buffer and the domain for its entire lifetime. This is an internal
supervisor contract, not a guest-visible handle or a domain generation token.
`user-context-init(context, bytes, domain, entry, arg, stack)` constructs fresh
zeroed registers and FPU data, x87 control 0x37f, MXCSR 0x1f80, user CS/SS and
IF1/IOPL0 flags. `user-context-set-tls(context, fs, gs)` admits zero or mapped
user addresses. `user-context-resume(context, budget)` runs one bounded activation
and returns a typed stop. `user-context-clone(target, bytes, source, domain)`
copies a suspended context into an independently owned user domain and sets child
RAX to zero. The caller separately copies memory and duplicates capability/FD
ownership, and writes the parent's actual child identifier into its return slot.

| Offset | Contents |
| --- | --- |
| 0–112 | r15,r14,r13,r12,r11,r10,r9,r8,rbp,rdi,rsi,rdx,rcx,rbx,rax |
| 120,128,136,144,152 | RIP, CS, RFLAGS, RSP, SS |
| 160–671 | 512-byte FXSAVE64 image |
| 672,680 | FS base, GS base |
| 688,696,704 | Stop kind, fault vector, error code |
| 712,720,728 | Owned domain, stop status, lifecycle phase |
| 736 | Internal format magic |
| 744–759 | Private CPU entry descriptor |
| 760 | Remaining delivered guest IRQ0 ticks after the last admitted run |

`user-context-remaining(context)` exposes the remaining guest IRQ quantum after
a stop; clone copies it, and admission failure preserves it. A resumed process
may pass the remaining value into its next activation. This counts delivered
guest IRQ0 ticks, excluding kernel service time; scheduling policy must separately
bound repeated transitions and cannot call this a wall-clock deadline.

Stop kinds are 1 Exit, 2 Fault, 3 Deadline and 4 Suspend. Status records the exit
return value, actual `128 + vector` fault result, 124 deadline result or suspended
RAX. Only fresh phase 1 and suspended phase 2 resume. Exit/fault/deadline phase 3
is terminal. Kernel callers can inspect the explicit frame; untrusted SCI imports
cannot resolve the `user-context-*` helper prefix.

Resume validates exact user segment selectors, canonical mapped executable RIP,
canonical mapped writable/NX RSP, bounded RFLAGS including architectural RF and excluding IOPL/TF/NT/AC, mapped
FS/GS and supported MXCSR bits before restoring the CPU. It scopes the existing
IRQ0 budget, PIC mask, current capability, logical domain and syscall hook. The
caller FS/GS and observer publication restore on return. Assembly saves the
kernel FX state in supervisor-only low hardware memory 0x4200–0x43ff, accessed
only with kernel CR3. Long-mode boot initializes this area with FXSAVE before
any .in entry, and validation restricts its hardware MXCSR mask to architectural
low 16 bits (using the architectural fallback when zero). Guest contexts remain
caller-owned memory. Both kernel
and guest GP/FX images survive ordinary syscall continuation. Fault entry now
saves GP/FX before touching registers or discarding guest floating-point faults.

`/tmp/space-user-context-rf/report.json` passes 62 actual CPL3 executions:
a cold check immediately after domain-init and before any user entry, rejecting
reserved MXCSR without executing FXRSTOR; ten real syscall suspensions,
independent child/parent continuations (the child overwrites RBX/XMM15/x87
before exit and the parent verifies its original state), genuine
#UD and #PF with error 5, real IRQ-driven infinite-loop deadlines and a caller
with IF0/IRQ0 masked. A finite guest observes three actual timer ticks before
suspending; the remaining quantum decreases accordingly and deadline reports zero. The guest verifies fresh zero GP/XMM/x87 data before writing canaries. The fixture checks actual register and guest FX snapshots,
byte-exact 512-byte kernel FX restoration, FS/GS, CR3, capability, PIC, IF, hook,
observer and stable allocation high water. Malformed selectors, flags, MXCSR,
noncanonical/unmapped RIP/RSP and kernel TLS refuse before CPU restore. An actual structurally valid SCI importing `user-context-resume` is refused by
the real registry before lifecycle allocation or entry; its public serial import
resolves. The shell survives. Existing syscall, budget and strict entry confidentiality gates pass.

Run `scripts/check-user-context.py --in /path/to/in --out /new/output` to repeat.
This is synchronous cooperative suspension plus scoped cancellation. It does not
add a general scheduler, address-space cloning, descriptor duplication, CPL0
preemption or a complete native process model. Linux child scheduling and native
component execution ownership remain separate policy layers.

A preserved Windows callback failure captured legitimate RF in RFLAGS `0x10283`
at `/tmp/space-windows-local-context-refusal2/5/contexts.json`. The earlier
validator rejected RF, preventing a suspended context from being reused. The
mask now admits RF, and twenty actual child/parent IRET continuations restore
that flag while TF/IOPL/NT/AC negative controls still refuse. The flag may clear
after executing the resumed instruction according to the CPU architecture.
