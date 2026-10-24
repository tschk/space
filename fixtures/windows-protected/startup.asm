BITS 64
section .headers start=0 vstart=0x140000000
image:
 dw 0x5a4d
 times 60-($-$$) db 0
 dd 128
 times 128-($-$$) db 0
 dd 0x4550
 dw 0x8664,3
 dd 0,0,0
 dw 240,0x22e
 dw 0x20b
 db 0,0
 dd 4096,1024,7680
 dd 0x1000,0x1000
 dq image
 dd 4096,512
 dw 6,0,0,0,6,0
 dd 0,0x7000,512,0
 dw 3,0x160
 dq 0x10000,0x1000,0x10000,0x1000
 dd 0,16
 times 9 dq 0
 dd 0x3000,40
 times 6 dq 0
 db '.text',0,0,0
 dd 4096,0x1000,4096,512,0,0
 dw 0,0
 dd 0x60000020
 db '.rdata',0,0
 dd 4096,0x3000,512,4608,0,0
 dw 0,0
 dd 0x40000040
 db '.data',0,0,0
 dd 8192,0x5000,512,5120,0,0
 dw 0,0
 dd 0xc0000040
section .text start=512 vstart=0x140001000
entry:
 mov rax,[gs:0x30]
 cmp rax,0x4e000000
 jne fail
 cmp qword [rax+8],0x4f004000
 jne fail
 cmp qword [rax+16],0x4f000000
 jne fail
 mov rax,[gs:0x60]
 mov rdx,0x140000000
 cmp [rax+16],rdx
 jne fail
 cmp qword [rel mode],9
 je success
 mov rax,[gs:0x58]
 mov rax,[rax]
 mov rdx,0x8877665544332211
 cmp [rax],rdx
 jne fail
 cmp qword [rax+8],0
 jne fail
 cmp byte [rax+4095],0
 jne fail
 cmp dword [rel index],0
 jne fail
 cmp qword [rel mode],8
 je success
 cmp qword [rel sequence],12
 jne fail
 mov edx,[rel mode]
 cmp edx,5
 je tls_execute
 cmp edx,6
 je teb_execute
 cmp edx,7
 je fs_zero
success:
 mov eax,42
 ret
fail:
 mov eax,99
 ret
fs_zero:
 mov rax,[fs:0]
 jmp fail
tls_execute:
 mov byte [rax],0xc3
 call rax
 jmp fail
teb_execute:
 mov rax,[gs:0x30]
 mov byte [rax],0xc3
 call rax
 jmp fail
callback1:
 mov rax,rsp
 and eax,15
 cmp eax,8
 jne bad_callback
 ; Exercise all four shadow-space slots without corrupting return address.
 mov qword [rsp+8],1
 mov qword [rsp+16],2
 mov qword [rsp+24],3
 mov qword [rsp+32],4
 mov rax,0x140000000
 cmp rcx,rax
 jne bad_callback
 cmp edx,1
 jne bad_callback
 test r8,r8
 jnz bad_callback
 mov ax,cs
 and eax,3
 cmp eax,3
 jne bad_callback
 mov eax,[rel mode]
 cmp eax,1
 je fault
 cmp eax,2
 je forever
 cmp eax,3
 je privileged
 cmp eax,4
 je forged
 mov qword [rel sequence],1
 ret
bad_callback:
 ud2
fault:
 mov eax,[0x100000]
 ret
forever:
 jmp forever
privileged:
 mov ecx,0xc0000101
 xor eax,eax
 xor edx,edx
 wrmsr
 ret
forged:
 mov qword [gs:0x30],0x100000
 mov rax,[gs:0x30]
 mov eax,[rax]
 ret
callback2:
 cmp qword [rel sequence],1
 jne bad_callback
 mov qword [rel sequence],12
 ; TLS writes must affect the private copy, never the source file template.
 mov rax,[gs:0x58]
 mov rax,[rax]
 mov qword [rax+16],73
 ret
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dq template,template+8,index,callbacks
 dd 4088,0x00d00000
 times 64-($-$$) db 0
callbacks:
 dq callback1,callback2,0
 times 128-($-$$) db 0
template:
 dq 0x8877665544332211
 times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
mode: dq 0
sequence: dq 0
index: dd 0xdeadbeef
 times 512-($-$$) db 0
