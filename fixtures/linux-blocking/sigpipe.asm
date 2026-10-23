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
 mov edi,[rel ends]
 call 72,rdi,1031,4096
 expect 4096
 call 56,17,0,0
 test rax,rax
 js fail
 jz child
 mov r14,rax
 mov edi,[rel ends+4]
 call 3,rdi,0,0
 expect 0
 ; This byte proves the large write published real data before reader closure.
 mov edi,[rel ends]
 call 0,rdi,buffer,1
 expect 1
 cmp byte[rel buffer],'P'
 jne fail
 mov edi,[rel ends]
 call 3,rdi,0,0
 expect 0
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
%ifdef IGNORE
 cmp dword[rel wait_status],0x1700
%else
 cmp dword[rel wait_status],13
%endif
 jne fail
 call 60,42,0,0
child:
 mov edi,[rel ends]
 call 3,rdi,0,0
 expect 0
%ifdef IGNORE
 mov r10d,8
 call 13,13,ignore_action,0
 expect 0
%endif
%ifdef MASKED
 mov r10d,8
 call 14,0,signal_mask,0
 expect 0
%endif
 mov edi,[rel ends+4]
 call 1,rdi,payload,8192
%ifdef IGNORE
 test rax,rax
 jle fail
 cmp rax,8192
 jae fail
 mov edi,[rel ends+4]
 call 1,rdi,payload,1
 expect -32
 call 60,23,0,0
%elifdef MASKED
 test rax,rax
 jle fail
 cmp rax,8192
 jae fail
 mov r10d,8
 call 14,1,signal_mask,0
 jmp fail
%else
 jmp fail
%endif
fail:
 call 60,1,0,0
 ud2
section .data
payload: times 8192 db 'P'
ignore_action: dq 1,0,0,0
signal_mask: dq 1 << 12
section .bss
align 8
ends: resq 1
wait_status: resq 1
buffer: resb 1
section .note.GNU-stack noalloc noexec nowrite progbits
