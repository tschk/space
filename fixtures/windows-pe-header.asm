; Fixed-address PE32+ console fixture with real named import descriptors/IAT.
BITS 64
ORG 0x280000
image:
    dw 0x5A4D
    times 60-($-$$) db 0
    dd 128
    times 128-($-$$) db 0
    dd 0x4550
    dw 0x8664, 1
    dd 0, 0, 0
    dw 240, 0x23
opt:
    dw 0x20B
    db 0, 0
    dd 3584, 0, 0
    dd entry-image, 512
    dq image
    dd 512, 512
    dw 6, 0, 0, 0, 6, 0
    dd 0, 4096, 512, 0
    dw 3, 0
    dq 0x100000, 0x1000, 0x100000, 0x1000
    dd 0, 16
    dq 0
    dd imports-image, 40
    times 14 dq 0
section_header:
    db '.text', 0, 0, 0
    dd 3584, 512, 3584, 512
    dd 0, 0
    dw 0, 0
    dd 0x60000020
    times 512-($-$$) db 0
