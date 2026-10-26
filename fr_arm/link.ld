/* Native French text patch: code+rodata go into a dead-code cavity of the game's .text, state into an extension of .bss
 * (the exheader bss size is raised by build_arm_native.py). Addresses are substituted by the build script. */
MEMORY {
    CAV (rx)  : ORIGIN = @CAV_ORG@, LENGTH = @CAV_LEN@
    BSS (rw)  : ORIGIN = @BSS_ORG@, LENGTH = @BSS_LEN@
}
SECTIONS {
    .text : { KEEP(*(.text.fr_enter)) *(.text*) *(.rodata*) . = ALIGN(4); } > CAV
    .bss (NOLOAD) : { *(.bss*) *(COMMON) . = ALIGN(8); } > BSS
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) *(.data*) *(.eh_frame*) }
}
