; Own real CPL3 fixture. Upstream application credit is always zero.
bits 64
global _start
section .text
_start:
    mov r12, [rsp+16]
    cmp byte [r12], 'w'
    je writer
    cmp byte [r12], 'q'
    je reader
    cmp byte [r12], 'x'
    je finished
    cmp byte [r12], 'f'
    je bad_pointer
    mov eax, 1
    mov edi, 1
    mov rsi, ready
    mov edx, 6
    syscall
    cmp rax, 6
    jne failed
reader:
    xor eax, eax
    xor edi, edi
    mov rsi, sample
    mov edx, 1
    syscall
    cmp rax, 1
    jne failed
    cmp byte [sample], 'a'
    jne failed
    mov byte [answer+4], 'a'
    mov eax, 1
    mov edi, 1
    mov rsi, answer
    mov edx, 6
    syscall
    cmp rax, 6
    jne failed
    xor eax, eax
    xor edi, edi
    mov rsi, sample
    mov edx, 1
    syscall
    cmp rax, 1
    jne failed
    cmp byte [sample], 'b'
    jne failed
    jmp finished
writer:
    xor ecx, ecx
.fill:
    mov [payload+rcx], cl
    inc ecx
    cmp ecx, 1024
    jne .fill
    xor r12d, r12d
.write:
    mov eax, 1
    mov edi, 1
    lea rsi, [payload+r12]
    mov edx, 1024
    sub rdx, r12
    syscall
    test rax, rax
    jle failed
    add r12, rax
    cmp r12, 1024
    jb .write
    jne failed
    jmp finished
bad_pointer:
    xor eax, eax
    xor edi, edi
    mov rsi, _start
    mov edx, 1
    syscall
    cmp rax, -14
    jne failed
finished:
    mov edi, 42
    mov eax, 60
    syscall
failed:
    mov edi, 99
    mov eax, 60
    syscall
section .rodata
ready: db 'ready',10
section .data
answer: db 'got:a',10
section .bss
sample: resb 1
payload: resb 1024
