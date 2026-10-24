; Real CPL3 fault payload, no imports or executable kernel pointers.
BITS 64
%ifndef LOAD_BASE
%define LOAD_BASE 0x70000000
%endif
ORG LOAD_BASE
    dq 0x5343490000000002, 1, entry, 4096
    dq 0, 0, 0, 0
entry:
%ifdef PAGE_FAULT
    mov rax, [0x1000]              ; kernel page table is not mapped to the guest
%else
    ud2
%endif
    mov eax, 99                    ; must never return this fabricated success
    ret
    times 4096-($-$$) db 0
