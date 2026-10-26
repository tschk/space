; Failed exec requests must return real errors and preserve the live image/fds.
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
 call 39,0,0,0
 mov r14,rax
 call 293,ends,0x800,0
 expect 0
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 1,r13,message,4
 expect 4
 call 59,missing_path,valid_argv,valid_env
 expect -2
 call 59,0x1000,valid_argv,valid_env
 expect -14
 call 59,self_path,0x1000,valid_env
 expect -14
 call 59,self_path,bad_argv,valid_env
 expect -14
 call 59,self_path,valid_argv,0x1000
 expect -14
 call 39,0,0,0
 expect r14
 cmp dword[rel private_value],17
 jne fail
 call 0,r12,buffer,4
 expect 4
 cmp dword[rel buffer],0x444f4f47 ; GOOD
 jne fail
 call 3,r12,0,0
 expect 0
 call 3,r13,0,0
 expect 0
 call 60,42,0,0
fail:
 call 60,1,0,0
 ud2
section .data
private_value: dd 17
message: db 'GOOD'
self_path: db '/proc/self/exe',0
missing_path: db '/no-child-image',0
program_name: db '/child-exec-refusal',0
align 8
valid_argv: dq program_name,0
bad_argv: dq program_name,0x1000,0
valid_env: dq 0
section .bss
align 8
ends: resq 1
buffer: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
