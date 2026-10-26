; Direct actual CPL3 invariant probe: a copy failure must prevent postcall store.
bits 64
org 0x20001000
mov eax,1
mov edi,1
mov esi,0x20000000
mov edx,8
syscall
mov qword[abs 0x20000010],1
mov eax,60
mov edi,99
syscall
ud2
times 4096-($-$$) db 0
