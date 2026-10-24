# Fixture boot layout repair

The expanded151-gate integration at `/workspace/lab151/report.json`, source
`34239e7`, finishes136 passed/15 failed, with source/compiler/application integrity
passed. It preserves failures from old injected-fixture reservations. The kernel
grew past the old1.5MiB reservation; for example the protected Windows probe's
kernel has1,613,208 bytes and ends at physical `0x289d98`, overlapping the old
`0x280000` fixture slot. The guard correctly stopped execution. This is not a
successful application/guest run and the original receipt is not rewritten.

The fixtures now occupy explicit free slots below the unchanged `0x300000`
kernel heap. `scripts/boot_fixture_layout.py` checks page alignment, the whole
kernel extent, nonempty payload, and fixture/heap separation before constructing
an output. It preserves all input bytes. Existing individual payload-size limits
remain. No image, import, memory, IRQ, lifetime or performance limit is raised.

| Fixture cohort | Physical staging |
|---|---|
| Single PE, legacy hand-authored foreign image, input or surface SCI | `0x2f0000` |
| Raw CPU/context fixture | `0x2e0000`; a separate private SCI stays at `0x2f0000` |
| Input plus two small SCI clients | `0x2d0000`, `0x2e0000`, `0x2f0000`, existing64KiB slot limits |
| Input plus calculator/editor SCI applications | `0x2b0000` input64KiB; `0x2c0000` and `0x2e0000` retain128KiB application slots |

The native shell's legacy fixture entrypoints and the hand-authored ELF/Mach-O/
PE headers move together. Kernel IRQ helper origins and physical callback offsets
move together. Protected guest virtual addresses stay unchanged. No acquired
original application bytes, preferred bases, ELF/Mach-O/PE rules or32-import
execution bound were altered. These physical addresses are test-image placement,
not a new foreign ABI or component transport.

Twelve host packing controls check exact input/padding/payload preservation and
refusal for overlap, heap overflow, empty payload and invalid/unaligned addresses.
The same oversized kernel must still fail at the old slot and succeed only when
the fixture moves to a safe slot. Focused QEMU repeats pass protected Windows
process/environment behavior, native IRQ preservation, actual CPU context
suspend/resume, legacy native GUI input/content/close checks and all trusted
foreign output/file/stream fixtures. The first context repeat caught two old
physical FPU-helper offsets and remains preserved separately from its passing
corrected repeat.

The complete matrix must be rerun from a new frozen source; focused repairs do
not turn the earlier151-gate failure into a passing run. Adding the shared layout
gate makes the next cached-artifact matrix152 gates. This does not complete the
[full application/desktop goal](../compatibility-coverage-goal.md).

One additional failure was the lifecycle probe image exceeding the unchanged
2MiB image allowance by13,168 bytes after appending nine private fixtures. That
instrumented test now explicitly packages its CLI/library/demo cohort (all kinds
5..19) plus all private cases. The unused GUI cohort (kinds20..22) stays in the
ordinary image and dedicated GUI gates. No CLI scenario, repeated cycle, abort,
capacity or resource assertion is removed: the focused repeat passes all81
scenarios, including70 repeated calc/checksum cycles. Its receipt records both
the original standard image hash and the explicitly retained/excluded kinds.
