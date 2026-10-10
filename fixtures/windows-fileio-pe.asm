%include "windows-pe-header.asm"
%macro open_file 1
    lea rcx, [rel %1]
    mov edx, 0x80000000
    mov r8d, 1
    xor r9d, r9d
    call [rel iat + 16]
%endmacro
%macro read_file 2
    mov rcx, rbx
    lea rdx, [rel %1]
    mov r8d, %2
    lea r9, [rel written]
    call [rel iat + 24]
%endmacro
entry:
    sub rsp, 56                    ; shadow space and three stack arguments
    mov qword [rsp + 32], 3
    mov qword [rsp + 40], 0x80
    mov qword [rsp + 48], 0
    mov ecx, 3                     ; an existing kernel-owned descriptor
    lea rdx, [rel buffer]
    mov r8d, 27
    lea r9, [rel written]
    mov qword [rsp + 32], 0
    call [rel iat + 24]
    test eax, eax
    jnz fail
    mov ecx, 3
    call [rel iat + 32]
    test eax, eax
    jnz fail
    mov qword [rsp + 32], 3
    open_file missing
    cmp rax, -1
    jne fail
    xor ecx, ecx
    mov edx, 0x80000000
    mov r8d, 1
    xor r9d, r9d
    call [rel iat + 16]
    cmp rax, -1
    jne fail
    mov qword [rsp + 32], 2         ; refuse CREATE_ALWAYS before VFS access
    open_file path
    cmp rax, -1
    jne fail
    mov qword [rsp + 32], 3
    open_file path
    cmp rax, 3
    jb fail
    cmp rax, -1
    je fail
    mov rbx, rax
    mov qword [rsp + 32], 0         ; ReadFile/WriteFile OVERLAPPED
    mov rcx, rbx
    xor edx, edx
    mov r8d, 27
    lea r9, [rel written]
    call [rel iat + 24]
    test eax, eax
    jnz fail
    cmp dword [rel written], 0
    jne fail
    read_file buffer, 4097
    test eax, eax
    jnz fail
    mov rcx, rbx
    lea rdx, [rel buffer]
    mov r8d, 27
    xor r9d, r9d
    call [rel iat + 24]
    test eax, eax
    jnz fail
    mov qword [rsp + 32], 1
    read_file buffer, 27
    test eax, eax
    jnz fail
    mov qword [rsp + 32], 0
    read_file buffer, 27
    cmp eax, 1
    jne fail
    cmp dword [rel written], 27
    jne fail
    lea rsi, [rel buffer]
    lea rdi, [rel expected]
    mov ecx, 27
    cld
    repe cmpsb
    jne fail
    read_file buffer, 27
    cmp eax, 1
    jne fail
    cmp dword [rel written], 0
    jne fail
    mov rcx, rbx
    call [rel iat + 32]
    cmp eax, 1
    jne fail
    mov rcx, rbx
    call [rel iat + 32]
    test eax, eax
    jnz fail
    mov ecx, 1
    lea rdx, [rel buffer]
    mov r8d, 27
    lea r9, [rel written]
    call [rel iat]
    cmp eax, 1
    jne fail
    cmp dword [rel written], 27
    jne fail
    mov qword [rsp + 32], 3
    mov r12d, 12                   ; keep the host's fd 3, release every own slot
.exhaust:
    open_file path
    cmp rax, 3
    jb fail
    cmp rax, -1
    je fail
    dec r12d
    jnz .exhaust
    open_file path
    cmp rax, -1
    jne fail
    mov ecx, 42
    call [rel iat + 8]
    ud2
fail:
    mov ecx, 99
    call [rel iat + 8]
    ud2
    times 0x800-($-$$) db 0
imports:
    dd lookup-image, 0, 0, dll-image, iat-image
    times 5 dd 0
    times 0x840-($-$$) db 0
lookup:
    dq write_name-image, exit_name-image, open_name-image, read_name-image, close_name-image, 0
    times 0x880-($-$$) db 0
iat:
    dq write_name-image, exit_name-image, open_name-image, read_name-image, close_name-image, 0
    times 0x900-($-$$) db 0
dll: db 'KERNEL32.dll', 0
    times 0x920-($-$$) db 0
write_name: dw 0
    db 'WriteFile', 0
    times 0x940-($-$$) db 0
exit_name: dw 0
    db 'ExitProcess', 0
    times 0x960-($-$$) db 0
open_name: dw 0
    db 'CreateFileA', 0
    times 0x980-($-$$) db 0
read_name: dw 0
    db 'ReadFile', 0
    times 0x9A0-($-$$) db 0
close_name: dw 0
    db 'CloseHandle', 0
    times 0xA00-($-$$) db 0
path: db 'foreign-read.txt', 0
missing: db 'foreign-does-not-exist.txt', 0
expected: db 'foreign: VFS file contents', 10
buffer: times 64 db 0
written: dd 0xFFFFFFFF
    times 4096-($-$$) db 0
