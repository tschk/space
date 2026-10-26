# Protected guest initial register state

Strict and interruptible CPL3 entries clear general registers except the explicit
RDI argument and architectural stack/instruction state. They clear all16 XMM
registers, overwrite all8 physical x87 register values with zero, then reset x87
control/status/tags and MXCSR. FNINIT alone is insufficient because FXSAVE can
still disclose the underlying x87 bytes. Kernel callee-saved general registers
and the complete saved FXSAVE state are restored on normal exit, CPU fault and
IRQ-budget cancellation. Legacy IOPL3 SCI entry keeps its prior contract.

FS and GS remain personality-owned state. This change does not establish their
save/reset contract or concurrent floating-point scheduling.

`scripts/check-user-initial-state.py` seeds kernel x87, every XMM register,
MXCSR and callee-saved general registers with actual instruction sequences. A
separate U=1 guest page observes its initial registers and FXSAVE image. The
kernel capsule compares all512 FXSAVE bytes after return. Four repetitions each
exercise normal strict exit, strict UD2 recovery, interruptible finite work and
actual IRQ0 infinite-loop cancellation, followed by shell availability.

`/tmp/space-user-initial-state-final/report.json` passes16 activations. The
retained pre-change trampoline fails the same test with guest result777 at
`/tmp/space-user-initial-state-old-control/`. Independent `--probe x87` and
`--probe xmm` controls also fail at
`/tmp/space-user-initial-state-old-x87/` and
`/tmp/space-user-initial-state-old-xmm/`; they skip unrelated observations so the
floating-point checks cannot be masked by the earlier general-register failure.
The current trampoline ends at0xE36 before its0xF00 boot-table slot and remains
4096bytes. Register confidentiality is one part of the protected process
boundary; these results do not establish protection for trusted CPL0 SCI apps.
