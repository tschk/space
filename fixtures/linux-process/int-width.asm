BITS 64
ORG 0x400000
; Labelled synthetic ELF: actual syscall register-width behavior, no host ABI.
db 0x7f,'ELF',2,1,1,0
times 8 db 0
dw 2,62
dd 1
dq entry,64,0
dd 0
dw 64,56,1,0,0,0
dd 1,5
dq 0,0x400000,0,4096,4096,4096
times 256-($-$$) db 0
entry:
    mov r13,[rsp+24]             ; real startup argv2: fixture input filename
    mov rdi,0x1234567800000001   ; int fd1, upper register bits ignored
    mov rsi,rsp
    xor edx,edx
    mov eax,1
    syscall
    test rax,rax
    jnz fail1
    mov rdi,0x12345678ffffff9c   ; AT_FDCWD with garbage upper32
    mov rsi,r13
    mov rdx,0xabcdef1200000000   ; O_RDONLY with garbage upper32
    xor r10d,r10d
    mov eax,257
    syscall
    cmp rax,3
    jne fail2
    mov r12,rax
    mov rdi,0x1234567800000003
    xor esi,esi
    mov rdx,0xabcdef1200000002   ; int SEEK_END
    mov eax,8
    syscall
    cmp rax,45
    jne fail3
    mov rdi,0x1234567800000003
    lea rsi,[rsp-16]
    mov edx,1
    xor r10d,r10d
    mov eax,17
    syscall
    cmp rax,1
    jne fail4
    cmp byte [rsp-16],123
    jne fail4
    mov rdi,0x1234567800000003
    mov rsi,0xabcdef1200000003   ; int F_GETFL
    xor edx,edx
    mov eax,72
    syscall
    test eax,3                  ; access mode; host also reports O_LARGEFILE
    jnz fail5
    mov rdi,0x12345678ffffff9c
    mov rsi,r13
    lea rdx,[rsp-160]
    mov r10,0xabcdef1200000100   ; unsigned int AT_SYMLINK_NOFOLLOW
    mov eax,262
    syscall
    test rax,rax
    jnz fail6
    mov rdi,0x1234567800000003
    mov rsi,0x100000000          ; off_t stays64; bounded profile rejects4GiB
    xor edx,edx
    mov eax,8
    syscall
    cmp rax,-22
    jne fail12
    mov rdi,0x1234567800000003
    mov eax,3
    syscall
    test rax,rax
    jnz fail7
    mov rdi,0x12345678ffffffff   ; signed int -1, never a valid fd
    lea rsi,[rsp-16]
    mov edx,1
    xor eax,eax
    syscall
    cmp rax,-9
    jne fail8
    mov edi,1
    mov rsi,rsp
    mov rax,0x1234000000000000   ; pointers retain their full64 bits
    or rsi,rax
    mov edx,1
    mov eax,1
    syscall
    cmp rax,-14
    jne fail9
    mov edi,1
    mov rsi,rsp
    mov rdx,0x100000000          ; size_t retains its full64 bits
    mov eax,1
    syscall
    cmp rax,-22
    jne fail10
    mov rax,0x100000027          ; x86_64 Linux dispatch number is int32 too
    syscall
    cmp rax,1000
    jbe fail11
    mov edi,42
    jmp leave
fail1: mov edi,101
    jmp leave
fail2: mov edi,102
    jmp leave
fail3: mov edi,103
    jmp leave
fail4: mov edi,104
    jmp leave
fail5: mov edi,105
    jmp leave
fail6: mov edi,106
    jmp leave
fail7: mov edi,107
    jmp leave
fail8: mov edi,108
    jmp leave
fail9: mov edi,109
    jmp leave
fail10: mov edi,110
    jmp leave
fail11: mov edi,111
    jmp leave
fail12: mov edi,112
leave:
    mov eax,60
    syscall
    ud2
times 4096-($-$$) db 0
