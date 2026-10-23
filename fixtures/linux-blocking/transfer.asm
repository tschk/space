; Ordinary Linux clone/pipe ELF: one write spans the real4096-byte ring.
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
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 72,r12,1031,4096
 expect 4096
 mov eax,56
 mov edi,17
 xor esi,esi
 xor edx,edx
 xor r10d,r10d
 xor r8d,r8d
 syscall
 test rax,rax
 js fail
 jz child
 mov r14,rax
 call 3,r13,0,0
 expect 0
%ifdef ROOT_FAULT
 ud2
%endif
 xor r15d,r15d
read:
 call 0,r12,buffer,2048
 test rax,rax
 js fail
 jz eof
 lea rbx,[rel payload]
 add rbx,r15
 lea rsi,[rel buffer]
 mov rcx,rax
 add r15,rax
 cmp r15,11000
 ja fail
compare:
 mov dl,[rbx]
 cmp dl,[rsi]
 jne fail
 inc rbx
 inc rsi
 dec rcx
 jnz compare
 jmp read
eof:
 cmp r15,11000
 jne fail
 call 3,r12,0,0
 expect 0
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
%ifdef CHILD_FAULT
 cmp dword[rel wait_status],4
%else
 cmp dword[rel wait_status],0x1700
%endif
 jne fail
 call 60,42,0,0
child:
 call 3,r12,0,0
 expect 0
 call 1,r13,payload,11000
 expect 11000
%ifdef CHILD_FAULT
 ud2
%endif
 call 3,r13,0,0
 expect 0
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
payload:
%assign i 0
%rep 2750
 dd i
%assign i i+1
%endrep
section .bss
align 8
ends: resq 1
wait_status: resq 1
buffer: resb 2048
section .note.GNU-stack noalloc noexec nowrite progbits
