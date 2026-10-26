BITS 64
ORG 0x1000
    mov eax, [0x4000]
    cmp eax, 1
    je high_fault
    cmp eax, 2
    je null_fault
    cmp eax, 3
    je readonly_fault
    cmp eax, 4
    je spin
    mov qword [0x4110], 0x22334455
    mov qword [0x100000], 0x11223344
    mov rbx, [0x4008]
    mov byte [rbx], 0x66
    mov rbx, [0x4010]
    mov byte [rbx], 0x77
    mov eax, 0x550001
    int 0x80
    ud2
high_fault:
    mov rax, 0xffff800000100000
    mov rax, [rax]
    ud2
null_fault:
    mov rax, [0]
    ud2
readonly_fault:
    mov byte [0x1000], 0
    ud2
spin:
    jmp spin
times 4096-($-$$) db 0
