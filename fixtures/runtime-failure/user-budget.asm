; Budgeted IOPL0/IF1 workload; RDI mode: 0=spin,1=finite IRQ/FPU,2=fault.
BITS 64
ORG 0x42000000
    pushfq
    pop rax
    and eax,0x3200
    cmp eax,0x200
    jne failure
    cmp edi,2
    je fault
    cmp edi,1
    je finite
spin:
    pause
    jmp spin
fault:
    ud2
finite:
    ; One IRQ changes kernel ticks, observed through a syscall policy below.
    ; Hardware registers/FPU must survive repeated real interrupts while busy.
    mov rbx,0x12345678
    mov r12,0x22334455
    mov r13,rsp
    mov qword [rsp-128],0x11223344
    mov eax,0x33445566
    movq xmm7,rax
    fld1
    mov dword [rsp-24],0x3f80
    ldmxcsr [rsp-24]
    mov eax,704
    syscall                        ; returns current timer tick count
    mov r14,rax
wait_irq:
    pause
    mov eax,704
    syscall
    sub rax,r14
    cmp rax,3
    jb wait_irq
    cmp rbx,0x12345678
    jne failure
    cmp r12,0x22334455
    jne failure
    cmp rsp,r13
    jne failure
    cmp qword [rsp-128],0x11223344
    jne failure
    movq rax,xmm7
    cmp rax,0x33445566
    jne failure
    fadd st0,st0
    fistp qword [rsp-16]
    cmp qword [rsp-16],2
    jne failure
    stmxcsr [rsp-24]
    cmp dword [rsp-24],0x3f80
    jne failure
    mov edi,42
    mov eax,703
    syscall
failure:
    mov edi,99
    mov eax,703
    syscall
    ud2
    times 4096-($-$$) db 0
