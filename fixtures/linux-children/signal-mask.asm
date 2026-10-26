; Actual kernel sigset layout, refusal validation and clone mask inheritance.
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
 mov r10d,16
 call 14,0,all_mask,previous
 expect -22
 mov r10d,8
 call 14,99,all_mask,previous
 expect -22
 call 14,0,0x1000,previous
 expect -14
 call 14,0,all_mask,0x1000
 expect -14
 cmp qword[rel previous],0x1234
 jne fail
 ; Linux may apply the requested mask before failing an invalid old-mask
 ; copyout. Normalize explicitly before testing valid mask inheritance.
 call 14,2,zero_mask,0
 expect 0
 ; SIGKILL and SIGSTOP cannot be blocked, including by the raw syscall.
 call 14,2,all_mask,previous
 expect 0
 cmp qword[rel previous],0
 jne fail
 call 14,0,0,previous
 expect 0
 cmp qword[rel previous],-262401
 jne fail
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
 cmp dword[rel wait_status],0x1700
 jne fail
 mov r10d,8
 call 14,0,0,previous
 expect 0
 cmp qword[rel previous],-262401
 jne fail
 call 14,2,zero_mask,previous
 expect 0
 call 60,42,0,0
child:
 mov r10d,8
 call 14,0,0,previous
 expect 0
 cmp qword[rel previous],-262401
 jne fail
 call 14,2,zero_mask,previous
 expect 0
 call 14,0,0,previous
 expect 0
 cmp qword[rel previous],0
 jne fail
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
all_mask: dq -1
zero_mask: dq 0
previous: dq 0x1234
child_tid: dd 0
section .bss
align 8
wait_status: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
