BITS 64
GLOBAL _start
SECTION .text
_start:
 mov r15,rsp
 cmp qword [r15],3
 jne fail
 cmp qword [r15+32],0
 jne fail
 cmp qword [r15+56],0
 jne fail
 mov rdi,[r15+8]
 lea rsi,[rel text0]
 call equal
 mov rdi,[r15+16]
 lea rsi,[rel text1]
 call equal
 mov rdi,[r15+24]
 lea rsi,[rel text2]
 call equal
 mov rdi,[r15+40]
 lea rsi,[rel env0]
 call equal
 mov rdi,[r15+48]
 lea rsi,[rel env1]
 call equal
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
