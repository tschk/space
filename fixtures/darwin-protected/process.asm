; Protected returning Mach-O fixture: RX text and RW/NX data/BSS.
BITS 64
ORG 0x41000000
image:
%ifdef PROTECTED_IMPORTS
    dd 0xfeedfacf, 0x01000007, 3, 2, 5, 272, 1, 0
%else
    dd 0xfeedfacf, 0x01000007, 3, 2, 3, 168, 1, 0
%endif
    dd 0x19, 72
    db '__TEXT', 0
    times 9 db 0
    dq image, 4096, 0, 4096
    dd 5, 5, 0, 0
    dd 0x19, 72
    db '__DATA', 0
    times 9 db 0
    dq 0x42000000, 4096, 4096, 16
    dd 3, 3, 0, 0
    dd 0x80000028, 24
    dq entry-image, 0
%ifdef PROTECTED_IMPORTS
    dd 0x80000022, 48
    dd 0, 0, bind_program-image, bind_end-bind_program, 0, 0, 0, 0, 0, 0
    dd 0xC, 56, 24, 0, 0, 0
    db '/usr/lib/libSystem.B.dylib', 0
    times 5 db 0
%endif
entry:
    mov rbx, 0x42000000
    mov rax, [rbx]
    cmp rax, 1
    je kernel_read
    cmp rax, 2
    je text_write
    cmp rax, 3
    je data_execute
    cmp rax, 4
    je stack_execute
    cmp rax, 5
    je port_write
    cmp rax, 6
    je ring_level
    cmp rax, 7
    je unmapped_read
    cmp rax, 9
    je forged_write
    cmp rax, 10
    je io_privilege
    cmp rax, 11
    je other_write
    cmp rax, 12
    je granted_write
    cmp rax, 13
    je getpid
    cmp rax, 14
    je unknown_call
    cmp rax, 15
    je bad_pointer
    cmp rax, 16
    je crossing_pointer
    cmp rax, 17
    je bad_descriptor
    cmp rax, 18
    je empty_write
    cmp rax, 19
    je explicit_exit
%ifdef PROTECTED_IMPORTS
    cmp rax, 20
    je imported_write
    cmp rax, 21
    je imported_exit
    cmp rax, 22
    je imported_denied
    cmp rax, 23
    je infinite_loop
%endif
    ; A fresh instance must not see BSS left by an earlier instance.
    cmp qword [rbx + 16], 0
    jne fail
    mov rax, 0x1122334455667788
    cmp [rbx + 8], rax
    jne fail
    mov qword [rbx + 16], 77
    cmp qword [rbx + 16], 77
    jne fail
success:
    mov eax, 42
    ret
fail:
    mov eax, 90
    ret
kernel_read:
    mov eax, [0x100000]
    jmp fail
text_write:
    mov byte [rel entry], 0xC3
    jmp fail
data_execute:
    mov byte [rbx + 32], 0xC3
    lea rax, [rbx + 32]
    call rax
    jmp fail
stack_execute:
    mov byte [rsp - 16], 0xC3
    lea rax, [rsp - 16]
    call rax
    jmp fail
port_write:
    mov dx, 0x80
    out dx, al
    jmp fail
ring_level:
    xor eax, eax
    mov ax, cs
    and eax, 3
    cmp eax, 3
    jne fail
    jmp success
unmapped_read:
    mov eax, [0x43000000]
    jmp fail
forged_write:
    mov eax, 0x2000004
    mov edi, 1
    mov esi, 0x100000
    mov edx, 1
    syscall
    jnc fail
    cmp eax, 13
    jne fail
    jmp success
other_write:
    mov dword [0x43000000], 77
    jmp fail
io_privilege:
    pushfq
    pop rax
    and eax, 0x3000
    jnz fail
    jmp success
granted_write:
    mov eax, 0x2000004
    mov edi, 1
    lea rsi, [rel message]
    mov edx, message_end-message
    stc
    syscall
    jc fail
    cmp eax, message_end-message
    jne fail
    jmp success
getpid:
    mov eax, 0x2000014
    stc
    int 0x80
    jc fail
    test eax, eax
    jle fail
    jmp success
unknown_call:
    mov eax, 0x2007fff
    clc
    syscall
    jnc fail
    cmp eax, 78
    jne fail
    jmp success
bad_pointer:
    mov esi, 0x100000
    mov edx, 1
    jmp expect_fault
crossing_pointer:
    mov esi, 0x42000fff
    mov byte [rsi], '^'
    mov edx, 2
expect_fault:
    mov eax, 0x2000004
    mov edi, 1
    syscall
    jnc fail
    cmp eax, 14
    jne fail
    jmp success
bad_descriptor:
    mov eax, 0x2000004
    mov edi, 3
    xor esi, esi
    xor edx, edx
    syscall
    jnc fail
    cmp eax, 9
    jne fail
    jmp success
empty_write:
    mov eax, 0x2000004
    mov edi, 1
    xor esi, esi
    xor edx, edx
    stc
    syscall
    jc fail
    test eax, eax
    jnz fail
    jmp success
explicit_exit:
    mov eax, 0x2000001
    mov edi, 298
    syscall
    jmp fail
%ifdef PROTECTED_IMPORTS
infinite_loop:
    jmp infinite_loop
imported_write:
    mov edi, 1
    lea rsi, [rel import_message]
    mov edx, import_message_end-import_message
    call [rbx+32]
    cmp eax, import_message_end-import_message
    jne fail
    jmp success
imported_exit:
    mov edi, 298
    call [rbx+40]
    jmp fail
imported_denied:
    mov edi, 1
    lea rsi, [rel import_message]
    mov edx, import_message_end-import_message
    call [rbx+32]
    cmp rax, -1
    jne fail
    call [rbx+48]
    cmp dword [rax], 13
    jne fail
    jmp success
import_message: db 'darwin-import-write', 10
import_message_end:
bind_program:
    db 0x11, 0x40, '_write', 0, 0x51, 0x71, 32, 0x90
    db 0x40, '_exit', 0, 0x71, 40, 0x90
    db 0x40, '_error', 0, 0x71, 48, 0x90, 0
bind_end:
%endif
message: db 'darwin-private-write', 10
message_end:
    times 4096-($-$$) db 0
    dq 0, 0x1122334455667788
    times 8192-($-$$) db 0
