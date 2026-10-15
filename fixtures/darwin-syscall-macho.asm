; Trusted x86_64 Mach-O fixture using Darwin BSD syscall numbers and carry errno.
BITS 64
ORG 0x280000
image:
    dd 0xfeedfacf, 0x01000007, 3, 2
    dd 2, 96, 1, 0
    dd 0x19, 72
    db '__TEXT', 0
    times 16-7 db 0
    dq image, 4096, 0, 4096
    dd 5, 5, 0, 0
    dd 0x80000028, 24
    dq entry-image, 0
entry:
    mov eax, 0x200FFFF
    syscall
    jnc fail
    cmp rax, 78
    jne fail
    mov eax, 0x2000004
    mov edi, 9
    lea rsi, [rel msg]
    mov edx, msglen
    syscall
    jnc fail
    cmp rax, 9
    jne fail
    mov eax, 0x2000004
    mov edi, 1
    xor esi, esi
    mov edx, msglen
    syscall
    jnc fail
    cmp rax, 14
    jne fail
    mov eax, 0x2000004
    mov edi, 1
    lea rsi, [rel msg]
    mov edx, msglen
    syscall
    jc fail
    cmp rax, msglen
    jne fail
    xor ebx, ebx
    xor ebp, ebp
    xor r12d, r12d
    xor r13d, r13d
    xor r14d, r14d
    xor r15d, r15d
    mov eax, 0x2000001
    mov edi, 42
    syscall
    ud2
fail:
    mov eax, 0x2000001
    mov edi, 99
    syscall
    ud2
msg: db 'darwin: hardware syscall hello', 10
msglen equ $-msg
    times 4096-($-$$) db 0
