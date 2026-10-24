; Valid-buffer Linux /dev/null oracle; no assumption about unused bad pointers.
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
 call 2,path,0x80002,0
 test rax,rax
 js fail
 mov r12,rax
 call 72,r12,1,0
 expect 1
 call 292,r12,10,0
 expect 10
 call 3,r12,0,0
 expect 0
 call 72,10,1,0
 expect 0
 call 72,10,3,0
 and eax,3
 expect 2
 call 5,10,stat_buffer,0
 expect 0
 mov eax,[rel stat_buffer+24]
 and eax,0xf000
 expect 0x2000
 cmp qword[rel stat_buffer+40],0x103
 jne fail
 call 0,10,buffer,5000
 expect 0
 call 1,10,buffer,5000
 expect 5000
 call 8,10,123,0
 expect 0
%ifdef CHECKED_BUFFER_PROFILE
 ; Space's explicit checked-buffer boundary is stricter than Linux's null
 ; fast path. This mode is never counted as Linux host agreement.
 call 0,10,0x1000,5000
 expect -14
 call 1,10,0x1000,5000
 expect -14
 call 1,10,buffer,65537
 expect -22
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
 cmp dword[rel wait_status],0x700
 jne fail
 call 1,10,buffer,5000
 expect 5000
 call 3,10,0,0
 expect 0
 call 0,10,buffer,1
 expect -9
 ; Access modes are enforced even though the object stores no bytes.
 call 2,path,0,0
 test rax,rax
 js fail
 mov r12,rax
 call 1,r12,buffer,1
 expect -9
 call 3,r12,0,0
 expect 0
 call 2,path,1,0
 test rax,rax
 js fail
 mov r12,rax
 call 0,r12,buffer,1
 expect -9
 call 3,r12,0,0
 expect 0
 call 60,42,0,0
child:
 call 33,10,0,0
 expect 0
 call 33,10,1,0
 expect 1
 call 3,10,0,0
 expect 0
 call 0,0,buffer,5000
 expect 0
 call 1,1,buffer,5000
 expect 5000
 call 3,0,0,0
 expect 0
 call 3,1,0,0
 expect 0
 call 60,7,0,0
fail:
 call 60,1,0,0
 ud2
section .data
path: db '/dev/null',0
child_tid: dd 0
section .bss
align 8
wait_status: resq 1
stat_buffer: resb 144
buffer: resb 5000
section .note.GNU-stack noalloc noexec nowrite progbits
