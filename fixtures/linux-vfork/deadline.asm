bits 64
global _start
section .text
_start:
 mov eax,58
 syscall
 test rax,rax
 js fail
 jz child
 mov rdi,rax
 cmp qword[rel shared],19
 jne fail
 mov eax,61
 lea rsi,[rel status]
 xor edx,edx
 xor r10d,r10d
 syscall
 test rax,rax
 js fail
 cmp dword[rel status],9
 jne fail
 mov edi,42
 jmp exit
child:
 mov qword[rel shared],19
spin: pause
 jmp spin
fail:
 mov edi,1
exit:
 mov eax,60
 syscall
section .data
shared: dq 17
section .bss
status: resq 1
