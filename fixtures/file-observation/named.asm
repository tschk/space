BITS 64
GLOBAL _start
section .text
_start:
 cld
 mov r12,rsp
 cmp qword [r12],3
 jne fail
 mov rsi,[r12+8]
 lea rdi,[rel relative]
 mov ecx,relative_end-relative
 repe cmpsb
 jne fail
 mov rsi,[r12+16]
 lea rdi,[rel token]
 mov ecx,token_end-token
 repe cmpsb
 jne fail
 mov rsi,[r12+24]
 lea rdi,[rel third]
 mov ecx,third_end-third
 repe cmpsb
 jne fail
 cmp qword [r12+32],0
 jne fail
 cmp qword [r12+56],0
 jne fail
 lea r13,[r12+64]
 mov ecx,16
.aux:
 cmp qword [r13],31
 je .found
 add r13,16
 loop .aux
 jmp fail
.found:
 mov rsi,[r13+8]
 lea rdi,[rel identity]
 mov ecx,identity_end-identity
 repe cmpsb
 jne fail
 mov eax,267
 mov rdi,-100
 lea rsi,[rel link]
 lea rdx,[rel buffer]
 mov r10d,64
 syscall
 cmp rax,identity_end-identity-1
 jne fail
 lea rsi,[rel buffer]
 lea rdi,[rel identity]
 mov ecx,identity_end-identity-1
 repe cmpsb
 jne fail
 cmp byte [rel buffer+identity_end-identity-1],0xa5
 jne fail
 mov eax,60
 mov edi,42
 syscall
 ud2
fail:
 mov eax,60
 mov edi,99
 syscall
 ud2
section .rodata
relative: db 'relative',0
relative_end:
token: db 'token',0
token_end:
third: db 'third',0
third_end:
identity: db '/stored-name',0
identity_end:
link: db '/proc/self/exe',0
section .data
buffer: times 64 db 0xa5
