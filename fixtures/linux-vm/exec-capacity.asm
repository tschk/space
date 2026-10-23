; Host self-exec succeeds77; declared Space binding-capacity profile returnsENOMEM.
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
 cmp byte[rax],'s'
 je replaced
initial:
 mov qword[rel canary],0x12345678
 call 293,ends,0x80800,0
 expect 0
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 1,r13,payload,8
 expect 8
 call 59,self_path,newargv,newenv
 expect -12
 cmp qword[rel canary],0x12345678
 jne fail
 call 72,r12,1,0
 expect 1
 call 72,r13,1,0
 expect 1
 call 0,r12,buffer,8
 expect 8
 mov rbx,[rel payload]
 cmp [rel buffer],rbx
 jne fail
 call 3,r12,0,0
 expect 0
 call 3,r13,0,0
 expect 0
 call 60,42,0,0
replaced:
 call 60,77,0,0
fail:
 call 60,99,0,0
 ud2
section .data
self_path: db '/proc/self/exe',0
arg0: db '/exec-capacity',0
arg1: db 'stage',0
payload: db 'OLDIMAGE'
align 8
newargv: dq arg0,arg1,0
newenv: dq 0
section .bss
align 8
canary: resq 1
ends: resd 2
buffer: resq 1
