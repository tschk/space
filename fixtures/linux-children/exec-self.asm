; Real clone -> execve(/proc/self/exe) replacement, inherited fds and stable PID.
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
 cmp qword[rsp],2
 jb initial
 mov rax,[rsp+16]
 cmp byte[rax],'e'
 je stage
initial:
 call 72,2,2,1
 expect 0
 call 293,ends,0x80800,0
 expect 0
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 292,r12,10,0x80000
 expect 10
 call 292,r13,11,0
 expect 11
 call 3,r12,0,0
 expect 0
 call 3,r13,0,0
 expect 0
 mov r10d,8
 call 13,13,ignore_action,0
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
 cmp dword[rel private_value],17
 jne fail
 call 72,2,1,0
 expect 1
 call 72,10,1,0
 expect 1
 call 3,11,0,0
 expect 0
 call 0,10,buffer,8
 expect 8
 cmp r14,[rel buffer]
 jne fail
 call 0,10,buffer,1
 expect 0
 call 3,10,0,0
 expect 0
 call 60,42,0,0
child:
 mov dword[rel private_value],99
 call 59,self_path,stage_argv,stage_env
 jmp fail
stage:
 cmp qword[rsp],2
 jne fail
 cmp dword[rel private_value],17
 jne fail
 call 72,2,1,0
 expect -9
 mov rax,[rsp+32]
 cmp dword[rax],0x454d4f48 ; HOME
 jne fail
 cmp word[rax+4],0x2f3d ; =/
 jne fail
 cmp byte[rax+6],0
 jne fail
 mov rax,[rsp+40]
 mov rbx,0x433d4c4c415f434c ; LC_ALL=C
 cmp qword[rax],rbx
 jne fail
 cmp byte[rax+8],0
 jne fail
 call 72,10,1,0
 expect -9
 call 72,11,1,0
 expect 0
 mov r10d,8
 call 13,13,0,old_action
 expect 0
 cmp qword[rel old_action],1
 jne fail
 call 39,0,0,0
 mov [rel pid_buffer],rax
 call 1,11,pid_buffer,8
 expect 8
 call 60,7,0,0
fail:
 call 60,1,0,0
 ud2
section .data
private_value: dd 17
child_tid: dd 0
pid_buffer: dq 0
ignore_action: dq 1,0,0,0
self_path: db '/proc/self/exe',0
program_name: db '/child-self',0
stage_name: db 'exec-stage',0
env_home: db 'HOME=/',0
env_locale: db 'LC_ALL=C',0
align 8
stage_argv: dq program_name,stage_name,0
stage_env: dq env_home,env_locale,0
section .bss
align 8
ends: resq 1
wait_status: resq 1
buffer: resq 1
old_action: resq 4
section .note.GNU-stack noalloc noexec nowrite progbits
