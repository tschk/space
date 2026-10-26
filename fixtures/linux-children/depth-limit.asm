; Explicit Space profile: rootdepth0, childdepth1..3, depth4 returnsEAGAIN.
bits 64
global _start
%macro expect 1
 cmp rax,%1
 jne fail
%endmacro
%macro call 4
 mov eax,%1
 mov rdi,%2
 mov rsi,%3
 mov rdx,%4
 syscall
%endmacro
section .text
_start:
node:
 mov r15d,[rel depth]
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x1200011,0,0
 cmp r15,3
 je limited
 test rax,rax
 js fail
 jz child
 mov r14,rax
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 cmp dword[rel wait_status],0x2a00
 jne fail
 cmp r15d,[rel depth]
 jne fail
 call 60,42,0,0
child:
 inc dword[rel depth]
 jmp node
limited:
 expect -11
 call 60,42,0,0
fail:
 call 60,1,0,0
 ud2
section .data
depth: dd 0
child_tid: dd 0
section .bss
align 8
wait_status: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
