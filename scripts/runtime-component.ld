SECTIONS {
  . = BASE;
  .text : { *(.text) }
  .data : { *(.data) }
  .rodata : { *(.rodata*) }
  .bss : { *(.bss COMMON) }
}
