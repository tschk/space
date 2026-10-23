; Genuine format6 chained fixups, immutable-adapter revision2, no host addresses.
BITS 64
ORG 0x41000000
image:
 dd 0xfeedfacf,0x1000007,3,2,5,240,1,0
 dd 0x19,72
 db '__TEXT',0
 times 9 db 0
 dq image,4096,0,4096
 dd 5,5,0,0
 dd 0x19,72
 db '__DATA',0
 times 9 db 0
 dq 0x42000000,8192,4096,8192
 dd 3,3,0,0
 dd 0x80000028,24
 dq entry-image,0
 dd 0x80000034,16
 dd fixups-image,fixups_end-fixups
 dd 0xC,56,24,0,0x20000,0x20000
 db '/usr/lib/libSystem.B.dylib',0
 times 6 db 0
entry:
 mov rax,rsp
 and eax,15
 cmp eax,8
 jne fail
 sub rsp,8
 mov ebx,0x42000000
 mov r14,[rbx]
 call [rbx+0x110]
 mov r13,rax
 cmp eax,0x4f004000
 jne fail
 ; All eleven imported slots must be eagerly bound before entry.
 mov r12d,0x40007000
 xor ecx,ecx
.iat:
 cmp [rbx+0x100+rcx*8],r12
 jne fail
 add r12,64
 inc ecx
 cmp ecx,11
 jne .iat
 mov edi,33
 call [rbx+0x138]
 test rax,rax
 jz fail
 test al,15
 jnz fail
 mov r12,rax
 cmp r14,1
 je invalid
 cmp r14,2
 je interior
 cmp r14,3
 je doublefree
 cmp r14,4
 je badrealloc
 cmp r14,5
 je fault
 cmp r14,6
 je spin
 cmp r14,7
 je execute
 cmp r14,8
 je before
 cmp r14,9
 je after
 cmp r14,10
 je revoke
 cmp r14,11
 je rawwrong
 cmp r14,12
 je metadata
 cmp r14,13
 je records
 ; Newly obtained bytes zero; fill an independent byte pattern.
 xor ecx,ecx
.fill:
 cmp byte[r12+rcx],0
 jne fail
 mov [r12+rcx],cl
 inc ecx
 cmp ecx,33
 jne .fill
 ; Force movement: a neighbouring live allocation prevents extension.
 mov edi,64
 call [rbx+0x138]
 test rax,rax
 jz fail
 mov r15,rax
 mov rdi,r12
 mov esi,9000
 call [rbx+0x148]
 test rax,rax
 jz fail
 cmp rax,r12
 je fail
 mov r12,rax
 xor ecx,ecx
.check:
 cmp [r12+rcx],cl
 jne fail
 inc ecx
 cmp ecx,33
 jne .check
 cmp byte[r12+8999],0
 jne fail
 ; The existing genuine write service consumes heap-owned user memory.
 mov byte[r12],72
 mov edi,1
 mov rsi,r12
 mov edx,1
 call [rbx+0x100]
 cmp eax,1
 jne fail
 mov byte[r12],0
 ; Shrinking keeps the exact object and prefix.
 mov rdi,r12
 mov esi,33
 call [rbx+0x148]
 cmp rax,r12
 jne fail
 ; Realloc failure preserves old allocation and errno is genuinely private.
 mov rdi,r12
 mov rsi,-1
 call [rbx+0x148]
 test rax,rax
 jnz fail
 cmp dword[r13],12
 jne fail
 cmp byte[r12+32],32
 jne fail
 ; Darwin realloc(p,0) obtains a new live minimum block then frees old.
 mov rdi,r12
 xor esi,esi
 call [rbx+0x148]
 test rax,rax
 jz fail
 cmp rax,r12
 je fail
 mov r12,rax
 cmp dword[r13],12
 jne fail
 ; zero factor times SIZE_MAX yields a valid minimum object.
 xor edi,edi
 mov rsi,-1
 call [rbx+0x140]
 test rax,rax
 jz fail
 cmp rax,r12
 je fail
 mov rdi,rax
 call [rbx+0x150]
 mov edi,2
 mov rsi,-1
 call [rbx+0x140]
 test rax,rax
 jnz fail
 cmp dword[r13],12
 jne fail
 mov edi,3
 mov esi,3000
 call [rbx+0x140]
 test rax,rax
 jz fail
 cmp byte[rax+8999],0
 jne fail
 mov rdi,rax
 call [rbx+0x150]
 mov rdi,r12
 call [rbx+0x150]
 mov rdi,r15
 call [rbx+0x150]
 xor edi,edi
 call [rbx+0x150]
 cmp dword[r13],12
 jne fail
 ; Coalescing makes the entire fixed arena available again.
 mov edi,65536
 call [rbx+0x138]
 test rax,rax
 jz fail
 mov r12,rax
 mov edi,1
 call [rbx+0x138]
 test rax,rax
 jnz fail
 cmp dword[r13],12
 jne fail
 mov rdi,r12
 xor esi,esi
 call [rbx+0x148]
 test rax,rax
 jnz fail
 cmp byte[r12],0
 jne fail
 ; Deliberately leave whole arena live to prove unconditional exit cleanup.
 jmp success
invalid:
 mov edi,0x41000000
 call [rbx+0x150]
 jmp fail
interior:
 lea rdi,[r12+1]
 call [rbx+0x150]
 jmp fail
doublefree:
 mov rdi,r12
 call [rbx+0x150]
 mov rdi,r12
 call [rbx+0x150]
 jmp fail
badrealloc:
 lea rdi,[r12+1]
 mov esi,40
 call [rbx+0x148]
 jmp fail
fault:
 mov rax,[0x30000000]
 jmp fail
spin:
 jmp spin
execute:
 call r12
 jmp fail
before:
 mov rax,[0x4cfffff8]
 jmp fail
after:
 mov rax,[0x4d010000]
 jmp fail
records:
 ; Release entry's initial object before exhausting supervisor record slots.
 mov rdi,r12
 call [rbx+0x150]
 xor r15d,r15d
.allocate:
 xor edi,edi
 call [rbx+0x138]
 test rax,rax
 jz fail
 test al,15
 jnz fail
 mov [rbx+0x1800+r15*8],rax
 inc r15
 cmp r15,127
 jne .allocate
 xor edi,edi
 call [rbx+0x138]
 test rax,rax
 jnz fail
 cmp dword[r13],12
 jne fail
 xor r15d,r15d
.release:
 mov rdi,[rbx+0x1800+r15*8]
 call [rbx+0x150]
 inc r15
 cmp r15,127
 jne .release
 mov edi,65536
 call [rbx+0x138]
 cmp eax,0x4d000000
 jne fail
 jmp success
revoke:
 mov eax,0x2fffffe
 syscall
 mov edi,16
 call [rbx+0x138]
 test rax,rax
 jnz fail
 cmp dword[r13],13
 jne fail
 mov edi,2
 mov esi,8
 call [rbx+0x140]
 test rax,rax
 jnz fail
 cmp dword[r13],13
 jne fail
 mov rdi,r12
 mov esi,64
 call [rbx+0x148]
 test rax,rax
 jnz fail
 cmp dword[r13],13
 jne fail
 mov rdi,r12
 call [rbx+0x150]
 test rax,rax
 jnz fail
 cmp dword[r13],13
 jne fail
 xor edi,edi
 call [rbx+0x150]
 cmp dword[r13],13
 jne fail
 jmp success
metadata:
 mov eax,0x2fffffd
 syscall
 mov rax,[rax]
 jmp fail
rawwrong:
 mov eax,0x3000010
 mov edi,16
 int 0x80
 test rax,rax
 jnz fail
 cmp dword[r13],22
 jne fail
success:
 add rsp,8
 mov eax,42
 ret
fail:
 mov edi,99
 mov eax,0x2000001
 syscall
 ud2
 times 4096-($-$$) db 0
 dq 0
 times 4096+0x100-($-$$) db 0
%assign index 0
%rep 10
 dq 0x8000000000000000 | (2 << 51) | index
%assign index index+1
%endrep
 dq 0x8000000000000000 | 10
 times 12288-($-$$) db 0
fixups:
 dd 0,32,imports-fixups,symbols-fixups,12,1,0,0
 dd 2,0,12
 dd 26
 dw 4096,6
 dq 0x1000000
 dd 0
 dw 2,0x100,0xffff
 align 4,db 0
imports:
 dd 1|((name_0-symbols)<<9)
 dd 1|((name_1-symbols)<<9)
 dd 1|((name_2-symbols)<<9)
 dd 1|((name_3-symbols)<<9)
 dd 1|((name_4-symbols)<<9)
 dd 1|((name_5-symbols)<<9)
 dd 1|((name_6-symbols)<<9)
 dd 1|((name_7-symbols)<<9)
 dd 1|((name_8-symbols)<<9)
 dd 1|((name_9-symbols)<<9)
 dd 1|((name_10-symbols)<<9)
 ; Valid unused import is still part of admission policy.
 dd 1|((name_7-symbols)<<9)
symbols:
name_0: db '_write',0
name_1: db '_exit',0
name_2: db '___error',0
name_3: db '_open',0
name_4: db '_read',0
name_5: db '_close',0
name_6: db '_lseek',0
name_7: db '_malloc',0
name_8: db '_calloc',0
name_9: db '_realloc',0
name_10: db '_free',0
name_unknown: db '_unknown',0
fixups_end:
