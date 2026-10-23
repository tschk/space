; Separate application-profile fixture: high preferred base and three sections.
BITS 64
section .headers start=0 vstart=0x140000000
image:
    dw 0x5A4D
    times 60-($-$$) db 0
    dd 128
    times 128-($-$$) db 0
    dd 0x4550
    dw 0x8664, 3
    dd 0, 0, 0
    dw 240, 0x22E
    dw 0x20B
    db 0, 0
    dd 4096, 1024, 7680
    dd 0x1000, 0x1000
    dq image
    dd 4096, 512
    dw 6, 0, 0, 0, 6, 0
    dd 0, 0x7000, 512, 0
    dw 3, 0x160
    dq 0x10000, 0x1000, 0x10000, 0x1000
    dd 0, 16
    dq 0
    dd 0x3000, 40
    times 10 dq 0
    dd 0x3080, 56
    times 3 dq 0
    db '.text', 0, 0, 0
    dd 4096, 0x1000, 4096, 512, 0, 0
    dw 0, 0
    dd 0x60000020
    db '.rdata', 0, 0
    dd 4096, 0x3000, 512, 4608, 0, 0
    dw 0, 0
    dd 0x40000040
    db '.data', 0, 0, 0
    dd 8192, 0x5000, 2048, 5120, 0, 0
    dw 0, 0
    dd 0xC0000040
%macro error_is 1
 call [r14+32]
 cmp eax,%1
 jne fail
%endmacro
%macro seed_error 0
 mov ecx,0x12345678
 call [r14+40]
%endmacro
%macro get_alpha 0
 lea rcx,[rel alpha]
 lea rdx,[rbx+1024]
 mov r8d,32
 call [r14]
%endmacro
section .text start=512 vstart=0x140001000
entry:
 sub rsp,40
 mov rbx,0x140005000
 mov r14,0x140003080
 lea rdi,[rbx+1024]
 mov al,90
 mov ecx,32
 rep stosb
 mov word [rbx+8190],0x5a5a
 seed_error
 cmp qword [rbx],18
 je empty_initial
 get_alpha
 cmp eax,3
 jne fail
 cmp dword [rbx+1024],0x00656e6f
 jne fail
 error_is 0x12345678
 mov qword [rbx+1024],0x5a5a5a5a
 mov eax,[rbx]
 cmp eax,1
 je size_query
 cmp eax,2
 je short_output
 cmp eax,3
 je missing
 cmp eax,4
 je empty_value
 cmp eax,5
 je bad_name
 cmp eax,6
 je readonly_output
 cmp eax,7
 je crossing_output
 cmp eax,8
 je mutate_snapshots
 cmp eax,9
 je delete_empty
 cmp eax,10
 je snapshot_pool
 cmp eax,11
 je failed_mutation
 cmp eax,12
 je missing_delete
 cmp eax,13
 je snapshot_write
 cmp eax,14
 je snapshot_execute
 cmp eax,15
 je bad_free
 cmp eax,16
 je fault
 cmp eax,17
 je forever
 cmp eax,20
 je map_full
success:
 mov eax,42
 add rsp,40
 ret
fail:
 mov eax,99
 add rsp,40
 ret
size_query:
 lea rcx,[rel alpha]
 xor edx,edx
 xor r8d,r8d
 call [r14]
 cmp eax,4
 jne fail
 error_is 0x12345678
 jmp success
short_output:
 lea rcx,[rel alpha]
 lea rdx,[rbx+1024]
 mov r8d,3
 call [r14]
 cmp eax,4
 jne fail
 cmp qword [rbx+1024],0x5a5a5a5a
 jne fail
 error_is 0x12345678
 jmp success
missing:
 lea rcx,[rel missing_name]
 lea rdx,[rbx+1024]
 mov r8d,32
 call [r14]
 test eax,eax
 jnz fail
 cmp qword [rbx+1024],0x5a5a5a5a
 jne fail
 error_is 203
 jmp success
empty_value:
 lea rcx,[rel empty_name]
 lea rdx,[rbx+1024]
 mov r8d,32
 call [r14]
 test eax,eax
 jnz fail
 cmp dword [rbx+1024],0x5a5a5a00
 jne fail
 error_is 0x12345678
 lea rcx,[rel empty_name]
 xor edx,edx
 xor r8d,r8d
 call [r14]
 cmp eax,1
 jne fail
 jmp success
bad_name:
 mov ecx,0x100000
 lea rdx,[rbx+1024]
 mov r8d,32
 call [r14]
 jmp pointer_error
readonly_output:
 lea rcx,[rel alpha]
 mov rdx,0x140003100
 mov r8d,4
 call [r14]
 jmp pointer_error
crossing_output:
 lea rcx,[rel alpha]
 lea rdx,[rbx+8190]
 mov r8d,4
 call [r14]
 cmp word [rbx+8190],0x5a5a
 jne fail
pointer_error:
 test eax,eax
 jnz fail
 error_is 998
 jmp success
mutate_snapshots:
 call [r14+8]
 mov r12,rax
 call [r14+8]
 mov r13,rax
 cmp r12,r13
 je fail
 mov rsi,r12
 lea rdi,[rel original_block]
 mov ecx,original_end-original_block
 repe cmpsb
 jne fail
 lea rcx,[rel alpha_w]
 lea rdx,[rel changed_w]
 call [r14+24]
 test eax,eax
 jz fail
 get_alpha
 cmp eax,7
 jne fail
 mov rax,0x006465676e616863
 cmp [rbx+1024],rax
 jne fail
 mov rsi,r12
 lea rdi,[rel original_block]
 mov ecx,original_end-original_block
 repe cmpsb
 jne fail
 call [r14+8]
 mov r15,rax
 mov rsi,r15
 lea rdi,[rel changed_block]
 mov ecx,changed_end-changed_block
 repe cmpsb
 jne fail
 mov rcx,r12
 call [r14+16]
 test eax,eax
 jz fail
 mov rcx,r12
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 87
 mov rcx,r13
 call [r14+16]
 mov rcx,r15
 call [r14+16]
 jmp success
delete_empty:
 lea rcx,[rel alpha_w]
 xor edx,edx
 call [r14+24]
 test eax,eax
 jz fail
 get_alpha
 test eax,eax
 jnz fail
 error_is 203
 lea rcx,[rel alpha_w]
 xor edx,edx
 call [r14+24]
 test eax,eax
 jz fail
 error_is 203
 lea rcx,[rel alpha_w]
 lea rdx,[rel empty_w]
 call [r14+24]
 test eax,eax
 jz fail
 get_alpha
 test eax,eax
 jnz fail
 cmp byte [rbx+1024],0
 jne fail
 jmp success
snapshot_pool:
 xor r12d,r12d
pool_get:
 call [r14+8]
 test rax,rax
 jz fail
 mov [rbx+2048+r12*8],rax
 inc r12d
 cmp r12d,4
 jne pool_get
 call [r14+8]
 test rax,rax
 jnz fail
 error_is 8
 xor r12d,r12d
pool_free:
 mov rcx,[rbx+2048+r12*8]
 call [r14+16]
 test eax,eax
 jz fail
 inc r12d
 cmp r12d,4
 jne pool_free
 mov r12d,100
pool_cycle:
 call [r14+8]
 test rax,rax
 jz fail
 mov rcx,rax
 call [r14+16]
 test eax,eax
 jz fail
 dec r12d
 jnz pool_cycle
 jmp success
failed_mutation:
 lea rcx,[rel alpha_w]
 lea rdx,[rel nonascii_w]
 call [r14+24]
 test eax,eax
 jnz fail
 error_is 1113
 lea rcx,[rel equals_w]
 lea rdx,[rel changed_w]
 call [r14+24]
 test eax,eax
 jnz fail
 error_is 87
 lea rcx,[rel alpha_w]
 lea rdx,[rbx+8191]
 call [r14+24]
 test eax,eax
 jnz fail
 error_is 998
 get_alpha
 cmp eax,3
 jne fail
 cmp dword [rbx+1024],0x00656e6f
 jne fail
 jmp success
missing_delete:
 lea rcx,[rel missing_w]
 xor edx,edx
 call [r14+24]
 test eax,eax
 jz fail
 error_is 0x12345678
 jmp success
snapshot_write:
 call [r14+8]
 test rax,rax
 jz fail
 mov byte [rax],65
 jmp fail
snapshot_execute:
 call [r14+8]
 test rax,rax
 jz fail
 call rax
 jmp fail
bad_free:
 call [r14+8]
 mov r12,rax
 lea rcx,[rax+2]
 call [r14+16]
 test eax,eax
 jnz fail
 error_is 87
 mov rcx,r12
 call [r14+16]
 test eax,eax
 jz fail
 jmp success
fault:
 lea rcx,[rel alpha_w]
 lea rdx,[rel changed_w]
 call [r14+24]
 mov eax,[0x100000]
 jmp fail
forever:
 lea rcx,[rel alpha_w]
 lea rdx,[rel changed_w]
 call [r14+24]
loop_forever:
 jmp loop_forever
empty_initial:
 get_alpha
 test eax,eax
 jnz fail
 error_is 203
 call [r14+8]
 test rax,rax
 jz fail
 cmp dword [rax],0
 jne fail
 mov rcx,rax
 call [r14+16]
 test eax,eax
 jz fail
 jmp success
map_full:
 lea rcx,[rel new_w]
 lea rdx,[rel changed_w]
 call [r14+24]
 test eax,eax
 jnz fail
 error_is 8
 get_alpha
 cmp eax,3
 jne fail
 jmp success
 times 4096-($-$$) db 0x90
section .rdata start=4608 vstart=0x140003000
 dd 0x3040,0,0,0x30c0,0x3080
 times 64-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0x3180,0
 times 128-($-$$) db 0
 dq 0x30e0,0x3100,0x3120,0x3140,0x3160,0x3180,0
 times 192-($-$$) db 0
 db 'KERNEL32.dll',0
 times 224-($-$$) db 0
 dw 0
 db 'GetEnvironmentVariableA',0
 times 256-($-$$) db 0
 dw 0
 db 'GetEnvironmentStringsW',0
 times 288-($-$$) db 0
 dw 0
 db 'FreeEnvironmentStringsW',0
 times 320-($-$$) db 0
 dw 0
 db 'SetEnvironmentVariableW',0
 times 352-($-$$) db 0
 dw 0
 db 'GetLastError',0
 times 384-($-$$) db 0
 dw 0
 db 'SetLastError',0
 times 512-($-$$) db 0
section .data start=5120 vstart=0x140005000
 dq 0
alpha: db 'alpha',0
empty_name: db 'Empty',0
missing_name: db 'HOME',0
alpha_w: dw 'a','L','p','H','a',0
changed_w: dw 'c','h','a','n','g','e','d',0
nonascii_w: dw 0x1000,0
equals_w: dw 'b','a','d','=','k','e','y',0
missing_w: dw 'N','O','N','E',0
new_w: dw 'N','E','W',0
empty_w: dw 0
original_block:
 dw 'A','L','P','H','A','=','o','n','e',0
 dw 'E','M','P','T','Y','=',0
 dw 'Z','u','l','u','=','l','a','s','t',0,0
original_end:
changed_block:
 dw 'a','L','p','H','a','=','c','h','a','n','g','e','d',0
 dw 'E','M','P','T','Y','=',0
 dw 'Z','u','l','u','=','l','a','s','t',0,0
changed_end:
 times 2048-($-$$) db 0
