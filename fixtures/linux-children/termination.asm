; Child stop causes must become real wait signals, never exit-status arithmetic.
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
%ifdef SIGPIPE
 call 293,ends,0,0
 expect 0
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 3,r12,0,0
 expect 0
%endif
 mov eax,56
 mov edi,0x1200011
 xor esi,esi
 xor edx,edx
 lea r10,[rel child_tid]
 xor r8d,r8d
 syscall
 test rax,rax
 js fail
 jz child
 mov r14,rax
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 mov eax,[rel wait_status]
%ifdef NORMAL_EXIT_134
 cmp eax,0x8600
%elifdef NORMAL_EXIT_141
 cmp eax,0x8d00
%else
 and eax,0x7f ; WTERMSIG ignores the optional host core-dump flag.
%ifdef SIGPIPE
 cmp eax,13
%elifdef PAGE_FAULT
 cmp eax,11
%elifdef GENERAL_PROTECTION
 cmp eax,11
%elifdef DEADLINE
 cmp eax,9
%else
 cmp eax,4
%endif
%endif
 jne fail
 call 60,42,0,0
child:
%ifdef NORMAL_EXIT_134
 call 60,134,0,0
%elifdef NORMAL_EXIT_141
 call 60,141,0,0
%elifdef SIGPIPE
 call 1,r13,message,1
 jmp fail
%elifdef PAGE_FAULT
 mov rax,[0x1000]
 jmp fail
%elifdef GENERAL_PROTECTION
 cli
 jmp fail
%elifdef DEADLINE
 jmp $
%else
 ud2
%endif
fail:
 call 60,1,0,0
 ud2
section .data
message: db 'x'
child_tid: dd 0
section .bss
align 8
ends: resq 1
wait_status: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
