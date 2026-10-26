/* Native (ARM11, on-console) replacement for the 3dsrecomp "overrides.h": lets the SAME override sources (overrides/fr_text.c,
 * frfont.h, frwrap.h) be compiled with arm-none-eabi-gcc and run inside the game process.
 * Model: every hooked game function enters fr_enter (rt.S) which builds a Context from the registers (r0-r3, s0-s15, entry sp/lr);
 * the C override then works exactly as in the recompiled build; CALL(...) runs a guest function with the Context's registers
 * (fr_call_guest). Guest memory is native memory here, so mem_read/mem_write are plain loads/stores. */
#ifndef FR_NATIVE_H
#define FR_NATIVE_H
#define FR_NATIVE 1
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* layout is known to rt.S: r at 0, vfp at 64, budget at 192, thumb at 196, floor_sp at 200.
 * r[13] is the game's stack pointer at entry (stack arguments live there); floor_sp is the lowest address that is still ours (rt.S keeps a
 * small save area just below the entry sp): guest calls run on min(r[13], floor_sp) so they never clobber it. */
typedef struct Context {
    uint32_t r[16];
    uint32_t vfp[32];
    int32_t budget;
    uint8_t thumb;
    uint32_t floor_sp;
} Context;

#define mem_read8(c, a)      (*(volatile uint8_t *)(uintptr_t)(uint32_t)(a))
#define mem_read16(c, a)     (*(volatile uint16_t *)(uintptr_t)(uint32_t)(a))
#define mem_read32(c, a)     (*(volatile uint32_t *)(uintptr_t)(uint32_t)(a))
#define mem_write8(c, a, v)  (*(volatile uint8_t *)(uintptr_t)(uint32_t)(a) = (uint8_t)(v))
#define mem_write16(c, a, v) (*(volatile uint16_t *)(uintptr_t)(uint32_t)(a) = (uint16_t)(v))
#define mem_write32(c, a, v) (*(volatile uint32_t *)(uintptr_t)(uint32_t)(a) = (uint32_t)(v))

void fr_call_guest(Context *ctx, uint32_t addr);       /* rt.S */
#define CALL(code) code(ctx)
#define RETURN_TO(v) do { (void)(v); return; } while (0)
#define RECOMP_OVERRIDE(address) void override_##address(Context *ctx)
#define RECOMP_ORIGINAL(address) fr_orig_##address

#undef getenv
#define getenv(x) ((char *)0)

#include "hooks.h"      /* generated: fr_orig_0x........ (trampolines) and f_........ aliases */
#endif
