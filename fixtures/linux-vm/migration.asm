; Ordinary static Linux ELF: exercise copied anonymous VM ownership through I/O.
; No Space imports, memory layout, native pointers or test-only guest syscalls.
bits 64
global _start
%macro expect 1
 cmp rax,%1
 jne fail
%endmacro
%macro call 4
 mov eax,%1
 mov rdi,%2
 mov rsi,%3
 mov rdx,%4
 syscall
%endmacro
section .text
_start:
 call 12,0,0,0
 test rax,rax
 js fail
 mov r12,rax
 lea rdi,[r12+8192]
 mov eax,12
 syscall
 lea rbx,[r12+8192]
 expect rbx
 mov qword[r12],12345
 mov qword[r12+4096],98765
 lea rdi,[r12+1]
 mov eax,12
 syscall
 lea rbx,[r12+1]
 expect rbx
 lea rdi,[r12+8192]
 mov eax,12
 syscall
 lea rbx,[r12+8192]
 expect rbx
 cmp qword[r12],12345
 jne fail
 cmp qword[r12+4096],0
 jne fail
 mov r10d,0x22
 mov r8,-1
 xor r9d,r9d
 call 9,0,12288,3
 test rax,rax
 js fail
 mov r13,rax
 mov rbx,0x1122334455667788
 mov [r13+4088],rbx
 mov rbx,0x7a79787776757473
 mov [r13+4096],rbx
 call 293,ends,0x800,0
 expect 0
 mov r14d,[rel ends]
 mov r15d,[rel ends+4]
 lea rsi,[r13+4088]
 call 1,r15,rsi,16
 expect 16
 call 0,r14,buffer,16
 expect 16
 mov rbx,0x1122334455667788
 cmp [rel buffer],rbx
 jne fail
 mov rbx,0x7a79787776757473
 cmp [rel buffer+8],rbx
 jne fail
 lea rdi,[r13+4096]
 call 10,rdi,4096,1
 expect 0
 lea rsi,[r13+4088]
 call 1,r15,rsi,8
 expect 8
 lea rsi,[r13+4096]
 call 0,r14,rsi,8
 expect -14
 call 0,r14,buffer,8
 expect 8
 mov rbx,0x1122334455667788
 cmp [rel buffer],rbx
 jne fail
 lea rdi,[r13+4096]
 call 10,rdi,4096,3
 expect 0
 mov eax,56
 mov edi,17
 xor esi,esi
 xor edx,edx
 xor r10d,r10d
 xor r8d,r8d
 syscall
 test rax,rax
 js fail
 jz child
 mov [rel child_pid],rax
 xor r10d,r10d
 call 61,[rel child_pid],wait_status,0
 cmp rax,[rel child_pid]
 jne fail
 cmp dword[rel wait_status],0x700
 jne fail
 mov rbx,0x7a79787776757473
 cmp [r13+4096],rbx
 jne fail
 mov rbx,0x1122334455667788
 cmp [r13+4088],rbx
 jne fail
 ; Failed exec validates copied vectors before replacing the old VM.
 call 59,self_path,-1,0
 expect -14
 mov rbx,0x7a79787776757473
 cmp [r13+4096],rbx
 jne fail
 lea rsi,[r13+4088]
 call 1,r15,rsi,16
 expect 16
 call 0,r14,buffer,16
 expect 16
 mov rbx,0x1122334455667788
 cmp [rel buffer],rbx
 jne fail
 mov rbx,0x7a79787776757473
 cmp [rel buffer+8],rbx
 jne fail
 call 11,r13,12288,0
 expect 0
 mov r10d,0x22
 mov r8,-1
 xor r9d,r9d
 call 9,0,4096,3
 test rax,rax
 js fail
 mov rbx,rax
 cmp qword[rbx],0
 jne fail
 call 11,rbx,4096,0
 expect 0
 call 3,r14,0,0
 expect 0
 call 3,r15,0,0
 expect 0
 call 60,42,0,0
child:
 mov qword[r13+4096],999
 lea rdi,[r13+8192]
 call 11,rdi,4096,0
 expect 0
 call 60,7,0,0
fail:
 call 60,99,0,0
 ud2
section .data
self_path: db '/proc/self/exe',0
section .bss
align 8
ends: resd 2
buffer: resb 32
child_pid: resq 1
wait_status: resd 1
