; Raw Linux x86_64 local-stream transport acceptance.
BITS 64
ORG 0x2f0000
image:
    dd 0x464c457f, 0x00010102, 0, 0
    dw 2, 62
    dd 1
    dq entry, 64, 0
    dd 0
    dw 64, 56, 1, 0, 0, 0
    dd 1, 5
    dq 0, image, image, 4096, 4096, 4096
    times 128-($-$$) db 0

entry:
    mov qword [rel pair], -1
    mov r13d, 100
    mov eax, 53
    mov edi, 2
    mov esi, 1
    xor edx, edx
    lea r10, [rel pair]
    syscall
    cmp rax, -97
    jne fail
    cmp qword [rel pair], -1
    jne fail
    mov eax, 53
    mov edi, 1
    xor r10d, r10d
    syscall
    cmp rax, -14
    jne fail
    cmp qword [rel pair], -1
    jne fail
    ; The orchestrator retains host fd3; guest may not access it.
    xor eax, eax
    mov edi, 3
    lea rsi, [rel received]
    mov edx, 1
    syscall
    cmp rax, -9
    jne fail
    mov r13d, 101
    mov eax, 53              ; socketpair(AF_UNIX, SOCK_STREAM, 0, pair)
    mov edi, 1
    mov esi, 1
    xor edx, edx
    lea r10, [rel pair]
    syscall
    test rax, rax
    jne fail
    mov r14d, [rel pair]
    mov r15d, [rel pair+4]
    ; Real wl_display.sync request: sender=1, size=12/opcode=0, callback id=2.
    ; Fragment the header and body across three writes and two reads.
    mov r13d, 102
    mov edi, r14d
    lea rsi, [rel request]
    mov edx, 3
    call write_exact
    add rsi, 3
    mov edx, 5
    call write_exact
    add rsi, 5
    mov edx, 4
    call write_exact
    mov edi, r15d
    lea rsi, [rel received]
    mov edx, 5
    call read_exact
    add rsi, 5
    mov edx, 7
    call read_exact
    mov rax, [rel received]
    cmp rax, [rel request]
    jne fail
    mov eax, [rel received+8]
    cmp eax, [rel request+8]
    jne fail
    ; Reverse direction confirms full duplex, then buffered data precedes EOF.
    mov edi, r15d
    lea rsi, [rel request]
    mov edx, 12
    call write_exact
    mov eax, 3
    mov edi, r15d
    syscall
    test rax, rax
    jne fail
    mov edi, r14d
    lea rsi, [rel received]
    mov edx, 12
    call read_exact
    xor eax, eax
    mov edx, 1
    syscall
    test rax, rax
    jne fail
    mov eax, 3
    syscall
    test rax, rax
    jne fail
    mov eax, 60
    mov edi, 42
    syscall
write_exact:
    mov eax, 1
    syscall
    cmp rax, rdx
    jne fail
    ret
read_exact:
    xor eax, eax
    syscall
    cmp rax, rdx
    jne fail
    ret
fail:
    mov eax, 60
    mov edi, r13d
    syscall
pair: dd -1, -1
request: dd 1, 12 << 16, 2
received: times 16 db 0
    times 4096-($-$$) db 0
