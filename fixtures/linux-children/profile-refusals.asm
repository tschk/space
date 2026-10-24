; Space's explicitly bounded child-process admission contract, NOT a Linux
; agreement oracle. Linux accepts some operations this profile refuses.
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
 cmp qword[rsp],17
 je fail ; An over-limit exec must not replace this image successfully.
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x111,0,0 ; CLONE_VM|SIGCHLD
 expect -38
 call 56,0x411,0,0 ; CLONE_FILES|SIGCHLD
 expect -38
 call 56,0x10011,0,0 ; CLONE_THREAD|SIGCHLD
 expect -38
 call 56,0x80011,0,0 ; CLONE_SETTLS|SIGCHLD
 expect -38
 call 56,65,0,0
 expect -22
 call 56,18,0,0
 expect -38
 call 56,0x1200011,stack_end-16,0
 expect -38
 mov r10d,0x1000
 call 56,0x1200011,0,0
 expect -14
 xor r10d,r10d
 call 56,0x1200011,0,0
 expect -14
 call 59,self_path,too_many_args,empty_env
 expect -7
 call 59,self_path,too_long_args,empty_env
 expect -7
 ; An actual completed child must survive rejected wait requests.
 lea r10,[rel child_tid]
 call 56,0x1200011,0,0
 test rax,rax
 js fail
 jz child
 mov r12,rax
 xor r10d,r10d
 call 61,r12,wait_status,0x10
 expect -38
 call 61,r12,0x1000,0
 expect -14
 mov r10d,0x1000
 call 61,r12,wait_status,0
 expect -14
 lea r10,[rel usage]
 call 61,r12,wait_status,0
 expect -38
 xor r10d,r10d
 call 61,r12,wait_status,0
 expect r12
 cmp dword[rel wait_status],0x1700
 jne fail
 call 61,r12,wait_status,0
 expect -10
 ; statusNULL is a real discard, not a successful wait stub.
 lea r10,[rel child_tid]
 call 56,0x1200011,0,0
 test rax,rax
 js fail
 jz child
 mov r12,rax
 xor r10d,r10d
 call 61,r12,0,1
 expect r12
 call 61,r12,0,1
 expect -10
 call 60,42,0,0
child:
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
self_path: db '/proc/self/exe',0
program_name: db '/child-refusals',0
long_argument: times 600 db 'x'
 db 0
align 8
too_many_args: times 17 dq program_name
 dq 0
too_long_args: dq program_name,long_argument,0
empty_env: dq 0
child_tid: dd 0
section .bss
align 8
wait_status: resq 1
usage: resb 144
stack_buffer: resb 8192
stack_end:
section .note.GNU-stack noalloc noexec nowrite progbits
