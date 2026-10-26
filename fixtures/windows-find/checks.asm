; Separate application-profile fixture: high preferred base and three sections.
BITS 64
section .headers start=0 vstart=0x140000000
image:
    dw 0x5A4D
    times 60-($-$$) db 0
    dd 128
    times 128-($-$$) db 0
    dd 0x4550
    dw 0x8664, 3
    dd 0, 0, 0
    dw 240, 0x22E
    dw 0x20B
    db 0, 0
    dd 4096, 7168, 0
    dd 0x1000, 0x1000
    dq image
    dd 4096, 512
    dw 6, 0, 0, 0, 6, 0
    dd 0, 0x7000, 512, 0
    dw 3, 0x160
    dq 0x10000, 0x1000, 0x10000, 0x1000
    dd 0, 16
    dq 0
    dd 0x3000, 40
    times 10 dq 0
    dd 0x3200, 104
    times 3 dq 0
    db '.text', 0, 0, 0
    dd 4096, 0x1000, 4096, 512, 0, 0
    dw 0, 0
    dd 0x60000020
    db '.rdata', 0, 0
    dd 4096, 0x3000, 3072, 4608, 0, 0
    dw 0, 0
    dd 0x40000040
    db '.data', 0, 0, 0
    dd 8192, 0x5000, 4096, 7680, 0, 0
    dw 0, 0
    dd 0xC0000040


%macro api 1
 call [r14+%1*8]
%endmacro
%macro check 1
 cmp rax,%1
 jne fail
%endmacro
%macro error 1
 api 7
 check %1
%endmacro
section .text start=512 vstart=0x140001000
entry:
 sub rsp,72
 mov rbx,0x140005000
 mov r14,0x140003200
 mov ecx,0x12345678
 api 8
 lea rcx,[rbx+256]
 lea rdx,[rbx+4096]
 mov eax,[rbx]
 cmp eax,16
 je stale_activation
 cmp eax,17
 je fls_callback
 cmp eax,14
 je firstw
 cmp eax,15
 je extended
 cmp eax,6
 je capacity
 cmp eax,7
 je refuse
 cmp eax,8
 je quota
 cmp eax,2
 je extended
 cmp eax,3
 je extended
 cmp eax,1
 je firstw
 api 0
 jmp opened
firstw:
 api 1
 jmp opened
extended:
 xor edx,edx
 lea r8,[rbx+4096]
 xor r9d,r9d
 mov qword [rsp+32],0
 mov qword [rsp+40],0
 cmp eax,15
 jne .defaultflags
 mov edx,1
 mov qword [rsp+40],1
.defaultflags:
 cmp eax,3
 je exa
 api 6
 jmp opened
exa:
 api 5
opened:
 cmp rax,0
 jle fail
 mov r12,rax
 error 0x12345678
 cmp qword [rbx],9
 jb .ordinary
 cmp qword [rbx],12
 jbe revoke
.ordinary:
 cmp qword [rbx],4
 je fault
 cmp qword [rbx],5
 je spin
 ; Compare every defined and reserved byte against an independent host oracle.
 lea rsi,[rbx+4096]
 lea rdi,[rbx+2048]
 mov rcx,[rbx+8]
 repe cmpsb
 jne fail
 cmp qword [rbx],13
 jae at_eof
 ; A bad next output must leave both the accepted bytes and cursor intact.
 mov rcx,r12
 mov rdx,0x70000000
 cmp qword [rbx],1
 je .badw
 cmp qword [rbx],2
 je .badw
 api 2
 jmp .badnext
.badw:
 api 3
.badnext:
 check 0
 error 998
 lea rsi,[rbx+4096]
 lea rdi,[rbx+2048]
 mov rcx,[rbx+8]
 repe cmpsb
 jne fail
 mov rcx,r12
 lea rdx,[rbx+4096]
 cmp qword [rbx],1
 je nextw
 cmp qword [rbx],2
 je nextw
 api 2
 jmp nextdone
nextw:
 api 3
nextdone:
 check 1
 lea rsi,[rbx+4096]
 lea rdi,[rbx+3072]
 mov rcx,[rbx+8]
 repe cmpsb
 jne fail
at_eof:
 mov rcx,r12
 lea rdx,[rbx+4096]
 cmp qword [rbx],14
 je eofw
 cmp qword [rbx],15
 je eofw
 cmp qword [rbx],1
 je eofw
 cmp qword [rbx],2
 je eofw
 api 2
 jmp eofdone
eofw:
 api 3
eofdone:
 check 0
 error 18
 lea rsi,[rbx+4096]
 lea rdi,[rbx+3072]
 mov rcx,[rbx+8]
 repe cmpsb
 jne fail
 mov rcx,r12
 api 4
 check 1
 error 18
 mov rcx,r12
 api 4
 check 0
 error 6
 mov rcx,r12
 lea rdx,[rbx+4096]
 api 2
 check 0
 error 6
 mov eax,42
 add rsp,72
 ret
stale_activation:
 mov rcx,[rbx+64]
 test rcx,rcx
 jz fail
 api 4
 check 0
 error 6
 mov rcx,[rbx+64]
 lea rdx,[rbx+4096]
 api 2
 check 0
 error 6
 jmp success
fls_callback:
 lea rcx,[rel find_callback]
 api 9
 cmp eax,-1
 je fail
 mov r12,rax
 mov rcx,r12
 mov edx,1
 api 10
 check 1
 mov rcx,r12
 api 11
 check 1
 cmp qword [rbx+128],1
 jne fail
 jmp success
find_callback:
 sub rsp,40
 lea rcx,[rbx+256]
 lea rdx,[rbx+4096]
 api 0
 cmp rax,-1
 jne .bad
 api 7
 cmp eax,50
 jne .bad
 mov qword [rbx+128],1
.bad:
 add rsp,40
 ret
; Both catalog slots are real observations. Failed third publication must
; preserve the second complete output. Reuse increments the opaque generation.
capacity:
 api 0
 cmp rax,0
 jle fail
 mov r12,rax
 lea rcx,[rbx+256]
 lea rdx,[rbx+4096]
 api 0
 cmp rax,0
 jle fail
 mov r13,rax
 lea rcx,[rbx+256]
 lea rdx,[rbx+4096]
 api 0
 check -1
 error 4
 lea rsi,[rbx+4096]
 lea rdi,[rbx+2048]
 mov ecx,320
 repe cmpsb
 jne fail
 mov rcx,r12
 api 4
 check 1
 lea rcx,[rbx+256]
 lea rdx,[rbx+4096]
 api 0
 cmp rax,0
 jle fail
 cmp rax,r12
 je fail
 mov r15,rax
 mov rcx,r12
 api 4
 check 0
 error 6
 mov rcx,r15
 api 4
 check 1
 mov rcx,r13
 api 4
 check 1
 jmp success
refuse:
 ; Every rejected request leaves the full existing output untouched.
 lea rdi,[rbx+4096]
 mov ecx,320
 mov al,0xa5
 rep stosb
 mov rcx,[rbx+16]
 lea rdx,[rbx+4096]
 cmp qword [rbx+40],0
 je .output
 mov rdx,[rbx+40]
.output:
 cmp qword [rbx+48],0
 je .a
 api 1
 jmp .done
.a:
 api 0
.done:
 check -1
 mov ecx,[rbx+24]
 mov r15,rcx
 api 7
 cmp rax,r15
 jne fail
 lea rsi,[rbx+4096]
 mov ecx,320
.loop:
 cmp byte [rsi],0xa5
 jne fail
 inc rsi
 loop .loop
 jmp success
quota:
 mov r15d,129
.loop:
 mov ecx,123
 api 4
 check 0
 dec r15d
 jnz .loop
 jmp fail
revoke:
 mov eax,0x100100
 int 0x80
 check 0
 mov rcx,r12
 lea rdx,[rbx+4096]
 api 2
 check 0
 error 5
 lea rsi,[rbx+4096]
 lea rdi,[rbx+2048]
 mov ecx,320
 repe cmpsb
 jne fail
 mov rcx,r12
 api 4
 check 1
 error 5
success:
 mov eax,42
 add rsp,72
 ret
fault:
 mov rax,0x70000000
 mov rax,[rax]
 jmp fail
spin:
 jmp spin
fail:
 mov eax,99
 add rsp,72
 ret
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x3300,0x3200
 times 64-($-$$) db 0
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0x3600,0x3640,0x3680,0x36c0,0
 times 512-($-$$) db 0
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0x3600,0x3640,0x3680,0x36c0,0
 times 768-($-$$) db 0
 db 'KERNEL32.dll',0
 times 1024-($-$$) db 0
 dw 0
 db 'FindFirstFileA',0
 times 1088-($-$$) db 0
 dw 0
 db 'FindFirstFileW',0
 times 1152-($-$$) db 0
 dw 0
 db 'FindNextFileA',0
 times 1216-($-$$) db 0
 dw 0
 db 'FindNextFileW',0
 times 1280-($-$$) db 0
 dw 0
 db 'FindClose',0
 times 1344-($-$$) db 0
 dw 0
 db 'FindFirstFileExA',0
 times 1408-($-$$) db 0
 dw 0
 db 'FindFirstFileExW',0
 times 1472-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 1536-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 1600-($-$$) db 0
 dw 0
 db 'FlsAlloc',0
 times 1664-($-$$) db 0
 dw 0
 db 'FlsSetValue',0
 times 1728-($-$$) db 0
 dw 0
 db 'FlsFree',0
 times 3072-($-$$) db 0
section .data start=7680 vstart=0x140005000
 times 4096 db 0
