; Blocked SIGPIPE queues in one process, clone clears child's pending set,
; and unblocking delivers the original default signal after real progress.
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
 call 293,progress_ends,0x800,0
 expect 0
 mov r12d,[rel progress_ends]
 mov r13d,[rel progress_ends+4]
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x1200011,0,0
 test rax,rax
 js fail
 jz child
 mov r14,rax
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 mov eax,[rel wait_status]
 and eax,0x7f
 cmp eax,13
 jne fail
 call 3,r13,0,0
 expect 0
 call 0,r12,buffer,2
 expect 2
 cmp word[rel buffer],0x5051 ; QP
 jne fail
 call 0,r12,buffer,1
 expect 0
 call 3,r12,0,0
 expect 0
 call 60,42,0,0
child:
 call 3,r12,0,0
 expect 0
 call 293,broken_ends,0x800,0
 expect 0
 mov edi,[rel broken_ends]
 call 3,rdi,0,0
 expect 0
 mov r15d,[rel broken_ends+4]
 mov r10d,8
 call 14,0,pipe_mask,0
 expect 0
 call 1,r15,progress_p,1
 expect -32
 ; The new grandchild inherits the mask but must not inherit pending SIGPIPE.
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x1200011,0,0
 test rax,rax
 js fail
 jz grandchild
 mov r14,rax
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 cmp dword[rel wait_status],0x1700
 jne fail
 call 1,r13,progress_p,1
 expect 1
 mov r10d,8
 call 14,2,zero_mask,0
 jmp fail ; Pending default SIGPIPE must terminate before returning.
grandchild:
 mov r10d,8
 call 14,2,zero_mask,0
 expect 0
 call 1,r13,progress_q,1
 expect 1
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
pipe_mask: dq 4096
zero_mask: dq 0
progress_p: db 'P'
progress_q: db 'Q'
child_tid: dd 0
section .bss
align 8
progress_ends: resq 1
broken_ends: resq 1
wait_status: resq 1
buffer: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
