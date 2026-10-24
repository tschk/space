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
    dd 4096, 3584, 0
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
    dd 0x3100, 80
    times 3 dq 0
    db '.text', 0, 0, 0
    dd 4096, 0x1000, 4096, 512, 0, 0
    dw 0, 0
    dd 0x60000020
    db '.rdata', 0, 0
    dd 4096, 0x3000, 1536, 4608, 0, 0
    dw 0, 0
    dd 0x40000040
    db '.data', 0, 0, 0
    dd 8192, 0x5000, 2048, 6144, 0, 0
    dw 0, 0
    dd 0xC0000040
%macro err 1
 call [r14+48]
 cmp eax,%1
 jne fail
%endmacro
%macro ptr 0
 mov rcx,r12
%endmacro
%macro enter 0
 ptr
 call [r14+16]
%endmacro
%macro leave 0
 ptr
 call [r14+32]
%endmacro
%macro delete 0
 ptr
 call [r14+40]
%endmacro
%macro state 2
 cmp dword [r12+12],%1
 jne fail
 cmp qword [r12+16],%2
 jne fail
%endmacro
section .text start=512 vstart=0x140001000
entry:
 sub rsp,40
 mov rbx,0x140005000
 mov r14,0x140003100
 lea r12,[rbx+256]
 lea r13,[rbx+320]
 mov ecx,0x12345678
 call [r14+56]
 ptr
 call [r14]
 cmp qword [r12],-1
 jne fail
 cmp dword [r12+8],-1
 jne fail
 state 0,0
 cmp qword [r12+24],0
 jne fail
 cmp qword [r12+32],0
 jne fail
 err 0x12345678
 mov ecx,24
 mov al,90
 lea rdi,[rbx+8168]
 rep stosb
 mov eax,[rbx]
 cmp eax,0
 je basic
 cmp eax,1
 je spin
 cmp eax,2
 je duplicate
 cmp eax,3
 je overlap
 cmp eax,4
 je null_init
 cmp eax,5
 je ro_init
 cmp eax,6
 je bad_cross
 cmp eax,7
 je misalign
 cmp eax,8
 je spin_flag
 cmp eax,9
 je uninit_try
 cmp eax,10
 je copied
 cmp eax,11
 je forged
 cmp eax,12
 je unowned_leave
 cmp eax,13
 je pool
 cmp eax,14
 je locked_delete
 cmp eax,15
 je double_delete
 cmp eax,16
 je kernel_enter
 cmp eax,17
 je overflow
 cmp eax,18
 je foreign_enter
 cmp eax,19
 je foreign_leave
 cmp eax,20
 je revoke
 cmp eax,21
 je live_readonly
 cmp eax,22
 je ledger_fault
 cmp eax,23
 je nx_fault
 cmp eax,24
 je infinite
 cmp eax,25
 je held_exit
 cmp eax,26
 je good_cross
 cmp eax,27
 je reuse
 cmp eax,28
 je void_null
 cmp eax,29
 je void_duplicate
 cmp eax,30
 je void_uninit
 cmp eax,31
 je pool
 jmp fail
basic:
 enter
 state 1,1
 call [r14+64]
 cmp eax,1
 jne fail
 cmp [r12+16],rax
 jne fail
 cmp dword [r12+8],0
 jne fail
 ptr
 call [r14+24]
 cmp eax,1
 jne fail
 state 2,1
 cmp dword [r12+8],1
 jne fail
 leave
 state 1,1
 leave
 state 0,0
 cmp dword [r12+8],-1
 jne fail
 delete
 cmp qword [r12],0
 jne fail
 err 0x12345678
 jmp success
spin:
 mov rcx,r13
 mov edx,4000
 call [r14+8]
 cmp eax,1
 jne fail
 cmp qword [r13+32],0
 jne fail
 mov rcx,r13
 call [r14+40]
 err 0x12345678
 jmp success
duplicate:
 ptr
 jmp false87_init
overlap:
 lea rcx,[r12+8]
 jmp false87_init
misalign:
 lea rcx,[r12+1]
false87_init:
 xor edx,edx
 call [r14+8]
 test eax,eax
 jnz fail
 err 87
 jmp success
null_init:
 xor ecx,ecx
 jmp false998_init
ro_init:
 mov rcx,0x140003300
 jmp false998_init
bad_cross:
 lea rcx,[rbx+8168]
false998_init:
 xor edx,edx
 call [r14+8]
 test eax,eax
 jnz fail
 err 998
 jmp success
spin_flag:
 mov rcx,r13
 mov edx,0x80000000
 call [r14+8]
 test eax,eax
 jnz fail
 err 87
 jmp success
uninit_try:
 mov rcx,r13
 jmp false87_try
copied:
 mov rsi,r12
 lea rdi,[rbx+512]
 mov ecx,40
 rep movsb
 lea rcx,[rbx+512]
false87_try:
 call [r14+24]
 test eax,eax
 jnz fail
 err 87
 jmp success
forged:
 mov dword [r12+8],0
 mov dword [r12+12],1
 mov qword [r12+16],2
 ptr
 call [r14+24]
 test eax,eax
 jnz fail
 err 87
 enter
 jmp fail
unowned_leave:
 leave
 jmp fail
pool:
 xor r15d,r15d
pool_init:
 imul rcx,r15,48
 lea rcx,[rbx+rcx+1024]
 xor edx,edx
 call [r14+8]
 cmp eax,1
 jne fail
 inc r15d
 cmp r15d,63
 jb pool_init
 lea rcx,[rbx+6000]
 cmp qword [rbx],31
 je pool_void
 xor edx,edx
 call [r14+8]
 test eax,eax
 jnz fail
 err 8
 xor r15d,r15d
pool_delete:
 imul rcx,r15,48
 lea rcx,[rbx+rcx+1024]
 call [r14+40]
 inc r15d
 cmp r15d,63
 jb pool_delete
 lea rcx,[rbx+6000]
 xor edx,edx
 call [r14+8]
 cmp eax,1
 jne fail
 jmp success
pool_void:
 call [r14]
 jmp fail
locked_delete:
 enter
 delete
 jmp fail
double_delete:
 delete
 delete
 jmp fail
kernel_enter:
 mov ecx,0x100000
 call [r14+16]
 jmp fail
overflow:
 mov ecx,1
 mov eax,0x100100
 int 0x80
 ptr
 call [r14+24]
 test eax,eax
 jnz fail
 err 534
 enter
 jmp fail
foreign_enter:
foreign_leave:
 xor ecx,ecx
 mov eax,0x100100
 int 0x80
 ptr
 call [r14+24]
 test eax,eax
 jnz fail
 err 0x12345678
 cmp qword [rbx],19
 je unowned_leave
 enter
 jmp fail
revoke:
 mov ecx,2
 mov eax,0x100100
 int 0x80
 mov rcx,r13
 xor edx,edx
 call [r14+8]
 test eax,eax
 jnz fail
 err 5
 ptr
 call [r14+24]
 test eax,eax
 jnz fail
 err 5
 leave
 jmp fail
live_readonly:
 mov ecx,4
 mov eax,0x100100
 int 0x80
 ptr
 call [r14+24]
 test eax,eax
 jnz fail
 err 998
 jmp success
ledger_fault:
 mov ecx,3
 mov eax,0x100100
 int 0x80
 mov rax,[rbx+16]
 mov rax,[rax]
 jmp fail
nx_fault:
 call r12
 jmp fail
infinite:
 enter
forever:
 jmp forever
held_exit:
 enter
 jmp success
good_cross:
 lea r12,[rbx+4080]
 ptr
 mov edx,123
 call [r14+8]
 cmp eax,1
 jne fail
 enter
 leave
 delete
 jmp success
reuse:
 mov r15d,100
reuse_loop:
 mov rcx,r13
 call [r14]
 mov rcx,r13
 call [r14+16]
 mov rcx,r13
 call [r14+32]
 mov rcx,r13
 call [r14+40]
 dec r15d
 jnz reuse_loop
 err 0x12345678
 jmp success
void_null:
 xor ecx,ecx
 call [r14]
 jmp fail
void_duplicate:
 ptr
 call [r14]
 jmp fail
void_uninit:
 mov rcx,r13
 call [r14+40]
 jmp fail
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
 dd 0x3040,0,0,0x31c0,0x3100
 times 64-($-$$) db 0
 dq 0x3200,0x3240,0x3280,0x32c0,0x3300,0x3340,0x3380,0x33c0,0x3400,0
 times 256-($-$$) db 0
 dq 0x3200,0x3240,0x3280,0x32c0,0x3300,0x3340,0x3380,0x33c0,0x3400,0
 times 448-($-$$) db 0
 db 'KERNEL32.dll',0
 times 512-($-$$) db 0
 dw 0
 db 'InitializeCriticalSection',0
 times 576-($-$$) db 0
 dw 0
 db 'InitializeCriticalSectionAndSpinCount',0
 times 640-($-$$) db 0
 dw 0
 db 'EnterCriticalSection',0
 times 704-($-$$) db 0
 dw 0
 db 'TryEnterCriticalSection',0
 times 768-($-$$) db 0
 dw 0
 db 'LeaveCriticalSection',0
 times 832-($-$$) db 0
 dw 0
 db 'DeleteCriticalSection',0
 times 896-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 960-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 1024-($-$$) db 0
 dw 0
 db 'GetCurrentThreadId',0
 times 1536-($-$$) db 0
section .data start=6144 vstart=0x140005000
 dq 0,0
 times 2048-($-$$) db 0
