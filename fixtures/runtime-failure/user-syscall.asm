; Strict CPL3 CPU bridge contract: actual SYSCALL, INT80 and resumable state.
BITS 64
ORG 0x42000000
entry:
    test rdx,rdx
    jnz failure
    stmxcsr [rsp-24]
    cmp dword [rsp-24],0x1f80
    jne failure
    mov dword [rsp-24],0x3f80
    ldmxcsr [rsp-24]
    fld1
    mov rbx,0x12345678
    mov r12,0x22334455
    mov r13,rsp
    mov qword [rsp-128],0x11223344
    mov eax,0x33445566
    movq xmm7,rax
    mov eax,701
    mov edi,17
    mov esi,23
    mov r10d,29
    std
    syscall
    jnc failure                    ; hook sets saved RFLAGS.CF
    pushfq
    pop rcx
    bt ecx,10
    jnc failure                    ; guest DF restored after kernel CLD
    cld
    cmp rax,69
    jne failure
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
    mov eax,702
    int 0x80
    jc failure                     ; hook clears saved RFLAGS.CF
    cmp rax,77
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
