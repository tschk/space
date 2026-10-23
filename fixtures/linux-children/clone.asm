; Synthetic ordinary Linux clone/wait contract. Identical bytes run on host/Space.
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
 call 293,ends,0x800,0
 expect 0
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 movdqu xmm0,[rel fx_canary]
 ; Match the real static-glibc BusyBox clone flags and private child_tidptr.
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
 movq rax,xmm0
 cmp rax,[rel fx_canary]
 jne fail
 movhlps xmm1,xmm0
 movq rax,xmm1
 cmp rax,[rel fx_canary+8]
 jne fail
 ; Child-first is a scheduling policy; Linux wait semantics stay ordinary.
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 cmp dword[rel wait_status],0x1700
 jne fail
 cmp dword[rel private_value],17
 jne fail
 cmp dword[rel child_tid],0x12345678
 jne fail
 ; Open-description status is shared across processes, unlike descriptor flags.
 call 72,r13,3,0
 expect 1
 ; Parent's descriptor survives the child's close, with buffered child data.
 call 3,r13,0,0
 expect 0
 call 0,r12,buffer,8
 expect 8
 cmp r14,[rel buffer]
 jne fail
 call 0,r12,buffer,1
 expect 0
 call 3,r12,0,0
 expect 0
 mov r10d,0
 call 61,r14,wait_status,1
 expect -10
 call 60,42,0,0
child:
 movq rax,xmm0
 cmp rax,[rel fx_canary]
 jne fail
 pxor xmm0,xmm0
 call 72,r13,4,1
 expect 0
 mov dword[rel private_value],99
 call 186,0,0,0
 cmp eax,[rel child_tid]
 jne fail
 mov [rel child_pid],rax
 call 3,r12,0,0
 expect 0
 call 1,r13,child_pid,8
 expect 8
 call 3,r13,0,0
 expect 0
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
fx_canary: dq 0x12345678abcdef01,0x324567890abcdef1
private_value: dd 17
child_tid: dd 0x12345678
child_pid: dq 0
section .bss
ends: resq 1
wait_status: resq 1
buffer: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
