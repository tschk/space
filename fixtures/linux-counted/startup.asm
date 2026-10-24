; Ordinary ELF verifies actual argc/argv/envp/auxv; host and Space exit42.
BITS 64
GLOBAL _start
%ifndef ARGC
 %define ARGC 3
%endif
SECTION .text
_start:
 mov r15,rsp
 test r15,15
 jnz fail
 cmp qword[r15],ARGC
 jne fail
 cmp qword[r15+(ARGC+1)*8],0
 jne fail
 cmp qword[r15+(ARGC+4)*8],0
 jne fail
 mov rdi,[r15+8]
 lea rsi,[rel text0]
 call equal
%if ARGC >= 2
 mov rdi,[r15+16]
 lea rsi,[rel text1]
 call equal
%endif
%if ARGC >= 3
 mov rdi,[r15+24]
 lea rsi,[rel text2]
 call equal
%endif
 mov rdi,[r15+(ARGC+2)*8]
 lea rsi,[rel env0]
 call equal
 mov rdi,[r15+(ARGC+3)*8]
 lea rsi,[rel env1]
 call equal
 lea r14,[r15+(ARGC+5)*8]
 xor r12d,r12d
 mov r13d,64
aux:
 mov rax,[r14]
 mov rdx,[r14+8]
 test rax,rax
 jz auxdone
 cmp eax,3
 jne notphdr
 cmp dword[rdx],1 ; first PT_LOAD in this linked ELF
 jne fail
 or r12d,1
notphdr:
 cmp eax,4
 jne notphent
 cmp rdx,56
 jne fail
 or r12d,2
notphent:
 cmp eax,5
 jne notphnum
 cmp rdx,2
 jb fail
 or r12d,4
notphnum:
 cmp eax,6
 jne notpagesz
 cmp rdx,4096
 jne fail
 or r12d,8
notpagesz:
 cmp eax,9
 jne notentry
 lea rax,[rel _start]
 cmp rdx,rax
 jne fail
 or r12d,16
notentry:
 cmp qword[r14],25
 jne notrandom
 test rdx,rdx
 jz fail
 mov rax,[rdx] ; genuinely readable16 entropy bytes
 mov rax,[rdx+8]
 or r12d,32
notrandom:
 cmp qword[r14],31
 jne nextround
 test rdx,rdx
 jz fail
 cmp byte[rdx],'/' ; host executable pathname differs from custom argv0
 jne fail
 or r12d,64
nextround:
 add r14,16
 dec r13d
 jnz aux
 jmp fail
auxdone:
 cmp qword[r14+8],0
 jne fail
 cmp r12d,127
 jne fail
 mov edi,42
 jmp exit
equal:
 mov al,[rdi]
 cmp al,[rsi]
 jne fail
 inc rdi
 inc rsi
 test al,al
 jnz equal
 ret
fail:
 mov edi,1
exit:
 mov eax,60
 syscall
 ud2
SECTION .rodata
text0: db '/high-source',0
text1: db 'hello-from-high-source',0
text2: db 'third-high-source',0
env0: db 'LC_ALL=C',0
env1: db 'HOME=/',0
