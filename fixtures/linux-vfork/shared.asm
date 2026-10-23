; Ordinary Linux ABI: genuine vfork shared VM, failed exec, typed exit and exec.
bits 64
global _start
%macro sys 4
 mov eax,%1
 mov rdi,%2
 mov rsi,%3
 mov rdx,%4
 syscall
%endmacro
%macro eq 1
 cmp rax,%1
 jne fail
%endmacro
section .text
_start:
 mov rax,[rsp+8]
 cmp byte[rax],'r'
 je replaced
 mov qword[rel shared],100
 sys 12,0,0,0
 mov r12,rax
 sys 58,0,0,0
 test rax,rax
 js fail
 jz firstchild
 mov r13,rax
 cmp qword[rel shared],111
 jne fail
 cmp qword[rel parent_progress],0
 jne fail
 mov qword[rel parent_progress],1
 sys 12,0,0,0
 lea rbx,[r12+4096]
 eq rbx
 cmp qword[r12],0x1234
 jne fail
 mov r14,[rel mapping]
 cmp qword[r14],0x5678
 jne fail
 sys 10,r14,4096,1
 eq 0
 cmp qword[r14],0x5678
 jne fail
 sys 11,r14,4096,0
 eq 0
 sys 61,r13,waitstatus,0
 eq r13
 cmp dword[rel waitstatus],23<<8
 jne fail
 ; A second child fails exec then signals a genuine fault; parent stays blocked.
 sys 58,0,0,0
 test rax,rax
 js fail
 jz faultchild
 mov r13,rax
 cmp qword[rel shared],222
 jne fail
 sys 61,r13,waitstatus,0
 eq r13
 cmp dword[rel waitstatus],4
 jne fail
 ; Exec must unblock the parent before the replacement can finish: it waits
 ; for a byte only the resumed parent can send through its surviving writer.
 sys 293,ends,0,0
 eq 0
 mov r15d,[rel ends+4]
 ; Real exec detaches from shared VM, retaining parent contents.
 sys 58,0,0,0
 test rax,rax
 js fail
 jz execchild
 mov r13,rax
 cmp qword[rel shared],333
 jne fail
 sys 1,r15,letter,1
 eq 1
 sys 61,r13,waitstatus,0
 eq r13
 cmp dword[rel waitstatus],7<<8
 jne fail
 cmp qword[rel shared],333
 jne fail
 sys 60,42,0,0
firstchild:
 cmp qword[rel parent_progress],0
 jne fail
 mov qword[rel shared],111
 lea rdi,[r12+4096]
 mov eax,12
 syscall
 lea rbx,[r12+4096]
 eq rbx
 mov qword[r12],0x1234
 mov r10d,0x22
 mov r8,-1
 xor r9d,r9d
 sys 9,0,4096,3
 test rax,rax
 js fail
 mov [rel mapping],rax
 mov qword[rax],0x5678
 sys 59,missing,execargs,0
 eq -2
 cmp qword[rel parent_progress],0
 jne fail
 sys 59,self,1,0
 eq -14
 cmp qword[rel parent_progress],0
 jne fail
 sys 60,23,0,0
faultchild:
 cmp qword[rel parent_progress],1
 jne fail
 mov qword[rel shared],222
 ud2
execchild:
 mov edi,[rel ends]
 xor esi,esi
 mov eax,33
 syscall
 eq 0
 mov qword[rel shared],333
 sys 59,self,execargs,envargs
 jmp fail
replaced:
 sys 0,0,received,1
 eq 1
 cmp byte[rel received],'Q'
 jne fail
 cmp qword[rel shared],17
 jne fail
 sys 60,7,0,0
fail:
 sys 60,1,0,0
section .rodata
self: db '/proc/self/exe',0
missing: db '/space-vfork-missing',0
name: db 'replacement',0
home: db 'HOME=/',0
locale: db 'LC_ALL=C',0
letter: db 'Q'
section .data
shared: dq 17
parent_progress: dq 0
mapping: dq 0
execargs: dq name,0
envargs: dq home,locale,0
section .bss
waitstatus: resq 1
ends: resd 2
received: resb 1
