; Retained completed children need distinct IDs despite reusable CPU domains.
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
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x1200011,0,0
 test rax,rax
 js fail
 jz child
 mov r12,rax
 mov dword[rel child_value],7
 call 56,0x1200011,0,0
 test rax,rax
 js fail
 jz child
 mov r13,rax
 cmp r12,r13
 je fail
 xor r10d,r10d
 call 61,r13,wait_status,0
 expect r13
 cmp dword[rel wait_status],0x700
 jne fail
 call 61,r12,wait_status,0
 expect r12
 cmp dword[rel wait_status],0x1700
 jne fail
 call 61,-1,wait_status,1
 expect -10
 call 60,42,0,0
child:
 mov edi,[rel child_value]
 call 60,rdi,0,0
fail:
 call 60,1,0,0
 ud2
section .data
child_value: dd 23
child_tid: dd 0
section .bss
align 8
wait_status: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
