; Kernel canaries and guest observations are real CPU register/FXSAVE operations.
BITS 64
ORG 0x280000
kernel_seed:
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    sub rsp, 64
    mov [job],rdi
    fxsave64 [original_fx]
    fninit
    times 8 fld1
%assign n 0
%rep 16
    pcmpeqd xmm %+ n,xmm %+ n
%assign n n+1
%endrep
    mov dword [mxcsr],0x3f80
    ldmxcsr [mxcsr]
    fxsave64 [seed_fx]
    mov rbx,0x11223344
    mov rbp,0x22334455
    mov r12,0x33445566
    mov r13,0x44556677
    mov r14,0x55667788
    mov r15,0x66778899
    mov rax,[rdi]
    add rdi,8
    call rax
    mov [outcome],rax
    cmp rbx,0x11223344
    jne bad_gp
    cmp rbp,0x22334455
    jne bad_gp
    cmp r12,0x33445566
    jne bad_gp
    cmp r13,0x44556677
    jne bad_gp
    cmp r14,0x55667788
    jne bad_gp
    cmp r15,0x66778899
    jne bad_gp
    fxsave64 [return_fx]
    lea rsi,[seed_fx]
    lea rdi,[return_fx]
    mov ecx,512
    cld
    repe cmpsb
    jne bad_fx
    mov rax,[outcome]
    jmp done
bad_gp:
    mov rax,-901
    jmp done
bad_fx:
    mov rax,-902
done:
    fxrstor64 [original_fx]
    add rsp,64
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret
align 16
original_fx: times 512 db 0
seed_fx: times 512 db 0
return_fx: times 512 db 0
job: dq 0
outcome: dq 0
mxcsr: dd 0
times 4096-($-$$) db 0
; Mapped independently at 0x42000000 in a U=1 RX page.
guest:
    test edi,0x100
    jnz .fx
    push rax
    push rbx
    push rcx
    push rdx
    push rsi
    push rbp
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15
    mov rsi,rsp
    mov ecx,14
.gp:
    cmp qword [rsi],0
    jne failure
    add rsi,8
    loop .gp
 .fx:
    sub rsp,528
    and rsp,-16
    fxsave64 [rsp]
    cmp word [rsp],0x37f
    jne failure
    cmp word [rsp+2],0
    jne failure
    cmp byte [rsp+4],0
    jne failure
    cmp dword [rsp+24],0x1f80
    jne failure
    test edi,0x200
    jnz .xmm_start
    lea rsi,[rsp+32]
    mov ecx,8
.x87:
    cmp qword [rsi],0
    jne failure
    cmp word [rsi+8],0
    jne failure
    add rsi,16
    loop .x87
.xmm_start:
    test edi,0x400
    jnz .action
    lea rsi,[rsp+160]
    mov ecx,256
.xmm:
    cmp byte [rsi],0
    jne failure
    inc rsi
    loop .xmm
.action:
    and edi,255
    cmp rdi,1
    je fault
    cmp rdi,2
    je infinite
    cmp rdi,3
    jne success
    mov ecx,10000000
.finite:
    dec ecx
    jnz .finite
success:
    mov edi,42
    mov eax,703
    syscall
fault:
    ud2
infinite:
    jmp infinite
failure:
    mov edi,777
    mov eax,703
    syscall
    ud2
times 8192-($-$$) db 0
