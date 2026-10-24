; Independent CPU exception triggers in strict CPL3; RDI selects the vector.
BITS 64
ORG 0x42000000
    cmp edi,0
    je integer_divide
    cmp edi,3
    je breakpoint
    cmp edi,16
    je x87_divide
    cmp edi,19
    je simd_divide
    ud2
integer_divide:
    mov eax,1
    xor edx,edx
    xor ecx,ecx
    div rcx
    ud2
breakpoint:
    int3
    ud2
x87_divide:
    fninit
    fnstcw [rsp-8]
    and word [rsp-8],~4             ; unmask x87 divide by zero
    fldcw [rsp-8]
    fld1
    fldz
    fdivp st1,st0
    fwait
    ud2
simd_divide:
    stmxcsr [rsp-8]
    and dword [rsp-8],~(1<<9)       ; unmask SSE divide by zero
    ldmxcsr [rsp-8]
    pxor xmm0,xmm0
    mov eax,1
    cvtsi2ss xmm1,eax
    divss xmm1,xmm0
    stmxcsr [rsp-8]
    ud2
    times 4096-($-$$) db 0
