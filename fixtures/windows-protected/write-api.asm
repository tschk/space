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
    dd 8192, 4096, 4096
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
    dd 8192, 0x1000, 8192, 512, 0, 0
    dw 0, 0
    dd 0x60000020
    db '.data', 0, 0, 0
    dd 8192, 0x3000, 4096, 8704, 0, 0
    dw 0, 0
    dd 0xC0000040
    times 512-($-$$) db 0
section .text start=512 vstart=0x44001000
%define IAT 0xA0
%define COUNT 0x500
%define POSITION 0x510
%define SIZE 0x520
%define BUFFER 0x600
%macro OPEN 2
    lea rcx, [rbx+%2]
    mov edx, %1
    mov r8d, 1
    xor r9d, r9d
    mov [rsp+32], r15
    mov qword [rsp+40], 0x80
    mov qword [rsp+48], 0
    call [rbx+IAT+40]
%endmacro
%macro WRITE 2
    mov rcx, r12
    %1
    mov r8d, %2
    lea r9, [rbx+COUNT]
    mov dword [r9], -1
    mov qword [rsp+32], 0
    call [rbx+IAT+8]
%endmacro
%macro SEEK 2
    mov rcx, r12
    mov rdx, %1
    lea r8, [rbx+POSITION]
    mov r9d, %2
    call [rbx+IAT+56]
    cmp eax, 1
    jne fail
%endmacro
%macro GET_SIZE 0
    mov rcx, r12
    lea rdx, [rbx+SIZE]
    call [rbx+IAT+72]
    cmp eax, 1
    jne fail
%endmacro
%macro READ 1
    mov rcx, r12
    lea rdx, [rbx+BUFFER]
    mov r8d, %1
    lea r9, [rbx+COUNT]
    mov dword [r9], -1
    mov qword [rsp+32], 0
    call [rbx+IAT+48]
%endmacro
%macro CLOSE 0
    mov rcx, r12
    call [rbx+IAT+64]
    cmp eax, 1
    jne fail
    xor r12d, r12d
%endmacro
%macro EXPECT_ERROR 1
    test eax, eax
    jnz fail
    cmp dword [rbx+COUNT], 0
    jne fail
    call [rbx+IAT+32]
    cmp eax, %1
    jne fail
%endmacro
entry:
    sub rsp, 72
    mov rbx, 0x44003000
    mov rbp, [rbx+0x300]
    xor r12d, r12d
    xor r13d, r13d
    mov r14d, 0x400
    mov r15d, 3
    cmp ebp, 100
    jae persistent
    cmp ebp, 0
    je pipeline
    cmp ebp, 1
    je create_new
    cmp ebp, 2
    je open_existing
    cmp ebp, 3
    je open_new
    cmp ebp, 4
    je truncate
    cmp ebp, 5
    je missing_truncate
    cmp ebp, 14
    je denied_create
    cmp ebp, 15
    je invalid_access
    cmp ebp, 16
    je invalid_sharing
    cmp ebp, 25
    je invalid_name
    cmp ebp, 10
    je readonly_write
    cmp ebp, 11
    je writeonly_read
    OPEN 0xC0000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    cmp ebp, 12
    je zero_after_seek
    cmp ebp, 13
    je revoke_write
    cmp ebp, 17
    je sharing_violation
    cmp ebp, 18
    je readonly_source
    cmp ebp, 19
    je zero_write
    cmp ebp, 21
    je oversized_file
    cmp ebp, 22
    je fault_after_write
    cmp ebp, 23
    je infinite_after_write
    cmp ebp, 24
    je sparse_write
    ; Invalid writes must not advance offset or modify content.
    mov rcx, r12
    lea rdx, [rbx+BUFFER]
    mov r8d, 4
    lea r9, [rbx+COUNT]
    mov dword [r9], -1
    mov qword [rsp+32], 0
    mov r13d, 998
    cmp ebp, 6
    jne .not_kernel
    mov edx, 0x100000
.not_kernel:
    cmp ebp, 7
    jne .not_cross
    mov edx, 0x44004FFF
    mov r8d, 2
.not_cross:
    cmp ebp, 8
    jne .not_count
    lea r9, [rel entry]
.not_count:
    cmp ebp, 9
    jne .not_overlapped
    mov qword [rsp+32], 1
    mov r13d, 87
.not_overlapped:
    cmp ebp, 20
    jne .not_huge
    mov r8d, 4097
    mov r13d, 87
.not_huge:
    call [rbx+IAT+8]
    test eax, eax
    jnz fail
    cmp ebp, 8
    je .count_unmodified
    cmp dword [rbx+COUNT], 0
    jne fail
    jmp .check_error
.count_unmodified:
    cmp dword [rbx+COUNT], -1
    jne fail
.check_error:
    call [rbx+IAT+32]
    cmp eax, r13d
    jne fail
unchanged:
    SEEK 0, 1
    cmp qword [rbx+POSITION], 0
    jne fail
    GET_SIZE
    cmp qword [rbx+SIZE], 16
    jne fail
    CLOSE
    jmp success
pipeline:
    mov r15d, 2
    OPEN 0xC0000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    call [rbx+IAT+32]
    cmp eax, 183
    jne fail
    GET_SIZE
    cmp qword [rbx+SIZE], 0
    jne fail
    xor edi, edi
.fill:
    mov eax, edi
    add eax, 'A'
    mov [rbx+BUFFER+rdi], al
    inc edi
    cmp edi, 64
    jb .fill
    WRITE {lea rdx, [rbx+BUFFER]}, 64
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 64
    jne fail
    SEEK 13, 0
    mov dword [rbx+BUFFER], 0x005A5A5A
    WRITE {lea rdx, [rbx+BUFFER]}, 3
    cmp eax, 1
    jne fail
    SEEK 0, 2
    mov dword [rbx+BUFFER], 0x6C696174
    WRITE {lea rdx, [rbx+BUFFER]}, 4
    cmp eax, 1
    jne fail
    GET_SIZE
    cmp qword [rbx+SIZE], 68
    jne fail
    CLOSE
    mov r15d, 3
    OPEN 0x80000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    READ 68
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 68
    jne fail
    xor edi, edi
.verify:
    mov eax, edi
    add eax, 'A'
    cmp edi, 13
    jb .normal
    cmp edi, 16
    jae .normal
    mov eax, 'Z'
.normal:
    cmp [rbx+BUFFER+rdi], al
    jne fail
    inc edi
    cmp edi, 64
    jb .verify
    cmp dword [rbx+BUFFER+64], 0x6C696174
    jne fail
    READ 1
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 0
    jne fail
    CLOSE
    jmp success
create_new:
    mov r15d, 1
    OPEN 0xC0000000, 0x440
    cmp eax, 3
    jne fail
    mov r12, rax
    mov rax, 0x6867666564636261
    mov [rbx+BUFFER], rax
    WRITE {lea rdx, [rbx+BUFFER]}, 8
    cmp eax, 1
    jne fail
    CLOSE
    OPEN 0xC0000000, 0x440
    cmp rax, -1
    jne fail
    call [rbx+IAT+32]
    cmp eax, 80
    jne fail
    jmp success
open_existing:
    mov r15d, 4
    OPEN 0xC0000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    call [rbx+IAT+32]
    cmp eax, 183
    jne fail
    jmp unchanged
open_new:
    mov r15d, 4
    OPEN 0xC0000000, 0x440
    cmp eax, 3
    jne fail
    mov r12, rax
    call [rbx+IAT+32]
    test eax, eax
    jnz fail
    GET_SIZE
    cmp qword [rbx+SIZE], 0
    jne fail
    CLOSE
    jmp success
truncate:
    mov r15d, 5
    OPEN 0x40000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    GET_SIZE
    cmp qword [rbx+SIZE], 0
    jne fail
    CLOSE
    jmp success
missing_truncate:
    mov r15d, 5
    OPEN 0x40000000, 0x4C0
    cmp rax, -1
    jne fail
    call [rbx+IAT+32]
    cmp eax, 2
    jne fail
    jmp success
readonly_write:
    OPEN 0x80000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    WRITE {lea rdx, [rbx+BUFFER]}, 4
    EXPECT_ERROR 5
    jmp unchanged
writeonly_read:
    OPEN 0x40000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    READ 4
    EXPECT_ERROR 5
    jmp unchanged
zero_after_seek:
    SEEK 32, 0
    WRITE {xor edx, edx}, 0
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 0
    jne fail
    GET_SIZE
    cmp qword [rbx+SIZE], 16
    jne fail
    SEEK 0, 1
    cmp qword [rbx+POSITION], 32
    jne fail
    CLOSE
    jmp success
revoke_write:
    mov eax, 0x100100
    int 0x80
    WRITE {lea rdx, [rbx+BUFFER]}, 4
    EXPECT_ERROR 5
    CLOSE
    jmp success
denied_create:
    mov r15d, 2
    OPEN 0x40000000, r14
    cmp rax, -1
    jne fail
    call [rbx+IAT+32]
    cmp eax, 5
    jne fail
    jmp success
invalid_access:
    OPEN 0, r14
    cmp rax, -1
    jne fail
    call [rbx+IAT+32]
    cmp eax, 87
    jne fail
    jmp success
invalid_name:
    xor edi, edi
.fill_name:
    mov byte [rbx+BUFFER+rdi], 'a'
    inc edi
    cmp edi, 25
    jb .fill_name
    mov byte [rbx+BUFFER+25], 0
    lea rcx, [rbx+BUFFER]
    mov edx, 0x40000000
    mov r8d, 1
    xor r9d, r9d
    mov qword [rsp+32], 1
    mov qword [rsp+40], 0x80
    mov qword [rsp+48], 0
    call [rbx+IAT+40]
    cmp rax, -1
    jne fail
    call [rbx+IAT+32]
    cmp eax, 206
    jne fail
    jmp success
invalid_sharing:
    lea rcx, [rbx+r14]
    mov edx, 0x40000000
    mov r8d, 4
    xor r9d, r9d
    mov qword [rsp+32], 3
    mov qword [rsp+40], 0x80
    mov qword [rsp+48], 0
    call [rbx+IAT+40]
    cmp rax, -1
    jne fail
    call [rbx+IAT+32]
    cmp eax, 87
    jne fail
    jmp success
sharing_violation:
    OPEN 0x40000000, r14
    cmp rax, -1
    jne fail
    call [rbx+IAT+32]
    cmp eax, 32
    jne fail
    jmp unchanged
readonly_source:
    WRITE {lea rdx, [rel entry]}, 8
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 8
    jne fail
    CLOSE
    jmp success
zero_write:
    WRITE {xor edx, edx}, 0
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 0
    jne fail
    jmp unchanged
oversized_file:
    SEEK 65536, 0
    WRITE {lea rdx, [rbx+BUFFER]}, 1
    EXPECT_ERROR 223
    GET_SIZE
    cmp qword [rbx+SIZE], 16
    jne fail
    SEEK 0, 1
    cmp qword [rbx+POSITION], 65536
    jne fail
    CLOSE
    jmp success
fault_after_write:
    mov dword [rbx+BUFFER], 0x54534554
    WRITE {lea rdx, [rbx+BUFFER]}, 4
    cmp eax, 1
    jne fail
    mov eax, [0x100000]
    jmp fail
infinite_after_write:
    mov dword [rbx+BUFFER], 0x54534554
    WRITE {lea rdx, [rbx+BUFFER]}, 4
    cmp eax, 1
    jne fail
.loop:
    jmp .loop
sparse_write:
    SEEK 80, 0
    mov dword [rbx+BUFFER], 0x74736574
    WRITE {lea rdx, [rbx+BUFFER]}, 4
    cmp eax, 1
    jne fail
    GET_SIZE
    cmp qword [rbx+SIZE], 84
    jne fail
    SEEK 16, 0
    READ 68
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 68
    jne fail
    xor edi, edi
.zeros:
    cmp byte [rbx+BUFFER+rdi], 0
    jne fail
    inc edi
    cmp edi, 64
    jb .zeros
    cmp dword [rbx+BUFFER+64], 0x74736574
    jne fail
    CLOSE
    jmp success
persistent:
    mov r14d, 0x480
    cmp ebp, 101
    je .read
    cmp ebp, 105
    je .read
    cmp ebp, 104
    je .prefix
    mov r15d, 1
    cmp ebp, 102
    jne .not_truncate
    mov r15d, 5
.not_truncate:
    cmp ebp, 103
    jne .open
    mov r15d, 2
.open:
    OPEN 0xC0000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    cmp ebp, 102
    jb .fill_begin
    GET_SIZE
    cmp qword [rbx+SIZE], 0
    jne fail
    cmp ebp, 103
    jne .fill_begin
    call [rbx+IAT+32]
    cmp eax, 183
    jne fail
.fill_begin:
    xor edi, edi
.fill:
    mov eax, edi
    xor edx, edx
    mov ecx, 251
    div ecx
    mov [rbx+BUFFER+rdi], dl
    inc edi
    cmp edi, 4096
    jb .fill
    WRITE {lea rdx, [rbx+BUFFER]}, 4096
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 4096
    jne fail
    WRITE {lea rdx, [rbx+BUFFER]}, 4096
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 4096
    jne fail
    CLOSE
    jmp .read
.prefix:
    mov r15d, 3
    OPEN 0xC0000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    mov rax, 0x68637461506E6957
    mov [rbx+BUFFER], rax
    WRITE {lea rdx, [rbx+BUFFER]}, 8
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 8
    jne fail
    CLOSE
.read:
    mov r15d, 3
    OPEN 0x80000000, r14
    cmp eax, 3
    jne fail
    mov r12, rax
    GET_SIZE
    cmp qword [rbx+SIZE], 8192
    jne fail
    mov r13d, 2
.read_chunk:
    READ 4096
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 4096
    jne fail
    xor edi, edi
.verify:
    mov eax, edi
    xor edx, edx
    mov ecx, 251
    div ecx
    cmp ebp, 104
    jb .compare
    cmp r13d, 2
    jne .compare
    cmp edi, 8
    jae .compare
    lea rax, [rel prefix_bytes]
    mov dl, [rax+rdi]
.compare:
    cmp [rbx+BUFFER+rdi], dl
    jne fail
    inc edi
    cmp edi, 4096
    jb .verify
    dec r13d
    jnz .read_chunk
    READ 1
    cmp eax, 1
    jne fail
    cmp dword [rbx+COUNT], 0
    jne fail
    CLOSE
success:
    add rsp, 72
    mov eax, 42
    ret
fail:
    add rsp, 72
    mov eax, 99
    ret
prefix_bytes: db 'WinPatch'
    times 8192-($-$$) db 0
section .data start=8704 vstart=0x44003000
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
    times 1152-($-$$) db 0
    db 'windows-persist.txt', 0
    times 1216-($-$$) db 0
    db 'windows-never-api.txt', 0
    times 4096-($-$$) db 0
