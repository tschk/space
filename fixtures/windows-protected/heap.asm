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
    dd 0x3080, 64
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
 call [r14+40]
 cmp eax,%1
 jne fail
%endmacro
%macro alloc_size 2
 mov rcx,r13
 mov edx,%1
 mov r8,%2
 call [r14+8]
%endmacro
%macro free_block 1
 mov rcx,r13
 xor edx,edx
 mov r8,%1
 call [r14+16]
 cmp eax,1
 jne fail
%endmacro
section .text start=512 vstart=0x140001000
entry:
 sub rsp,40
 mov rbx,0x140005000
 mov r14,0x140003080
 call [r14+40]
 test eax,eax
 jnz fail
 mov ecx,0x12345678
 call [r14+48]
 call [r14]
 test rax,rax
 jz fail
 mov r13,rax
 mov rdx,[gs:0x60]
 cmp [rdx+48],rax
 jne fail
 call [r14]
 cmp rax,r13
 jne fail
 alloc_size 8,33
 test rax,rax
 jz fail
 test al,15
 jnz fail
 mov r12,rax
 mov ecx,33
 mov rdi,rax
 xor eax,eax
 repe scasb
 jne fail
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 call [r14+32]
 cmp rax,33
 jne fail
 mov ecx,33
 mov rdi,r12
 mov al,0x73
 rep stosb
 error_is 0x12345678
 mov eax,[rbx]
 cmp eax,1
 je zero_size
 cmp eax,2
 je multipage
 cmp eax,3
 je bad_flags
 cmp eax,4
 je overflow
 cmp eax,5
 je bad_handle
 cmp eax,6
 je bad_pointer
 cmp eax,7
 je resize
 cmp eax,8
 je move_resize
 cmp eax,9
 je inplace_fail
 cmp eax,10
 je invalid_resize
 cmp eax,11
 je slots
 cmp eax,12
 je arena
 cmp eax,13
 je nx_fault
 cmp eax,14
 je handle_fault
 cmp eax,15
 je forever
 cmp eax,16
 je revoke
 cmp eax,17
 je stale
 cmp eax,18
 je free_null
 cmp eax,19
 je resize_zero
 cmp eax,20
 je free_flags
 cmp eax,21
 je kernel_free
 cmp eax,22
 je realloc_oom
 cmp eax,23
 je metadata_fault
 free_block r12
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 87
 jmp success
zero_size:
 alloc_size 0,0
 test rax,rax
 jz fail
 mov r15,rax
 mov rcx,r13
 xor edx,edx
 mov r8,r15
 call [r14+32]
 test rax,rax
 jnz fail
 free_block r15
 jmp success
multipage:
 alloc_size 8,4097
 test rax,rax
 jz fail
 mov r15,rax
 mov rdi,rax
 mov ecx,4097
 xor eax,eax
 repe scasb
 jne fail
 mov dword [r15+4093],0x73
 cmp dword [r15+4093],0x73
 jne fail
 free_block r15
 jmp success
bad_flags:
 alloc_size 4,64
 test rax,rax
 jnz fail
 error_is 0x12345678
 jmp success
overflow:
 alloc_size 0,-1
 test rax,rax
 jnz fail
 alloc_size 0,262145
 test rax,rax
 jnz fail
 error_is 0x12345678
 cmp byte [r12],0x73
 jne fail
 jmp success
bad_handle:
 lea rcx,[r13+1]
 xor edx,edx
 mov r8d,64
 call [r14+8]
 test rax,rax
 jnz fail
 error_is 0x12345678
 lea rcx,[r13+1]
 xor edx,edx
 mov r8,r12
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 6
 jmp success
bad_pointer:
 mov rcx,r13
 xor edx,edx
 lea r8,[r12+1]
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 87
 mov rcx,r13
 xor edx,edx
 lea r8,[r12+1]
 call [r14+32]
 cmp rax,-1
 jne fail
 error_is 87
 cmp byte [r12],0x73
 jne fail
 jmp success
resize:
 mov rcx,r13
 mov edx,8
 mov r8,r12
 mov r9d,128
 call [r14+24]
 cmp rax,r12
 jne fail
 mov rdi,r12
 mov ecx,33
 mov al,0x73
 repe scasb
 jne fail
 lea rdi,[r12+33]
 mov ecx,95
 xor eax,eax
 repe scasb
 jne fail
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 mov r9d,17
 call [r14+24]
 cmp rax,r12
 jne fail
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 call [r14+32]
 cmp rax,17
 jne fail
 error_is 0x12345678
 jmp success
move_resize:
inplace_fail:
 alloc_size 0,32
 test rax,rax
 jz fail
 mov r15,rax
 mov rcx,r13
 mov edx,8
 cmp qword [rbx],9
 jne resize_call
 or edx,16
resize_call:
 mov r8,r12
 mov r9d,256
 call [r14+24]
 cmp qword [rbx],9
 je expect_inplace_fail
 test rax,rax
 jz fail
 cmp rax,r12
 je fail
 mov [rbx+128],r12
 mov rdi,rax
 mov r12,rax
 mov ecx,33
 mov al,0x73
 repe scasb
 jne fail
 lea rdi,[r12+33]
 mov ecx,223
 xor eax,eax
 repe scasb
 jne fail
 mov rcx,r13
 xor edx,edx
 mov r8,[rbx+128]
 call [r14+32]
 cmp rax,-1
 jne fail
 error_is 87
 free_block r15
 free_block r12
 jmp success
expect_inplace_fail:
 test rax,rax
 jnz fail
 error_is 0x12345678
 cmp byte [r12],0x73
 jne fail
 free_block r15
 jmp success
invalid_resize:
 mov rcx,r13
 xor edx,edx
 xor r8d,r8d
 mov r9d,64
 call [r14+24]
 test rax,rax
 jnz fail
 mov rcx,r13
 xor edx,edx
 lea r8,[r12+1]
 mov r9,-1
 call [r14+24]
 test rax,rax
 jnz fail
 error_is 0x12345678
 jmp success
slots:
 xor r15d,r15d
slot_loop:
 alloc_size 0,1
 test rax,rax
 jz fail
 mov [rbx+256+r15*8],rax
 inc r15d
 cmp r15d,127
 jb slot_loop
 alloc_size 0,1
 test rax,rax
 jnz fail
 error_is 0x12345678
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 mov r9d,64
 call [r14+24]
 test rax,rax
 jnz fail
 error_is 0x12345678
 cmp byte [r12],0x73
 jne fail
 xor r15d,r15d
slot_free:
 mov rax,[rbx+256+r15*8]
 free_block rax
 inc r15d
 cmp r15d,127
 jb slot_free
 jmp success
arena:
 alloc_size 0,262144
 test rax,rax
 jnz fail
 free_block r12
 alloc_size 8,262144
 test rax,rax
 jz fail
 mov r15,rax
 mov byte [r15+262143],0x73
 cmp byte [r15+262143],0x73
 jne fail
 alloc_size 0,0
 test rax,rax
 jnz fail
 free_block r15
 alloc_size 0,0
 test rax,rax
 jz fail
 jmp success
nx_fault:
 mov byte [r12],0xc3
 call r12
 jmp fail
handle_fault:
 mov rax,[r13]
 jmp fail
forever:
 jmp forever
revoke:
 xor ecx,ecx
 mov eax,0x100100
 int 0x80
 alloc_size 8,64
 test rax,rax
 jnz fail
 error_is 0x12345678
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 mov r9d,64
 call [r14+24]
 test rax,rax
 jnz fail
 error_is 0x12345678
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 call [r14+32]
 cmp rax,-1
 jne fail
 error_is 5
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 5
 call [r14]
 test rax,rax
 jnz fail
 error_is 5
 cmp byte [r12],0x73
 jne fail
 jmp success
stale:
 mov rcx,[rbx+8]
 cmp rcx,r13
 je fail
 xor edx,edx
 mov r8d,64
 call [r14+8]
 test rax,rax
 jnz fail
 error_is 0x12345678
 jmp success
free_null:
 xor ecx,ecx
 xor edx,edx
 xor r8d,r8d
 call [r14+16]
 cmp eax,1
 jne fail
 mov rcx,r13
 xor edx,edx
 xor r8d,r8d
 call [r14+16]
 cmp eax,1
 jne fail
 error_is 0x12345678
 jmp success
resize_zero:
 mov rcx,r13
 mov edx,1
 mov r8,r12
 xor r9d,r9d
 call [r14+24]
 cmp rax,r12
 jne fail
 mov rcx,r13
 mov edx,1
 mov r8,r12
 call [r14+32]
 test rax,rax
 jnz fail
 error_is 0x12345678
 jmp success
free_flags:
 mov rcx,r13
 mov edx,8
 mov r8,r12
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 87
 cmp byte [r12],0x73
 jne fail
 jmp success
kernel_free:
 mov rcx,r13
 xor edx,edx
 mov r8d,0x100000
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 87
 jmp success
realloc_oom:
 alloc_size 0,32
 test rax,rax
 jz fail
 mov r15,rax
 mov rcx,r13
 xor edx,edx
 mov r8,r12
 mov r9d,262144
 call [r14+24]
 test rax,rax
 jnz fail
 error_is 0x12345678
 cmp byte [r12],0x73
 jne fail
 jmp success
metadata_fault:
 mov rax,[rbx+16]
 mov rax,[rax]
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
 dd 0x3040,0,0,0x30c0,0x3080
 times 64-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0x3180,0x31a0,0
 times 128-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0x3180,0x31a0,0
 times 192-($-$$) db 0
 db 'KERNEL32.dll',0
 times 224-($-$$) db 0
 dw 0
 db 'GetProcessHeap',0
 times 256-($-$$) db 0
 dw 0
 db 'HeapAlloc',0
 times 288-($-$$) db 0
 dw 0
 db 'HeapFree',0
 times 320-($-$$) db 0
 dw 0
 db 'HeapReAlloc',0
 times 352-($-$$) db 0
 dw 0
 db 'HeapSize',0
 times 384-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 416-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
 dq 0,0
 times 2048-($-$$) db 0
