; Native CPL3 context fixture, not a foreign process personality.
BITS 64
ORG 0x42000000
%define DATA 0x44000000
    cmp edi,1
    je isolated
    cmp edi,2
    je copied
    cmp edi,3
    je readonly_fault
    cmp edi,4
    je execute_fault
    cmp edi,5
    je unmapped_fault
    cmp edi,6
    je busy
    cmp edi,7
    je deadline
    cmp edi,9
    je bridge
    cmp edi,8
    je plain
    test edi,edi
    jnz bad
    mov rax,[abs DATA]
    cmp rax,100
    jne bad
    inc rax
    mov [abs DATA],rax
    mov rbx,0x1122334455667788
    movq xmm15,rbx
    mov eax,900
    syscall
    test rax,rax
    jz child
    cmp rax,84
    jne bad
    mov rax,[abs DATA]
    cmp rax,111
    jne bad
    mov rax,0x1122334455667788
    cmp rbx,rax
    jne bad
    movq rcx,xmm15
    cmp rcx,rax
    jne bad
    add qword[abs DATA],100
    mov edi,42
    jmp exit
child:
    mov rax,[abs DATA]
    cmp rax,101
    jne bad
    add qword[abs DATA],10
    mov rbx,0x4348494c44465831
    movq xmm15,rbx
    mov edi,43
    jmp exit
isolated:
    cmp qword[abs DATA],100
    jne bad
    mov edi,45
    jmp exit
copied:
    cmp qword[abs DATA],101
    jne bad
    add qword[abs DATA],500
    mov edi,44
    jmp exit
readonly_fault:
    mov qword[abs DATA],999
    jmp bad
execute_fault:
    mov eax,DATA
    jmp rax
unmapped_fault:
    mov rax,[abs 0x45000000]
    jmp bad
busy:
    mov eax,902
    syscall
    jmp bad
bridge:
    mov eax,903
    syscall
    cmp rax,84
    jne bad
    cmp qword[abs DATA],777
    jne bad
    mov edi,48
    jmp exit
deadline:
    pause
    jmp deadline
plain:
    mov edi,47
exit:
    mov eax,901
    syscall
bad:
    ud2
TIMES 4096-($-$$) db 0
