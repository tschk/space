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
    or eax, 1 << 5                    ; CR4.PAE
    mov cr4, eax

    mov ecx, 0xC0000080              ; IA32_EFER
    rdmsr
    or eax, 1 << 8                    ; EFER.LME
    wrmsr

    mov eax, cr0
    or eax, 0x80000001              ; CR0.PG | CR0.PE
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
; `.in` dispatcher published at [0x4000] with the vector in rdi, then returns.
isr_timer:
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    mov rdi, 32
    mov rax, [0x4000]
    call rax
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
; (vector, error_code, faulting_rip). The handler reports and halts.
exc_0:
    push 0          ; no CPU error code; push a placeholder
    push 0          ; vector 0 (divide error)
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
exc_common:
    mov rdi, [rsp]       ; vector
    mov rsi, [rsp + 8]   ; error code
    mov rdx, [rsp + 16]  ; faulting RIP
    mov rax, [0x4050]
    call rax
.hang:
    cli
    hlt
    jmp .hang

; --- preemptive timer gate -------------------------------------------------
; Saves the full interrupted register state, hands a pointer to it to the `.in`
; scheduler published at [0x4028], and resumes whatever task the scheduler
; selects (possibly a different one) via its returned stack pointer + iretq.
isr_timer_preempt:
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
    mov rdi, rsp                 ; arg0 = pointer to saved register frame
    mov rax, [0x4070]            ; syscall_dispatch, published by the .in kernel
    call rax
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
    pop rax                      ; picks up return value written by dispatch
    iretq

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

align 4
mb_info: dd 0

align 8
gdt:
    dq 0x0000000000000000           ; null descriptor
    dq 0x00AF9A000000FFFF           ; 0x08: 64-bit code (P, DPL0, exec/read, L)
    dq 0x00CF92000000FFFF           ; 0x10: data (P, DPL0, read/write)
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

times 0x1000 - ($ - $$) db 0        ; pad to TRAMPOLINE_RESERVE
