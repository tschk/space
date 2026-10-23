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
    dd 0x3060, 32
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
    dd 8192, 0x5000, 512, 5120, 0, 0
    dw 0, 0
    dd 0xC0000040
section .text start=512 vstart=0x140001000
entry:
    mov rbx, 0x140005000
    mov r14, 0x140003060
    mov rax, [rbx]
    cmp eax, 1
    je readonly_write
    cmp eax, 2
    je readonly_execute
    cmp eax, 3
    je headers_write
    cmp eax, 4
    je text_write
    cmp eax, 5
    je bss_execute
    cmp eax, 6
    je kernel_read
    cmp eax, 7
    je peer_read
    cmp eax, 8
    je port_write
    cmp eax, 9
    je imported_write
    cmp eax, 10
    je imported_pid
    cmp eax, 11
    je imported_exit
    cmp eax, 12
    je infinite
    cmp eax, 13
    je invalid_output
    cmp eax, 14
    je crossing_input
    mov ax, cs
    and eax, 3
    cmp eax, 3
    jne fail
    mov rax, 0x140000000
    cmp word [rax], 0x5A4D
    jne fail
    cmp qword [rbx+512], 0
    jne fail
    cmp qword [rbx+4608], 0
    jne fail
    mov qword [rbx+4608], 73
success:
    mov eax, 42
    ret
fail:
    mov eax, 99
    ret
readonly_write:
    mov rax, 0x140003100
    mov byte [rax], 0
    jmp fail
readonly_execute:
    mov rax, 0x140003000
    call rax
    jmp fail
headers_write:
    mov rax, 0x140000000
    mov byte [rax], 0
    jmp fail
text_write:
    mov byte [rel entry], 0xC3
    jmp fail
bss_execute:
    mov byte [rbx+512], 0xC3
    lea rax, [rbx+512]
    call rax
    jmp fail
kernel_read:
    mov eax, [0x100000]
    jmp fail
peer_read:
    mov eax, [0x43000000]
    jmp fail
port_write:
    mov dx, 0x80
    out dx, al
    jmp fail
infinite:
    jmp infinite
imported_pid:
    sub rsp, 40
    call [r14]
    add rsp, 40
    test eax, eax
    jle fail
    jmp success
imported_exit:
    sub rsp, 40
    mov ecx, 0x1234002A
    call [r14+16]
    jmp fail
imported_write:
    sub rsp, 40
    mov ecx, 1
    mov rdx, 0x140003100
    mov r8d, 21
    lea r9, [rbx+32]
    mov qword [rsp+32], 0
    call [r14+8]
    add rsp, 40
    cmp eax, 1
    jne fail
    cmp dword [rbx+32], 21
    jne fail
    jmp success
invalid_output:
    sub rsp, 40
    mov ecx, 1
    mov rdx, 0x140003100
    mov r8d, 21
    mov r9, 0x140003120
    mov qword [rsp+32], 0
    call [r14+8]
    add rsp, 40
    test eax, eax
    jnz fail
    jmp success
crossing_input:
    sub rsp, 40
    mov ecx, 1
    mov rdx, 0x140006FFF
    mov r8d, 2
    lea r9, [rbx+32]
    mov qword [rsp+32], 0
    call [r14+8]
    add rsp, 40
    test eax, eax
    jnz fail
    cmp dword [rbx+32], 0
    jne fail
    jmp success
    times 4096-($-$$) db 0
section .rdata start=4608 vstart=0x140003000
    dd 0x3040, 0, 0, 0x3080, 0x3060
    times 5 dd 0
    times 64-($-$$) db 0
    dq 0x30A0, 0x30C0, 0x30E0, 0
    times 96-($-$$) db 0
    dq 0x30A0, 0x30C0, 0x30E0, 0
    times 128-($-$$) db 0
    db 'kernel32.DLL', 0
    times 160-($-$$) db 0
    dw 123
    db 'GetCurrentProcessId', 0
    times 192-($-$$) db 0
    dw 34
    db 'WriteFile', 0
    times 224-($-$$) db 0
    dw 0
    db 'ExitProcess', 0
    times 256-($-$$) db 0
    db 'windows-multisection', 10
    times 288-($-$$) db 0
    db 'Readonly', 0
    times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
    dq 0
    times 512-($-$$) db 0
