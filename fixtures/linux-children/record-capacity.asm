; Explicit Space profile: root + at most7 child registrations for one job.
; Reaping does not reset that bounded execution-work budget; job teardown does.
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
 xor r12d,r12d
 xor r15d,r15d
create:
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x1200011,0,0
 test rax,rax
 js fail
 jz child
 cmp rax,r15
 jle fail
 mov r15,rax
 lea rbx,[rel pids]
 mov [rbx+r12*8],rax
 inc r12
 inc dword[rel child_status]
 cmp r12,7
 jb create
 call 56,0x1200011,0,0
 expect -11
reap:
 dec r12
 lea rbx,[rel pids]
 mov r14,[rbx+r12*8]
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 lea eax,[r12+1]
 shl eax,8
 cmp eax,[rel wait_status]
 jne fail
 test r12,r12
 jnz reap
 call 61,-1,wait_status,1
 expect -10
 lea r10,[rel child_tid]
 call 56,0x1200011,0,0
 expect -11
 call 60,42,0,0
child:
 mov edi,[rel child_status]
 call 60,rdi,0,0
fail:
 call 60,1,0,0
 ud2
section .data
child_status: dd 1
child_tid: dd 0
section .bss
align 8
pids: resq 7
wait_status: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
