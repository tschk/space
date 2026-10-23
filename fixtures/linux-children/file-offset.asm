; argv1 names a real seeded seven-byte file: abcdef\n. No hosted file proxy.
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
 mov rdi,[rsp+16]
 call 2,rdi,2,0
 test rax,rax
 js fail
 mov r12,rax
 call 0,r12,buffer,2
 expect 2
 cmp word[rel buffer],0x6261
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
 ; The child's read/write advanced the one inherited native open description.
 call 0,r12,buffer,1
 expect 1
 cmp byte[rel buffer],10
 jne fail
 call 8,r12,0,0
 expect 0
 call 0,r12,buffer,7
 expect 7
 mov rax,[rel buffer]
 shl rax,8
 mov rbx,0x0a59586463626100
 cmp rax,rbx
 jne fail
 call 3,r12,0,0
 expect 0
 call 60,42,0,0
child:
 call 0,r12,buffer,2
 expect 2
 cmp word[rel buffer],0x6463
 jne fail
 call 1,r12,replacement,2
 expect 2
 ; The child's descriptor close must not revoke the parent's binding.
 call 3,r12,0,0
 expect 0
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
replacement: db 'XY'
child_tid: dd 0
section .bss
align 8
wait_status: resq 1
buffer: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
