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
    dd 4096, 1024, 7680
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
    dd 0x3080, 56
    times 3 dq 0
    db '.text', 0, 0, 0
    dd 4096, 0x1000, 4096, 512, 0, 0
    dw 0, 0
    dd 0x60000020
    db '.rdata', 0, 0
    dd 4096, 0x3000, 512, 4608, 0, 0
    dw 0, 0
    dd 0x40000040
    db '.data', 0, 0, 0
    dd 8192, 0x5000, 2048, 5120, 0, 0
    dw 0, 0
    dd 0xC0000040
section .text start=512 vstart=0x140001000
entry:
 sub rsp,40
 mov rbx,0x140005000
 mov r14,0x140003080
 xor ecx,ecx
 call [r14+40]                  ; Invalid standard handle seeds error87
 call [r14]                     ; GetCommandLineA
 mov r12,rax
 call [r14+8]                   ; GetCommandLineW
 mov r13,rax
 xor esi,esi
compare_line:
 mov al,[r12+rsi]
 cmp al,[rbx+rsi+512]
 jne fail
 cmp al,[r13+rsi*2]
 jne fail
 cmp byte [r13+rsi*2+1],0
 jne fail
 inc esi
 cmp esi,[rbx+8]
 jb compare_line
 xor ecx,ecx
 call [r14+24]                  ; GetModuleHandleW(NULL)
 mov rdx,0x140000000
 cmp rax,rdx
 jne fail
 lea rdi,[rbx+1024]
 mov ecx,112
 mov al,0xa5
 rep stosb
 lea rcx,[rbx+1024]
 call [r14+16]                  ; GetStartupInfoW, sizeof104
 cmp dword [rbx+1024],104
 jne fail
 cmp qword [rbx+1032],0
 jne fail
 cmp qword [rbx+1040],0
 jne fail
 cmp dword [rbx+1084],0         ; dwFlags
 jne fail
 cmp qword [rbx+1104],-1
 jne fail
 cmp qword [rbx+1112],1
 jne fail
 cmp qword [rbx+1120],2
 jne fail
 mov rax,0xa5a5a5a5a5a5a5a5
 cmp [rbx+1128],rax
 jne fail
 call [r14+32]
 cmp eax,87
 jne fail
 mov eax,[rbx]
 cmp eax,1
 je write_a
 cmp eax,2
 je write_w
 cmp eax,3
 je execute
 cmp eax,4
 je readonly_info
 cmp eax,5
 je cross_info
 cmp eax,6
 je null_info
 cmp eax,7
 je missing_module
 cmp eax,8
 je kernel_module
 cmp eax,9
 je unterminated_module
 cmp eax,10
 je forever
 cmp eax,11
 je fs_zero
 cmp eax,12
 je cross_module
success:
 mov eax,42
 add rsp,40
 ret
fail:
 mov eax,99
 add rsp,40
 ret
write_a:
 mov byte [r12],0
 jmp fail
write_w:
 mov byte [r13],0
 jmp fail
execute:
 call r12
 jmp fail
readonly_info:
 mov rcx,0x140003200
 call [r14+16]
 jmp error_998
cross_info:
 lea rcx,[rbx+8192-100]
 mov rdi,rcx
 mov al,0xa5
 mov ecx,100
 rep stosb
 lea rcx,[rbx+8192-100]
 call [r14+16]
 mov esi,8192-100
check_untouched:
 cmp byte [rbx+rsi],0xa5
 jne fail
 inc esi
 cmp esi,8192
 jne check_untouched
 jmp error_998
null_info:
 xor ecx,ecx
 call [r14+16]
 jmp error_998
missing_module:
 mov rcx,0x1400031a0
 call [r14+24]
 test rax,rax
 jnz fail
 call [r14+32]
 cmp eax,126
 jne fail
 jmp success
kernel_module:
 mov ecx,0x100000
 call [r14+24]
 test rax,rax
 jnz fail
 jmp error_998
unterminated_module:
 lea rdi,[rbx+2048]
 mov eax,0x41
 mov ecx,260
 rep stosw
 lea rcx,[rbx+2048]
 call [r14+24]
 test rax,rax
 jnz fail
 call [r14+32]
 cmp eax,206
 jne fail
 jmp success
cross_module:
 lea rcx,[rbx+8191]
 call [r14+24]
 test rax,rax
 jnz fail
 jmp error_998
error_998:
 call [r14+32]
 cmp eax,998
 jne fail
 jmp success
forever:
 jmp forever
fs_zero:
 mov rax,[fs:0]
 jmp fail
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x30c0,0x3080
 times 64-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0x3180,0
 times 128-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0x3180,0
 times 192-($-$$) db 0
 db 'KERNEL32.dll',0
 times 224-($-$$) db 0
 dw 0
 db 'GetCommandLineA',0
 times 256-($-$$) db 0
 dw 0
 db 'GetCommandLineW',0
 times 288-($-$$) db 0
 dw 0
 db 'GetStartupInfoW',0
 times 320-($-$$) db 0
 dw 0
 db 'GetModuleHandleW',0
 times 352-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 384-($-$$) db 0
 dw 0
 db 'GetStdHandle',0
 times 416-($-$$) db 0
 dw 'm','i','s','s','i','n','g','.','d','l','l',0
 times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
 dq 0,0
 times 2048-($-$$) db 0
