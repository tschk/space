; Private Mach-O fixture: raw Darwin syscalls and seven typed libSystem imports.
; RX text / RW-NX data, no native or host function pointers.
BITS 64
ORG 0x41000000
image:
 dd 0xfeedfacf,0x01000007,3,2,5,272,1,0
 dd 0x19,72
 db '__TEXT',0
 times 9 db 0
 dq image,4096,0,4096
 dd 5,5,0,0
 dd 0x19,72
 db '__DATA',0
 times 9 db 0
 dq 0x42000000,12288,4096,4096
 dd 3,3,0,0
 dd 0x80000028,24
 dq entry-image,0
 dd 0x80000022,48
 dd 0,0,bind_program-image,bind_end-bind_program,0,0,0,0,0,0
 dd 0xC,56,24,0,0,0
 db '/usr/lib/libSystem.B.dylib',0
 times 5 db 0
%macro ERR 1
 jnc fail
 cmp rax,%1
 jne fail
%endmacro
%macro OK 1
 jc fail
 cmp rax,%1
 jne fail
%endmacro
entry:
 mov rbx,0x42000000
 mov r13,[rbx]
 cmp r13,23
 je wide_raw
 cmp r13,24
 je wide_import
 cmp r13,25
 je fs_probe
 cmp r13,26
 je gs_probe
 cmp r13,21
 je component_syscall
 cmp r13,22
 je component_import
 cmp r13,17
 jge imported
 cmp r13,1
 je denied
 cmp r13,5
 je ambient
 cmp r13,9
 je missing
 cmp r13,10
 je longpath
 cmp r13,11
 je flags
 cmp r13,12
 je unknown
 cmp r13,16
 je pathcross
 call openfile
 OK 3
 mov r12,rax
 cmp r13,6
 je fault
 cmp r13,7
 je spin
 cmp r13,8
 je revoke
 cmp r13,2
 je readonly
 cmp r13,3
 je crossing
 cmp r13,4
 je badptr
 cmp r13,13
 je badseek
 cmp r13,14
 je doubleclose
 cmp r13,15
 je oversized
 ; Read all 8192 actual file bytes; compare with independent fixed alphabet.
 mov edi,r12d
 mov esi,0x42000400
 mov edx,8192
 mov eax,0x2000003
 syscall
 OK 8192
 xor r8d,r8d
 mov r9,0x42000400
verify:
 mov rax,r8
 and eax,15
 lea r10,[rel alphabet]
 mov dl,[r10+rax]
 cmp [r9+r8],dl
 jne fail
 inc r8
 cmp r8,8192
 jne verify
 ; EOF and relative seek use real shared descriptor offset.
 mov edi,r12d
 mov esi,0x42000400
 mov edx,1
 mov eax,0x2000003
 syscall
 OK 0
 mov edi,r12d
 mov rsi,-1
 mov edx,2
 mov eax,0x20000c7
 syscall
 OK 8191
 mov edi,r12d
 mov esi,0x42000400
 mov edx,16
 mov eax,0x2000003
 syscall
 OK 1
 cmp byte [r9],'f'
 jne fail
 jmp success ; Deliberately leave open for supervisor cleanup.
readonly:
 mov esi,entry
 mov edx,16
 jmp readerror
crossing:
 mov esi,0x42002ff0
 mov edx,32
 jmp readerror
badptr:
 mov esi,0x100000
 mov edx,16
readerror:
 mov edi,r12d
 mov eax,0x2000003
 syscall
 ERR 14
 ; Rejected reads must not advance the VFS offset.
 mov edi,r12d
 xor esi,esi
 mov edx,1
 mov eax,0x20000c7
 syscall
 OK 0
 jmp success
badseek:
 mov edi,r12d
 xor esi,esi
 mov edx,3
 mov eax,0x20000c7
 syscall
 ERR 22
 jmp success
doubleclose:
 mov edi,r12d
 mov eax,0x2000006
 syscall
 OK 0
 mov edi,r12d
 mov eax,0x2000006
 syscall
 ERR 9
 jmp success
oversized:
 mov edi,r12d
 mov esi,0x42000400
 mov edx,65537
 mov eax,0x2000003
 syscall
 ERR 22
 jmp success
revoke:
 mov eax,0x2fffffe
 syscall
 OK 0
 mov edi,r12d
 mov esi,0x42000400
 mov edx,1
 mov eax,0x2000003
 syscall
 ERR 13
 mov edi,r12d
 xor esi,esi
 mov edx,1
 mov eax,0x20000c7
 syscall
 ERR 13
 ; Revocation cannot strand owned descriptors: close remains allowed.
 mov edi,r12d
 mov eax,0x2000006
 syscall
 OK 0
 jmp success
ambient:
 mov edi,3
 mov esi,0x42000400
 mov edx,1
 mov eax,0x2000003
 syscall
 ERR 9
 mov edi,3
 mov eax,0x2000006
 syscall
 ERR 9
 jmp success
denied:
 call openfile
 ERR 13
 mov edi,0x100000
 xor esi,esi
 mov eax,0x2000005
 syscall
 ERR 13
 jmp success
missing:
 lea rdi,[rel absent]
 xor esi,esi
 mov eax,0x2000005
 syscall
 ERR 2
 jmp success
longpath:
 lea rdi,[rel overlong]
 xor esi,esi
 mov eax,0x2000005
 syscall
 ERR 63
 jmp success
flags:
 lea rdi,[rel path]
 mov esi,1
 mov eax,0x2000005
 syscall
 ERR 22
 jmp success
unknown:
 mov eax,0x2000fff
 syscall
 ERR 78
 jmp success
pathcross:
 mov rdi,0x42002fff
 mov byte [rdi],'x'
 xor esi,esi
 mov eax,0x2000005
 syscall
 ERR 14
 jmp success
fault:
 mov eax,[0x100000]
 jmp fail
spin:
 jmp spin
fs_probe:
 mov rax,[fs:0]
 jmp fail
gs_probe:
 mov rax,[gs:0]
 jmp fail
wide_raw:
 lea rdi,[rel path]
 mov rsi,0xdeadbeef00000000
 mov eax,0x2000005
 syscall
 OK 3
 mov rdi,0xdeadbeef00000003
 mov esi,0x42000400
 mov edx,1
 mov eax,0x2000003
 syscall
 OK 1
 cmp byte [0x42000400],'0'
 jne fail
 mov rdi,0xdeadbeef00000003
 xor esi,esi
 mov rdx,0xfeedface00000001
 mov eax,0x20000c7
 syscall
 OK 1
 mov rdi,0xdeadbeef00000003
 xor esi,esi
 mov rdx,0xfeedface00000000
 mov eax,0x20000c7
 syscall
 OK 0
 ; Pointer, count and file offset remain full-width arguments.
 mov rdi,0xdeadbeef00000003
 mov rsi,0x142000400
 mov edx,1
 mov eax,0x2000003
 syscall
 ERR 14
 mov rdi,0xdeadbeef00000003
 mov esi,0x42000400
 mov rdx,0x100000001
 mov eax,0x2000003
 syscall
 ERR 22
 mov rdi,0xdeadbeef00000003
 mov rsi,0x100000001
 xor edx,edx
 mov eax,0x20000c7
 syscall
 ERR 22
 mov rdi,0xdeadbeef00000003
 mov eax,0x2000006
 syscall
 OK 0
 mov rdi,0xdeadbeefffffffff
 mov eax,0x2000006
 syscall
 ERR 9
 mov rdi,0xdeadbeef00000001
 xor esi,esi
 xor edx,edx
 mov eax,0x2000004
 syscall
 OK 0
 jmp success
wide_import:
 lea rdi,[rel path]
 mov rsi,0xdeadbeef00000000
 call [rbx+56]
 cmp rax,3
 jne fail
 mov rdi,0xdeadbeef00000003
 mov esi,0x42000400
 mov edx,1
 call [rbx+64]
 cmp rax,1
 jne fail
 cmp byte [0x42000400],'0'
 jne fail
 mov rdi,0xdeadbeef00000003
 xor esi,esi
 mov rdx,0xfeedface00000001
 call [rbx+80]
 cmp rax,1
 jne fail
 mov rdi,0xdeadbeef00000003
 xor esi,esi
 mov rdx,0xfeedface00000000
 call [rbx+80]
 test rax,rax
 jnz fail
 mov rdi,0xdeadbeef00000003
 call [rbx+72]
 test rax,rax
 jnz fail
 mov rdi,0xdeadbeefffffffff
 call [rbx+72]
 cmp rax,-1
 jne fail
 call [rbx+48]
 cmp dword [rax],9
 jne fail
 jmp success
; Exact on-disk boundary: 24 bytes exists, 25 bytes must report Darwin63,
; before filesystem lookup can turn representability refusal into ENOENT2.
component_syscall:
 lea rdi,[rel component24]
 xor esi,esi
 mov eax,0x2000005
 syscall
 OK 3
 mov edi,eax
 mov eax,0x2000006
 syscall
 OK 0
 lea rdi,[rel component25]
 xor esi,esi
 mov eax,0x2000005
 syscall
 ERR 63
 jmp success
component_import:
 lea rdi,[rel component24]
 xor esi,esi
 call [rbx+56]
 cmp rax,3
 jne fail
 mov edi,eax
 call [rbx+72]
 test rax,rax
 jnz fail
 lea rdi,[rel component25]
 xor esi,esi
 call [rbx+56]
 cmp rax,-1
 jne fail
 call [rbx+48]
 cmp dword [rax],63
 jne fail
 jmp success
imported:
 call [rbx+48]
 cmp dword [rax],0
 jne fail
 lea rdi,[rel path]
 xor esi,esi
 call [rbx+56]
 cmp r13,18
 je imported_denied
 cmp rax,3
 jne fail
 mov r12,rax
 cmp r13,19
 je imported_badptr
 cmp r13,20
 je imported_badclose
 mov edi,r12d
 mov esi,4090
 xor edx,edx
 call [rbx+80]
 cmp rax,4090
 jne fail
 mov edi,r12d
 mov esi,0x42000400
 mov edx,16
 call [rbx+64]
 cmp rax,16
 jne fail
 ; Verify a cross-4KiB read from actual VFS offset4090.
 xor r8d,r8d
 lea r10,[rel alphabet]
 mov r9,0x42000400
imported_verify:
 lea rax,[r8+4090]
 and eax,15
 mov dl,[r10+rax]
 cmp [r9+r8],dl
 jne fail
 inc r8
 cmp r8,16
 jne imported_verify
 mov edi,r12d
 call [rbx+72]
 test rax,rax
 jnz fail
 mov edi,1
 xor esi,esi
 xor edx,edx
 call [rbx+32]
 test rax,rax
 jnz fail
 mov edi,42
 call [rbx+40]
 jmp fail
imported_denied:
 cmp rax,-1
 jne fail
 call [rbx+48]
 cmp dword [rax],13
 jne fail
 jmp success
imported_badptr:
 mov edi,r12d
 mov esi,entry
 mov edx,16
 call [rbx+64]
 cmp rax,-1
 jne fail
 call [rbx+48]
 cmp dword [rax],14
 jne fail
 mov edi,r12d
 xor esi,esi
 mov edx,1
 call [rbx+80]
 test rax,rax
 jnz fail
 jmp success
imported_badclose:
 mov edi,r12d
 call [rbx+72]
 test rax,rax
 jnz fail
 mov edi,r12d
 call [rbx+72]
 cmp rax,-1
 jne fail
 call [rbx+48]
 cmp dword [rax],9
 jne fail
 jmp success
openfile:
 lea rdi,[rel path]
 xor esi,esi
 mov eax,0x2000005
 syscall
 ret
success:
 mov eax,42
 ret
fail:
 mov eax,90
 ret
bind_program:
 db 0x11,0x40,'_write',0,0x51,0x71,32,0x90
 db 0x40,'_exit',0,0x71,40,0x90
 db 0x40,'_error',0,0x71,48,0x90
 db 0x40,'_open',0,0x71,56,0x90
 db 0x40,'_read',0,0x71,64,0x90
 db 0x40,'_close',0,0x71,72,0x90
 db 0x40,'_lseek',0,0x71,80,0x90,0
bind_end:
component24: db '/abcdefghijklmnopqrstuvwx',0
component25: db '/abcdefghijklmnopqrstuvwxy',0
path: db '/darwin-file-api.txt',0
absent: db '/darwin-missing.txt',0
alphabet: db '0123456789abcdef'
overlong: times 256 db 'x'
 db 0
 times 4096-($-image) db 0
 dq 0
 times 8192-($-image) db 0
