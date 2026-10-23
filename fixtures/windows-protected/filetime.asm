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
    dd 0x3080, 40
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
 call [r14+16]
 test eax,eax
 jnz fail
 cmp dword [gs:0x68],0
 jne fail
 mov eax,0x5a
 mov ecx,32
 lea rdi,[rbx+248]
 rep stosb
 mov ecx,16
 lea rdi,[rbx+4090]
 rep stosb
 mov ecx,6
 lea rdi,[rbx+8192-6]
 rep stosb
 mov ecx,0x12345678
 call [r14+8]                          ; SetLastError
 lea r15,[rbx+256]
 mov eax,[rbx]
 cmp eax,1
 je null_output
 cmp eax,2
 je kernel_output
 cmp eax,3
 je readonly_output
 cmp eax,4
 je crossing_output
 cmp eax,5
 je unaligned_output
 cmp eax,6
 je set_rtc
 cmp eax,7
 je revoke_time
 cmp eax,9
 je set_null
 cmp eax,10
 je valid_crossing
 jmp invoke
null_output:
 xor r15d,r15d
 jmp invoke
kernel_output:
 mov r15d,0x100000
 jmp invoke
readonly_output:
 mov r15,0x140003100
 jmp invoke
crossing_output:
 lea r15,[rbx+8192-6]
 jmp invoke
unaligned_output:
 inc r15
 jmp invoke
valid_crossing:
 lea r15,[rbx+4093]
 jmp invoke
set_rtc:
 mov ecx,1
 jmp control
set_null:
 xor r15d,r15d
 mov ecx,1
 jmp control
revoke_time:
 xor ecx,ecx
control:
 mov eax,0x100100
 int 0x80
invoke:
 mov rcx,r15
 call [r14]                            ; void GetSystemTimeAsFileTime
 mov eax,[rbx]
 cmp eax,6
 je fail
 cmp eax,7
 je fail
 cmp eax,9
 je fail
 mov rax,[r15]
 cmp rax,[rbx+8]
 jb fail
 cmp rax,[rbx+16]
 ja fail
 xor edx,edx
 mov ecx,10000000
 div rcx
 test edx,edx
 jnz fail
 call [r14+16]
 cmp eax,0x12345678
 jne fail
 cmp dword [gs:0x68],0x12345678
 jne fail
 call [r14+24]
 cmp eax,1
 jne fail
 cmp qword [rbx],8
 je forever
 mov eax,42
 add rsp,40
 ret
fail:
 mov eax,99
 add rsp,40
 ret
forever:
 jmp forever
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x30c0,0x3080
 times 64-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0
 times 128-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0
 times 192-($-$$) db 0
 db 'KERNEL32.dll',0
 times 224-($-$$) db 0
 dw 0
 db 'GetSystemTimeAsFileTime',0
 times 256-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 288-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 320-($-$$) db 0
 dw 0
 db 'GetCurrentThreadId',0
 times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
 dq 0,0,0
 times 2048-($-$$) db 0
