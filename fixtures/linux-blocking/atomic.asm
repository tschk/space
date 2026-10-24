; Two concurrent writers publish3000-byte records into a4096-byte pipe.
; Each record must remain contiguous even across scheduler handoffs.
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
 lea r15,[rel record_a]
 call 56,17,0,0
 test rax,rax
 js fail
 jz child
 mov rbp,rax
 lea r15,[rel record_b]
 call 56,17,0,0
 test rax,rax
 js fail
 jz child
 mov r14,rax
 mov edi,[rel ends+4]
 call 3,rdi,0,0
 expect 0
 xor r12d,r12d
 xor r15d,r15d
read:
 mov edi,[rel ends]
 call 0,rdi,buffer,2048
 test rax,rax
 js fail
 jz eof
 mov r8,rax
 lea rbx,[rel buffer]
verify:
 test r12,r12
 jnz compare
 mov r13b,[rbx]
 cmp r13b,'A'
 je count_a
 cmp r13b,'B'
 jne fail
 inc dword[rel records_b]
 jmp boundary
count_a:
 inc dword[rel records_a]
boundary:
 mov r12d,3000
compare:
 cmp byte[rbx],r13b
 jne fail
 dec r12
 inc r15
 cmp r15,12000
 ja fail
 inc rbx
 dec r8
 jnz verify
 jmp read
eof:
 cmp r15,12000
 jne fail
 test r12,r12
 jnz fail
 cmp dword[rel records_a],2
 jne fail
 cmp dword[rel records_b],2
 jne fail
 mov edi,[rel ends]
 call 3,rdi,0,0
 expect 0
 xor r10d,r10d
 call 61,rbp,wait_status,0
 expect rbp
 cmp dword[rel wait_status],0x1700
 jne fail
 xor r10d,r10d
 call 61,r14,wait_status,0
 expect r14
 cmp dword[rel wait_status],0x1700
 jne fail
 call 60,42,0,0
child:
 mov edi,[rel ends]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends+4]
 call 1,rdi,r15,3000
 expect 3000
 mov edi,[rel ends+4]
 call 1,rdi,r15,3000
 expect 3000
 mov edi,[rel ends+4]
 call 3,rdi,0,0
 expect 0
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
record_a: times 3000 db 'A'
record_b: times 3000 db 'B'
section .bss
align 8
ends: resq 1
wait_status: resq 1
records_a: resd 1
records_b: resd 1
buffer: resb 2048
section .note.GNU-stack noalloc noexec nowrite progbits
