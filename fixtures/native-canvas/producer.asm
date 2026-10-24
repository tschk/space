; Synthetic native CPL3 producer, not an upstream application.
BITS 64
ORG 0x20000000
 mov ebx,edi
 mov eax,902
 syscall
 mov eax,ebx
 mov edi,0x20010000
 mov ecx,32768
 cmp ebx,-1
 je partial_fault
 cld
 rep stosd
 mov eax,901
 mov edi,42
 syscall
 ud2
partial_fault:
 mov ecx,16384
 cld
 rep stosd
 mov byte[0x20000000],0
 ud2
 times 4096-($-$$) db 0
