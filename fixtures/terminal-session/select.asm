; Synthetic native controls only; zero upstream application credit.
bits 64
global _start
%macro SELECT 3
 mov eax,%1
 mov edi,1
 mov rsi,%2
 xor edx,edx
 xor r10d,r10d
 mov r8,%3
 xor r9d,r9d
 syscall
%endmacro
%macro EXPECT 1
 inc r15d
 cmp rax,%1
 jne failed
%endmacro
section .text
_start:
 xor r15d,r15d
 mov r12,[rsp+16]
 cmp byte [r12],'p'
 je post
 cmp byte [r12],'w'
 je writer
 cmp byte [r12],'d'
 je denied
 mov qword [readfds],1
 mov qword [tv],0
 mov qword [tv+8],0
 SELECT 23,readfds,tv
 EXPECT 0
 cmp qword [readfds],0
 jne failed
 mov qword [readfds],1
 SELECT 270,_start,tv
 EXPECT -14
 mov qword [tv],-1
 SELECT 270,readfds,tv
 EXPECT -22
 mov qword [tv],0
 mov qword [tv+8],1000000000
 SELECT 270,readfds,tv
 EXPECT -22
 mov qword [readfds],2
 mov qword [tv+8],0
 SELECT 270,readfds,tv
 EXPECT -95
 mov qword [readfds],1
 SELECT 270,readfds,0
 EXPECT 1
 cmp qword [readfds],1
 jne failed
 xor eax,eax
 xor edi,edi
 mov rsi,sample
 mov edx,1
 syscall
 EXPECT 1
 cmp byte [sample],'a'
 jne failed
 mov qword [readfds],1
 mov qword [tv],0
 mov qword [tv+8],20000000
 SELECT 270,readfds,tv
 EXPECT 0
 cmp qword [readfds],0
 jne failed
 cmp qword [tv],0
 jne failed
 cmp qword [tv+8],0
 jne failed
 xor eax,eax
 xor edi,edi
 mov rsi,sample
 mov edx,1
 syscall
 EXPECT 1
 cmp byte [sample],'b'
 jne failed
 jmp finished
post:
 mov eax,1
 mov edi,1
 mov rsi,linefeed
 mov edx,1
 syscall
 EXPECT 1
 xor eax,eax
 xor edi,edi
 mov rsi,sample
 mov edx,1
 syscall
 EXPECT 1
 cmp byte [sample],'a'
 jne failed
 jmp finished
writer:
 xor ecx,ecx
.fill:
 mov [payload+rcx],cl
 inc ecx
 cmp ecx,1024
 jne .fill
 xor r12d,r12d
.write:
 mov eax,1
 mov edi,1
 lea rsi,[payload+r12]
 mov edx,1024
 sub rdx,r12
 syscall
 test rax,rax
 jle failed
 add r12,rax
 cmp r12,1024
 jb .write
 jne failed
 jmp finished
denied:
 mov qword [readfds],1
 mov qword [tv],0
 mov qword [tv+8],20000000
 SELECT 270,readfds,tv
 EXPECT -13
 cmp qword [readfds],1
 jne failed
 cmp qword [tv+8],20000000
 jne failed
finished:
 mov edi,42
 mov eax,60
 syscall
failed:
 lea edi,[r15+100]
 mov eax,60
 syscall
section .rodata
linefeed: db 10
section .bss
align 8
readfds: resq 1
tv: resq 2
sample: resb 1
payload: resb 1024
