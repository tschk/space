; Own CPL3 ABI fixture, not an upstream application. Exit42 means all checks.
bits 64
global _start
%macro equal 2
    cmp %1, %2
    jne failed
%endmacro
section .text
_start:
    mov rdi, [rsp+16]
    mov r13, rdi
    mov rsi, 2
    xor edx, edx
    mov r10, rdi
    mov rdi, -100
    mov rdx, rsi
    mov rsi, r10
    mov eax, 257
    syscall
    test rax, rax
    js failed
    mov r12, rax
    mov [rows], eax
    mov rdi, rows
    mov esi, 3
    mov edx, -1
    mov eax, 7
    syscall
    equal rax, 2
    equal word [rows+4], 0x145
    equal word [rows+6], 0x145
    equal word [rows+14], 0
    equal word [rows+22], 32
    equal qword [guard], 0x12345678
    ; poll must not advance the native open-file offset.
    mov rdi, r12
    xor esi, esi
    mov edx, 1
    mov eax, 8
    syscall
    equal rax, 0
    mov rdi, r12
    mov rsi, sample_byte
    mov edx, 1
    xor eax, eax
    syscall
    equal rax, 1
    equal byte [sample_byte], 'o'
    ; EOF is still immediately readable on a regular file.
    mov rdi, r12
    xor esi, esi
    mov edx, 2
    mov eax, 8
    syscall
    equal rax, 9
    mov word [rows+4], 1
    mov rdi, rows
    mov esi, 1
    mov edx, -1
    mov eax, 7
    syscall
    equal rax, 1
    equal word [rows+6], 1
    mov rdi, r12
    mov rsi, sample_byte
    mov edx, 1
    xor eax, eax
    syscall
    equal rax, 0
    ; Unrequested/unknown event bits and ignored negative descriptors.
    mov word [rows+4], 0x8000
    mov rdi, rows
    mov esi, 2
    xor edx, edx
    mov eax, 7
    syscall
    equal rax, 0
    equal word [rows+6], 0
    equal word [rows+14], 0
    ; Actual waits are refused, with all outputs unchanged.
    mov word [rows+6], 0x5555
    mov rdi, rows
    mov esi, 1
    mov edx, 1
    mov eax, 7
    syscall
    equal rax, -95
    equal word [rows+6], 0x5555
    ; Unsupported serial handle after a valid ready row must be atomic.
    mov word [rows+4], 1
    mov dword [rows+8], 1
    mov word [rows+14], 0x5555
    mov rdi, rows
    mov esi, 2
    xor edx, edx
    mov eax, 7
    syscall
    equal rax, -95
    equal word [rows+6], 0x5555
    equal word [rows+14], 0x5555
    xor edi, edi
    mov esi, 1
    xor edx, edx
    mov eax, 7
    syscall
    equal rax, -14
    mov rdi, readonly
    mov esi, 1
    mov eax, 7
    syscall
    equal rax, -14
    equal word [readonly+6], 0x5555
    mov rdi, rows
    mov esi, 17
    mov eax, 7
    syscall
    equal rax, -22
    xor edi, edi
    xor esi, esi
    xor edx, edx
    mov eax, 7
    syscall
    equal rax, 0
    mov edx, -1
    mov eax, 7
    syscall
    equal rax, -95
    ; Native inline resize: shrink, unchanged offset, zero-filled extension.
    mov rdi, r12
    mov esi, 4
    mov eax, 77
    syscall
    equal rax, 0
    mov rdi, r12
    xor esi, esi
    mov edx, 1
    mov eax, 8
    syscall
    equal rax, 9
    mov rdi, r12
    mov esi, 9
    mov eax, 77
    syscall
    equal rax, 0
    mov rdi, r12
    mov rsi, statbuf
    mov eax, 5
    syscall
    equal rax, 0
    equal qword [statbuf+48], 9
    mov rdi, r12
    mov esi, 4
    xor edx, edx
    mov eax, 8
    syscall
    equal rax, 4
    mov rdi, r12
    mov rsi, sample_byte
    mov edx, 5
    xor eax, eax
    syscall
    equal rax, 5
    equal dword [sample_byte], 0
    equal byte [sample_byte+4], 0
    mov rdi, r12
    mov rsi, -1
    mov eax, 77
    syscall
    equal rax, -22
    mov rdi, r12
    mov esi, 97
    mov eax, 77
    syscall
    equal rax, -95
    mov edi, 9999
    mov esi, 1
    mov eax, 77
    syscall
    equal rax, -9
    mov rdi, -100
    mov rsi, r13
    xor edx, edx
    mov eax, 257
    syscall
    test rax, rax
    js failed
    mov r14, rax
    mov rdi, r14
    mov esi, 1
    mov eax, 77
    syscall
    equal rax, -22
    mov rdi, r14
    mov eax, 3
    syscall
    equal rax, 0
    mov rdi, r12
    mov eax, 3
    syscall
    equal rax, 0
    mov edi, 42
    jmp exit
failed:
    mov edi, 99
exit:
    mov eax, 60
    syscall
section .rodata
readonly: dd 9999
    dw 1, 0x5555
section .data
rows: dd 0
    dw 0x145, 0x5555
    dd -1
    dw 1, 0x5555
    dd 9999
    dw 0, 0x5555
guard: dq 0x12345678
sample_byte: times 8 db 0
statbuf: times 144 db 0
