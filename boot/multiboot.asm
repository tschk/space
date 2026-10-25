; Space nanokernel boot trampoline.
;
; This is the irreducible CPU bring-up shim that AGENTS.md permits to live
; outside `.in`: QEMU's multiboot loader hands control to us in 32-bit
; protected mode with paging off, and this code establishes x86_64 long mode
; before calling the `.in`-compiled kernel_entry.
;
; Assembled as a flat binary (`nasm -f bin`) and embedded by the Inauguration
; compiler at the front of the boot image. It is padded to exactly 0x1000 bytes
; so that the first compiled `.in` function (kernel_entry) lands at KCODE_BASE.

BITS 32
org 0x100000
default abs  ; explicit (NASM 2.16+ requires this, default rel not safe in 32-bit)

MB_MAGIC     equ 0x1BADB002
MB_FLAGS     equ 0x00010800          ; AOUT_KLUDGE | BIT11 (VBE info)
MB_CHECKSUM  equ -(MB_MAGIC + MB_FLAGS)

KIMAGE_BASE  equ 0x100000
KCODE_BASE   equ 0x101000            ; KIMAGE_BASE + 0x1000 (TRAMPOLINE_RESERVE)
KERNEL_ENTRY equ 0x101100            ; KCODE_BASE + 0x100 (SCI header size)

; Page-table scratch in low memory (free in QEMU after boot).
PML4 equ 0x1000
PDPT equ 0x2000
PD   equ 0x3000
; Extra page directories for 1-4 GiB identity mapping (framebuffer MMIO).
; Use addresses above 0x10000 to avoid QEMU multiboot info/mmap in low memory.
PD2  equ 0x10000   ; 1-2 GiB
PD3  equ 0x11000   ; 2-3 GiB
PD4  equ 0x12000   ; 3-4 GiB

mb_header:
    dd MB_MAGIC
    dd MB_FLAGS
    dd MB_CHECKSUM
    dd mb_header                     ; header_addr
    dd KIMAGE_BASE                   ; load_addr
    dd 0                             ; load_end_addr (0 => load whole file)
    dd 0                             ; bss_end_addr  (0 => no extra bss)
    dd entry32                       ; entry_addr

entry32:
    cli
    mov esp, 0x90000                 ; temporary stack in low memory
    mov [mb_info], ebx               ; preserve the multiboot info pointer

    ; Zero PML4/PDPT/PD (3 pages at 0x1000..0x4000).
    mov edi, PML4
    mov ecx, 0x3000 / 4
    xor eax, eax
    rep stosd

    ; Zero PD2/PD3/PD4 (3 pages at 0x5000..0x8000).
    mov edi, PD2
    mov ecx, 0x3000 / 4
    xor eax, eax
    rep stosd

    ; PML4[0] -> PDPT, PDPT[0..3] -> PD/PD2/PD3/PD4 (present + writable).
    mov dword [PML4], PDPT | 0x3
    mov dword [PDPT], PD   | 0x3       ; 0-1 GiB
    mov dword [PDPT + 8], PD2 | 0x3    ; 1-2 GiB
    mov dword [PDPT + 16], PD3 | 0x3   ; 2-3 GiB
    mov dword [PDPT + 24], PD4 | 0x3   ; 3-4 GiB

    ; Fill all page directories: identity-map the first 4 GiB with 2 MiB pages.
    mov edi, PD
    mov eax, 0x83                     ; present | writable | page-size(2MiB)
    mov ecx, 512
.fill_pd1:
    mov [edi], eax
    add eax, 0x200000
    add edi, 8
    loop .fill_pd1

    mov edi, PD2
    mov eax, 0x40000083               ; 1 GiB base + flags
    mov ecx, 512
.fill_pd2:
    mov [edi], eax
    add eax, 0x200000
    add edi, 8
    loop .fill_pd2

    mov edi, PD3
    mov eax, 0x80000083               ; 2 GiB base + flags
    mov ecx, 512
.fill_pd3:
    mov [edi], eax
    add eax, 0x200000
    add edi, 8
    loop .fill_pd3

    mov edi, PD4
    mov eax, 0xC0000083               ; 3 GiB base + flags
    mov ecx, 512
.fill_pd4:
    mov [edi], eax
    add eax, 0x200000
    add edi, 8
    loop .fill_pd4

    mov eax, PML4
    mov cr3, eax

    mov eax, cr4
    or eax, (1 << 5) | (1 << 9) | (1 << 10) ; PAE, OSFXSR, OSXMMEXCPT
    mov cr4, eax

    mov ecx, 0xC0000080              ; IA32_EFER
    rdmsr
    or eax, (1 << 8) | 1              ; EFER.LME + SCE (64-bit SYSCALL)
    or eax, 1 << 11
    wrmsr

    mov eax, cr0
    and eax, ~((1 << 2) | (1 << 3))  ; clear EM/TS for baseline x87/SSE
    or eax, 0x80000023              ; PG | NE (native x87 faults) | MP | PE
    mov cr0, eax

    lgdt [gdt_desc]
    jmp 0x08:long_mode               ; far jump into the 64-bit code segment

BITS 64
long_mode:
    cld
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov fs, ax
    mov gs, ax
    mov rsp, 0x90000
    fninit
    ldmxcsr [initial_mxcsr]
    fxsave64 [kernel_fx_state]       ; initialize architectural MXCSR_MASK before .in

    ; Foreign-fixture stubs live at 0x4110+: 0x40E0..0x4108 and 0x4118 are the
    ; native user-mode publications. SYSCALL MSRs (STAR/LSTAR/FMASK) are
    ; programmed in `.in` by cpu-init-syscall-msrs() via Inauguration wrmsr intrinsics.
    mov qword [0x4110], foreign_syscall_entry
    mov qword [0x4120], foreign_run
    mov qword [0x4128], foreign_writefile
    mov qword [0x4130], foreign_exitprocess
    mov qword [0x4138], foreign_createfilea
    mov qword [0x4140], foreign_readfile
    mov qword [0x4148], foreign_closehandle
    mov qword [0x4150], runtime_invoke
    mov qword [0x4158], runtime_abort
    mov qword [0x4160], enter_user_strict
    mov qword [0x4168], user_syscall_continue
    mov qword [0x4170], runtime_random64
    mov qword [0x4178], exc_3
    mov qword [0x4180], exc_16
    mov qword [0x4188], exc_19
    mov qword [0x4190], enter_user_interruptible
    mov qword [0x4198], runtime_rflags
    mov qword [0x41A8], enter_user_context
    mov qword [0x41B8], 0             ; scoped kernel user-context observer
    mov qword [0x41C0], gdt          ; native descriptor relocation inputs
    mov qword [0x41C8], gdt_end - gdt - 1

    ; Publish the ISR stub addresses so the `.in` kernel can install them in
    ; its IDT. The kernel publishes its dispatcher at [0x4000]; the stubs read
    ; it back at interrupt time.
    mov rbx, 0x4008
    mov rax, isr_timer
    mov [rbx], rax
    mov rbx, 0x4010
    mov rax, isr_default
    mov [rbx], rax
    mov rbx, 0x4018
    mov rax, context_switch
    mov [rbx], rax
    mov rbx, 0x4020
    mov rax, isr_timer_preempt
    mov [rbx], rax
    ; Publish exception stub addresses: divide(0), invalid-opcode(6),
    ; general-protection(13), page-fault(14).
    mov rbx, 0x4030
    mov rax, exc_0
    mov [rbx], rax
    mov rbx, 0x4038
    mov rax, exc_6
    mov [rbx], rax
    mov rbx, 0x4040
    mov rax, exc_13
    mov [rbx], rax
    mov rbx, 0x4048
    mov rax, exc_14
    mov [rbx], rax
    mov rbx, 0x4058
    mov rax, cr3_read
    mov [rbx], rax
    mov rbx, 0x4060
    mov rax, cr3_write
    mov [rbx], rax
    mov rbx, 0x4068
    mov rax, isr_syscall
    mov [rbx], rax
    mov rbx, 0x4078
    mov rax, syscall_write_demo
    mov [rbx], rax
    mov rbx, 0x4080
    mov rax, comp_invoke_stub
    mov [rbx], rax
    mov rbx, 0x40D0
    mov rax, [boot_image_table]
    mov [rbx], rax
    mov rbx, 0x40E0
    mov rax, enter_user
    mov [rbx], rax
    mov rbx, 0x40E8
    mov rax, leave_user
    mov [rbx], rax
    mov rbx, 0x40F8
    mov rax, kernel_cr3
    mov [rbx], rax
    mov rbx, 0x4100
    mov rax, tss
    mov [rbx], rax
    mov rbx, 0x4118
    mov rax, guest_active
    mov [rbx], rax

    xor rdi, rdi
    mov edi, [mb_info]               ; arg0 = multiboot info pointer
    mov rax, KERNEL_ENTRY
    call rax

.hang:
    cli
    hlt
    jmp .hang

; --- interrupt service stubs (64-bit) --------------------------------------
; Default gate: ignore and return.
isr_default:
    iretq

; Timer gate (IRQ0 -> vector 32). Saves caller-clobbered registers, calls the
; `.in` dispatcher with aligned parameter scratch and DF clear, then restores
; GP/FPU/CR3/flags state. The separate CPL3 path performs scoped cancellation.
isr_timer:
    cmp qword [rel guest_active], 0
    je .kernel
    test byte [rsp + 8], 3          ; CPU-saved CS, before register changes
    jnz isr_user_timer
.kernel:
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    mov rax, cr3
    mov r11, rsp
    and rsp, -16
    sub rsp, 592                    ; native parameter scratch, metadata, FPU image
    mov [rsp + 64], rax
    mov [rsp + 72], r11
    fxsave64 [rsp + 80]
    mov rax, [rel kernel_cr3]
    test rax, rax
    jz .dispatch
    mov cr3, rax
.dispatch:
    mov rdi, 32
    mov rax, [0x4000]
    cld                            ; interrupted kernel code may have DF set
    call rax
    fxrstor64 [rsp + 80]
    mov rax, [rsp + 64]
    mov rsp, [rsp + 72]
    mov cr3, rax
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    iretq

; --- CPU exception stubs ---------------------------------------------------
; Each stub normalizes the stack to [vector][error_code][RIP][CS][RFLAGS]...
; then calls the `.in` handler published at [0x4050] with
; (vector, error_code, faulting_rip, saved_cs). Only an active CPL3 fault may
; return an instance status; the capsule independently verifies its origin.
exc_0:
    push 0          ; no CPU error code; push a placeholder
    push 0          ; vector 0 (divide error)
    jmp exc_common
exc_3:
    push 0
    push 3          ; breakpoint (INT3 advances RIP)
    jmp exc_common
exc_6:
    push 0
    push 6          ; invalid opcode
    jmp exc_common
exc_13:
    push 13         ; #GP: CPU already pushed an error code
    jmp exc_common
exc_14:
    push 14         ; #PF: CPU already pushed an error code
    jmp exc_common
exc_16:
    push 0
    push 16         ; native x87 floating-point exception
    jmp exc_common
exc_19:
    push 0
    push 19         ; SIMD floating-point exception
    jmp exc_common
exc_common:
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push rdi
    push rbp
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov rax, cr3
    mov r11, rsp
    and rsp, -16
    sub rsp, 592
    mov [rsp + 64], rax
    mov [rsp + 72], r11
    fxsave64 [rsp + 80]
    mov rax, [rel kernel_cr3]
    test rax, rax
    jz .handler
    mov cr3, rax
.handler:
    mov rdi, [r11 + 120]
    mov rsi, [r11 + 128]
    mov rdx, [r11 + 136]
    mov rcx, [r11 + 144]
    cmp qword [rel guest_active], 0
    je .policy
    test cl, 3
    jz .policy
    fxrstor64 [kernel_fx_state]
.policy:
    mov rax, [0x4050]
    cld
    call rax
    mov r11, [rsp + 72]
    mov rcx, [r11 + 144]
    and ecx, 3
    cmp ecx, 3
    jne .hang
    cmp qword [rel guest_active], 0
    je .hang
    mov rdi, r11
    lea rsi, [rsp + 80]
    mov edx, 2
    mov rcx, [r11 + 120]
    mov r8, [r11 + 128]
    mov r9, rax
    call user_context_capture
    mov rdi, rax
    jmp leave_user
.hang:
    cli
    hlt
    jmp .hang

; --- preemptive timer gate -------------------------------------------------
; Saves the full interrupted register state, hands a pointer to it to the `.in`
; scheduler published at [0x4028], and resumes whatever task the scheduler
; selects (possibly a different one) via its returned stack pointer + iretq.
isr_timer_preempt:
    cmp qword [rel guest_active], 0
    je .kernel
    test byte [rsp + 8], 3
    jnz isr_user_timer
.kernel:
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push rdi
    push rbp
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov rdi, rsp                 ; arg0 = pointer to the saved context
    mov rax, [0x4028]            ; schedule_tick, published by the .in kernel
    call rax
    mov rsp, rax                 ; switch to the selected task's saved context
    jmp user_pop_frame

; Synchronous CPL3 timer cancellation. No task/scheduler selection occurs here.
isr_user_timer:
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push rdi
    push rbp
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov rax, cr3
    mov r11, rsp
    and rsp, -16
    sub rsp, 592
    mov [rsp + 64], rax
    mov [rsp + 72], r11
    fxsave64 [rsp + 80]
    mov rax, [rel kernel_cr3]
    mov cr3, rax
    fxrstor64 [kernel_fx_state]
    mov rdi, [rsp + 72]
    mov rax, [0x41A0]              ; .in IRQ accounting and scoped budget policy
    cld
    call rax
    test rax, rax
    jz .resume
    mov rdi, [rsp + 72]
    lea rsi, [rsp + 80]
    mov edx, 3
    xor ecx, ecx
    xor r8d, r8d
    mov r9, rax
    call user_context_capture
    mov rdi, rax
    jmp leave_user
.resume:
    fxrstor64 [rsp + 80]
    mov rax, [rsp + 64]
    mov rsp, [rsp + 72]
    mov cr3, rax
    jmp user_pop_frame

; --- syscall gate (int 0x80) -------------------------------------------------
; Saves all GP registers into a frame on the stack, passes a pointer to that
; frame to the `.in` syscall_dispatch function published at [0x4070], then
; restores all registers and returns via iretq. The dispatch function reads
; the syscall number from RAX in the frame (offset 112) and the arguments from
; RDI (72), RSI (80), RDX (88), then writes the return value back into the RAX
; slot so iretq delivers it to the caller.
isr_syscall:
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push rdi
    push rbp
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov rax, cr3
    mov r11, rsp
    and rsp, -16
    sub rsp, 592                    ; 64-byte .in scratch, metadata, 512-byte FPU image
    mov [rsp + 64], rax
    mov [rsp + 72], r11
    fxsave64 [rsp + 80]
    mov qword [rel user_syscall_continue], 0
    mov rax, [rel kernel_cr3]
    test rax, rax
    jz .dispatch
    mov cr3, rax
.dispatch:
    cmp qword [rel guest_active], 0
    je .policy
    mov rcx, [rsp + 72]
    test byte [rcx + 128], 3
    jz .policy
    fxrstor64 [kernel_fx_state]     ; policy executes with kernel x87/SSE state
.policy:
    mov rdi, [rsp + 72]             ; unmodified 15-GP-register frame
    mov rax, [0x4070]
    cld
    call rax
    cmp qword [rel guest_active], 0
    je .restore
    mov rcx, [rsp + 72]
    mov rcx, [rcx + 128]            ; CPU/synthetic saved CS
    and ecx, 3
    cmp ecx, 3
    jne .restore
    cmp qword [rel user_syscall_continue], 1
    je .restore
    mov rdi, [rsp + 72]
    lea rsi, [rsp + 80]
    mov edx, 1
    cmp qword [rel user_syscall_continue], 2
    jne .stop_kind
    mov edx, 4
.stop_kind:
    xor ecx, ecx
    xor r8d, r8d
    mov r9, [rdi + 112]
    call user_context_capture
    mov rdi, [rsp + 72]
    mov rdi, [rdi + 112]
    jmp leave_user
.restore:
    fxrstor64 [rsp + 80]
    mov rax, [rsp + 64]
    mov rsp, [rsp + 72]
    mov cr3, rax
    jmp user_pop_frame

; syscall_write_demo(buf, len) -> Int
; rdi = buf address, rsi = length (passed via invoke2 from .in code).
; Rearranges registers into the syscall convention (RAX=num, RDI=fd, RSI=buf,
; RDX=len) and triggers sys_write(1, buf, len) via int 0x80. Returns the
; syscall result in RAX.
syscall_write_demo:
    mov rdx, rsi                 ; rdx = len (arg2)
    mov rsi, rdi                 ; rsi = buf (arg1)
    mov rdi, 1                   ; rdi = fd stdout (arg0)
    mov rax, 0                   ; rax = sys_write syscall number
    int 0x80
    ret                          ; rax has the return value

; --- component invocation stub ----------------------------------------------
; Used by the preemptive scheduler to start a runtime-loaded component in its
; isolated domain. On entry RDI holds the task index. The kernel publishes the
; bases of preempt_entry at [0x40A0], preempt_cap_info at [0x40A8],
; preempt_pml4 at [0x40B0], and the kernel PML4 at [0x40C0]. The stub looks up
; the component entry, argument, and PML4 for that index, switches CR3, calls the
; entry, then returns to the kernel domain and loops. It runs from low
; identity-mapped memory so it is available in every domain.
comp_invoke_stub:
    cli
    push rbx
    push r11
    push r12
    mov r12, rdi
    shl r12, 3
    mov rbx, [0x40A0]
    mov r11, [rbx + r12]
    mov rbx, [0x40A8]
    mov rdi, [rbx + r12]
    mov rbx, [0x40B0]
    mov rbx, [rbx + r12]
    mov cr3, rbx
    call r11
    mov rbx, [0x40C0]
    mov cr3, rbx
    pop r12
    pop r11
    pop rbx
    ; The component entry returned: park this task. Interrupts stay enabled
    ; so the timer keeps scheduling other tasks; this task's context is
    ; resumed here on each future tick and never re-enters the component.
.park:
    sti
    hlt
    jmp .park

; A single synchronous trusted fixture owns this saved continuation. Interrupts
; stay disabled; exit abandons the payload stack and restores the kernel caller.
foreign_run:
    cmp qword [foreign_saved_rsp], 0
    jne foreign_run_busy
    pushfq
    cli
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    mov [foreign_saved_rsp], rsp
    sub rsp, 32                     ; entry shadow space for Microsoft x64
    call rdi
foreign_finish:
    mov rsp, [foreign_saved_rsp]
    mov qword [foreign_saved_rsp], 0
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    popfq
    ret
foreign_run_busy:
    mov rax, -16
    ret

foreign_syscall_entry:
    cmp qword [rel guest_active], 0
    jne user_syscall_entry
    cmp qword [foreign_saved_rsp], 0
    je .inactive
    lea rsp, [rsp - 128]             ; skip the SysV red zone: leaf payloads may
                                     ; keep live data in the 128 bytes below RSP
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push rdi
    push rbp
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov rdi, rsp                     ; same GP frame layout as int 0x80
    sub rsp, 64                      ; reserve .in callee parameter scratch
    cld
    call [0x40D8]                    ; returns 1 for exit, 0 for syscall return
    add rsp, 64
    cmp rax, 1
    je .exit
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rbp
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rbx
    pop rax
    push r11
    popfq
    lea rsp, [rsp + 128]             ; hand back the payload RSP above the red zone
    jmp rcx                         ; CPL0 only; SYSRET would require CPL3
.exit:
    mov rax, [rsp + 112]
    jmp foreign_finish
.inactive:
    mov rax, -38
    push r11
    popfq
    jmp rcx

; SYSCALL does not switch stacks. Preserve the user RSP before touching its
; red zone, then synthesize the CPU frame used by the shared INT80 dispatcher.
user_syscall_entry:
    mov [rel user_syscall_rsp], rsp
    mov rsp, [rel tss + 4]
    push qword 0x23
    push qword [rel user_syscall_rsp]
    push r11
    push qword 0x1B
    push rcx
    jmp isr_syscall

align 8
foreign_saved_rsp: dq 0

; Microsoft x64 imports reuse the trusted dispatcher frame. Preserve RDI/RSI;
; the dispatcher uses integer operations only and leaves XMM6-XMM15 untouched.
foreign_writefile:
    mov eax, 1
    jmp foreign_fileio_import
foreign_readfile:
    xor eax, eax
foreign_fileio_import:
    mov r10, [rsp + 40]              ; fifth argument: OVERLAPPED
    push rdi
    push rsi
    mov rdi, rcx
    mov rsi, rdx
    mov edx, r8d
    pushfq
    pop r11
    lea rcx, [rel .done]
    jmp foreign_syscall_entry
.done:
    pop rsi
    pop rdi
    ret
foreign_createfilea:
    lea r10, [rsp]                   ; caller RSP for 5th..7th Win64 args validated in .in
    push rdi
    push rsi
    mov rdi, rcx
    mov rsi, rdx
    mov eax, 2
    pushfq
    pop r11
    lea rcx, [rel .done]
    jmp foreign_syscall_entry
.done:
    pop rsi
    pop rdi
    ret
foreign_closehandle:
    push rdi
    push rsi
    mov rdi, rcx
    mov eax, 3
    pushfq
    pop r11
    lea rcx, [rel .done]
    jmp foreign_syscall_entry
.done:
    pop rsi
    pop rdi
    ret
foreign_exitprocess:
    mov edi, ecx
    mov eax, 60
    pushfq
    pop r11
    jmp foreign_syscall_entry

runtime_rflags:
    pushfq
    pop rax
    ret

; Hardware entropy capsule: runtime_random64(kernel_output_pointer).
; No fallback seed. Store only after hardware reports a successful sample.
runtime_random64:
    push rbx
    mov eax, 1
    cpuid
    bt ecx, 30
    jnc .unsupported
    mov ecx, 16
.retry:
    rdrand rax
    jc .success
    loop .retry
    mov rax, -11
    pop rbx
    ret
.unsupported:
    mov rax, -38
    pop rbx
    ret
.success:
    mov [rdi], rax
    xor eax, eax
    pop rbx
    ret

; --- cooperative context switch --------------------------------------------
; context_switch(rdi = pointer to the outgoing task's saved-RSP slot,
;                rsi = the incoming task's saved RSP).
; Saves callee-saved registers, stores RSP into [rdi], loads RSP from rsi, and
; restores the incoming task's callee-saved registers before returning into it.
context_switch:
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    mov [rdi], rsp
    mov rsp, rsi
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret

; --- CR3 read/write stubs for domain subsystem -----------------------------
; cr3_read() -> Int: returns the current CR3 in rax.
; Published at [0x4058] for the `.in` kernel's domain operations.
cr3_read:
    mov rax, cr3
    ret

; cr3_write(cr3: Int) -> void: sets CR3. Called via invoke1(stub, value).
; Published at [0x4060] so invoke1 passes the PML4 phys addr in rdi.
cr3_write:
    mov cr3, rdi
    ret

; enter_user(args): rdi -> {rip, arg, user_rsp, user_cr3}. IRETQ to CPL3.
enter_user:
    mov eax, 0x3002
    jmp enter_user_common

; Strict synchronous guest: no user I/O privilege and no asynchronous IRQs.
enter_user_strict:
    mov eax, 0x2
    jmp enter_user_common

enter_user_context:
    cmp qword [rel guest_active], 0
    jne enter_user_common.busy
    mov rax, [rdi]
    mov [rel user_context_pointer], rax
    mov eax, 0x202
    jmp enter_user_common
enter_user_interruptible:
    mov eax, 0x202
enter_user_common:
    cmp qword [rel guest_active], 0
    jne .busy
    mov [enter_rflags], rax
    fxsave64 [kernel_fx_state]
    fninit
    ldmxcsr [initial_mxcsr]
    test qword [enter_rflags], 0x3000
    jnz .fx_ready                   ; preserve legacy entry register contract
    ; FNINIT clears tags, not underlying x87 bytes. Overwrite all eight slots.
    times 8 fldz
    fninit
    pxor xmm0, xmm0
    pxor xmm1, xmm1
    pxor xmm2, xmm2
    pxor xmm3, xmm3
    pxor xmm4, xmm4
    pxor xmm5, xmm5
    pxor xmm6, xmm6
    pxor xmm7, xmm7
    pxor xmm8, xmm8
    pxor xmm9, xmm9
    pxor xmm10, xmm10
    pxor xmm11, xmm11
    pxor xmm12, xmm12
    pxor xmm13, xmm13
    pxor xmm14, xmm14
    pxor xmm15, xmm15
.fx_ready:
    pushfq
    pop qword [enter_saved_rflags]
    pop qword [enter_saved_rip]
    mov [enter_saved_rbx], rbx
    mov [enter_saved_rbp], rbp
    mov [enter_saved_r12], r12
    mov [enter_saved_r13], r13
    mov [enter_saved_r14], r14
    mov [enter_saved_r15], r15
    mov [enter_saved_rsp], rsp
    mov qword [rel guest_active], 1
    cmp qword [rel user_context_pointer], 0
    jne .context
    mov r8, [rdi]
    mov r9, [rdi + 8]
    mov rdx, [rdi + 16]
    mov rcx, [rdi + 24]
    cli
    mov rax, [rel tss + 4]
    test rax, rax
    jz .segs
    mov rsp, rax
.segs:
    mov ax, 0x23
    mov ds, ax
    mov es, ax
    push qword 0x23
    push rdx
    push qword [enter_rflags]
    push qword 0x1B
    push r8
    mov rdi, r9
    xor edx, edx                    ; ELF rtld_fini is absent; argument remains in RDI
    test rcx, rcx
    jz .iret
    mov cr3, rcx
.iret:
    test qword [enter_rflags], 0x3000
    jnz .ready
    ; Only the explicit argument and IRET frame cross the strict entry boundary.
    xor eax, eax
    xor ebx, ebx
    xor ecx, ecx
    xor edx, edx
    xor esi, esi
    xor ebp, ebp
    xor r8d, r8d
    xor r9d, r9d
    xor r10d, r10d
    xor r11d, r11d
    xor r12d, r12d
    xor r13d, r13d
    xor r14d, r14d
    xor r15d, r15d
.ready:
    iretq
.context:
    mov r8, [rdi + 8]
    mov rsi, [rel user_context_pointer]
    mov rsp, [rel tss + 4]
    sub rsp, 160
    mov rdi, rsp
    mov ecx, 20
    cld
    rep movsq
    mov rsi, [rel user_context_pointer]
    fxrstor64 [rsi + 160]
    mov ax, 0x23
    mov ds, ax
    mov es, ax
    mov cr3, r8
    jmp user_pop_frame
.busy:
    mov rax, -16
    ret

user_pop_frame:
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rbp
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rbx
    pop rax
    iretq

; Notify kernel policy only after the guest register/FX image is saved and
; kernel CR3/FPU restored. The callback cannot replace the hardware frame.
user_context_capture:
    cmp qword [rel user_context_pointer], 0
    je .done
    sub rsp, 88
    mov [rsp + 64], rax
    mov rax, [0x41B8]
    test rax, rax
    jz .return
    call rax
.return:
    mov rax, [rsp + 64]
    add rsp, 88
.done:
    ret

leave_user:
    cli
    mov rax, rdi
    mov qword [rel guest_active], 0
    mov qword [rel user_context_pointer], 0
    mov rcx, [rel kernel_cr3]
    test rcx, rcx
    jz .stack
    mov cr3, rcx
.stack:
    mov rsp, [enter_saved_rsp]
    fxrstor64 [kernel_fx_state]
    mov bx, 0x10
    mov ds, bx
    mov es, bx
    mov ss, bx
    mov r15, [enter_saved_r15]
    mov r14, [enter_saved_r14]
    mov r13, [enter_saved_r13]
    mov r12, [enter_saved_r12]
    mov rbp, [enter_saved_rbp]
    mov rbx, [enter_saved_rbx]
    push qword [enter_saved_rflags]
    popfq
    jmp qword [enter_saved_rip]

; Runtime-owned synchronous call boundary. An abort abandons component frames
; and returns only to this saved caller. Nested boundaries are refused.
runtime_invoke:
    cmp qword [runtime_saved_rsp], 0
    jne .busy
    pushfq
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    mov [runtime_saved_rsp], rsp
    mov r11, rdi
    mov rdi, rsi
    sub rsp, 64                     ; native .in callee parameter scratch
    call r11
runtime_finish:
    mov rsp, [runtime_saved_rsp]
    mov qword [runtime_saved_rsp], 0
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    popfq
    ret
runtime_invoke.busy:
    mov rax, -16
    ret

runtime_abort:
    cmp qword [runtime_saved_rsp], 0
    je .fatal
    mov rax, rdi
    jmp runtime_finish
.fatal:
    ud2

align 4
mb_info: dd 0

align 8
kernel_cr3: dq 0
enter_saved_rsp: dq 0
enter_saved_rbx: dq 0
enter_saved_rbp: dq 0
enter_saved_r12: dq 0
enter_saved_r13: dq 0
enter_saved_r14: dq 0
enter_saved_r15: dq 0
enter_saved_rip: dq 0
guest_active: dq 0
enter_rflags: dq 0
enter_saved_rflags: dq 0
runtime_saved_rsp: dq 0
user_syscall_rsp: dq 0
user_syscall_continue: dq 0
user_context_pointer: dq 0
initial_mxcsr: dd 0x1F80
; Supervisor-only low hardware-state page; accessed only on kernel CR3.
kernel_fx_state equ 0x4200

align 16
tss:
    dd 0
    dq 0
    times 102 - 12 db 0
    dw 104                         ; no I/O bitmap within the 103-byte TSS limit

align 8
gdt:
    dq 0x0000000000000000           ; null
    dq 0x00AF9A000000FFFF           ; 0x08 kernel CS DPL0
    dq 0x00CF92000000FFFF           ; 0x10 kernel DS DPL0
    dq 0x00AFFA000000FFFF           ; 0x18 user CS DPL3
    dq 0x00CFF2000000FFFF           ; 0x20 user DS DPL3
tss_desc:
    dw 103
    dw tss
    db 0x10
    db 0x89
    db 0
    db 0
    dd 0
    dd 0
    dq 0x00CFFA000000FFFF           ; 0x38 user compatibility CS DPL3, 32-bit
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

times 0xF00 - ($ - $$) db 0
boot_image_table: dq 0
times 0x1000 - ($ - $$) db 0        ; pad to TRAMPOLINE_RESERVE
