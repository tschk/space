; An earlier blocked child must not hide a later waitable zombie.
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
 call 293,ends,0,0
 expect 0
 call 56,17,0,0
 test rax,rax
 js fail
 jz first
 mov rbp,rax
 call 56,17,0,0
 test rax,rax
 js fail
 jz second
 mov r14,rax
 xor r10d,r10d
 call 61,-1,wait_status,0
 expect r14
 cmp dword[rel wait_status],0x1700
 jne fail
 mov edi,[rel ends+4]
 call 1,rdi,byte_q,1
 expect 1
 mov edi,[rel ends+4]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends]
 call 3,rdi,0,0
 expect 0
 xor r10d,r10d
 call 61,rbp,wait_status,0
 expect rbp
 cmp dword[rel wait_status],0x700
 jne fail
 call 60,42,0,0
first:
 mov edi,[rel ends+4]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends]
 call 0,rdi,buffer,1
 expect 1
 cmp byte[rel buffer],'Q'
 jne fail
 call 60,7,0,0
second:
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
byte_q: db 'Q'
section .bss
align 8
ends: resq 1
wait_status: resq 1
buffer: resb 1
section .note.GNU-stack noalloc noexec nowrite progbits
