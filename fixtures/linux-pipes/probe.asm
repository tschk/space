; Synthetic ordinary Linux ABI contract probe, not an upstream application.
; Build with nasm -f elf64, then ld -static -z noexecstack. No libc/shims.
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
 call 293,ends,0x80800,0
 expect 0
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 72,r13,1031,0x100001000
 expect 4096
%ifdef LEAK_FAULT
 ud2
%endif
%ifdef LEAK_TIMEOUT
 jmp $
%endif
%ifdef BLOCKING_LIMIT
 call 3,r12,0,0
 expect 0
 call 3,r13,0,0
 expect 0
 call 293,ends,0,0
 expect 0
 mov edi,[rel ends]
 call 0,rdi,buffer,1
 ; No runnable owner can write. Space cancels the owned graph with explicit
 ; edge deadlock125; this syscall must not fabricate EOF or return ENOSYS.
 jmp fail
%endif
%ifdef DEFAULT_SIGPIPE
 call 3,r12,0,0
 expect 0
 call 1,r13,message,1
 ; A successful return would omit default SIGPIPE termination.
 jmp fail
%endif
 ; End access modes and nonblocking state are actual descriptor properties.
 call 72,r12,3,0
 expect 0x800
 call 72,r13,3,0
 expect 0x801
 call 72,r12,1,0
 expect 1
 call 72,r13,1,0
 expect 1
 call 5,r12,statbuf,0
 expect 0
 mov rbp,[rel statbuf+8]
 test rbp,rbp
 jz fail
 call 5,r13,statbuf2,0
 expect 0
 cmp rbp,[rel statbuf2+8]
 jne fail
 ; No data, no EOF while a writer reference still exists.
 call 0,r12,buffer,1
 expect -11
 call 0,r12,0,0
 expect 0
 call 1,r13,0,0
 expect 0
 call 0,r13,buffer,1
 expect -9
 call 1,r12,message,1
 expect -9
 ; Dup clears CLOEXEC. Closing the original does not close the open endpoint.
 call 32,r13,0,0
 test rax,rax
 js fail
 mov r14,rax
 call 72,r14,1,0
 expect 0
 call 3,r13,0,0
 expect 0
 call 1,r14,message,6
 expect 6
 call 0,r12,0x1000,6
 expect -14
 call 0,r12,buffer,6
 expect 6
 mov rax,[rel buffer]
 mov rbx,[rel message]
 shl rax,16
 shl rbx,16
 cmp rax,rbx
 jne fail
 ; Shared open-description nonblocking flags; per-fd CLOEXEC stays separate.
 call 32,r14,0,0
 test rax,rax
 js fail
 mov r15,rax
 call 72,r14,4,1
 expect 0
 call 72,r15,3,0
 expect 1
 call 72,r15,4,0x100000800
 expect 0
 call 72,r14,3,0
 expect 0x801
 call 72,r15,2,0x100000001
 expect 0
 call 72,r15,1,0
 expect 1
 call 72,r14,1,0
 expect 0
 call 72,r14,0,0x10000000c
 expect 12
 call 3,12,0,0
 expect 0
 ; A short atomic write cannot publish a prefix when space is insufficient.
 call 1,r14,payload,4090
 expect 4090
 call 1,r14,message,8
 expect -11
 call 0,r12,buffer,8192
 expect 4090
 call 0,r12,buffer,1
 expect -11
 ; Large nonblocking writes transfer actual available prefixes.
 call 1,r14,payload,5000
 expect 4096
 call 1,r14,message,1
 expect -11
 call 0,r12,buffer,100
 expect 100
 call 1,r14,payload,200
 expect -11
 call 1,r14,payload,5000
 ; Linux pipe implementations may retain an occupied page after a short
 ; read: a large nonblocking write may then EAGAIN rather than copy100.
 mov ebx,4096
 cmp rax,100
 je partial_done
 cmp rax,-11
 jne fail
 mov ebx,3996
partial_done:
 call 0,r12,buffer,8192
 expect rbx
 ; Reject malformed requests without mutating user output or consuming bytes.
 call 293,ends,0x10,0
 expect -22
 call 293,_start,0x800,0
 expect -14
 call 293,0x1000,0x800,0
 expect -14
 call 72,r14,999,0
 cmp rax,-38
 je unsupported_fcntl
 expect -22
unsupported_fcntl:
 ; Redirect a real pipe onto stdout; output must enter the private ring.
 call 33,r14,1,0
 expect 1
 call 1,1,message,6
 expect 6
 call 0,r12,buffer,6
 expect 6
 call 3,1,0,0
 expect 0
 call 1,1,message,1
 expect -9
 ; dup3 preserves CLOEXEC and rejects a same-fd request, including flags0.
 call 292,r12,10,0x80000
 expect 10
 call 72,10,1,0
 expect 1
 call 5,10,statbuf2,0
 expect 0
 cmp rbp,[rel statbuf2+8]
 jne fail
 call 292,10,10,0
 expect -22
 call 33,10,10,0
 expect 10
 call 3,r12,0,0
 expect 0
 ; Buffered EOF only after the final writer reference is closed.
 call 1,r14,message,6
 expect 6
 call 3,r14,0,0
 expect 0
 call 0,10,buffer,6
 expect 6
 call 0,10,buffer,1
 expect -11
 call 3,r15,0,0
 expect 0
 call 0,10,buffer,1
 expect 0
 call 3,10,0,0
 expect 0
 ; A fresh pair is empty and has a real FIFO identity, never a path pointer.
 call 293,ends,0x800,0
 expect 0
 mov r12d,[rel ends]
 mov r13d,[rel ends+4]
 call 0,r12,buffer,1
 expect -11
 call 5,r12,statbuf,0
 expect 0
 cmp rbp,[rel statbuf+8]
 je fail
 mov eax,[rel statbuf+24]
 and eax,0xf000
 cmp eax,0x1000
 jne fail
 ; Only ignored SIGPIPE makes a closed-peer write return EPIPE normally.
 xor r10d,r10d
 call 13,13,ignore_action,old_action
 ; The fourth syscall argument is r10, not rcx.
 ; This first deliberately malformed call has sigsetsize0 and must fail.
 expect -22
 mov r10d,8
 call 13,13,ignore_action,old_action
 expect 0
 cmp qword[rel old_action],0
 jne fail
 mov r10d,8
 call 13,13,0,old_action
 expect 0
 cmp qword[rel old_action],1
 jne fail
 call 3,r12,0,0
 expect 0
 call 1,r13,message,1
 expect -32
 call 3,r13,0,0
 expect 0
pass:
 call 60,42,0,0
 ud2
fail:
 call 60,1,0,0
 ud2
section .data
message: db 'pipes!',0,0
ignore_action: dq 1,0,0,0
payload: times 5000 db 'x'
section .bss
align 8
ends: resq 1
old_action: resq 4
statbuf: resb 144
statbuf2: resb 144
buffer: resb 8192
section .note.GNU-stack noalloc noexec nowrite progbits
