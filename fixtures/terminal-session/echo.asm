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
    cmp byte [r12], 't'
    je controls
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
    jmp finished
controls:
    mov eax, 1
    mov edi, 1
    mov rsi, control_ready
    mov edx, 8
    syscall
    cmp rax, 8
    jne failed
    mov eax, 16
    xor edi, edi
    mov esi, 0x5401
    mov rdx, modes
    syscall
    test rax, rax
    jne failed
    cmp qword [modes], 0
    jne failed
    cmp dword [modes+8], 0xb0
    jne failed
    cmp dword [modes+12], 0
    jne failed
    cmp byte [modes+23], 1
    jne failed
    mov byte [modes+17], 3
    mov eax, 16
    xor edi, edi
    mov esi, 0x5402
    mov rdx, modes
    syscall
    test rax, rax
    jne failed
    mov dword [modes+12], 2 ; unsupported canonical mode must refuse atomically
    mov eax, 16
    xor edi, edi
    mov esi, 0x5402
    mov rdx, modes
    syscall
    cmp rax, -95
    jne failed
    mov eax, 16
    xor edi, edi
    mov esi, 0x5401
    mov rdx, modes
    syscall
    test rax, rax
    jne failed
    cmp dword [modes+12], 0
    jne failed
    cmp byte [modes+17], 3
    jne failed
    mov eax, 16
    xor edi, edi
    mov esi, 0x5403 ; genuinely drain queued output before applying modes
    mov rdx, modes
    syscall
    test rax, rax
    jne failed
    mov eax, 16
    xor edi, edi
    mov esi, 0x5404 ; genuinely discard queued input
    mov rdx, modes
    syscall
    test rax, rax
    jne failed
    mov eax, 16
    xor edi, edi
    mov esi, 0x5413
    mov rdx, geometry
    syscall
    test rax, rax
    jne failed
    cmp dword [geometry], (80 << 16) | 24
    jne failed
    cmp dword [geometry+4], 0
    jne failed
    mov eax, 5
    xor edi, edi
    mov rsi, stat_buffer
    syscall
    test rax, rax
    jne failed
    mov eax, [stat_buffer+24]
    and eax, 0xf000
    cmp eax, 0x2000
    jne failed
    mov eax, 72
    xor edi, edi
    mov esi, 3
    syscall
    test rax, rax
    jne failed
    mov eax, 72
    xor edi, edi
    mov esi, 4
    mov edx, 0x800
    syscall
    test rax, rax
    jne failed
    xor eax, eax
    xor edi, edi
    mov rsi, sample
    mov edx, 1
    syscall
    cmp rax, -11
    jne failed
    mov eax, 7
    mov rdi, poll_row
    mov esi, 1
    xor edx, edx
    syscall
    test rax, rax
    jne failed
    cmp word [poll_row+6], 0
    jne failed
    mov word [poll_row+6], 0x5555
    mov eax, 7
    mov rdi, poll_row
    mov esi, 1
    mov edx, 20
    syscall
    test rax, rax
    jne failed
    cmp word [poll_row+6], 0
    jne failed
    ; A completed finite poll must retire its deadline before a plain read.
    mov eax, 72
    xor edi, edi
    mov esi, 4
    xor edx, edx
    syscall
    test rax, rax
    jne failed
    xor eax, eax
    xor edi, edi
    mov rsi, sample
    mov edx, 1
    syscall
    cmp rax, 1
    jne failed
    cmp byte [sample], 'a'
    jne failed
    mov eax, 7
    mov rdi, poll_row
    mov esi, 1
    mov edx, -1
    syscall
    cmp rax, 1
    jne failed
    cmp word [poll_row+6], 1
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
    mov eax, 3
    xor edi, edi
    syscall
    test rax, rax
    jne failed
    xor eax, eax
    xor edi, edi
    mov rsi, sample
    mov edx, 1
    syscall
    cmp rax, -9
    jne failed
    mov eax, 72
    xor edi, edi
    mov esi, 3
    syscall
    cmp rax, -9
    jne failed
    mov eax, 7
    mov rdi, poll_row
    mov esi, 1
    xor edx, edx
    syscall
    cmp rax, 1
    jne failed
    cmp word [poll_row+6], 32
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
control_ready: db 'control',10
section .data
answer: db 'got:a',10
poll_row: dd 0
dw 1, 0x5555
section .bss
modes: resb 36
geometry: resb 8
stat_buffer: resb 144
sample: resb 1
payload: resb 1024
