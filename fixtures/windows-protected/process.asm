; Original bounded PE32+ fixture, not a Windows application compatibility claim.
BITS 64
section .headers start=0 vstart=0x44000000
image:
    dw 0x5A4D
    times 60-($-$$) db 0
    dd 128
    times 128-($-$$) db 0
    dd 0x4550
    dw 0x8664, 2
    dd 0, 0, 0
    dw 240, 0x23
optional:
    dw 0x20B
    db 0, 0
    dd 4096, 512, 3584
    dd 0x1000, 0x1000
    dq image
    dd 4096, 512
    dw 6, 0, 0, 0, 6, 0
    dd 0, 0x4000, 512, 0
    dw 3, 256
    dq 0x10000, 0x1000, 0x10000, 0x1000
    dd 0, 16
    dq 0
    dd 0x3000, 40
    times 14 dq 0
    db '.text', 0, 0, 0
    dd 4096, 0x1000, 4096, 512, 0, 0
    dw 0, 0
    dd 0x60000020
    db '.data', 0, 0, 0
    dd 4096, 0x3000, 512, 4608, 0, 0
    dw 0, 0
    dd 0xC0000040
    times 512-($-$$) db 0
section .text start=512 vstart=0x44001000
entry:
    mov rbx, 0x44003000
    mov rax, [rbx+256]
    cmp eax, 24
    je infinite_loop
    cmp eax, 1
    je kernel_read
    cmp eax, 2
    je text_write
    cmp eax, 3
    je data_execute
    cmp eax, 4
    je stack_execute
    cmp eax, 5
    je port_write
    cmp eax, 6
    je other_read
    cmp eax, 7
    je other_write
    cmp eax, 8
    je headers_write
    cmp eax, 9
    je hole_read
    cmp eax, 10
    je imported_write
    cmp eax, 11
    je denied_write
    cmp eax, 12
    je invalid_handle
    cmp eax, 13
    je invalid_pointer
    cmp eax, 14
    je bad_written
    cmp eax, 15
    je bad_overlapped
    cmp eax, 16
    je empty_write
    cmp eax, 17
    je crossing_pointer
    cmp eax, 18
    je output_to_code
    cmp eax, 19
    je explicit_exit
    cmp eax, 20
    je process_id
    cmp eax, 21
    je unknown_service
    cmp eax, 22
    je invalid_std_handle
    cmp eax, 23
    je readonly_input
    mov ax, cs
    and eax, 3
    cmp eax, 3
    jne fail
    pushfq
    pop rax
    test eax, 0x3000
    jnz fail
    cmp qword [rbx+512], 0
    jne fail
    cmp qword [rbx+264], 0x12345678
    jne fail
    mov qword [rbx+512], 77
success:
    mov eax, 42
    ret
fail:
    mov eax, 99
    ret
infinite_loop:
    jmp infinite_loop
kernel_read:
    mov eax, [0x100000]
    jmp fail
text_write:
    mov byte [rel entry], 0xC3
    jmp fail
data_execute:
    mov byte [rbx+512], 0xC3
    lea rax, [rbx+512]
    call rax
    jmp fail
stack_execute:
    mov byte [rsp-16], 0xC3
    lea rax, [rsp-16]
    call rax
    jmp fail
port_write:
    mov dx, 0x80
    out dx, al
    jmp fail
other_read:
    mov eax, [0x43000000]
    jmp fail
other_write:
    mov dword [0x43000000], 77
    jmp fail
headers_write:
    mov byte [0x44000000], 0
    jmp fail
hole_read:
    mov eax, [0x44002000]
    jmp fail
process_id:
    sub rsp, 40
    call [rbx+112+16]
    add rsp, 40
    test eax, eax
    jle fail
    jmp success
explicit_exit:
    sub rsp, 40
    mov ecx, 0x1234002A
    call [rbx+112+24]
    jmp fail
unknown_service:
    mov eax, 0x999999
    int 0x80
    test eax, eax
    jnz fail
    sub rsp, 40
    call [rbx+112+32]
    add rsp, 40
    cmp eax, 120
    jne fail
    jmp success
invalid_std_handle:
    sub rsp, 40
    mov ecx, -10
    call [rbx+112]
    cmp rax, -1
    jne fail
    call [rbx+112+32]
    add rsp, 40
    cmp eax, 87
    jne fail
    jmp success
imported_write:
    xor ebp, ebp
    jmp write_setup
denied_write:
    mov ebp, 5
    jmp write_setup
invalid_handle:
    mov ebp, 6
    jmp write_setup
invalid_pointer:
    mov ebp, 998
    jmp write_setup
bad_written:
    mov ebp, 998
    jmp write_setup
bad_overlapped:
    mov ebp, 87
    jmp write_setup
empty_write:
    xor ebp, ebp
    jmp write_setup
crossing_pointer:
    mov ebp, 998
    jmp write_setup
output_to_code:
    mov ebp, 998
    jmp write_setup
readonly_input:
    xor ebp, ebp
write_setup:
    sub rsp, 40
    mov ecx, -11
    call [rbx+112]
    cmp eax, 1
    jne fail
    mov ecx, eax
    lea rdx, [rbx+288]
    mov r8d, message_end-message
    lea r9, [rbx+280]
    mov dword [r9], 0xFFFFFFFF
    mov qword [rsp+32], 0
    mov rax, [rbx+256]
    cmp eax, 12
    jne .not_handle
    mov ecx, 3
.not_handle:
    cmp eax, 13
    jne .not_pointer
    mov edx, 0x100000
.not_pointer:
    cmp eax, 14
    jne .not_written
    xor r9d, r9d
.not_written:
    cmp eax, 15
    jne .not_overlapped
    mov qword [rsp+32], 1
.not_overlapped:
    cmp eax, 16
    jne .not_empty
    xor edx, edx
    xor r8d, r8d
.not_empty:
    cmp eax, 17
    jne .not_crossing
    mov edx, 0x44003FFF
    mov byte [rdx], 'X'
    mov r8d, 2
.not_crossing:
    cmp eax, 18
    jne .not_code
    lea r9, [rel entry]
.not_code:
    cmp eax, 23
    jne .not_readonly
    lea rdx, [rel text_message]
    mov r8d, text_message_end-text_message
.not_readonly:
    mov edi, 0x12345678
    mov esi, 0x23456789
    mov r12d, 0x3456789A
    mov r13d, 0x456789AB
    mov r14d, 0x56789ABC
    mov r15d, 0x6789ABCD
    movq xmm6, r12
    movq xmm15, r15
    call [rbx+112+8]
    mov r10d, eax
    cmp edi, 0x12345678
    jne fail
    cmp esi, 0x23456789
    jne fail
    cmp r12d, 0x3456789A
    jne fail
    cmp r13d, 0x456789AB
    jne fail
    cmp r14d, 0x56789ABC
    jne fail
    cmp r15d, 0x6789ABCD
    jne fail
    movq rax, xmm6
    cmp rax, r12
    jne fail
    movq rax, xmm15
    cmp rax, r15
    jne fail
    mov eax, r10d
    test ebp, ebp
    jnz .expected_failure
    cmp eax, 1
    jne fail
    mov eax, [rbx+280]
    mov rcx, [rbx+256]
    cmp ecx, 16
    je .expect_empty
    cmp ecx, 23
    je .expect_text
    cmp eax, message_end-message
    jne fail
    jmp .done
.expect_text:
    cmp eax, text_message_end-text_message
    jne fail
    jmp .done
.expect_empty:
    test eax, eax
    jnz fail
    jmp .done
.expected_failure:
    test eax, eax
    jnz fail
    mov rcx, [rbx+256]
    cmp ecx, 14
    je .unmodified
    cmp ecx, 18
    je .unmodified
    cmp dword [rbx+280], 0
    jne fail
    jmp .error
.unmodified:
    cmp dword [rbx+280], 0xFFFFFFFF
    jne fail
.error:
    call [rbx+112+32]
    cmp eax, ebp
    jne fail
.done:
    add rsp, 40
    jmp success
text_message: db 'windows-readonly-input', 10
text_message_end:
    times 4096-($-$$) db 0
section .data start=4608 vstart=0x44003000
    dd 0x3040, 0, 0, 0x30A0, 0x3070
    times 5 dd 0
    times 64-($-$$) db 0
lookup:
    dq 0x30B0, 0x30C0, 0x30D0, 0x30F0, 0x3140, 0
    times 112-($-$$) db 0
iat:
    dq 0x30B0, 0x30C0, 0x30D0, 0x30F0, 0x3140, 0
    db 'KERNEL32.dll', 0
    times 176-($-$$) db 0
    dw 0
    db 'GetStdHandle', 0
    times 192-($-$$) db 0
    dw 0
    db 'WriteFile', 0
    times 208-($-$$) db 0
    dw 0
    db 'GetCurrentProcessId', 0
    times 240-($-$$) db 0
    dw 0
    db 'ExitProcess', 0
    times 256-($-$$) db 0
mode: dq 0
    dq 0x12345678
    times 280-($-$$) db 0
written: dd 0
    times 288-($-$$) db 0
message: db 'windows-private-write', 10
message_end:
    times 320-($-$$) db 0
    dw 0
    db 'GetLastError', 0
    times 512-($-$$) db 0
