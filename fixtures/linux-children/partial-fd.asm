; Space-only admission profile. The independent native witness owns two of13
; native descriptors, leaving exactly five duplicate slots after our six ends.
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
 xor r13d,r13d
create:
 lea r12,[rel ends]
 lea r12,[r12+r13*8]
 call 293,r12,0x80800,0
 expect 0
 mov edi,[r12+4]
 lea rsi,[rel bytes]
 add rsi,r13
 call 1,rdi,rsi,1
 expect 1
 inc r13
 cmp r13,3
 jb create
 xor r15d,r15d
attempt:
%ifdef CUMULATIVE_IRQ
 rdtsc
 shl rdx,32
 or rax,rdx
 mov r14,rax
spin:
 rdtsc
 shl rdx,32
 or rax,rdx
 sub rax,r14
 cmp rax,20000000
 jb spin
%endif
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x1200011,0,0
 expect -24
%ifdef ADMISSION_RETRY
 inc r15
 cmp r15,32
 jb attempt
 lea r10,[rel child_tid]
 xor r8d,r8d
 call 56,0x1200011,0,0
 expect -11
%endif
 cmp dword[rel child_tid],0x12345678
 jne fail
 xor r10d,r10d
 call 61,-1,wait_status,1
 expect -10
 xor r13d,r13d
verify:
 lea r12,[rel ends]
 lea r12,[r12+r13*8]
 mov edi,[r12]
 call 72,rdi,1,0
 expect 1
 mov edi,[r12]
 call 72,rdi,3,0
 expect 0x800
 mov edi,[r12+4]
 call 72,rdi,1,0
 expect 1
 mov edi,[r12+4]
 call 72,rdi,3,0
 expect 0x801
 mov edi,[r12]
 call 0,rdi,buffer,1
 expect 1
 lea rbx,[rel bytes]
 mov al,[rbx+r13]
 cmp al,[rel buffer]
 jne fail
 ; Rollback must preserve both native endpoint references, not merely bytes.
 mov edi,[r12+4]
 lea rsi,[rbx+r13]
 call 1,rdi,rsi,1
 expect 1
 mov edi,[r12]
 call 0,rdi,buffer,1
 expect 1
 lea rbx,[rel bytes]
 mov al,[rbx+r13]
 cmp al,[rel buffer]
 jne fail
 inc r13
 cmp r13,3
 jb verify
%ifndef ADMISSION_RETRY
 mov edi,[rel ends+16]
 call 3,rdi,0,0
 expect 0
 mov edi,[rel ends+20]
 call 3,rdi,0,0
 expect 0
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
 cmp dword[rel wait_status],0x1700
 jne fail
 xor r10d,r10d
 call 61,-1,wait_status,1
 expect -10
%endif
 xor r13d,r13d
close:
 lea rbx,[rel ends]
 mov edi,[rbx+r13*4]
 call 3,rdi,0,0
 expect 0
 inc r13
%ifdef ADMISSION_RETRY
 cmp r13,6
%else
 cmp r13,4
%endif
 jb close
 call 60,42,0,0
child:
 call 60,23,0,0
fail:
 call 60,1,0,0
 ud2
section .data
child_tid: dd 0x12345678
bytes: db 'ABC'
section .bss
align 8
ends: resd 6
wait_status: resq 1
buffer: resb 1
section .note.GNU-stack noalloc noexec nowrite progbits
