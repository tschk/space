; Trusted fixed-address x86_64 ELF fixture. No return address, no ret: entry
; uses raw Linux syscalls and must exit the process itself. Loaded RX at
; 0x280000; data kept inside the single 4096-byte PT_LOAD.
BITS 64
ORG 0x280000
image:
    dd 0x464c457f, 0x00010102, 0, 0
    dw 2, 62
    dd 1
    dq entry
    dq 64
    dq 0
    dd 0
    dw 64, 56, 1, 0, 0, 0
    dd 1, 5
    dq 0
    dq image, image
    dq 4096, 4096, 4096
    times 128-($-$$) db 0
entry:
    mov rax, 9999
    syscall
    cmp rax, -38
    jne fail

    mov rax, 1
    mov rdi, 9
    lea rsi, [rel msg]
    mov rdx, msg.len
    syscall
    cmp rax, -9
    jne fail

    mov rax, 1
    mov rdi, 1
    xor esi, esi
    mov rdx, msg.len
    syscall
    cmp rax, -14
    jne fail

    mov rbx, 0x1111111111111111
    mov rbp, 0x2222222222222222
    mov r12, 0x3333333333333333
    mov r13, 0x4444444444444444
    mov r14, 0x5555555555555555
    mov r15, 0x6666666666666666

    mov rax, 1
    mov rdi, 1
    lea rsi, [rel msg]
    mov rdx, msg.len
    syscall
    cmp rax, msg.len
    jne fail

    xor ebx, ebx
    xor ebp, ebp
    xor r12d, r12d
    xor r13d, r13d
    xor r14d, r14d
    xor r15d, r15d

    mov rax, 60
    mov rdi, 42
    syscall
    ud2
fail:
    mov rax, 60
    mov rdi, 99
    syscall
    ud2
msg:
    db 'linux: hardware syscall hello'
    db 10
.len equ $ - msg
    times 4096-($-$$) db 0
