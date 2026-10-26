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
    dd 4096, 5120, 0
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
    dd 0x3200, 72
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
    dd 8192, 0x5000, 2048, 7680, 0, 0
    dw 0, 0
    dd 0xC0000040


%macro api 1
 call [r14+%1*8]
%endmacro
section .text start=512 vstart=0x140001000
entry:
 sub rsp,72
 mov rbx,0x140005000
 mov r14,0x140003200
 mov ecx,0x12345678
 api 7
 mov eax,[rbx]
 cmp eax,0
 je mb
 cmp eax,1
 je wc
 cmp eax,2
 je cpinfo
 cmp eax,3
 je acp
 cmp eax,4
 je oem
 cmp eax,5
 je valid
 cmp eax,6
 je bad_mb_stack
 cmp eax,7
 je bad_wc_stack
 jmp fail
bad_mb_stack:
 mov rbp,rsp
 mov rsp,0x4f004fd8
 mov ecx,65001
 mov edx,8
 mov r8,[rbx+56]
 mov r9d,1
 api 4
 mov rsp,rbp
 jmp check
bad_wc_stack:
 mov rbp,rsp
 mov rsp,0x4f004fc8
 mov ecx,65001
 mov edx,128
 mov r8,[rbx+56]
 mov r9d,1
 api 5
 mov rsp,rbp
 jmp check
mb:
 mov rcx,[rbx+8]
 mov rdx,[rbx+16]
 mov r8,[rbx+56]
 mov r9,[rbx+24]
 mov rax,[rbx+64]
 mov [rsp+32],rax
 mov rax,[rbx+32]
 mov [rsp+40],rax
 api 4
 jmp check
wc:
 mov rcx,[rbx+8]
 mov rdx,[rbx+16]
 mov r8,[rbx+56]
 mov r9,[rbx+24]
 mov rax,[rbx+64]
 mov [rsp+32],rax
 mov rax,[rbx+32]
 mov [rsp+40],rax
 mov rax,[rbx+104]
 mov [rsp+48],rax
 mov rax,[rbx+112]
 mov [rsp+56],rax
 api 5
 jmp check
cpinfo:
 mov rcx,[rbx+8]
 mov rdx,[rbx+64]
 api 2
 jmp check
acp:
 api 0
 jmp check
oem:
 api 1
 jmp check
valid:
 mov rcx,[rbx+8]
 api 3
check:
 cmp rax,[rbx+40]
 jne fail
 api 6
 cmp eax,[rbx+48]
 jne fail
 cmp qword [rbx+88],2
 je large_check
 xor esi,esi
 mov rdi,[rbx+64]
.compare:
 cmp rsi,[rbx+80]
 jge success
 mov al,[rbx+rsi+1536]
 cmp [rdi+rsi],al
 jne fail
 inc esi
 jmp .compare
large_check:
 xor esi,esi
 mov rdi,[rbx+64]
 mov r8,[rbx+40]
 mov r9,[rbx+32]
 cmp qword [rbx],0
 jne .loop
 shl r8,1
 shl r9,1
.loop:
 cmp rsi,r9
 jge success
 mov al,90
 cmp rsi,r8
 jge .byte
 mov al,65
 cmp qword [rbx],0
 jne .byte
 test esi,1
 jz .byte
 xor eax,eax
.byte:
 cmp [rdi+rsi],al
 jne fail
 inc esi
 jmp .loop
success:
 mov eax,42
 add rsp,72
 ret
fail:
 mov eax,99
 add rsp,72
 ret
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x3300,0x3200
 times 64-($-$$) db 0
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0
 times 512-($-$$) db 0
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0
 times 768-($-$$) db 0
 db "KERNEL32.dll",0
 times 1024-($-$$) db 0
 dw 0
 db "GetACP",0
 times 1088-($-$$) db 0
 dw 0
 db "GetOEMCP",0
 times 1152-($-$$) db 0
 dw 0
 db "GetCPInfo",0
 times 1216-($-$$) db 0
 dw 0
 db "IsValidCodePage",0
 times 1280-($-$$) db 0
 dw 0
 db "MultiByteToWideChar",0
 times 1344-($-$$) db 0
 dw 0
 db "WideCharToMultiByte",0
 times 1408-($-$$) db 0
 dw 0
 db "GetLastError",0
 times 1472-($-$$) db 0
 dw 0
 db "SetLastError",0
 times 3072-($-$$) db 0
section .data start=7680 vstart=0x140005000
 times 2048 db 0
