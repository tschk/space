; Trusted CPL0 interrupt ABI control, loaded by its private QEMU test only.
BITS 64
ORG 0x2e0000
entry:
    pushfq
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    sub rsp,560
    mov r15,rsp
    fxsave64 [r15]
    mov r12,rdi
    sub rsp,[r12+24]               ; test both interrupted stack alignments
    mov r13,rsp
    mov qword [r15+528],0x55667788
    fninit
    fld1
    mov dword [r15+512],0x3f80
    ldmxcsr [r15+512]
    mov eax,0x33445566
    movq xmm7,rax
    mov eax,0x1001
    mov ebx,0x1002
    mov ecx,0x1003
    mov edx,0x1004
    mov esi,0x1005
    mov edi,0x1006
    mov r8d,0x1008
    mov r9d,0x1009
    mov r10d,0x1010
    mov r11d,0x1011
    mov r14d,0x1014
    std
.wait:
    pause
    cmp qword [r12],3
    jb .wait
    mov [r12+8],r11
    cmp r11,0x1011
    jne .bad_gp
    cmp eax,0x1001
    jne .bad_gp
    cmp ebx,0x1002
    jne .bad_gp
    cmp ecx,0x1003
    jne .bad_gp
    cmp edx,0x1004
    jne .bad_gp
    cmp esi,0x1005
    jne .bad_gp
    cmp edi,0x1006
    jne .bad_gp
    cmp r8d,0x1008
    jne .bad_gp
    cmp r9d,0x1009
    jne .bad_gp
    cmp r10d,0x1010
    jne .bad_gp
    cmp r14d,0x1014
    jne .bad_gp
    cmp rsp,r13
    jne .bad_gp
    cmp qword [r15+528],0x55667788
    jne .bad_gp
    pushfq
    pop rax
    test eax,1024
    jz .bad_gp                    ; interrupted DF must be restored
    cld
    movq rax,xmm7
    cmp rax,0x33445566
    jne .bad_fx
    fnstsw ax
    and eax,0x3800
    cmp eax,0x3800                ; one original x87 value, TOP=7
    jne .bad_fx
    fadd st0,st0
    fistp qword [r15+520]
    cmp qword [r15+520],2
    jne .bad_fx
    stmxcsr [r15+512]
    cmp dword [r15+512],0x3f80
    jne .bad_fx
    mov eax,42
    jmp .done
.bad_gp:
    mov eax,1
    jmp .done
.bad_fx:
    mov eax,2
.done:
    cld
    mov rsp,r15
    fxrstor64 [rsp]
    add rsp,560
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    popfq
    ret
    times 1024-($-$$) db 0
; A handler may clobber caller-saved XMM/x87 state. Its interrupt wrapper must
; preserve the interrupted context, even though this ordinary callback need not.
clobber_fx:
    pxor xmm7,xmm7
    fld1
    stmxcsr [rsp-8]
    xor dword [rsp-8],32
    ldmxcsr [rsp-8]
    ret
    times 1280-($-$$) db 0
; Parameter-home-area stress for the native .in interrupt-call contract.
; The timer caller must reserve these 64 bytes, independently of GP saves.
callback_bridge:
    mov rax,rsp
    and eax,15
    mov [0x2e0608],rax
%assign slot 0
%rep 8
    mov qword [rsp+8+slot],0x2020+slot
%assign slot slot+8
%endrep
    jmp qword [0x2e0600]
    times 4096-($-$$) db 0
