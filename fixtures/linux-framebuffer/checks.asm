bits 64
section .text
global _start
%macro call 2
 mov eax,%1
 syscall
 cmp rax,%2
 jne fail
%endmacro
_start:
 mov r15,[rsp+16]
 movzx r15d,byte [r15]
 lea rdi,[rel path]
 mov esi,2
 xor edx,edx
 mov eax,2
 syscall
 cmp rax,3
 jl fail
 mov r12,rax
 mov rdi,r12
 mov esi,3
 xor edx,edx
 call 72,2                         ; F_GETFL
 mov rdi,r12
 mov esi,0x4600
 lea rdx,[rel buffer]
 call 16,0
 cmp dword [rel buffer],256
 jne fail
 cmp dword [rel buffer+4],128
 jne fail
 cmp dword [rel buffer+24],32
 jne fail
 cmp dword [rel buffer+32],16
 jne fail
 cmp dword [rel buffer+36],8
 jne fail
 cmp dword [rel buffer+44],8
 jne fail
 cmp dword [rel buffer+48],8
 jne fail
 cmp dword [rel buffer+60],8
 jne fail
 mov esi,0x4602
 call 16,0
 cmp qword [rel buffer+16],0       ; no physical framebuffer
 jne fail
 cmp dword [rel buffer+24],131072
 jne fail
 cmp dword [rel buffer+32],2
 jne fail
 cmp dword [rel buffer+48],1024
 jne fail
 cmp qword [rel buffer+56],0       ; no physical MMIO
 jne fail
 mov esi,0x4600
 xor edx,edx
 call 16,-14
 mov esi,0x4601                   ; mode changes unsupported
 lea rdx,[rel buffer]
 call 16,-25
 call 32,-95                     ; device dup refused
 lea rdi,[rel file]
 xor esi,esi
 xor edx,edx
 mov eax,2
 syscall
 cmp rax,3
 jl fail
 mov r13,rax
 mov rdi,r13
 mov rsi,r12
 call 33,-95                     ; replacement cannot steal device slot
 mov rdi,r13
 call 3,0
 lea rdi,[rel pair]
 call 22,0
 mov edi,[rel pair+4]
 mov rsi,r12
 call 33,-95                     ; pipe replacement likewise refused
 mov edi,[rel pair]
 call 3,0
 mov edi,[rel pair+4]
 call 3,0
 xor edi,edi
 mov esi,131072
 mov edx,3
 mov r10d,1
 mov r8,r12
 mov r9d,4096
 call 9,-22
 xor r9d,r9d
 mov edx,1
 call 9,-22
 mov edx,3
 mov r10d,0x22
 call 9,-22
 mov r10d,1
 mov eax,9
 syscall
 test rax,rax
 jle fail
 mov r14,rax
 cmp r15b,'f'
 je fault
 cmp r15b,'d'
 je deadline
 xor edi,edi
 call 9,-16                      ; no fake alias/same-address mapping
 mov rdi,r14
 mov esi,4096
 mov edx,1
 call 10,-95
 call 11,-22                     ; partial unmap retains full source
 call 57,-95
 call 58,-95
 mov edi,17
 xor esi,esi
 call 56,-95
 xor edi,edi
 xor esi,esi
 xor edx,edx
 call 59,-95
 mov rdi,r12
 call 3,0                        ; mapping survives closed descriptor
 mov esi,0x4600
 lea rdx,[rel buffer]
 call 16,-9
 mov rdi,r14
 mov ecx,32768
 mov eax,0x5500aabb
 rep stosd
 mov rdi,r14
 mov esi,131072
 call 11,0                       ; actual stopped copy and presentation
 lea rdi,[rel path]
 mov esi,2
 mov eax,2
 syscall
 cmp rax,3
 jl fail
 mov r12,rax
 xor edi,edi
 mov esi,131072
 mov edx,3
 mov r10d,1
 mov r8,r12
 xor r9d,r9d
 call 9,-95                      ; completed mapping retires this finite lease
 mov rdi,r12
 call 3,0
 mov edi,42
 jmp done
fault:
 mov byte [rel _start],0
 jmp fail
deadline:
 mov eax,1
 mov edi,1
 lea rsi,[rel marker]
 mov edx,marker_end-marker
 syscall
.spin:
 jmp .spin
fail:
 mov edi,99
done:
 mov eax,60
 syscall
 ud2
section .rodata
marker: db 'framebuffer: deadline armed',10
marker_end:
path: db '/dev/fb0',0
file: db '/fbv-test.bmp',0
section .bss
align 8
buffer: resb 160
pair: resb 8
