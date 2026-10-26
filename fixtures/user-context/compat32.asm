BITS 32
ORG 0x42000000
    mov eax, [0x42002000]
    cmp eax, 1
    je spin
    cmp eax, 2
    je readonly_fault
    cmp eax, 3
    je privileged_fault
    cmp eax, 4
    je nx_fault
    mov ebx, 0x12345678
    mov eax, 0x11223344
    movd xmm0, eax
    fld1
    mov eax, 0x320001
    int 0x80
    cmp eax, 0x89ABCDEF
    jne bad
    cmp ebx, 0x12345678
    jne bad
    movd eax, xmm0
    cmp eax, 0x11223344
    jne bad
    fstp dword [0x42002010]
    cmp dword [0x42002010], 0x3f800000
    jne bad
    mov eax, 0x320002
    int 0x80
bad:
    ud2
spin:
    jmp spin
readonly_fault:
    mov byte [0x42000000], 0
    jmp bad
privileged_fault:
    out 0x80, al
    jmp bad
nx_fault:
    jmp 0x42002000
times 4096-($-$$) db 0
BITS 64
    mov eax, 0x320002
    int 0x80
    ud2
times 8192-($-$$) db 0
