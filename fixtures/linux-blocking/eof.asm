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
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 56,17,0,0
 test rax,rax
 js fail
 jz child
 mov r14,rax
%ifndef DEADLOCK
 call 3,r12,0,0
 expect 0
%endif
%ifdef DEADLOCK
 ; Retain the writer but join the child in a read: no runnable producer.
 call 0,r12,buffer,1
 jmp fail
%elifdef RUNNABLE_IRQ
spin:
 jmp spin
%else
 call 3,r13,0,0
 expect 0
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 cmp dword[rel wait_status],0x1700
 jne fail
 call 60,42,0,0
%endif
child:
 call 3,r13,0,0
 expect 0
 call 0,r12,buffer,1
 expect 0
 call 3,r12,0,0
 expect 0
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .bss
align 8
ends: resq 1
wait_status: resq 1
buffer: resb 1
section .note.GNU-stack noalloc noexec nowrite progbits
