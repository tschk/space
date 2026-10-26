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
    dd 0x3200, 216
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
%macro check 1
 cmp rax,%1
 jne fail
%endmacro
section .text start=512 vstart=0x140001000
entry:
 mov qword [rsp+8],1
 mov qword [rsp+16],2
 mov qword [rsp+24],3
 mov qword [rsp+32],4
 sub rsp,40
 mov rax,[gs:0x30]
 cmp rax,0x4e000000
 jne fail
 mov rax,[gs:0x60]
 cmp rax,0x4e005000
 jne fail
 mov rbx,0x140005000
 mov r14,0x140003200
 movdqu xmm15,[rel vector]
 api 0
 mov r12,rax
 mov rax,[gs:0x60]
 cmp [rax+48],r12
 jne fail
 mov rcx,r12
 mov edx,8
 mov r8d,128
 api 1
 test rax,rax
 jz fail
 mov r15,rax
 cmp qword [r15],0
 jne fail
 mov rcx,r15
 api 9
 mov rcx,r15
 api 10
 cmp dword [r15+12],1
 jne fail
 api 3
 cmp eax,-1
 je fail
 mov r13d,eax
 mov ecx,r13d
 mov rdx,r15
 api 4
 check 1
 mov rax,[gs:0x1480]
 cmp rax,r15
 jne fail
 mov ecx,r13d
 api 5
 cmp rax,r15
 jne fail
 mov rcx,0x140003b00
 lea rdx,[rbx+256]
 mov r8d,32
 api 13
 check 3
 cmp dword [rbx+256],0x00656e6f
 jne fail
 api 15
 test rax,rax
 jz fail
 mov rsi,rax
 ; Snapshot is immutable and retains ALPHA=one through callback mutation.
 mov rcx,0x140003b10
 mov rdx,0x140003b20
 api 14
 check 1
 ; Hardware-optional real counter: unavailable must preserve output.
 call counter
 test eax,eax
 jnz fail
%ifndef NO_CLOCK
 lea rcx,[rbx+64]
 api 19
 mov rax,[rbx+64]
 cmp rax,[rbx+80]
 jl fail
 cmp rax,[rbx+88]
 jg fail
%endif
 api 22
 cmp dword [rax],0x696c7173
 jne fail
 cmp byte [rax+11],0
 jne fail
 ; FLS callback consumes all the same services while critical is held.
 lea rcx,[rel callback]
 api 6
 cmp eax,-1
 je fail
 mov [rbx+40],eax
 mov ecx,eax
 mov rdx,r15
 api 7
 check 1
 cmp qword [rbx],1
 je normal_exit
 mov ecx,[rbx+40]
 api 8
 check 1
 movdqu xmm0,[rel vector]
 pcmpeqb xmm0,xmm15
 pmovmskb eax,xmm0
 cmp eax,65535
 jne fail
 cmp qword [rbx+24],1
 jne fail
 cmp dword [r15+12],1
 jne fail
 mov ecx,r13d
 api 5
 cmp rax,0x12345678
 jne fail
 mov rcx,0x140003b00
 lea rdx,[rbx+256]
 mov r8d,32
 api 13
 check 5
 cmp dword [rbx+256],0x65726874
 jne fail
 cmp word [rbx+260],0x0065
 jne fail
 cmp word [rsi+12],'o'
 jne fail
 cmp qword [rbx],4
 je forever
 cmp qword [rbx],5
 je timer_revoke
 cmp qword [rbx],6
 je memory_revoke
 cmp qword [rbx],7
 je invalid_counter
 cmp qword [rbx],8
 je private_read
 cmp qword [rbx],9
 je snapshot_write
 cmp qword [rbx],10
 je heap_execute
 cmp qword [rbx],12
 je clock_fail
cleanup:
 mov rcx,rsi
 api 16
 check 1
 mov rcx,r15
 api 11
 mov rcx,r15
 api 12
 mov rcx,r12
 xor edx,edx
 mov r8,r15
 api 2
 check 1
 mov ecx,r13d
 api 25
 check 1
success:
 mov eax,42
 add rsp,40
 ret
fail:
 mov eax,99
 add rsp,40
 ret
normal_exit:
 mov ecx,42
 api 23
 jmp fail
forever:
 jmp forever
private_read:
 mov rax,[rbx+32]
 mov rax,[rax]
 jmp fail
snapshot_write:
 mov byte [rsi],0
 jmp fail
heap_execute:
 call r15
 jmp fail
invalid_counter:
 xor ecx,ecx
 api 17
 check 0
 api 20
 check 998
 jmp cleanup
timer_revoke:
 mov eax,0x100100
 mov ecx,1
 int 0x80
 mov qword [rbx+48],90
 lea rcx,[rbx+48]
 api 17
 check 0
 cmp qword [rbx+48],90
 jne fail
 api 20
 check 5
 jmp cleanup
memory_revoke:
 mov eax,0x100100
 mov ecx,2
 int 0x80
 mov rcx,0x140003b00
 lea rdx,[rbx+256]
 mov r8d,32
 api 13
 check 0
 api 20
 check 5
 mov rcx,r15
 api 24
 check 0
 api 20
 check 5
 ; Filetime still has an independent live TimeSource grant.
 lea rcx,[rbx+64]
 api 19
 jmp success
clock_fail:
 mov eax,0x100100
 mov ecx,3
 int 0x80
 lea rcx,[rbx+64]
 api 19
 jmp fail
; Return0 when actual QPC matches the trusted hardware availability oracle.
counter:
%ifdef NO_CLOCK
 xor eax,eax
 ret
%endif
 sub rsp,40
 mov qword [rbx+48],90
 lea rcx,[rbx+48]
 api 18
 cmp qword [rbx+8],0
 je .unavailable
 cmp eax,1
 jne .bad
 cmp qword [rbx+48],0
 jle .bad
 lea rcx,[rbx+48]
 api 17
 cmp eax,1
 jne .bad
 mov rax,[rbx+48]
 mov [rbx+56],rax
 lea rcx,[rbx+48]
 api 17
 cmp eax,1
 jne .bad
 mov rax,[rbx+48]
 cmp rax,[rbx+56]
 jl .bad
 xor eax,eax
 add rsp,40
 ret
.unavailable:
 test eax,eax
 jnz .bad
 cmp qword [rbx+48],90
 jne .bad
 api 20
 cmp eax,31
 jne .bad
 lea rcx,[rbx+48]
 api 17
 test eax,eax
 jnz .bad
 cmp qword [rbx+48],90
 jne .bad
 api 20
 cmp eax,31
 jne .bad
 xor eax,eax
 add rsp,40
 ret
.bad:
 mov eax,1
 add rsp,40
 ret
callback:
 push rbx
 push rbp
 push rsi
 push rdi
 push r12
 push r13
 push r14
 push r15
 sub rsp,40
 mov rax,[gs:0x10]
 cmp rax,0x4c000000
 jne callback_fail
 cmp rsp,0x4c001f70
 ja callback_fail
 test rsp,15
 jnz callback_fail
 movdqu xmm0,[rel vector]
 pcmpeqb xmm0,xmm15
 pmovmskb eax,xmm0
 cmp eax,65535
 jne callback_fail
 cmp rcx,r15
 jne callback_fail
 mov rcx,r15
 api 24
 cmp eax,1
 jne callback_fail
 cmp dword [r15+12],2
 jne callback_fail
 mov ecx,r13d
 api 5
 cmp rax,r15
 jne callback_fail
 mov rcx,r12
 xor edx,edx
 mov r8d,32
 api 1
 test rax,rax
 jz callback_fail
 mov r8,rax
 mov rcx,r12
 xor edx,edx
 api 2
 cmp eax,1
 jne callback_fail
 call counter
 test eax,eax
 jnz callback_fail
 mov rcx,0x140003b10
 mov rdx,0x140003b40
 api 14
 cmp eax,1
 jne callback_fail
 mov ecx,r13d
 mov edx,0x12345678
 api 4
 cmp eax,1
 jne callback_fail
 mov rcx,r15
 api 11
 inc qword [rbx+24]
 cmp qword [rbx],13
 je clock_fail
 cmp qword [rbx],2
 je callback_fault
 cmp qword [rbx],3
 je callback_forever
 cmp qword [rbx],11
 je callback_exit
 add rsp,40
 pop r15
 pop r14
 pop r13
 pop r12
 pop rdi
 pop rsi
 pop rbp
 pop rbx
 ret
callback_fault:
 xor eax,eax
 mov rax,[rax]
callback_forever:
 jmp callback_forever
callback_exit:
 mov ecx,42
 api 23
callback_fail:
 ud2
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x3300,0x3200
 times 64-($-$$) db 0
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0x3600,0x3640,0x3680,0x36c0,0x3700,0x3740,0x3780,0x37c0,0x3800,0x3840,0x3880,0x38c0,0x3900,0x3940,0x3980,0x39c0,0x3a00,0x3a40,0
 times 512-($-$$) db 0
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0x3600,0x3640,0x3680,0x36c0,0x3700,0x3740,0x3780,0x37c0,0x3800,0x3840,0x3880,0x38c0,0x3900,0x3940,0x3980,0x39c0,0x3a00,0x3a40,0
 times 768-($-$$) db 0
 db "KERNEL32.dll",0
 times 1024-($-$$) db 0
 dw 0
 db "GetProcessHeap",0
 times 1088-($-$$) db 0
 dw 0
 db "HeapAlloc",0
 times 1152-($-$$) db 0
 dw 0
 db "HeapFree",0
 times 1216-($-$$) db 0
 dw 0
 db "TlsAlloc",0
 times 1280-($-$$) db 0
 dw 0
 db "TlsSetValue",0
 times 1344-($-$$) db 0
 dw 0
 db "TlsGetValue",0
 times 1408-($-$$) db 0
 dw 0
 db "FlsAlloc",0
 times 1472-($-$$) db 0
 dw 0
 db "FlsSetValue",0
 times 1536-($-$$) db 0
 dw 0
 db "FlsFree",0
 times 1600-($-$$) db 0
 dw 0
 db "InitializeCriticalSection",0
 times 1664-($-$$) db 0
 dw 0
 db "EnterCriticalSection",0
 times 1728-($-$$) db 0
 dw 0
 db "LeaveCriticalSection",0
 times 1792-($-$$) db 0
 dw 0
 db "DeleteCriticalSection",0
 times 1856-($-$$) db 0
 dw 0
 db "GetEnvironmentVariableA",0
 times 1920-($-$$) db 0
 dw 0
 db "SetEnvironmentVariableW",0
 times 1984-($-$$) db 0
 dw 0
 db "GetEnvironmentStringsW",0
 times 2048-($-$$) db 0
 dw 0
 db "FreeEnvironmentStringsW",0
 times 2112-($-$$) db 0
 dw 0
%ifdef NO_CLOCK
 db "GetLastError",0
%else
 db "QueryPerformanceCounter",0
%endif
 times 2176-($-$$) db 0
 dw 0
%ifdef NO_CLOCK
 db "GetLastError",0
%else
 db "QueryPerformanceFrequency",0
%endif
 times 2240-($-$$) db 0
 dw 0
%ifdef NO_CLOCK
 db "GetLastError",0
%else
 db "GetSystemTimeAsFileTime",0
%endif
 times 2304-($-$$) db 0
 dw 0
 db "GetLastError",0
 times 2368-($-$$) db 0
 dw 0
 db "SetLastError",0
 times 2432-($-$$) db 0
 dw 0
 db "GetCommandLineA",0
 times 2496-($-$$) db 0
 dw 0
 db "ExitProcess",0
 times 2560-($-$$) db 0
 dw 0
 db "TryEnterCriticalSection",0
 times 2624-($-$$) db 0
 dw 0
 db "TlsFree",0
 times 2816-($-$$) db 0
 db "ALPHA",0
 times 2832-($-$$) db 0
 dw 'A','L','P','H','A',0
 times 2848-($-$$) db 0
 dw 't','w','o',0
 times 2880-($-$$) db 0
 dw 't','h','r','e','e',0
 times 2928-($-$$) db 0
vector: dq 0x123456789abcdef0,0x23456789abcdef01
 times 3072-($-$$) db 0
section .data start=7680 vstart=0x140005000
 times 2048 db 0
