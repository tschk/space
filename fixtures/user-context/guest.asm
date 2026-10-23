BITS 64
ORG 0x42000000
    or rax, rbx
    or rax, rcx
    or rax, rdx
    or rax, rsi
    or rax, rbp
    or rax, r8
    or rax, r9
    or rax, r10
    or rax, r11
    or rax, r12
    or rax, r13
    or rax, r14
    or rax, r15
    test rax, rax
    jnz .bad
    fxsave64 [rsp-1024]
    lea rsi, [rsp-1024+32]
    mov ecx, 8
.fresh_x87:
    cmp qword [rsi], 0
    jne .bad
    cmp word [rsi+8], 0
    jne .bad
    add rsi, 16
    loop .fresh_x87
    mov ecx, 32
.fresh_xmm:
    cmp qword [rsi], 0
    jne .bad
    add rsi, 8
    loop .fresh_xmm
    mov rax, 0x5746554354583132
    movq xmm15, rax
    fld1
    cmp rdi, 1
    je .fault
    cmp rdi, 2
    je .forever
    cmp rdi, 3
    je .page
    mov rbx, 0x1122334455667788
    mov rbp, 0x1020304050607080
    mov r12, 0x123456789abcdef0
    mov r13, 0xfedcba9876543210
    mov r14, 0x5566778899aabbcc
    mov r15, 0x8877665544332211
    mov r8, 0x2233445566778899
    mov r9, 0x33445566778899aa
    mov r10, 0x445566778899aabb
    mov rdx, 0x778899aabbccddee
    mov rsi, 0x66778899aabbccdd
    mov rax, 0x5746554354583132
    mov [rsp-8], rax
    movq xmm15, rax
    mov eax, 800
    syscall
.resume:
    test rax, rax
    jz .child
    cmp rax, 84
    jne .bad
    mov edi, 42
    jmp .verify
.child:
    mov edi, 43
.verify:
    mov rax, 0x1122334455667788
    cmp rbx, rax
    jne .bad
    mov rax, 0x123456789abcdef0
    cmp r12, rax
    jne .bad
    mov rax, 0x5746554354583132
    cmp [rsp-8], rax
    jne .bad
    movq rcx, xmm15
    cmp rax, rcx
    jne .bad
    fst qword [rsp-16]
    mov rax, 0x3ff0000000000000
    cmp [rsp-16], rax
    jne .bad
    mov rax, [fs:0]
    cmp rax, 0x12345678
    jne .bad
    mov rax, [gs:0]
    cmp rax, 0x12345678
    jne .bad
    cmp edi, 43
    jne .exit
    mov rbx, 0x4348494c44465831
    movq xmm15, rbx
    fldpi
.exit:
    mov eax, 801
    syscall
.bad:
    ud2
.fault:
    mov rbx, 0x1122334455667788
    ud2
.forever:
    mov rbx, 0x1122334455667788
    jmp .forever
.page:
    mov rbx, 0x1122334455667788
    mov rax, [0x100000]
    ud2
TIMES 2048-($-$$) db 0
; Kernel-only state setup and snapshot helpers, called on identity addresses.
    fninit
    fldpi
    mov rax, 0x4b45524e454c4658
    movq xmm15, rax
    fxsave64 [rdi]
    ret
TIMES 2304-($-$$) db 0
    fxsave64 [rdi]
    ret
TIMES 4096-($-$$) db 0
