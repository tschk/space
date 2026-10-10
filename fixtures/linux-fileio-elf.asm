; Trusted read-only VFS exercise. Darwin includes this with its own header/ABI.
BITS 64
ORG 0x280000
image:
%ifdef FOREIGN_DARWIN
    dd 0xfeedfacf, 0x01000007, 3, 2, 2, 96, 1, 0
    dd 0x19, 72
    db '__TEXT', 0
    times 9 db 0
    dq image, 4096, 0, 4096
    dd 5, 5, 0, 0
    dd 0x80000028, 24
    dq 128, 0
%define OPEN 0x2000005
%define READ 0x2000003
%define CLOSE 0x2000006
%define WRITE 0x2000004
%define EXIT 0x2000001
%else
    dd 0x464c457f, 0x00010102, 0, 0
    dw 2, 62
    dd 1
    dq entry, 64, 0
    dd 0
    dw 64, 56, 1, 0, 0, 0
    dd 1, 5
    dq 0, image, image, 4096, 4096, 4096
    times 128-($-$$) db 0
%define OPEN 2
%define READ 0
%define CLOSE 3
%define WRITE 1
%define EXIT 60
%endif
%assign FAIL_STAGE 100
%macro expect_error 1
%assign FAIL_STAGE FAIL_STAGE + 1
    mov r13d, FAIL_STAGE
%ifdef FOREIGN_DARWIN
    jnc fail
%if %1 == 36
    cmp rax, 63
%else
    cmp rax, %1
%endif
%else
    cmp rax, -%1
%endif
    jne fail
%endmacro
%macro expect_ok 0
%assign FAIL_STAGE FAIL_STAGE + 1
    mov r13d, FAIL_STAGE
%ifdef FOREIGN_DARWIN
    jc fail
%else
    test rax, rax
    js fail
%endif
%endmacro
entry:
    mov eax, OPEN
    xor edi, edi
    xor esi, esi
    syscall
    expect_error 14
    mov eax, OPEN
    lea rdi, [rel missing]
    xor esi, esi
    syscall
    expect_error 2
    mov eax, OPEN
    lea rdi, [rel path]
    mov esi, 1                    ; writes/creation flags are unsupported
    syscall
    expect_error 22
    mov eax, OPEN
    lea rdi, [rel longpath]
    xor esi, esi
    syscall
    expect_error 36
    mov eax, OPEN
    lea rdi, [rel maxpath]
    xor esi, esi
    syscall
    expect_error 2
    mov eax, OPEN
    mov edi, image + 4095         ; no NUL before the image boundary
    xor esi, esi
    syscall
    expect_error 14
    mov eax, READ
    mov edi, 3                     ; an existing kernel-owned descriptor
    lea rsi, [rel buffer]
    mov edx, 27
    syscall
    expect_error 9
    mov eax, CLOSE
    mov edi, 3
    syscall
    expect_error 9
    mov eax, OPEN
    lea rdi, [rel path]
    xor esi, esi
    syscall
    expect_ok
    mov rbx, rax
    mov eax, READ
    mov rdi, rbx
    xor esi, esi
    mov edx, 27
    syscall
    expect_error 14
    mov eax, READ
    mov rdi, rbx
    mov esi, image + 4095
    mov edx, 2
    syscall
    expect_error 14
    mov eax, READ
    mov rdi, rbx
    lea rsi, [rel buffer]
    mov edx, 4097
    syscall
    expect_error 14
    mov eax, READ
    mov rdi, rbx
    lea rsi, [rel buffer]
    mov edx, 27
    syscall
    expect_ok
    cmp rax, 27
    jne fail
    lea rsi, [rel buffer]
    lea rdi, [rel expected]
    mov ecx, 27
    cld
    repe cmpsb
    jne fail
    mov eax, READ
    mov rdi, rbx
    lea rsi, [rel buffer]
    mov edx, 27
    syscall
    expect_ok
    test rax, rax
    jnz fail
    mov eax, CLOSE
    mov rdi, rbx
    syscall
    expect_ok
    test rax, rax
    jnz fail
    mov eax, CLOSE
    mov rdi, rbx
    syscall
    expect_error 9
    mov eax, WRITE
    mov edi, 1
    lea rsi, [rel buffer]
    mov edx, 27
    syscall
    expect_ok
    cmp rax, 27
    jne fail
    mov r12d, 12                  ; host owns fd 3; leave all other slots open
.exhaust:
    mov eax, OPEN
    lea rdi, [rel path]
    xor esi, esi
    syscall
    expect_ok
    dec r12d
    jnz .exhaust
    mov eax, OPEN
    lea rdi, [rel path]
    xor esi, esi
    syscall
    expect_error 24
%ifdef FOREIGN_RETURN
    mov eax, 42
    ret
%else
    mov eax, EXIT
    mov edi, 42
    syscall
    ud2
%endif
fail:
    mov eax, EXIT
    mov edi, r13d
    syscall
    ud2
path: db 'foreign-read.txt', 0
missing: db 'foreign-does-not-exist.txt', 0
expected: db 'foreign: VFS file contents', 10
buffer: times 64 db 0
longpath: times 256 db 'x'
maxpath: times 255 db 'x'
    db 0
    times 4095-($-$$) db 0
    db 'x'
