; Trusted fixed-address x86_64 Mach-O fixture. Entry follows Space's function ABI.
BITS 64
ORG 0x280000
image:
    dd 0xfeedfacf, 0x01000007, 3, 2
    dd 2, 96, 1, 0
    dd 0x19, 72
    db '__TEXT', 0
    times 16-7 db 0
    dq image, 4096, 0, 4096
    dd 5, 5, 0, 0
    dd 0x80000028, 24
    dq entry-image, 0
entry:
    mov eax, 42
    ret
    times 4096-($-$$) db 0
