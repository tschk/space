; Space 32-bit v86 boot trampoline.
;
; Multiboot1 loader hands control to us in 32-bit protected mode with paging
; off. This trampoline sets up 32-bit paging with 4 MiB identity-mapped
; pages, installs a 32-bit GDT, and calls the .in-compiled kernel_entry at
; 0x101100. It deliberately stays in protected mode (no long mode).
;
; Assembled as a flat binary and embedded at the front of the boot image.
; Padded to exactly 0x1000 bytes so kernel_entry lands at 0x101100.

BITS 32
org 0x100000
default abs

MB_MAGIC     equ 0x1BADB002
MB_FLAGS     equ 0x00010800          ; AOUT_KLUDGE | BIT11 (VBE info)
MB_CHECKSUM  equ -(MB_MAGIC + MB_FLAGS)

KIMAGE_BASE  equ 0x100000
KCODE_BASE   equ 0x101000            ; KIMAGE_BASE + 0x1000 (TRAMPOLINE_RESERVE)
KERNEL_ENTRY equ 0x101100            ; KCODE_BASE + 0x100 (SCI header size)

; Page directory for 32-bit identity mapping (4 MiB pages).
PAGE_DIR     equ 0x1000

mb_header:
    dd MB_MAGIC
    dd MB_FLAGS
    dd MB_CHECKSUM
    dd mb_header                     ; header_addr
    dd KIMAGE_BASE                   ; load_addr
    dd 0                             ; load_end_addr (0 => load whole file)
    dd 0                             ; bss_end_addr  (0 => no extra bss)
    dd entry32                       ; entry_addr

entry32:
    cli
    mov esp, 0x90000                 ; temporary stack in low memory
    mov [mb_info], ebx               ; preserve multiboot info pointer

    ; Build a 32-bit page directory with 4 MiB pages identity-mapping the
    ; first 4 GiB. 1024 entries * 4 bytes = 4096 bytes at PAGE_DIR.
    mov edi, PAGE_DIR
    mov ecx, 1024
    xor eax, eax
    rep stosd

    mov edi, PAGE_DIR
    mov eax, 0x83                     ; present | writable | page-size (4 MiB)
    mov ecx, 1024
.fill_pd:
    mov [edi], eax
    add eax, 0x400000
    add edi, 4
    loop .fill_pd

    mov eax, PAGE_DIR
    mov cr3, eax

    mov eax, cr4
    or eax, 1 << 4                    ; CR4.PSE (4 MiB pages)
    mov cr4, eax

    mov eax, cr0
    or eax, 0x80000001              ; CR0.PG | CR0.PE
    mov cr0, eax

    lgdt [gdt_desc]
    jmp 0x08:protected_32            ; far jump to reload CS with 32-bit code segment

protected_32:
    cld
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov fs, ax
    mov gs, ax
    mov esp, 0x90000

    xor eax, eax
    mov eax, [mb_info]               ; arg0 = multiboot info pointer
    call KERNEL_ENTRY

.hang:
    cli
    hlt
    jmp .hang

align 4
mb_info: dd 0

align 8
gdt:
    dq 0x0000000000000000           ; null descriptor
    dq 0x00CF9A000000FFFF           ; 0x08: 32-bit code (P, DPL0, exec/read, 4 GiB limit)
    dq 0x00CF92000000FFFF           ; 0x10: data (P, DPL0, read/write, 4 GiB limit)
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

times 0x1000 - ($ - $$) db 0        ; pad to TRAMPOLINE_RESERVE
