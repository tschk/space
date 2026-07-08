# Portability Plan: x86_64 + aarch64

## Goal

Boot the Space kernel on both x86_64 (QEMU + KVM/TCG) and aarch64 (QEMU + HVF,
native Apple Silicon) from a single `.in` source tree.

## Status

- Inauguration emits working aarch64 code (ELF relocatable `.o`, `static-lib`)
- x86_64 native lowering is complete (boot image, serial, timer, interrupts, PCI)
- aarch64 lowering lacks platform builtins (`outb`/`inb` aliases for MMIO,
  `mrs`/`msr` for system registers, GIC interrupt controller)

## Work Plan

### Phase 1: Abstract hardware access (platform HAL)

Introduce a thin platform HAL that each arch implements.  The kernel calls
`hal_putchar()`, `hal_get_tick()`, `hal_eoi()`, `hal_pci_read()` instead of
raw `outb`/`inb`.

Files to create:
```
kernel/hal_x86_64.in     — x86_64 port I/O, PIC, PIT
kernel/hal_aarch64.in    — aarch64 MMIO (PL011 UART), GIC, ARM Generic Timer
kernel/hal.in            — dispatcher (selects hal_* based on arch)
```

**x86_64 HAL:** Mostly just renames — `outb(0x3F8, ch)` becomes
`hal_putchar(ch)` → `outb(COM1, ch)`.

**aarch64 HAL:** Needs new builtins in Inauguration:
- `load64(addr)` / `store64(addr, val)` for MMIO (already exist)
- `mrs(sysreg)` / `msr(sysreg, val)` for system register access
- GIC memory-mapped register access

No MMIO port I/O on aarch64.  Serial is PL011 at fixed address on QEMU virt
(`0x9000000`).  Timer is `CNTPCT_EL0` via `mrs`.  Interrupts are GICv2/v3.

### Phase 2: Platform init (trampoline)

**x86_64:** Existing `boot/multiboot.asm` (32-bit → long mode, page tables, GDT).
QEMU multiboot loads at `0x100000`.

**aarch64:** Minimal entry in assembly.  QEMU `-kernel` loads ELF at the default
entry point in EL3/EL2.  We need:
- Drop to EL1
- Set up exception vectors
- Set up stack
- Call `kernel_entry`

Use QEMU virt machine with `-M virt` (PL011 at `0x9000000`, GIC at `0x8000000`,
flash at `0x0`).

New file:
```
boot/aarch64_entry.S    — aarch64 bring-up
```

### Phase 3: `0o755` fix

The .in parser doesn't support octal literals.  Change `0o755` → `493` and
`0o644` → `420` in `kernel/fs2_file.in`.  This is a trivial one-line fix but
blocks aarch64 compilation.

### Phase 4: Conditional compilation

The kernel needs a way to select platform code at compile time.  Options:
- **Separate kernel-root files:** `kernel-root-x86_64.in` and
  `kernel-root-aarch64.in` that import the right HAL.
- **Compile-time flag:** Have the build pass a `--target` flag or let the .in
  source detect the target triple (not supported yet).

Recommendation: separate root files with shared code in platform-neutral `.in`
files (scheduler, domain, filesystem, process, channels are already
arch-neutral).

### Phase 5: QEMU boot scripts

```sh
# x86_64
qemu-system-x86_64 -kernel build/kernel.bin -m 256M -nographic \
  -device isa-debug-exit,iobase=0xf4 -accel kvm

# aarch64 (on Apple Silicon)
qemu-system-aarch64 -M virt -cpu max -m 256M -nographic \
  -kernel build/kernel-aarch64.bin -accel hvf
```

### Phase 6: Benchmark

Compile kernel-root-aarch64.in, boot in `qemu-system-aarch64 -M virt -accel hvf`,
measure boot-to-shell via serial polling (same method as `bench-boot.sh`).

Expected aarch64 boot-to-shell: ~100-300ms (HVF acceleration + virt machine has
faster firmware/init).

## Files changed

```
kernel/fs2_file.in           — 0o755 → 493 (blocking)
kernel/hal.in                — NEW: platform dispatch
kernel/hal_x86_64.in         — NEW: x86_64 port I/O + PIC + PIT
kernel/hal_aarch64.in        — NEW: aarch64 MMIO + GIC + timer
boot/aarch64_entry.S         — NEW: aarch64 trampoline
boot/multiboot.asm           — unchanged
kernel/kernel-root.in        — use hal instead of raw outb/inb
kernel/interrupts.in         — move PIC/PIT code to hal_x86_64
kernel/serial.in             — move COM1 code to hal_x86_64
scripts/bench-boot.sh        — add aarch64 variant
scripts/boot.sh              — add --aarch64 flag
```

## Non-goals

- Full aarch64 PCI support (QEMU virt has ECAM, but no port I/O)
- NVMe on aarch64 (not in QEMU virt default config)
- USB on aarch64 (not needed for boot)
- Framebuffer/display (VGA is x86-only; QEMU virt uses virtio-gpu)
