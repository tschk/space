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
 call [r14+32]                       ; GetLastError, fresh activation
 test eax,eax
 jnz fail
 cmp dword [gs:0x68],0
 jne fail
 call [r14]                          ; GetCurrentProcessId
 test eax,eax
 jle fail
 cmp rax,[gs:0x40]
 jne fail
 call [r14+8]                        ; GetCurrentThreadId
 cmp eax,1
 jne fail
 cmp rax,[gs:0x48]
 jne fail
 call [r14+16]                       ; GetCurrentProcess pseudo handle
 cmp rax,-1
 jne fail
 mov rcx,0x12345678
 call [r14+24]                       ; SetLastError
 cmp dword [gs:0x68],0x12345678
 jne fail
 call [r14+8]
 cmp eax,1
 jne fail
 call [r14+16]
 cmp rax,-1
 jne fail
 call [r14+32]
 cmp eax,0x12345678
 jne fail
 mov eax,[rbx]
 cmp eax,1
 je close_pseudo
 cmp eax,2
 je truncate_dword
 cmp eax,3
 je direct_teb_error
 cmp eax,4
 je fault
 cmp eax,5
 je forever
success:
 mov eax,42
 add rsp,40
 ret
fail:
 mov eax,99
 add rsp,40
 ret
close_pseudo:
 call [r14+16]
 mov rcx,rax
 call [r14+40]                       ; pseudo handle is not a file/capability
 test eax,eax
 jnz fail
 cmp dword [gs:0x68],6
 jne fail
 call [r14+32]
 cmp eax,6
 jne fail
 jmp success
truncate_dword:
 mov rcx,0x12345678ffffffff
 call [r14+24]
 cmp dword [gs:0x68],-1
 jne fail
 call [r14+32]
 cmp eax,-1
 jne fail
 jmp success
direct_teb_error:
 mov dword [gs:0x68],0xa5a50001
 call [r14+8]
 cmp eax,1
 jne fail
 call [r14+32]
 cmp eax,0xa5a50001
 jne fail
 cmp dword [gs:0x68],0xa5a50001
 jne fail
 jmp success
fault:
 mov eax,[0x100000]
 jmp fail
forever:
 jmp forever
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
 db 'GetCurrentProcessId',0
 times 256-($-$$) db 0
 dw 0
 db 'GetCurrentThreadId',0
 times 288-($-$$) db 0
 dw 0
 db 'GetCurrentProcess',0
 times 320-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 352-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 384-($-$$) db 0
 dw 0
 db 'CloseHandle',0
 times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
 dq 0,0
 times 2048-($-$$) db 0
