; Space nanokernel boot trampoline.
;
; This is the irreducible CPU bring-up shim that AGENTS.md permits to live
; outside `.in`: QEMU's multiboot loader hands control to us in 32-bit
; protected mode with paging off, and this code establishes x86_64 long mode
; before calling the `.in`-compiled kernel_entry.
;
; Assembled as a flat binary (`nasm -f bin`) and embedded by the Inauguration
; compiler at the front of the boot image. It is padded to exactly 0x2000 bytes
; so that the first compiled `.in` function (kernel_entry) lands at KCODE_BASE.

BITS 32
org 0x100000

MB_MAGIC     equ 0x1BADB002
MB_FLAGS     equ 0x00010000          ; AOUT_KLUDGE: provide load/entry addresses
MB_CHECKSUM  equ -(MB_MAGIC + MB_FLAGS)

KIMAGE_BASE  equ 0x100000
KERNEL_ENTRY equ 0x102000            ; KIMAGE_BASE + 0x2000 (TRAMPOLINE_RESERVE)

; Page-table scratch in low memory (free in QEMU after boot).
PML4 equ 0x1000
PDPT equ 0x2000
PD   equ 0x3000

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
    mov [mb_info], ebx               ; preserve the multiboot info pointer

    ; Zero PML4/PDPT/PD (3 pages at 0x1000..0x4000).
    mov edi, PML4
    mov ecx, 0x3000 / 4
    xor eax, eax
    rep stosd

    ; PML4[0] -> PDPT, PDPT[0] -> PD (present + writable).
    mov dword [PML4], PDPT | 0x3
    mov dword [PDPT], PD   | 0x3

    ; Fill the page directory: identity-map the first 1 GiB with 2 MiB pages.
    mov edi, PD
    mov eax, 0x83                     ; present | writable | page-size(2MiB)
    mov ecx, 512
.fill_pd:
    mov [edi], eax
    add eax, 0x200000
    add edi, 8
    loop .fill_pd

    mov eax, PML4
    mov cr3, eax

    mov eax, cr4
    or eax, 1 << 5                    ; CR4.PAE
    mov cr4, eax

    mov ecx, 0xC0000080              ; IA32_EFER
    rdmsr
    or eax, 1 << 8                    ; EFER.LME
    wrmsr

    mov eax, cr0
    or eax, 0x80000001              ; CR0.PG | CR0.PE
    mov cr0, eax

    lgdt [gdt_desc]
    jmp 0x08:long_mode               ; far jump into the 64-bit code segment

BITS 64
long_mode:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov fs, ax
    mov gs, ax
    mov rsp, 0x90000

    xor rdi, rdi
    mov edi, [mb_info]               ; arg0 = multiboot info pointer
    mov rax, KERNEL_ENTRY
    call rax

.hang:
    cli
    hlt
    jmp .hang

align 4
mb_info: dd 0

align 8
gdt:
    dq 0x0000000000000000           ; null descriptor
    dq 0x00AF9A000000FFFF           ; 0x08: 64-bit code (P, DPL0, exec/read, L)
    dq 0x00CF92000000FFFF           ; 0x10: data (P, DPL0, read/write)
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

times 0x2000 - ($ - $$) db 0        ; pad to TRAMPOLINE_RESERVE
