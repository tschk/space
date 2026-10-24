; Finite10000-round two-pipe ping-pong. Host completes42; Space's explicit
;4096 admitted-work limit must cancel with edge126 before this finite end.
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
 call 293,ends+8,0,0
 expect 0
 call 56,17,0,0
 test rax,rax
 js fail
 jz child
 mov r14,rax
 mov edi,[rel ends]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends+12]
 call 3,rdi,0,0
 expect 0
 xor r15d,r15d
parent_loop:
 mov edi,[rel ends+4]
 call 1,rdi,payload,1
 expect 1
 mov edi,[rel ends+8]
 call 0,rdi,buffer,1
 expect 1
 cmp byte[rel buffer],'Q'
 jne fail
 inc r15
 cmp r15,10000
 jb parent_loop
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 cmp dword[rel wait_status],0x1700
 jne fail
 call 60,42,0,0
child:
 mov edi,[rel ends+4]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends+8]
 call 3,rdi,0,0
 expect 0
 xor r15d,r15d
child_loop:
 mov edi,[rel ends]
 call 0,rdi,buffer,1
 expect 1
 cmp byte[rel buffer],'Q'
 jne fail
 mov edi,[rel ends+12]
 call 1,rdi,buffer,1
 expect 1
 inc r15
 cmp r15,10000
 jb child_loop
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
payload: db 'Q'
section .bss
align 8
ends: resq 2
wait_status: resq 1
buffer: resb 1
section .note.GNU-stack noalloc noexec nowrite progbits
