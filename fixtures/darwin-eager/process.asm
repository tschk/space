; Genuine format6 chained fixups, immutable-adapter revision1, no host addresses.
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
 dd 0xC,56,24,0,0x10000,0x10000
 db '/usr/lib/libSystem.B.dylib',0
 times 6 db 0
entry:
 mov rax,rsp
 and eax,15
 cmp eax,8
 jne fail
 cmp qword[rsp],0x40006000
 jne fail
 cmp edi,2
 jne fail
 cmp qword[rsi+16],0
 jne fail
 cmp qword[rdx+16],0
 jne fail
 cmp qword[rcx+8],0
 jne fail
 sub rsp,8
 mov rbx,0x42000000
 mov r14,[rbx]
 ; Preparation must have resolved every slot before the first bound call.
 mov r12d,0x40007000
 xor ecx,ecx
.iat:
 cmp [rbx+0x100+rcx*8],r12
 jne fail
 add r12,64
 inc ecx
 cmp ecx,7
 jne .iat
 mov rax,[rbx+0x100]
 cmp [rbx+0x138],rax
 jne fail
 cmp [rbx+0x1000],rax
 jne fail
 cmp qword[rbx+0x140],0x42000500
 jne fail
 call [rbx+0x110]
 cmp eax,0x4f004000
 jne fail
 cmp dword[rax],0
 jne fail
 mov r13,rax
 cmp r14,12
 je denied_flags
 mov rdi,[rbx+0x140]
 xor esi,esi
 call [rbx+0x118]
 cmp r14,1
 je denied_storage
 cmp eax,3
 jne fail
 mov r12,rax
 cmp r14,3
 je fault
 cmp r14,4
 je spin
 cmp r14,5
 je success
 cmp r14,6
 je revoke
 cmp r14,8
 je fsfault
 cmp r14,9
 je gsfault
 cmp r14,7
 je crossing
 cmp r14,10
 je readonly_buffer
normal_read:
 mov edi,r12d
 lea rsi,[rbx+0x1800]
 mov edx,16
 call [rbx+0x120]
 cmp eax,16
 jne fail
 mov rax,0x3736353433323130
 cmp [rbx+0x1800],rax
 jne fail
 mov rax,0x6665646362613938
 cmp [rbx+0x1808],rax
 jne fail
 mov edi,r12d
 mov esi,8
 xor edx,edx
 call [rbx+0x130]
 cmp eax,8
 jne fail
 mov edi,r12d
 lea rsi,[rbx+0x1800]
 mov edx,8
 call [rbx+0x120]
 cmp eax,8
 jne fail
 mov rax,0x6665646362613938
 cmp [rbx+0x1800],rax
 jne fail
 mov edi,r12d
 call [rbx+0x128]
 test eax,eax
 jne fail
 mov edi,r12d
 lea rsi,[rbx+0x1800]
 mov edx,1
 call [rbx+0x120]
 cmp rax,-1
 jne fail
 cmp dword[r13],9
 jne fail
 mov edi,1
 lea rsi,[rel message]
 mov edx,message_end-message
 call [rbx+0x138]
 cmp r14,2
 je denied_serial
 cmp eax,message_end-message
 jne fail
 cmp dword[r13],9
 jne fail
 ; Second-page alias is a real separate chained slot, not fixed symbol index.
 mov edi,1
 lea rsi,[rel message]
 xor edx,edx
 call [rbx+0x1000]
 test eax,eax
 jne fail
 cmp r14,11
 je typed_exit
success:
 add rsp,8
 mov eax,42
 ret
typed_exit:
 mov edi,42
 call [rbx+0x108]
 ud2
denied_storage:
 cmp rax,-1
 jne fail
 cmp dword[r13],13
 jne fail
 jmp success
denied_serial:
 cmp rax,-1
 jne fail
 cmp dword[r13],13
 jne fail
 jmp success
denied_flags:
 mov rdi,[rbx+0x140]
 mov esi,1
 call [rbx+0x118]
 cmp rax,-1
 jne fail
 cmp dword[r13],22
 jne fail
 jmp success
crossing:
 mov edi,r12d
 mov esi,0x42001ff8
 mov edx,16
 call [rbx+0x120]
 cmp rax,-1
 jne fail
 cmp dword[r13],14
 jne fail
 jmp normal_read
readonly_buffer:
 mov edi,r12d
 mov esi,0x41000000
 mov edx,1
 call [rbx+0x120]
 cmp rax,-1
 jne fail
 cmp dword[r13],14
 jne fail
 jmp normal_read
revoke:
 mov eax,0x2fffffe
 syscall
 mov edi,r12d
 lea rsi,[rbx+0x1800]
 mov edx,1
 call [rbx+0x120]
 cmp rax,-1
 jne fail
 cmp dword[r13],13
 jne fail
 mov edi,r12d
 call [rbx+0x128]
 test eax,eax
 jne fail
 jmp success
fault:
 mov rax,[0x30000000]
 ud2
fsfault:
 mov rax,[fs:0]
 ud2
gsfault:
 mov rax,[gs:0]
 ud2
spin:
 jmp spin
fail:
 mov edi,99
 mov eax,0x2000001
 syscall
 ud2
message: db 'eager-bound',10
message_end:
 times 4096-($-$$) db 0
 dq 0
 times 4096+0x100-($-$$) db 0
%assign index 0
%rep 7
 dq 0x8000000000000000 | (2 << 51) | index
%assign index index+1
%endrep
 dq 0x8000000000000000 | (2 << 51)
 dq 0x1000500
 times 4096+0x500-($-$$) db 0
 db 'darwin-eager.txt',0
 times 8192-($-$$) db 0
 dq 0x8000000000000000
 times 12288-($-$$) db 0
fixups:
 dd 0,32,imports-fixups,symbols-fixups,8,1,0,0
 dd 2,0,12
 dd 26
 dw 4096,6
 dq 0x1000000
 dd 0
 dw 2,0x100,0
 align 4,db 0
imports:
 dd 1|((name_write-symbols)<<9),1|((name_exit-symbols)<<9)
 dd 1|((name_error-symbols)<<9),1|((name_open-symbols)<<9)
 dd 1|((name_read-symbols)<<9),1|((name_close-symbols)<<9),1|((name_seek-symbols)<<9)
 dd 1|((name_write-symbols)<<9)
symbols:
name_write: db '_write',0
name_exit: db '_exit',0
name_error: db '___error',0
name_open: db '_open',0
name_read: db '_read',0
name_close: db '_close',0
name_seek: db '_lseek',0
name_unknown: db '_unknown',0
fixups_end:
