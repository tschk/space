BITS 64
%ifndef PE_OFFSET
%define PE_OFFSET 256
%endif
%define TEXT_BYTES 0x300000
section .headers start=0 vstart=0x140000000
image:
 dw 0x5a4d
 times 60-($-$$) db 0
 dd PE_OFFSET
 times PE_OFFSET-($-$$) db 0
 dd 0x4550
 dw 0x8664,3
 dd 0,0,0
 dw 240,0x22e
 dw 0x20b
 db 0,0
 dd TEXT_BYTES,1024,7680
 dd 0x1000,0x1000
 dq image
 dd 4096,512
 dw 6,0,0,0,6,0
 dd 0,0x305000,1024,0
 dw 3,0x8160
 dq 0x10000,0x1000,0x10000,0x1000
 dd 0,16
 times 16 dq 0
 db '.text',0,0,0
 dd TEXT_BYTES,0x1000,TEXT_BYTES,1024,0,0
 dw 0,0
 dd 0x60000020
 db '.rdata',0,0
 dd 4096,0x301000,512,1024+TEXT_BYTES,0,0
 dw 0,0
 dd 0x40000040
 db '.data',0,0,0
 dd 8192,0x303000,512,1536+TEXT_BYTES,0,0
 dw 0,0
 dd 0xc0000040
section .text start=1024 vstart=0x140001000
entry:
 mov rbx,0x140303000
 mov r15,0x140000000
 mov ax,cs
 and eax,3
 cmp eax,3
 jne fail
 mov eax,[rbx+8]
 cmp [r15+60],eax
 jne fail
 cmp word [r15],0x5a4d
 jne fail
 cmp qword [rbx+4608],0
 jne fail
 mov eax,[rbx]
 cmp eax,1
 je text_write
 cmp eax,2
 je data_execute
 cmp eax,3
 je header_write
 cmp eax,4
 je readonly_write
 cmp eax,5
 je kernel_read
 cmp eax,6
 je forever
 cmp eax,7
 je last_text_write
 cmp eax,8
 je gs_zero
 sub rsp,40
 call last_code
 add rsp,40
 ret
fail:
 mov eax,99
 ret
text_write:
 mov byte [rel entry],0xc3
 jmp fail
data_execute:
 mov byte [rbx],0xc3
 call rbx
 jmp fail
header_write:
 mov byte [r15],0
 jmp fail
readonly_write:
 mov rax,0x140301000
 mov byte [rax],0
 jmp fail
kernel_read:
 mov eax,[0x100000]
 jmp fail
forever:
 jmp forever
last_text_write:
 mov byte [rel last_code],0xc3
 jmp fail
gs_zero:
 mov rax,[gs:0]
 jmp fail
 times TEXT_BYTES-32-($-$$) db 0x90
last_code:
 mov eax,42
 ret
 times TEXT_BYTES-($-$$) db 0x90
section .rdata start=1024+TEXT_BYTES vstart=0x140301000
 db 'large synthetic PE view',0
 times 512-($-$$) db 0
section .data start=1536+TEXT_BYTES vstart=0x140303000
 dq 0,PE_OFFSET
 times 512-($-$$) db 0
