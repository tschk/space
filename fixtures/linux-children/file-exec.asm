; Real file: clone inherits one open description, exec closes child fd10 only.
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
 mov rax,[rsp+16]
 cmp byte[rax],'e'
 je stage
 mov rdi,rax
 call 2,rdi,0x80002,0
 test rax,rax
 js fail
 mov r12,rax
 call 72,r12,1,0
 expect 1
 call 0,r12,buffer,2
 expect 2
 cmp word[rel buffer],0x6261
 jne fail
 call 292,r12,10,0x80000
 expect 10
 call 292,r12,11,0
 expect 11
 call 292,r12,12,0
 expect 12
 call 3,r12,0,0
 expect 0
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
 call 72,10,1,0
 expect 1
 call 72,11,1,0
 expect 0
 call 72,12,1,0
 expect 0
 call 0,11,buffer,1
 expect 1
 cmp byte[rel buffer],10
 jne fail
 call 8,10,0,0
 expect 0
 call 0,10,buffer,7
 expect 7
 mov rax,[rel buffer]
 shl rax,8
 mov rbx,0x0a59586463626100
 cmp rax,rbx
 jne fail
 call 3,10,0,0
 expect 0
 call 3,11,0,0
 expect 0
 call 3,12,0,0
 expect 0
 call 60,42,0,0
child:
 ; Descriptor flags belong to the child table, not the shared file offset.
 call 72,12,2,1
 expect 0
 call 72,12,1,0
 expect 1
 mov dword[rel private_value],99
 call 59,self_path,stage_argv,stage_env
 jmp fail
stage:
 cmp qword[rsp],2
 jne fail
 cmp dword[rel private_value],17
 jne fail
 call 72,10,1,0
 expect -9
 call 72,12,1,0
 expect -9
 call 72,11,1,0
 expect 0
 call 0,11,buffer,2
 expect 2
 cmp word[rel buffer],0x6463
 jne fail
 call 1,11,replacement,2
 expect 2
 call 3,11,0,0
 expect 0
 call 60,7,0,0
fail:
 call 60,1,0,0
 ud2
section .data
private_value: dd 17
child_tid: dd 0
replacement: db 'XY'
self_path: db '/proc/self/exe',0
program_name: db '/file-child',0
stage_name: db 'exec-stage',0
align 8
stage_argv: dq program_name,stage_name,0
stage_env: dq 0
section .bss
align 8
wait_status: resq 1
buffer: resq 1
section .note.GNU-stack noalloc noexec nowrite progbits
