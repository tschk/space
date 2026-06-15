OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(_start)

PHDRS
{
  text    PT_LOAD    FLAGS((1 << 0) | (1 << 2))
  rodata  PT_LOAD    FLAGS((1 << 2))
  data    PT_LOAD    FLAGS((1 << 1) | (1 << 2))
  dynamic PT_DYNAMIC FLAGS((1 << 1) | (1 << 2))
}

SECTIONS
{
  . = 0xFFFFFFFF80000000 + SIZEOF_HEADERS;

  .text : {
    *(.text .text.*)
  } :text

  . = ALIGN(CONSTANT(MAXPAGESIZE));

  .rodata : {
    *(.rodata .rodata.*)
  } :rodata

  . = ALIGN(CONSTANT(MAXPAGESIZE));

  .data : {
    *(.data .data.*)
  } :data

  .bss : {
    *(.bss .bss.*)
    *(COMMON)
  } :data

  .got : {
    *(.got .got.*)
  } :data

  /DISCARD/ : {
    *(.comment .comment.*)
    *(.note .note.*)
    *(.eh_frame .eh_frame.*)
    *(.debug .debug.*)
    *(.debug_*)
  }
}
