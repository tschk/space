%include "windows-pe-header.asm"
entry:
    sub rsp, 40                    ; Microsoft x64 shadow space + fifth arg
    mov qword [rsp + 32], 0
    mov ecx, 9
    lea rdx, [rel msg]
    mov r8d, msglen
    lea r9, [rel written]
    call [rel iat]
    test eax, eax
    jnz fail
    cmp dword [rel written], 0
    jne fail
    mov ecx, 1
    xor edx, edx
    mov r8d, msglen
    lea r9, [rel written]
    call [rel iat]
    test eax, eax
    jnz fail
    mov ecx, 1
    lea rdx, [rel msg]
    mov r8d, msglen
    xor r9d, r9d
    call [rel iat]
    test eax, eax
    jnz fail
    mov qword [rsp + 32], 1
    mov ecx, 1
    lea rdx, [rel msg]
    mov r8d, msglen
    lea r9, [rel written]
    call [rel iat]
    test eax, eax
    jnz fail
    mov qword [rsp + 32], 0
    mov rdi, 0x12345678
    mov rsi, 0x23456789
    mov ecx, 1
    lea rdx, [rel msg]
    mov r8d, msglen
    lea r9, [rel written]
    call [rel iat]
    cmp eax, 1
    jne fail
    cmp dword [rel written], msglen
    jne fail
    cmp rdi, 0x12345678
    jne fail
    cmp rsi, 0x23456789
    jne fail
    xor ebx, ebx
    xor ebp, ebp
    xor r12d, r12d
    xor r13d, r13d
    xor r14d, r14d
    xor r15d, r15d
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
    dq write_name-image, exit_name-image, 0
    times 0x880-($-$$) db 0
iat:
    dq write_name-image, exit_name-image, 0
    times 0x900-($-$$) db 0
dll: db 'KERNEL32.dll', 0
    times 0x920-($-$$) db 0
write_name: dw 0
    db 'WriteFile', 0
    times 0x940-($-$$) db 0
exit_name: dw 0
    db 'ExitProcess', 0
    times 0xA00-($-$$) db 0
msg: db 'windows: PE import hello', 10
msglen equ $-msg
written: dd 0xFFFFFFFF
    times 4096-($-$$) db 0
