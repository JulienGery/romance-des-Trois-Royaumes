@ Runtime glue for the native French text patch (ARM mode, ARMv6K + VFPv2). See overrides.h.
        .arm
        .syntax unified
        .fpu vfp
        .text
        .set CTX_SIZE, 208          @ sizeof(Context) rounded up to 8

@ r12 = override function, r0-r3 = original arguments, lr = original caller's lr, sp = entry sp (stack args at [sp]).
@ Only 32 bytes are used on the game's stack (below the entry sp, so the game's own scratch use of sp-0x60... is untouched);
@ the Context and the C code live on a private stack (fr_cstack, one 8 KiB level per nesting depth).
        .global fr_enter
        .type fr_enter, %function
fr_enter:
        push    {r4-r6, lr}
        sub     sp, sp, #16
        mov     r5, sp                          @ r5 = hardware sp to restore = floor_sp (entry sp - 32)
        push    {r0-r3, r12}                    @ (below the floor, only live during the next call)
        sub     sp, sp, #4
        bl      fr_acquire                      @ r0 = top of this thread's next private C stack level
        add     sp, sp, #4
        mov     r6, r0                          @ top of the private stack level
        pop     {r0-r3, r12}
        sub     r4, r6, #CTX_SIZE               @ r4 = ctx (on the private stack)
        mov     sp, r4
        stmia   r4, {r0-r3}
        add     r6, r5, #32
        str     r6, [r4, #52]                   @ r[13] = entry sp
        ldr     r6, [r5, #28]
        str     r6, [r4, #56]                   @ r[14] = caller lr
        mov     r6, #0
        str     r6, [r4, #60]                   @ r[15]
        str     r5, [r4, #200]                  @ floor_sp
        add     r6, r4, #64
        vstmia  r6, {s0-s15}
        mov     r0, r4
        blx     r12
        bl      fr_release
        ldmia   r4, {r0-r3}                     @ the override leaves its results in the Context
        mov     sp, r5
        add     sp, sp, #16
        pop     {r4-r6, pc}
        .ltorg

@ void fr_call_guest(Context *ctx, uint32_t addr): run a game function with ctx's r0-r3 / s0-s15 / sp, store results back
        .global fr_call_guest
        .type fr_call_guest, %function
fr_call_guest:
        push    {r4-r8, lr}
        mov     r4, r0
        mov     r5, r1
        mov     r6, sp
        add     r7, r4, #64
        vldmia  r7, {s0-s15}
        ldr     r7, [r4, #52]                   @ guest sp
        ldr     r8, [r4, #200]                  @ floor_sp: our save area starts here
        cmp     r7, r8
        bls     1f                              @ the override already moved sp below the floor: use it
        sub     r8, r8, #32                     @ still the entry sp: run below our save area, but give the callee a copy of the
        mov     r6, r8                          @ caller's stack arguments (8 words) so that functions with stack args still see them
        ldmia   r7!, {r0-r3}
        stmia   r6!, {r0-r3}
        ldmia   r7!, {r0-r3}
        stmia   r6!, {r0-r3}
        mov     r7, r8
        mov     r6, sp                          @ (hardware sp to restore: recompute, r6 was reused as a pointer)
1:
        mov     sp, r7
        ldmia   r4, {r0-r3}
        blx     r5
        mov     sp, r6
        stmia   r4, {r0-r3}
        add     r7, r4, #64
        vstmia  r7, {s0-s15}
        pop     {r4-r8, pc}

        .include "stubs.S"
        .ltorg
