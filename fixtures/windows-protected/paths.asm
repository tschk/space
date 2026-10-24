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
    dd 0x3200, 120
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
 api 8
 cmp eax,%1
 jne fail
%endmacro
%macro readargs 0
 mov rcx,r12
 lea rdx,[rbx+4096]
 mov r8d,16
 lea r9,[rbx+160]
 mov qword [rsp+32],0
%endmacro
section .text start=512 vstart=0x140001000
entry:
 sub rsp,72
 mov rbx,0x140005000
 mov r14,0x140003200
 ; Each activation starts at declared C:\, never the preceding app's cwd.
 mov ecx,2048
 lea rdx,[rbx+4096]
 api 1
 check 3
 mov rax,0x005c003a0043
 cmp [rbx+4096],rax
 jne fail
 mov rcx,0x140003b00
 api 0
 check 1
 mov ecx,0x12345678
 api 9
 mov eax,[rbx]
 cmp eax,0
 je setcwd
 cmp eax,1
 je getcwd
 cmp eax,2
 je createw
 cmp eax,3
 je createa
 cmp eax,4
 je gettype
 cmp eax,10
 je write_roundtrip
 cmp eax,11
 je read_roundtrip
 cmp eax,12
 je share
 cmp eax,14
 je private_read
 cmp eax,15
 je held_deadline
 cmp eax,16
 je revoke
 cmp eax,17
 je private_handle_read
 jmp fail
setcwd:
 mov rcx,[rbx+56]
 api 0
 call expected
 ; Get cwd count query includes NUL; full result excludes it.
 xor ecx,ecx
 xor edx,edx
 api 1
 cmp rax,[rbx+128]
 jne fail
 mov ecx,1
 lea rdx,[rbx+4096]
 api 1
 cmp rax,[rbx+128]
 jne fail
 mov ecx,2048
 lea rdx,[rbx+4096]
 api 1
 mov rdx,[rbx+128]
 dec rdx
 cmp rax,rdx
 jne fail
 mov rsi,0x4d000000
 lea rdi,[rbx+4096]
 mov rcx,[rbx+128]
 shl rcx,1
 repe cmpsb
 jne fail
 jmp success
getcwd:
 mov rcx,[rbx+32]
 mov rdx,[rbx+64]
 api 1
 call expected
 jmp success
createw:
 call create_args
 mov rax,[rbx+32]
 mov [rsp+32],rax
 mov qword [rsp+40],0x80
 mov qword [rsp+48],0
 api 2
 jmp opened
createa:
 call create_args
 mov rax,[rbx+32]
 mov [rsp+32],rax
 mov qword [rsp+40],0x80
 mov qword [rsp+48],0
 api 3
opened:
 mov r12,rax
 call expected
 cmp r12,-1
 je success
 mov rcx,r12
 api 4
 check 1
 mov rcx,r12
 api 7
 check 1
 jmp success
gettype:
 mov rcx,[rbx+16]
 api 4
 call expected
 jmp success
expected:
 sub rsp,40
 cmp rax,[rbx+40]
 jne .bad
 api 8
 cmp eax,[rbx+48]
 jne .bad
 add rsp,40
 ret
.bad:
 ud2
create_args:
 mov rcx,[rbx+56]
 mov rdx,[rbx+16]
 mov r8,[rbx+24]
 xor r9d,r9d
 ; Helper returns before the actual imported call. Its caller owns stack args.
 ret
write_roundtrip:
 call write_open
 mov rcx,r12
 mov rdx,0x140003b40
 mov r8d,16
 lea r9,[rbx+160]
 mov qword [rsp+32],0
 api 5
 check 1
 cmp dword [rbx+160],16
 jne fail
 mov rcx,r12
 api 7
 check 1
read_roundtrip:
 lea rcx,[rbx+2304]
 mov edx,0x80000000
 mov r8d,3
 xor r9d,r9d
 mov qword [rsp+32],3
 mov qword [rsp+40],0x80
 mov qword [rsp+48],0
 api 3
 cmp rax,3
 jne fail
 mov r12,rax
 readargs
 api 6
 check 1
 cmp dword [rbx+160],16
 jne fail
 mov rax,0x3736353433323130
 cmp [rbx+4096],rax
 jne fail
 mov rax,0x4645444342413938
 cmp [rbx+4104],rax
 jne fail
 mov rcx,r12
 lea rdx,[rbx+168]
 api 12
 check 1
 cmp qword [rbx+168],16
 jne fail
 readargs
 api 6
 check 1
 cmp dword [rbx+160],0
 jne fail
 mov rcx,r12
 api 7
 check 1
 mov rcx,r12
 api 4
 check 0
 error 6
 jmp success
write_open:
 sub rsp,72
 mov rcx,[rbx+56]
 mov edx,0xc0000000
 mov r8d,3
 xor r9d,r9d
 mov qword [rsp+32],2
 mov qword [rsp+40],0x80
 mov qword [rsp+48],0
 api 2
 cmp rax,3
 jne .bad
 mov r12,rax
 add rsp,72
 ret
.bad:
 ud2
share:
 mov rcx,[rbx+56]
 mov edx,0x80000000
 xor r8d,r8d
 xor r9d,r9d
 mov qword [rsp+32],3
 mov qword [rsp+40],0x80
 mov qword [rsp+48],0
 api 2
 cmp rax,3
 jne fail
 mov r12,rax
 lea rcx,[rbx+2304]
 mov edx,0x80000000
 mov r8d,3
 xor r9d,r9d
 api 3
 check -1
 error 32
 mov rcx,r12
 api 7
 check 1
 jmp success
private_read:
 mov rax,[rbx+144]
 mov rax,[rax]
 jmp fail
held_deadline:
 call write_open
.forever:
 jmp .forever
private_handle_read:
 call write_open
 mov eax,0x100100
 mov ecx,2
 int 0x80
 mov rax,[rbx+144]
 mov rax,[rax]
 jmp fail
revoke:
 call write_open
 mov eax,0x100100
 mov ecx,1
 int 0x80
 mov rcx,[rbx+56]
 api 0
 check 0
 error 5
 mov ecx,2048
 lea rdx,[rbx+4096]
 api 1
 check 0
 error 5
 mov rcx,r12
 api 4
 check 0
 error 5
 mov rcx,[rbx+56]
 mov edx,0x80000000
 mov r8d,3
 xor r9d,r9d
 mov qword [rsp+32],3
 mov qword [rsp+40],0x80
 mov qword [rsp+48],0
 api 2
 check -1
 error 5
 mov rcx,r12
 api 7
 check 1
 jmp success
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
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0x3600,0x3640,0x3680,0x36c0,0x3700,0x3740,0
 times 512-($-$$) db 0
 dq 0x3400,0x3440,0x3480,0x34c0,0x3500,0x3540,0x3580,0x35c0,0x3600,0x3640,0x3680,0x36c0,0x3700,0x3740,0
 times 768-($-$$) db 0
 db "KERNEL32.dll",0
 times 1024-($-$$) db 0
 dw 0
 db "SetCurrentDirectoryW",0
 times 1088-($-$$) db 0
 dw 0
 db "GetCurrentDirectoryW",0
 times 1152-($-$$) db 0
 dw 0
 db "CreateFileW",0
 times 1216-($-$$) db 0
 dw 0
 db "CreateFileA",0
 times 1280-($-$$) db 0
 dw 0
 db "GetFileType",0
 times 1344-($-$$) db 0
 dw 0
 db "WriteFile",0
 times 1408-($-$$) db 0
 dw 0
 db "ReadFile",0
 times 1472-($-$$) db 0
 dw 0
 db "CloseHandle",0
 times 1536-($-$$) db 0
 dw 0
 db "GetLastError",0
 times 1600-($-$$) db 0
 dw 0
 db "SetLastError",0
 times 1664-($-$$) db 0
 dw 0
 db "GetStdHandle",0
 times 1728-($-$$) db 0
 dw 0
 db "ExitProcess",0
 times 1792-($-$$) db 0
 dw 0
 db "GetFileSizeEx",0
 times 1856-($-$$) db 0
 dw 0
 db "SetFilePointerEx",0
 times 2816-($-$$) db 0
 dw 'C',':',92,'w','p',0
 times 2880-($-$$) db 0
 db '0123456789ABCDEF'
 times 3072-($-$$) db 0
section .data start=7680 vstart=0x140005000
 times 4096 db 0
