; Neither process can run its write until its read completes: a closed graph.
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
 mov edi,[rel ends+4]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends+8]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends]
 call 0,rdi,buffer,1
 expect 1
 mov edi,[rel ends+12]
 call 1,rdi,buffer,1
 jmp fail
child:
 mov edi,[rel ends]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends+12]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends+8]
 call 0,rdi,buffer,1
 expect 1
 mov edi,[rel ends+4]
 call 1,rdi,buffer,1
fail:
 call 60,1,0,0
 ud2
section .bss
align 8
ends: resq 2
buffer: resb 1
section .note.GNU-stack noalloc noexec nowrite progbits
