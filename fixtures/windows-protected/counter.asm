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
    dd 0x3080, 48
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
%macro error_is 1
 call [r14+16]
 cmp eax,%1
 jne fail
%endmacro
section .text start=512 vstart=0x140001000
entry:
 sub rsp,40
 mov rbx,0x140005000
 mov r14,0x140003080
 call [r14+16]
 test eax,eax
 jnz fail
 mov ecx,0x12345678
 call [r14+24]
 lea rdi,[rbx+248]
 mov ecx,80
 mov al,90
 rep stosb
 lea rdi,[rbx+4090]
 mov ecx,16
 rep stosb
 mov ecx,6
 lea rdi,[rbx+8192-6]
 rep stosb
 lea rcx,[rbx+256]
 call [r14+8]                    ; QueryPerformanceFrequency
 cmp eax,1
 jne fail
 mov rax,[rbx+256]
 cmp rax,[rbx+8]
 jne fail
 test rax,rax
 jle fail
 cmp qword [rbx],10
 jne first_counter
 mov ecx,2                      ; trusted test hardware raise past2^32
 mov eax,0x100100
 int 0x80
first_counter:
 lea rcx,[rbx+272]
 call [r14]                      ; QueryPerformanceCounter
 cmp eax,1
 jne fail
 mov r12,[rbx+272]
 test r12,r12
 js fail
 mov ecx,1000
pause_loop:
 pause
 loop pause_loop
 lea rcx,[rbx+280]
 call [r14]
 cmp eax,1
 jne fail
 cmp [rbx+280],r12
 jbe fail
 error_is 0x12345678
 mov eax,[rbx]
 cmp eax,1
 je null_counter
 cmp eax,2
 je kernel_frequency
 cmp eax,3
 je readonly_counter
 cmp eax,4
 je crossing_counter
 cmp eax,5
 je valid_crossing
 cmp eax,6
 je revoke
 cmp eax,7
 je backward
 cmp eax,8
 je sign_overflow
 cmp eax,9
 je forever
 cmp eax,10
 je wide_counter
 cmp eax,11
 je wallclock
 cmp eax,12
 je null_frequency
 cmp eax,13
 je text_counter
 cmp eax,14
 je unaligned_frequency
 mov ecx,4                       ; independent real IF0 advancement proof
 mov eax,0x100100
 int 0x80
 jmp success
null_counter:
 xor ecx,ecx
 call [r14]
 jmp pointer_error
kernel_frequency:
 mov ecx,0x100000
 call [r14+8]
 jmp pointer_error
readonly_counter:
 mov rcx,0x140003100
 call [r14]
 jmp pointer_error
crossing_counter:
 lea rcx,[rbx+8192-6]
 call [r14]
 jmp pointer_error
null_frequency:
 xor ecx,ecx
 call [r14+8]
 jmp pointer_error
text_counter:
 lea rcx,[rel entry]
 call [r14]
pointer_error:
 test eax,eax
 jnz fail
 error_is 998
 jmp success
valid_crossing:
 lea rcx,[rbx+4093]
 call [r14]
 cmp eax,1
 jne fail
 mov rax,[rbx+4093]
 cmp rax,[rbx+280]
 jbe fail
 jmp success
revoke:
 xor ecx,ecx
 mov eax,0x100100
 int 0x80
 lea rcx,[rbx+256]
 call [r14]
 test eax,eax
 jnz fail
 error_is 5
 lea rcx,[rbx+256]
 call [r14+8]
 test eax,eax
 jnz fail
 error_is 5
 jmp success
backward:
 mov ecx,1
 jmp hardware_failure
sign_overflow:
 mov ecx,3
hardware_failure:
 mov eax,0x100100
 int 0x80
 lea rcx,[rbx+256]
 call [r14]
 test eax,eax
 jnz fail
 error_is 31
 lea rcx,[rbx+256]
 call [r14+8]
 test eax,eax
 jnz fail
 error_is 31
 jmp success
wide_counter:
 cmp dword [rbx+276],0
 je fail
 cmp dword [rbx+284],0
 je fail
 jmp success
wallclock:
 lea rcx,[rbx+304]
 call [r14+32]
 cmp qword [rbx+304],0
 je fail
 lea rcx,[rbx+296]
 call [r14]
 cmp eax,1
 jne fail
 error_is 0x12345678
 jmp success
unaligned_frequency:
 lea rcx,[rbx+301]
 call [r14+8]
 cmp eax,1
 jne fail
 mov rax,[rbx+301]
 cmp rax,[rbx+8]
 jne fail
 jmp success
forever:
 jmp forever
success:
 mov eax,42
 add rsp,40
 ret
fail:
 mov eax,99
 add rsp,40
 ret
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x30c0,0x3080
 times 64-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0
 times 128-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0
 times 192-($-$$) db 0
 db 'KERNEL32.dll',0
 times 224-($-$$) db 0
 dw 0
 db 'QueryPerformanceCounter',0
 times 256-($-$$) db 0
 dw 0
 db 'QueryPerformanceFrequency',0
 times 288-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 320-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 352-($-$$) db 0
 dw 0
 db 'GetSystemTimeAsFileTime',0
 times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
 dq 0,0
 times 2048-($-$$) db 0
