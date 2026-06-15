// Space nanokernel entry point for x86_64
// Boot protocol: Limine
// Calls into .in-compiled kernel_entry after minimal setup

.section .text

.global _start
.type _start, @function

_start:
    // The Limine boot protocol provides:
    //   rdi = pointer to boot info structure
    //   rsi = pointer to Limine boot info
    // We need to:
    //   1. Set up a stack
    //   2. Zero BSS
    //   3. Call kernel_entry

    // Set up stack pointer (grows downward, 16-byte aligned)
    lea rsp, [rip + _stack_top]
    and rsp, ~0xF

    // Zero BSS
    lea rdi, [rip + _bss_start]
    lea rcx, [rip + _bss_end]
    sub rcx, rdi
    xor al, al
    cld
    rep stosb

    // Save Limine boot info pointer
    mov r12, rsi

    // Call kernel_entry defined in .in
    // Pass boot info pointer as argument
    mov rdi, r12
    call kernel_entry

    // If kernel_entry returns, halt
    cli
.halt:
    hlt
    jmp .halt

.section .bss

.align 16
_stack_bottom:
    .skip 16384
_stack_top:

_bss_start:
    .skip 0
_bss_end:
