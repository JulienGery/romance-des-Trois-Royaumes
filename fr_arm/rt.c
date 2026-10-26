/* freestanding helpers + runtime state for the native patch (no libc in the game's address space for us) */
#include <stddef.h>
#include <stdint.h>
/* private C stacks: FR_SLOTS threads x FR_LEVELS nesting levels x FR_LV bytes. A thread owns a slot (key = its TLS address, unique per thread),
 * so two threads inside overrides at the same time never share a stack or a nesting counter. */
#define FR_SLOTS 8
#define FR_LEVELS 4
#define FR_LV 6144
static struct { uint32_t key, depth; } fr_slot[FR_SLOTS];
static uint8_t fr_cstack[FR_SLOTS][FR_LEVELS][FR_LV] __attribute__((aligned(8)));
static inline uint32_t fr_tls(void) { uint32_t t; __asm__ volatile("mrc p15, 0, %0, c13, c0, 3" : "=r"(t)); return t; }
static int fr_find(uint32_t tls) {
    for (int i = 0; i < FR_SLOTS; i++) if (fr_slot[i].key == tls) return i;
    for (int i = 0; i < FR_SLOTS; i++) if (fr_slot[i].key == 0 && __sync_bool_compare_and_swap(&fr_slot[i].key, 0, tls)) return i;
    for (int i = 0; i < FR_SLOTS; i++) if (fr_slot[i].key == tls) return i;      /* lost a race against ourselves: cannot happen, but be safe */
    return 0;                                                                  /* out of slots: degrade to a shared one */
}
uint32_t fr_acquire(void) {
    int s = fr_find(fr_tls()); uint32_t d = fr_slot[s].depth++;
    if (d >= FR_LEVELS) d = FR_LEVELS - 1;
    return (uint32_t)&fr_cstack[s][d][FR_LV];
}
void fr_release(void) { int s = fr_find(fr_tls()); if (fr_slot[s].depth) fr_slot[s].depth--; }
void *memcpy(void *d, const void *s, size_t n) { uint8_t *a = d; const uint8_t *b = s; while (n--) *a++ = *b++; return d; }
void *memmove(void *d, const void *s, size_t n) { uint8_t *a = d; const uint8_t *b = s; if (a < b) while (n--) *a++ = *b++; else { a += n; b += n; while (n--) *--a = *--b; } return d; }
void *memset(void *d, int c, size_t n) { uint8_t *a = d; while (n--) *a++ = (uint8_t)c; return d; }
int memcmp(const void *x, const void *y, size_t n) { const uint8_t *a = x, *b = y; for (; n; n--, a++, b++) if (*a != *b) return *a - *b; return 0; }
size_t strlen(const char *s) { size_t n = 0; while (s[n]) n++; return n; }
/* no libgcc in the cavity: integer division (ARM11 has no divide instruction) */
unsigned __aeabi_uidiv(unsigned n, unsigned d) {
    unsigned q = 0, r = 0;
    if (!d) return 0;
    for (int i = 31; i >= 0; i--) { r = (r << 1) | ((n >> i) & 1); if (r >= d) { r -= d; q |= 1u << i; } }
    return q;
}
int __aeabi_idiv(int n, int d) {
    int neg = 0; unsigned un = n, ud = d;
    if (n < 0) { un = -(unsigned)n; neg ^= 1; }
    if (d < 0) { ud = -(unsigned)d; neg ^= 1; }
    unsigned q = __aeabi_uidiv(un, ud);
    return neg ? -(int)q : (int)q;
}
