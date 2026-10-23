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
    dd 4096, 1536, 7680
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
    dd 0x3100, 128
    times 3 dq 0
    db '.text', 0, 0, 0
    dd 4096, 0x1000, 4096, 512, 0, 0
    dw 0, 0
    dd 0x60000020
    db '.rdata', 0, 0
    dd 4096, 0x3000, 1024, 4608, 0, 0
    dw 0, 0
    dd 0x40000040
    db '.data', 0, 0, 0
    dd 8192, 0x5000, 2048, 5632, 0, 0
    dw 0, 0
    dd 0xC0000040
%macro error_is 1
 call [r14+64]
 cmp eax,%1
 jne fail
%endmacro
section .text start=512 vstart=0x140001000
entry:
 mov qword [rsp+8],11
 mov qword [rsp+16],22
 mov qword [rsp+24],33
 mov qword [rsp+32],44
 lea rax,[rsp+40]
 cmp rax,[gs:8]
 ja fail_early
 mov rax,rsp
 and eax,15
 cmp eax,8
 jne fail_early
 sub rsp,40
 mov rbx,0x140005000
 mov r14,0x140003100
 mov rax,[gs:0x60]
 cmp rax,0x4e005000
 jne fail
 xor ecx,ecx
 call [r14+104]
 mov rdx,0x140000000
 cmp rax,rdx
 jne fail
 mov rax,[gs:0x58]
 cmp rax,0x4e002000
 jne fail
 call [r14]
 cmp eax,64
 jae fail
 mov r12d,eax
 mov rcx,rax
 call [r14+8]
 test rax,rax
 jnz fail
 error_is 0
 mov ecx,r12d
 mov rdx,0x123456789abcdef0
 call [r14+16]
 cmp eax,1
 jne fail
 mov rax,[gs:r12*8+0x1480]
 mov rdx,0x123456789abcdef0
 cmp rax,rdx
 jne fail
 mov eax,[rbx]
 cmp eax,1
 je tls_limit
 cmp eax,2
 je tls_bad
 cmp eax,3
 je fls_plain
 cmp eax,5
 je fls_zero
 cmp eax,6
 je fls_limit
 cmp eax,7
 je bad_callback
 cmp eax,8
 je kernel_callback
 cmp eax,16
 je revoke
 cmp eax,20
 je fls_bad
 cmp eax,0
 je tls_simple
 lea rcx,[rel callback]
 call [r14+32]
 cmp eax,-1
 je fail
 mov r13d,eax
 mov [rbx+48],eax
 mov ecx,eax
 mov rdx,0x123456789abcdef0
 cmp qword [rbx],18
 jne set_fls
 mov edx,1
set_fls:
 call [r14+48]
 cmp eax,1
 jne fail
 cmp qword [rbx],18
 jne setup_fx
 lea rcx,[rel callback]
 call [r14+32]
 mov [rbx+56],eax
 cmp eax,-1
 je fail
setup_fx:
 mov rax,0x1122334455667788
 movq xmm15,rax
 mov rax,0x8877665544332211
 movq xmm6,rax
 mov rbp,0x1133557799bbddff
 mov rsi,0x1234432112344321
 mov rdi,0x1111333355557777
 mov r15,0x2122334455667788
 mov dword [rbx+112],0x3f80
 ldmxcsr [rbx+112]
 fninit
 fld1
 cmp qword [rbx],11
 je success
 cmp qword [rbx],12
 je explicit_exit
 cmp qword [rbx],13
 je success
 cmp qword [rbx],14
 je success
 cmp qword [rbx],18
 je success
 mov ecx,r13d
 call [r14+56]
 cmp eax,1
 jne fail
 cmp qword [rbx+24],1
 jne fail
 cmp qword [gs:8],0x4f004000
 jne fail
 cmp qword [gs:16],0x4f000000
 jne fail
 movq rax,xmm15
 mov rdx,0x1122334455667788
 cmp rax,rdx
 jne fail
 movq rax,xmm6
 mov rdx,0x8877665544332211
 cmp rax,rdx
 jne fail
 mov rax,0x1133557799bbddff
 cmp rbp,rax
 jne fail
 mov rax,0x1234432112344321
 cmp rsi,rax
 jne fail
 mov rax,0x1111333355557777
 cmp rdi,rax
 jne fail
 mov rax,0x2122334455667788
 cmp r15,rax
 jne fail
 stmxcsr [rbx+116]
 cmp dword [rbx+116],0x3f80
 jne fail
 fstp qword [rbx+96]
 mov rax,0x3ff0000000000000
 cmp [rbx+96],rax
 jne fail
 mov ecx,r12d
 call [r14+8]
 mov edx,0xfeedbeef
 cmp rax,rdx
 jne fail
 mov ecx,r13d
 call [r14+56]
 test eax,eax
 jnz fail
 error_is 87
 jmp success
tls_simple:
 mov ecx,r12d
 call [r14+24]
 cmp eax,1
 jne fail
 mov ecx,r12d
 call [r14+8]
 test rax,rax
 jnz fail
 error_is 87
 jmp success
tls_limit:
 xor r15d,r15d
alloc_tls:
 call [r14]
 cmp eax,64
 jae fail
 mov [rbx+256+r15*4],eax
 inc r15d
 cmp r15d,63
 jb alloc_tls
 call [r14]
 cmp eax,-1
 jne fail
 error_is 8
 xor r15d,r15d
free_tls:
 mov ecx,[rbx+256+r15*4]
 call [r14+24]
 cmp eax,1
 jne fail
 inc r15d
 cmp r15d,63
 jb free_tls
 jmp success
tls_bad:
 mov ecx,64
 call [r14+8]
 test rax,rax
 jnz fail
 error_is 87
 mov ecx,-1
 xor edx,edx
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 87
 mov ecx,-1
 call [r14+24]
 test eax,eax
 jnz fail
 jmp success
fls_plain:
 xor ecx,ecx
 call [r14+32]
 cmp eax,-1
 je fail
 mov r13d,eax
 mov ecx,eax
 call [r14+40]
 test rax,rax
 jnz fail
 error_is 0
 mov ecx,r13d
 mov rdx,0x123456789abcdef0
 call [r14+48]
 cmp eax,1
 jne fail
 mov ecx,r13d
 call [r14+40]
 mov rdx,0x123456789abcdef0
 cmp rax,rdx
 jne fail
 mov ecx,r13d
 call [r14+56]
 cmp eax,1
 jne fail
 cmp qword [rbx+24],0
 jne fail
 jmp success
fls_zero:
 lea rcx,[rel callback]
 call [r14+32]
 mov ecx,eax
 call [r14+56]
 cmp eax,1
 jne fail
 cmp qword [rbx+24],0
 jne fail
 jmp success
fls_limit:
 xor r15d,r15d
alloc_fls:
 xor ecx,ecx
 call [r14+32]
 cmp eax,-1
 je fail
 mov [rbx+256+r15*4],eax
 inc r15d
 cmp r15d,16
 jb alloc_fls
 xor ecx,ecx
 call [r14+32]
 cmp eax,-1
 jne fail
 error_is 8
 xor r15d,r15d
free_fls:
 mov ecx,[rbx+256+r15*4]
 call [r14+56]
 cmp eax,1
 jne fail
 inc r15d
 cmp r15d,16
 jb free_fls
 jmp success
bad_callback:
 mov rcx,rbx
 jmp expect_bad_callback
kernel_callback:
 mov ecx,0x100000
expect_bad_callback:
 call [r14+32]
 cmp eax,-1
 jne fail
 error_is 998
 jmp success
revoke:
 mov eax,0x100100
 int 0x80
 call [r14]
 cmp eax,-1
 jne fail
 error_is 5
 mov ecx,r12d
 call [r14+8]
 test eax,eax
 jnz fail
 error_is 5
 mov ecx,r12d
 call [r14+24]
 test eax,eax
 jnz fail
 xor ecx,ecx
 call [r14+32]
 cmp eax,-1
 jne fail
 error_is 5
 jmp success
fls_bad:
 xor ecx,ecx
 call [r14+40]
 test eax,eax
 jnz fail
 error_is 87
 mov ecx,17
 call [r14+56]
 test eax,eax
 jnz fail
 error_is 87
 jmp success
explicit_exit:
 mov ecx,43
 call [r14+112]
 jmp fail
success:
 mov eax,42
 add rsp,40
 ret
fail:
 mov eax,99
 add rsp,40
 ret
fail_early:
 mov eax,99
 ret
callback:
 lea rax,[rsp+40]
 cmp rax,[gs:8]
 ja callback_fail_early
 cmp qword [gs:8],0x4c002000
 jne callback_fail_early
 cmp qword [gs:16],0x4c000000
 jne callback_fail_early
 mov qword [rsp+8],55
 mov qword [rsp+16],66
 mov qword [rsp+24],77
 mov qword [rsp+32],88
 mov rax,rsp
 and eax,15
 cmp eax,8
 jne callback_fail_early
 sub rsp,40
 mov rbx,0x140005000
 mov r14,0x140003100
 inc qword [rbx+24]
 mov [rbx+32],rcx
 cmp qword [rbx],18
 je pingpong
 mov rax,0x123456789abcdef0
 cmp rcx,rax
 jne callback_fail
 movq rax,xmm15
 mov rdx,0x1122334455667788
 cmp rax,rdx
 jne callback_fail
 movq rax,xmm6
 mov rdx,0x8877665544332211
 cmp rax,rdx
 jne callback_fail
 stmxcsr [rbx+116]
 cmp dword [rbx+116],0x3f80
 jne callback_fail
 fst qword [rbx+104]
 mov rax,0x3ff0000000000000
 cmp [rbx+104],rax
 jne callback_fail
 mov ecx,[rbx+48]
 call [r14+40]
 cmp rax,[rbx+32]
 jne callback_fail
 cmp qword [rbx],9
 je callback_fault
 cmp qword [rbx],13
 je callback_fault
 cmp qword [rbx],10
 je callback_forever
 cmp qword [rbx],14
 je callback_forever
 cmp qword [rbx],17
 je callback_exit
 cmp qword [rbx],15
 jne do_heap
 mov ecx,[rbx+48]
 call [r14+56]
 test eax,eax
 jnz callback_fail
 error_is 170
do_heap:
 cmp qword [rbx],19
 jne set_tls
 call [r14+80]
 mov r15,rax
 mov rcx,rax
 mov edx,8
 mov r8d,32
 call [r14+88]
 test rax,rax
 jz callback_fail
 mov qword [rax],0x4567
 mov rcx,r15
 xor edx,edx
 mov r8,rax
 call [r14+96]
 cmp eax,1
 jne callback_fail
set_tls:
 mov ecx,r12d
 mov edx,0xfeedbeef
 call [r14+16]
 cmp eax,1
 jne callback_fail
 pxor xmm15,xmm15
 pxor xmm6,xmm6
 mov dword [rbx+116],0x1f80
 ldmxcsr [rbx+116]
 fninit
 fldz
 mov r12,0x99999999
 mov r13,0x99999999
 mov r14,0x99999999
 mov r15,0x99999999
 xor ebp,ebp
 xor edi,edi
 xor esi,esi
 xor ebx,ebx
 add rsp,40
 ret
pingpong:
 mov ecx,[rbx+56]
 mov edx,2
 cmp qword [rbx+32],1
 je set_pingpong
 mov ecx,[rbx+48]
 mov edx,1
set_pingpong:
 call [r14+48]
 cmp eax,1
 jne callback_fail
 add rsp,40
 ret
callback_fault:
 mov eax,[0x100000]
 jmp callback_fail
callback_forever:
 jmp callback_forever
callback_exit:
 mov ecx,44
 call [r14+112]
 jmp callback_fail
callback_fail:
 mov qword [rbx+40],1
 add rsp,40
 ret
callback_fail_early:
 ret
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x31c0,0x3100
 times 64-($-$$) db 0
 dq 0x3200,0x3220,0x3240,0x3260,0x3280,0x32a0,0x32c0,0x32e0,0x3300,0x3320,0x3340,0x3360,0x3380,0x33a0,0x33c0,0
 times 256-($-$$) db 0
 dq 0x3200,0x3220,0x3240,0x3260,0x3280,0x32a0,0x32c0,0x32e0,0x3300,0x3320,0x3340,0x3360,0x3380,0x33a0,0x33c0,0
 times 448-($-$$) db 0
 db 'KERNEL32.dll',0
 times 512-($-$$) db 0
 dw 0
 db 'TlsAlloc',0
 times 544-($-$$) db 0
 dw 0
 db 'TlsGetValue',0
 times 576-($-$$) db 0
 dw 0
 db 'TlsSetValue',0
 times 608-($-$$) db 0
 dw 0
 db 'TlsFree',0
 times 640-($-$$) db 0
 dw 0
 db 'FlsAlloc',0
 times 672-($-$$) db 0
 dw 0
 db 'FlsGetValue',0
 times 704-($-$$) db 0
 dw 0
 db 'FlsSetValue',0
 times 736-($-$$) db 0
 dw 0
 db 'FlsFree',0
 times 768-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 800-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 832-($-$$) db 0
 dw 0
 db 'GetProcessHeap',0
 times 864-($-$$) db 0
 dw 0
 db 'HeapAlloc',0
 times 896-($-$$) db 0
 dw 0
 db 'HeapFree',0
 times 928-($-$$) db 0
 dw 0
 db 'GetModuleHandleW',0
 times 960-($-$$) db 0
 dw 0
 db 'ExitProcess',0
 times 1024-($-$$) db 0
section .data start=5632 vstart=0x140005000
 dq 0,0
 times 2048-($-$$) db 0
