; Original PE32+ file API client; consumes real Space VFS data, no host service.
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
    dw 0x20B
    db 0, 0
    dd 4096, 4096, 4096
    dd 0x1000, 0x1000
    dq image
    dd 4096, 512
    dw 6, 0, 0, 0, 6, 0
    dd 0, 0x5000, 512, 0
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
    dd 8192, 0x3000, 4096, 4608, 0, 0
    dw 0, 0
    dd 0xC0000040
    times 512-($-$$) db 0
section .text start=512 vstart=0x44001000
entry:
    sub rsp, 72
    mov rbx, 0x44003000
    mov rbp, [rbx+0x300]
    xor r12d, r12d
    cmp ebp, 6
    je invalid_handle
    lea rcx, [rbx+0x400]
    mov edx, 0x80000000
    mov r8d, 1
    xor r9d, r9d
    mov qword [rsp+32], 3
    mov qword [rsp+40], 0x80
    mov qword [rsp+48], 0
    cmp ebp, 2
    jne .not_create
    mov qword [rsp+32], 2
.not_create:
    cmp ebp, 3
    jne .not_missing
    lea rcx, [rbx+0x440]
.not_missing:
    cmp ebp, 4
    jne .not_path
    mov ecx, 0x100000
.not_path:
    cmp ebp, 5
    jne .not_long
    lea rcx, [rbx+0x600]
    mov rax, 0x4141414141414141
    xor edi, edi
.fill_path:
    mov [rcx+rdi], rax
    add edi, 8
    cmp edi, 256
    jb .fill_path
.not_long:
    call [rbx+0xA0+40]
    cmp ebp, 1
    je expect_create_denied
    cmp ebp, 2
    je expect_create_flags
    cmp ebp, 3
    je expect_create_missing
    cmp ebp, 4
    je expect_create_pointer
    cmp ebp, 5
    je expect_create_long
    cmp eax, 3
    jne fail
    mov r12, rax
    cmp ebp, 19
    je exhaust_handles
    cmp ebp, 20
    je success
    cmp ebp, 22
    je fault_after_open
    cmp ebp, 23
    je infinite_after_open
    cmp ebp, 12
    je seek_bad_output
    cmp ebp, 13
    je seek_negative
    cmp ebp, 14
    je seek_bad_method
    cmp ebp, 15
    je seek_huge
    cmp ebp, 16
    je size_bad_output
    cmp ebp, 17
    je size_bad_handle
    cmp ebp, 18
    je other_handle
    cmp ebp, 21
    je revoke_after_open
    cmp ebp, 24
    je zero_before_eof
    cmp ebp, 0
    jne read_failure
    ; Exact file size and prefix through real borrowed VFS descriptor.
    mov rcx, r12
    lea rdx, [rbx+0x520]
    call [rbx+0xA0+72]
    cmp eax, 1
    jne fail
    cmp qword [rbx+0x520], 16
    jne fail
    mov rcx, r12
    lea rdx, [rbx+0x600]
    mov r8d, 4
    lea r9, [rbx+0x500]
    mov qword [rsp+32], 0
    call [rbx+0xA0+48]
    cmp eax, 1
    jne fail
    cmp dword [rbx+0x500], 4
    jne fail
    cmp dword [rbx+0x600], 0x33323130
    jne fail
    mov rcx, r12
    mov edx, 2
    lea r8, [rbx+0x510]
    mov r9d, 1
    call [rbx+0xA0+56]
    cmp eax, 1
    jne fail
    cmp qword [rbx+0x510], 6
    jne fail
    mov rcx, r12
    lea rdx, [rbx+0x600]
    mov r8d, 16
    lea r9, [rbx+0x500]
    mov qword [rsp+32], 0
    call [rbx+0xA0+48]
    cmp eax, 1
    jne fail
    cmp dword [rbx+0x500], 10
    jne fail
    cmp dword [rbx+0x600], 0x39383736
    jne fail
    cmp word [rbx+0x608], 0x6665
    jne fail
    mov rcx, r12
    lea rdx, [rbx+0x600]
    mov r8d, 16
    lea r9, [rbx+0x500]
    call [rbx+0xA0+48]
    cmp eax, 1
    jne fail
    cmp dword [rbx+0x500], 0
    jne fail
    mov rcx, r12
    xor edx, edx
    xor r8d, r8d
    lea r9, [rbx+0x500]
    call [rbx+0xA0+48]
    cmp eax, 1
    jne fail
    cmp dword [rbx+0x500], 0
    jne fail
    mov rcx, r12
    mov rdx, -2
    lea r8, [rbx+0x510]
    mov r9d, 2
    call [rbx+0xA0+56]
    cmp eax, 1
    jne fail
    cmp qword [rbx+0x510], 14
    jne fail
    mov rcx, r12
    xor edx, edx
    xor r8d, r8d
    xor r9d, r9d
    call [rbx+0xA0+56]
    cmp eax, 1
    jne fail
    mov rcx, r12
    call [rbx+0xA0+64]
    cmp eax, 1
    jne fail
    mov rcx, r12
    call [rbx+0xA0+64]
    test eax, eax
    jnz fail
    mov r13d, 6
    xor r12d, r12d
    jmp check_error
read_failure:
    mov rcx, r12
    lea rdx, [rbx+0x600]
    mov r8d, 4
    lea r9, [rbx+0x500]
    mov dword [r9], 0xFFFFFFFF
    mov qword [rsp+32], 0
    mov r13d, 998
    cmp ebp, 25
    jne .not_large
    mov r8d, 4097
    mov r13d, 87
.not_large:
    cmp ebp, 7
    jne .not_read_bad
    mov edx, 0x100000
.not_read_bad:
    cmp ebp, 8
    jne .not_read_code
    lea rdx, [rel entry]
.not_read_code:
    cmp ebp, 9
    jne .not_crossing
    mov edx, 0x44004FFF
    mov r8d, 2
.not_crossing:
    cmp ebp, 10
    jne .not_overlap
    mov qword [rsp+32], 1
    mov r13d, 87
.not_overlap:
    cmp ebp, 11
    jne .not_count
    lea r9, [rel entry]
.not_count:
    call [rbx+0xA0+48]
    test eax, eax
    jnz fail
    cmp ebp, 11
    je .count_unchanged
    cmp dword [rbx+0x500], 0
    jne fail
    jmp check_error
.count_unchanged:
    cmp dword [rbx+0x500], 0xFFFFFFFF
    jne fail
    jmp check_error
zero_before_eof:
    mov rcx, r12
    xor edx, edx
    xor r8d, r8d
    lea r9, [rbx+0x500]
    mov dword [r9], -1
    mov qword [rsp+32], 0
    call [rbx+0xA0+48]
    cmp eax, 1
    jne fail
    cmp dword [rbx+0x500], 0
    jne fail
    mov rcx, r12
    xor edx, edx
    lea r8, [rbx+0x510]
    mov r9d, 1
    call [rbx+0xA0+56]
    cmp eax, 1
    jne fail
    cmp qword [rbx+0x510], 0
    jne fail
    jmp success
invalid_handle:
    mov ecx, 3
    lea rdx, [rbx+0x600]
    mov r8d, 4
    lea r9, [rbx+0x500]
    mov qword [rsp+32], 0
    call [rbx+0xA0+48]
    test eax, eax
    jnz fail
    mov r13d, 6
    jmp check_error
other_handle:
    mov ecx, 4
    lea rdx, [rbx+0x600]
    mov r8d, 4
    lea r9, [rbx+0x500]
    mov qword [rsp+32], 0
    call [rbx+0xA0+48]
    test eax, eax
    jnz fail
    mov r13d, 6
    jmp check_error
seek_bad_output:
    mov rcx, r12
    mov edx, 1
    lea r8, [rel entry]
    xor r9d, r9d
    call [rbx+0xA0+56]
    test eax, eax
    jnz fail
    mov r13d, 998
    jmp check_error
seek_negative:
    mov rdx, -1
    xor r9d, r9d
    mov r13d, 131
    jmp seek_failure
seek_bad_method:
    xor edx, edx
    mov r9d, 99
    mov r13d, 87
    jmp seek_failure
seek_huge:
    mov edx, 0x80000000
    xor r9d, r9d
    mov r13d, 87
seek_failure:
    mov rcx, r12
    lea r8, [rbx+0x510]
    mov qword [r8], -1
    call [rbx+0xA0+56]
    test eax, eax
    jnz fail
    cmp qword [rbx+0x510], -1
    jne fail
    jmp check_error
size_bad_output:
    mov rcx, r12
    lea rdx, [rel entry]
    call [rbx+0xA0+72]
    test eax, eax
    jnz fail
    mov r13d, 998
    jmp check_error
size_bad_handle:
    mov ecx, 999
    lea rdx, [rbx+0x520]
    mov qword [rdx], -1
    call [rbx+0xA0+72]
    test eax, eax
    jnz fail
    cmp qword [rbx+0x520], -1
    jne fail
    mov r13d, 6
    jmp check_error
expect_create_denied:
    mov r13d, 5
    jmp create_failed
expect_create_flags:
    mov r13d, 87
    jmp create_failed
expect_create_missing:
    mov r13d, 2
    jmp create_failed
expect_create_pointer:
    mov r13d, 998
    jmp create_failed
expect_create_long:
    mov r13d, 206
create_failed:
    cmp rax, -1
    jne fail
    jmp check_error
exhaust_handles:
    lea rcx, [rbx+0x400]
    mov edx, 0x80000000
    mov r8d, 1
    xor r9d, r9d
    mov qword [rsp+32], 3
    mov qword [rsp+40], 0x80
    mov qword [rsp+48], 0
    call [rbx+0xA0+40]
    cmp rax, -1
    jne exhaust_handles
    mov r13d, 4
    jmp check_error
fault_after_open:
    mov eax, [0x100000]
    jmp fail
infinite_after_open:
    jmp infinite_after_open
revoke_after_open:
    mov eax, 0x100100
    int 0x80
    mov rcx, r12
    lea rdx, [rbx+0x600]
    mov r8d, 4
    lea r9, [rbx+0x500]
    mov qword [rsp+32], 0
    call [rbx+0xA0+48]
    test eax, eax
    jnz fail
    mov r13d, 5
check_error:
    call [rbx+0xA0+32]
    cmp eax, r13d
    jne fail
    cmp ebp, 21
    jne .not_revoked
    mov rcx, r12
    lea rdx, [rbx+0x520]
    mov qword [rdx], -1
    call [rbx+0xA0+72]
    test eax, eax
    jnz fail
    cmp qword [rbx+0x520], -1
    jne fail
    call [rbx+0xA0+32]
    cmp eax, 5
    jne fail
    mov rcx, r12
    xor edx, edx
    lea r8, [rbx+0x510]
    mov qword [r8], -1
    xor r9d, r9d
    call [rbx+0xA0+56]
    test eax, eax
    jnz fail
    cmp qword [rbx+0x510], -1
    jne fail
    call [rbx+0xA0+32]
    cmp eax, 5
    jne fail
    lea rcx, [rbx+0x400]
    mov edx, 0x80000000
    mov r8d, 1
    xor r9d, r9d
    mov qword [rsp+32], 3
    mov qword [rsp+40], 0x80
    mov qword [rsp+48], 0
    call [rbx+0xA0+40]
    cmp rax, -1
    jne fail
    call [rbx+0xA0+32]
    cmp eax, 5
    jne fail
.not_revoked:
    cmp r12d, 3
    jl success
    ; Check invalid read/seek paths never advanced the VFS offset.
    cmp ebp, 7
    jb .close
    cmp ebp, 18
    ja .close
    mov rcx, r12
    xor edx, edx
    lea r8, [rbx+0x510]
    mov r9d, 1
    call [rbx+0xA0+56]
    cmp eax, 1
    jne fail
    cmp qword [rbx+0x510], 0
    jne fail
.close:
    mov rcx, r12
    call [rbx+0xA0+64]
    cmp eax, 1
    jne fail
success:
    add rsp, 72
    mov eax, 42
    ret
fail:
    add rsp, 72
    mov eax, 99
    ret
    times 4096-($-$$) db 0
section .data start=4608 vstart=0x44003000
    dd 0x3040, 0, 0, 0x3100, 0x30A0
    times 5 dd 0
    times 64-($-$$) db 0
    dq 0x3120, 0x3140, 0x3160, 0x3180, 0x31A0, 0x31C0, 0x31E0, 0x3200, 0x3220, 0x3240, 0
    times 160-($-$$) db 0
    dq 0x3120, 0x3140, 0x3160, 0x3180, 0x31A0, 0x31C0, 0x31E0, 0x3200, 0x3220, 0x3240, 0
    times 256-($-$$) db 0
    db 'KERNEL32.dll', 0
%macro import_name 2
    times %1-($-$$) db 0
    dw 0
    db %2, 0
%endmacro
    import_name 288, 'GetStdHandle'
    import_name 320, 'WriteFile'
    import_name 352, 'GetCurrentProcessId'
    import_name 384, 'ExitProcess'
    import_name 416, 'GetLastError'
    import_name 448, 'CreateFileA'
    import_name 480, 'ReadFile'
    import_name 512, 'SetFilePointerEx'
    import_name 544, 'CloseHandle'
    import_name 576, 'GetFileSizeEx'
    times 768-($-$$) db 0
    dq 0
    times 1024-($-$$) db 0
    db 'windows-file-api.txt', 0
    times 1088-($-$$) db 0
    db 'windows-missing-api.txt', 0
    times 4096-($-$$) db 0
