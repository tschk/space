; Genuine strict Mach-O, main or UNIXTHREAD, with independent ABI assertions.
BITS 64
ORG 0x41000000
%ifndef THREAD
%define THREAD 0
%endif
image:
 dd 0xfeedfacf,0x1000007,3,2,3
%if THREAD
 dd 328
%else
 dd 168
%endif
 dd 1,0
 dd 0x19,72
 db '__TEXT',0
 times 9 db 0
 dq image,4096,0,4096
 dd 5,5,0,0
 dd 0x19,72
 db '__DATA',0
 times 9 db 0
 dq 0x42000000,4096,4096,4096
 dd 3,3,0,0
%if THREAD
 dd 5,184,4,42
 times 16 dq 0
 dq entry
 times 4 dq 0
%else
 dd 0x80000028,24
 dq entry-image,0
%endif
entry:
 cmp r8,0
 jne fail
 cmp r9,0
 jne fail
 mov rax,rsp
 and eax,15
%if THREAD
 cmp eax,0
 jne fail
 cmp rdi,0
 jne fail
 cmp rsi,0
 jne fail
 cmp rdx,0
 jne fail
 cmp rcx,0
 jne fail
 mov rdi,[rsp]
 lea rsi,[rsp+8]
 lea rdx,[rsi+rdi*8+8]
 mov rcx,rdx
.find_apple:
 cmp qword[rcx],0
 lea rcx,[rcx+8]
 jne .find_apple
%else
 cmp eax,8
 jne fail
 cmp qword[rsp],0x40006000
 jne fail
%endif
 cmp dword[0x4f004000],0
 jne fail
 cmp qword[0x42000000],8
 je empty_vectors
 cmp qword[0x42000000],9
 je maximum_vectors
 cmp edi,2
 jne fail
 cmp qword[rsi+16],0
 jne fail
 cmp qword[rdx+16],0
 jne fail
 cmp qword[rcx+8],0
 jne fail
 mov r12,rsi
 mov r13,rdx
 mov r14,rcx
 mov rdi,[r12]
 lea rsi,[rel arg0]
 call text_equal
 mov rdi,[r12+8]
 lea rsi,[rel arg1]
 call text_equal
 mov rdi,[r13]
 lea rsi,[rel env0]
 call text_equal
 mov rdi,[r13+8]
 lea rsi,[rel env1]
 call text_equal
 mov rdi,[r14]
 lea rsi,[rel apple0]
 call text_equal
 mov rbx,0x42000000
 cmp qword[rbx],10
 je maximum_segments
 cmp qword[rbx],1
 je pagefault
 cmp qword[rbx],2
 je spin
 cmp qword[rbx],3
 je argvfault
 cmp qword[rbx],4
 je stackfault
 cmp qword[rbx],5
 je fsfault
 cmp qword[rbx],6
 je gsfault
 cmp qword[rbx],7
 je callerfault
 mov eax,0x2ffffee
 syscall
 jnc fail
 cmp eax,78
 jne fail
success:
 mov eax,42
%if THREAD
 mov edi,eax
 mov eax,0x2000001
 syscall
 ud2
%else
 ret
%endif
maximum_segments:
 cmp byte[0x4100ffff],0
 jne fail
 mov byte[0x4200ffff],90
 cmp byte[0x4200ffff],90
 jne fail
 jmp success
empty_vectors:
 cmp edi,0
 jne fail
 cmp qword[rsi],0
 jne fail
 cmp qword[rdx],0
 jne fail
 cmp qword[rcx],0
 jne fail
 jmp success
maximum_vectors:
 cmp edi,16
 jne fail
 mov r12,rsi
 mov r13,rdx
 mov r14,rcx
 mov r15d,16
.max_next:
 mov rdi,[r12]
 lea rsi,[rel boundary]
 call text_equal
 mov rdi,[r13]
 lea rsi,[rel boundary]
 call text_equal
 mov rdi,[r14]
 lea rsi,[rel boundary]
 call text_equal
 add r12,8
 add r13,8
 add r14,8
 dec r15d
 jnz .max_next
 cmp qword[r12],0
 jne fail
 cmp qword[r13],0
 jne fail
 cmp qword[r14],0
 jne fail
 jmp success
text_equal:
 cmp rdi,0x4f005200
 jb fail
 cmp rdi,0x4f006000
 jae fail
.next:
 mov al,[rdi]
 cmp al,[rsi]
 jne fail
 inc rdi
 inc rsi
 test al,al
 jnz .next
 ret
pagefault:
 mov rax,[0x30000000]
 ud2
argvfault:
 mov rax,[0x4f006000]
 ud2
stackfault:
 mov rax,[0x4efff000]
 ud2
fsfault:
 mov rax,[fs:0]
 ud2
gsfault:
 mov rax,[gs:0]
 ud2
callerfault:
 mov rax,[rbx+8]
 mov rax,[rax]
 ud2
spin:
 jmp spin
fail:
 mov edi,99
 mov eax,0x2000001
 syscall
 ud2
boundary: db 'x',0
arg0: db 'startup-fixture',0
arg1: db 'two words',0
env0: db 'A=alpha',0
env1: db 'EMPTY=',0
apple0: db 'executable_path=/fixture',0
 times 4096-($-$$) db 0
 dq 0
 times 8192-($-$$) db 0
