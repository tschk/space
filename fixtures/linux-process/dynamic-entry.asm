; Own ET_DYN CPU control, not an upstream application. No interpreter/relocator.
bits 64
default rel
global _start
section .text
_start:
 mov r12, rsp
 mov r13, 101
 mov rcx, [rsp]
 lea rbx, [rsp+rcx*8+16]
.env:
 cmp qword [rbx], 0
 lea rbx, [rbx+8]
 jne .env
 xor r14d, r14d
.aux:
 mov rax, [rbx]
 test rax, rax
 jz .checked
 cmp eax, 3
 jne .base
 mov rdx, [rbx+8]
 cmp dword [rdx-64], 0x464c457f
 jne fail
 or r14d, 1
.base:
 cmp eax, 7
 jne .entry
 cmp qword [rbx+8], 0
 jne fail
 or r14d, 2
.entry:
 cmp eax, 9
 jne .next
 lea rdx, [_start]
 cmp rdx, [rbx+8]
 jne fail
 or r14d, 4
.next:
 add rbx, 16
 jmp .aux
.checked:
 cmp r14d, 7
 jne fail
 inc r13
 mov rax, [r12+16]
 cmp byte [rax], 's'
 je .second
 ; Actual owned self-exec must preserve ET_DYN bias and rebuild correct auxv.
 lea rax, [name]
 mov [args], rax
 lea rax, [second]
 mov [args+8], rax
 mov qword [args+16], 0
 mov eax, 59
 lea rdi, [self]
 lea rsi, [args]
 xor edx, edx
 syscall
 jmp fail
.second:
 inc r13
 mov eax, 2
 lea rdi, [path]
 mov esi, 0x242
 mov edx, 384
 syscall
 cmp rax, 3
 jl fail
 mov r15, rax
 lea rax, [hello]
 mov [vec], rax
 mov qword [vec+8], 5
 lea rax, [world]
 mov [vec+16], rax
 mov qword [vec+24], 6
 mov eax, 20
 mov rdi, r15
 lea rsi, [vec]
 mov edx, 2
 syscall
 cmp rax, 11
 jne fail
 inc r13
 ; A late invalid vector must not publish the first valid buffer.
 mov qword [vec+16], 0x100000
 mov eax, 20
 mov rdi, r15
 lea rsi, [vec]
 mov edx, 2
 syscall
 cmp rax, -14
 jne fail
 mov eax, 8
 mov rdi, r15
 xor esi, esi
 mov edx, 1
 syscall
 cmp rax, 11
 jne fail
 inc r13
 mov eax, 20
 mov rdi, r15
 lea rsi, [vec]
 mov edx, 65
 syscall
 cmp rax, -95
 jne fail
 mov eax, 20
 mov rdi, r15
 lea rsi, [vec]
 mov edx, -1
 syscall
 cmp rax, -22
 jne fail
 mov qword [vec+8], 65537
 mov eax, 20
 mov rdi, r15
 lea rsi, [vec]
 mov edx, 1
 syscall
 cmp rax, -22
 jne fail
 inc r13
 mov eax, 8
 mov rdi, r15
 xor esi, esi
 xor edx, edx
 syscall
 test rax, rax
 jne fail
 xor eax, eax
 mov rdi, r15
 lea rsi, [result]
 mov edx, 16
 syscall
 cmp rax, 11
 jne fail
 lea rsi, [result]
 lea rdi, [expected]
 mov ecx, 11
 repe cmpsb
 jne fail
 inc r13
 ; Zero-length vectors ignore their unused pointer; invalid descriptors refuse.
 mov eax, 20
 mov rdi, r15
 xor esi, esi
 xor edx, edx
 syscall
 test rax, rax
 jne fail
 mov eax, 20
 mov edi, -1
 xor esi, esi
 xor edx, edx
 syscall
 cmp rax, -9
 jne fail
 mov eax, 20
 mov rdi, r15
 mov esi, 0x100000
 mov edx, 1
 syscall
 cmp rax, -14
 jne fail
 ; Synchronous vector profile must not silently use serial for a pipe endpoint.
 mov eax, 22
 lea rdi, [pipefds]
 syscall
 test rax, rax
 jne fail
 mov eax, 20
 mov edi, [pipefds+4]
 lea rsi, [vec]
 mov edx, 1
 syscall
 cmp rax, -95
 jne fail
 mov eax, 3
 mov edi, [pipefds]
 syscall
 mov eax, 3
 mov edi, [pipefds+4]
 syscall
 mov eax, 60
 mov edi, 42
 syscall
fail:
 mov eax, 60
 mov rdi, r13
 syscall
section .rodata
name: db '/probe',0
second: db 'second',0
self: db '/proc/self/exe',0
path: db '/vector.txt',0
hello: db 'hello'
world: db ' world'
expected: db 'hello world'
section .bss
align 8
args: resq 3
vec: resq 4
result: resb 16
pipefds: resd 2
