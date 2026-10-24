; Genuine modern Mach-O layout and chained pointers, preferred4GiB image.
; This is an ABI fixture, never an original application coverage claim.
BITS 64
ORG 0x100000000
image:
 dd 0xfeedfacf,0x1000007,3,2,17,1512,0x200085,0
 dd 0x19,72
 db '__PAGEZERO',0
 times 5 db 0
 dq 0,0x100000000,0,0
 dd 0,0,0,0
 dd 0x19,552
 db '__TEXT',0
 times 9 db 0
 dq image,8192,0,8192
 dd 5,5,6,0
; Every section_64 name is a real16-byte fixed field.
%macro sec 9
%%start:
 db %1
 times 16-($-%%start) db 0
%%segment:
 db %2
 times 16-($-%%segment) db 0
 dq %3,%4
 dd %5,%6,0,0,%7,%8,%9,0
%endmacro
 sec '__text','__TEXT',entry,code_end-entry,entry-image,4,0x80000400,0,0
 sec '__stubs','__TEXT',stubs,18,stubs-image,1,0x80000408,0,6
 sec '__const','__TEXT',constant,16,constant-image,4,0,0,0
 sec '__cstring','__TEXT',message,message_end-message,message-image,0,2,0,0
 sec '__ustring','__TEXT',unicode,4,unicode-image,1,0,0,0
 sec '__unwind_info','__TEXT',unwind,28,unwind-image,2,0,0,0
 dd 0x19,232
 db '__DATA_CONST',0
 times 3 db 0
 dq 0x100002000,4096,8192,4096
 dd 3,3,2,16
 sec '__got','__DATA_CONST',0x100002000,24,8192,3,6,3,0
 sec '__const','__DATA_CONST',0x100002018,8,8216,3,0,0,0
 dd 0x19,232
 db '__DATA',0
 times 9 db 0
 dq 0x100003000,4096,12288,4096
 dd 3,3,2,0
 sec '__data','__DATA',0x100003000,64,12288,3,0,0,0
 sec '__bss','__DATA',0x100003040,64,0,3,1,0,0
 dd 0x19,72
 db '__LINKEDIT',0
 times 5 db 0
 dq 0x100004000,4096,16384,file_end-linkedit
 dd 1,1,0,0
 dd 0x80000034,16
 dd fixups-image,fixups_end-fixups
 dd 0x80000033,16
 dd exports-image,exports_end-exports
 dd 2,24
 dd symtab-image,4,strtab-image,strtab_end-strtab
 dd 11,80
 dd 0,0,0,1,1,3
 dd 0,0,0,0,0,0
 dd indirect-image,6,0,0,0,0
 dd 14,32,12
 db '/usr/lib/dyld',0
 times 6 db 0
 dd 27,24
 db 'space-highva-v01'
 dd 50,32,1,0xE0000,0xE0500,1,3,1
 dd 42,16
 dq 0
 dd 0x80000028,24
 dq entry-image,0
 dd 12,56,24,2,0x5418A02,0x10000
 db '/usr/lib/libSystem.B.dylib',0
 times 5 db 0
 dd 38,16
 dd function_starts-image,4
 dd 41,16
 dd file_end-image,0
 times 0x800-($-$$) db 0
entry:
 mov rax,rsp
 and eax,15
 cmp eax,8
 jne fail
 mov rax,0x130000000
 cmp [rsp],rax
 jne fail
 cmp edi,2
 jne fail
 mov rax,0x110005000
 cmp rsi,rax
 jne fail
 cmp qword[rsi+16],0
 jne fail
 cmp qword[rdx+8],0
 jne fail
 cmp qword[rcx+8],0
 jne fail
 mov rax,[rsi]
 cmp byte[rax],'h'
 jne fail
 mov rax,[rsi+8]
 cmp byte[rax],'x'
 jne fail
 mov rax,[rdx]
 cmp byte[rax],'e'
 jne fail
 mov rax,[rcx]
 cmp byte[rax],'a'
 jne fail
 ; Bound slots and rebase target preserve all high bits.
 mov rbx,0x100002000
 mov r12,0x130001000
 cmp [rbx],r12
 jne fail
 add r12,64
 cmp [rbx+8],r12
 jne fail
 add r12,64
 cmp [rbx+16],r12
 jne fail
 lea rax,[rel message]
 cmp [rbx+24],rax
 jne fail
 mov r15,0x100003000
 cmp [r15+8],rax
 jne fail
 cmp qword[r15+64],0
 jne fail
 mov qword[r15+64],0x1234
 cmp qword[r15+64],0x1234
 jne fail
 mov r14,[r15]
 sub rsp,8
 call [rbx+16]
 mov r13,0x110004000
 cmp rax,r13
 jne fail
 cmp dword[rax],0
 jne fail
 cmp r14,1
 je pagezero
 cmp r14,2
 je oldlow
 cmp r14,3
 je readonly_got
 cmp r14,4
 je execute_data
 cmp r14,5
 je text_write
 cmp r14,6
 je stack_execute
 cmp r14,7
 je link_write
 cmp r14,8
 je timeout
 cmp r14,9
 je invalid_opcode
 cmp r14,10
 je raw_exit
 cmp r14,11
 je unknown_raw
 cmp r14,12
 je crossing_pointer
continue_write:
 ; High pointer write and errno-preserving successful C ABI.
 mov edi,1
 lea rsi,[rel message]
 mov edx,message_end-message
 call [rbx]
 cmp eax,message_end-message
 jne fail
 mov edi,-1
 xor esi,esi
 mov edx,1
 call [rbx]
 cmp rax,-1
 jne fail
 cmp dword[r13],9
 jne fail
 mov edi,1
 mov esi,0x41000000
 mov edx,1
 call [rbx]
 cmp rax,-1
 jne fail
 cmp dword[r13],14
 jne fail
 mov edi,1
 lea rsi,[rel message]
 xor edx,edx
 call [rbx]
 test eax,eax
 jne fail
 cmp dword[r13],14
 jne fail
 add rsp,8
 mov eax,42
 ret
pagezero:
 xor eax,eax
 mov rax,[rax]
 jmp fail
oldlow:
 mov eax,0x4d000000
 mov rax,[rax]
 jmp fail
readonly_got:
 mov qword[rbx],0
 jmp fail
execute_data:
 call r15
 jmp fail
text_write:
 lea rax,[rel entry]
 mov byte[rax],0
 jmp fail
stack_execute:
 call rsp
 jmp fail
link_write:
 mov rax,0x100004000
 mov byte[rax],0
 jmp fail
timeout:
 jmp timeout
invalid_opcode:
 ud2
raw_exit:
 mov edi,42
 call [rbx+8]
 ud2
unknown_raw:
 mov eax,0x2007fff
 syscall
 jnc fail
 cmp eax,78
 jne fail
 jmp continue_write
crossing_pointer:
 mov edi,1
 mov rsi,0x100004fff
 mov edx,2
 call [rbx]
 cmp rax,-1
 jne fail
 cmp dword[r13],14
 jne fail
 jmp continue_write
fail:
 mov edi,99
 mov eax,0x2000001
 syscall
 ud2
code_end:
 times 0x1800-($-$$) db 0
stubs:
 jmp [rel got_write]
 jmp [rel got_exit]
 jmp [rel got_error]
 times 0x1900-($-$$) db 0
constant:
 dq 0x0123456789abcdef,0xfedcba9876543210
 times 0x1a00-($-$$) db 0
message: db 'darwin-high',10
message_end:
 times 0x1b00-($-$$) db 0
unicode: dw 'x',0
 times 0x1c00-($-$$) db 0
unwind: dd 1,28,0,28,0,28,0
 times 8192-($-$$) db 0
got_write: dq 0x8010000000000000
got_exit: dq 0x8010000000000001
got_error: dq 0x8010000000000002
 dq message-image
 times 12288-($-$$) db 0
 dq 0,message-image
 times 12352-($-$$) db 0
 ; Deliberately nonzero file padding at the zerofill BSS range.
 times 12416-($-$$) db 0xa5
 times 16384-($-$$) db 0
linkedit:
fixups:
 dd 0,32,imports-fixups,pool-fixups,3,1,0,0
 dd 5,0,0,24,48,0
 dd 24
 dw 4096,6
 dq 0x2000
 dd 0
 dw 1,0
 dd 24
 dw 4096,6
 dq 0x3000
 dd 0
 dw 1,8
imports:
 dd 1|((name_write-pool)<<9),1|((name_exit-pool)<<9),1|((name_error-pool)<<9)
pool:
name_write: db '_write',0
name_exit: db '_exit',0
name_error: db '___error',0
fixups_end:
 align 8,db 0
exports:
 db 0,1,'__mh_execute_header',0,23,2,0,0,0
exports_end:
function_starts: db 0x80,0x10,0,0
 align 8,db 0
symtab:
 dd symbol_header-strtab
 db 15,1
 dw 16
 dq image
%macro undef 1
 dd %1-strtab
 db 1,0
 dw 256
 dq 0
%endmacro
 undef symbol_write
 undef symbol_exit
 undef symbol_error
indirect: dd 1,2,3,1,2,3
strtab:
 db 0
symbol_header: db '__mh_execute_header',0
symbol_write: db '_write',0
symbol_exit: db '_exit',0
symbol_error: db '___error',0
strtab_end:
file_end:
