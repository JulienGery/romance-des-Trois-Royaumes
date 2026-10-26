/* Diagnostics and self tests (log only). Hook: FUN_00112FDC runs several times during boot, after the font object exists.
 * Reminder: code after CALL(original) is skipped when the original does I/O (svc); log BEFORE calling. */
#include "/Users/juliengery/Documents/yokai_watch_claude/overrides/frfont.h"
#include "/Users/juliengery/Documents/yokai_watch_claude/overrides/frwrap.h"
#include <stdlib.h>

extern int fr_wrap_disabled;

static void dump_textures(Context *ctx) {
    uint32_t group = fr_rd(ctx, FO_TEXGROUP);
    uint32_t g2 = group ? mem_read32(ctx, group + 8) : 0;
    uint32_t arr = g2 ? mem_read32(ctx, g2 + 0xC) : 0;
    fprintf(stderr, "[diag] textures: group=%08X array=%08X flag1214=%u\n", group, arr, fr_rd(ctx, FO_ASCII_FLAG));
    for (int i = 0; arr && i < 8; i++)
        fprintf(stderr, "[diag]   slot %d: width=%u\n", i, mem_read32(ctx, arr + i * 0x40 + 24));
}

static const char *test_strings[] = {
    "Hello, World! 0123456789",
    "The quick brown fox jumps over the lazy dog ~ | } ; : / - ? !",
    "Imprudence !  Ca va ?  A l'assaut quand meme !",
    "\xE3\x81\x93\xE3\x82\x93\xE3\x81\xAB\xE3\x81\xA1\xE3\x81\xAF\xE4\xB8\x96\xE7\x95\x8C",
    "Mixed \xE6\x97\xA5\xE6\x9C\xAC\xE8\xAA\x9E and ASCII and \xE3\x82\xAB\xE3\x82\xBF\xE3\x82\xAB\xE3\x83\x8A",
    "Line one\nLine two is longer than line one\nand three",
    "\x15 BIG \x14 normal \x16 small \x14 back",
    "Icon \x10" "A then text",
    "\xE3\x80\x90\xE5\xA4\xA7\xE4\xB8\x88\xE5\xA4\xAB\xEF\xBC\x9A\xE3\x81\xA0\xE3\x81\x84\xE3\x81\x98\xE3\x82\x87\xE3\x81\x86\xE3\x81\xB6\xE3\x80\x91\xEF\xBC\x81 ruby test",
    "\xE3\x80\x90r\xE3\x80\x91red text\xE3\x80\x90" "e\xE3\x80\x91 normal",
    "\xE3\x81\x82\xE3\x81\x84\xE3\x81\x86\xE3\x81\x88\xE3\x81\x8A\xE3\x81\x8B\xE3\x81\x8D\xE3\x81\x8F\xE3\x81\x91\xE3\x81\x93\xE3\x81\x95\xE3\x81\x97\xE3\x81\x99\xE3\x81\x9B\xE3\x81\x9D\xE3\x81\x9F\xE3\x81\xA1\xE3\x81\xA4\xE3\x81\xA6\xE3\x81\xA8\xE3\x80\x8D\xE3\x80\x81\xE3\x80\x82\xE3\x81\xAA\xE3\x81\xAB\xE3\x81\xAC\xE3\x81\xAD\xE3\x81\xAE",
    "\xEF\xBC\xA1\xEF\xBC\xA2\xEF\xBC\xA3 fullwidth ascii \xEF\xBD\x81\xEF\xBD\x82",
    "A very long sentence that certainly has to wrap around when the width is limited to a small number of pixels, with, punctuation. And more! Really?",
    "",
    " ",
};

static unsigned rng_state = 12345;
static unsigned rnd(void) { rng_state = rng_state * 1103515245u + 12345u; return (rng_state >> 16) & 0x7FFF; }

/* Compare the C port (legacy widths) with the original FUN_0052CEA4 on many inputs. */
static void selftest_measure(Context *ctx) {
    int total = 0, bad = 0;
    int32_t old_budget = ctx->budget; ctx->budget = 0x3FFFFFFF;
    uint32_t lr = ctx->r[14], sp0 = ctx->r[13];
    uint32_t base = (sp0 - 0x4000) & ~7u;
    uint32_t strp = base, outp = base + 0x800, stk = base + 0x900, buf2 = base + 0xA00;
    static const int cws[] = {12, 14, 16, 22};
    static const int wraps[] = {0x7FFFFFFF, 90, 150, 301};
    static const int spaces[] = {-1, 0, 2};
    int ntests = (int)(sizeof(test_strings) / sizeof(test_strings[0]));
    fr_legacy_mode = 1; fr_wrap_disabled = 1;
    for (int t = 0; t < ntests; t++) {
        const char *s = test_strings[t];
        size_t L = strlen(s) + 1;
        for (size_t i = 0; i < L; i++) mem_write8(ctx, strp + i, (uint8_t)s[i]);
        for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) for (int sp = 0; sp < 3; sp++) {
            int cw = cws[a], wrap = wraps[b], spc = spaces[sp], lsp = (b & 1) ? 8 : 2;
            uint32_t res[2][8];
            for (int which = 0; which < 2; which++) {
                fr_wr(ctx, FO_ASCII_FLAG, 1); fr_wr(ctx, FO_CHARW, cw); fr_wr(ctx, FO_CHARH, cw);
                fr_wr(ctx, FO_SPACING, spc); fr_wr(ctx, FO_LINESP, lsp); fr_wr(ctx, FO_WRAP, wrap);
                for (int k = 0; k < 6; k++) mem_write32(ctx, outp + k * 4, 0xDEADBEEF);
                uint32_t n, w, h, f6, f7;
                if (which == 0) {      /* original */
                    mem_write32(ctx, stk, 1); mem_write32(ctx, stk + 4, outp + 8); mem_write32(ctx, stk + 8, outp + 12);
                    ctx->r[13] = stk; ctx->r[0] = FONT_OBJ; ctx->r[1] = strp; ctx->r[2] = outp; ctx->r[3] = outp + 4; ctx->r[14] = lr;
                    CALL(RECOMP_ORIGINAL(0x0052CEA4));
                    n = ctx->r[0]; w = mem_read32(ctx, outp); h = mem_read32(ctx, outp + 4);
                    f6 = mem_read32(ctx, outp + 8); f7 = mem_read32(ctx, outp + 12);
                } else {               /* port: preprocess with the original, then the C core */
                    ctx->r[13] = buf2 + 0x440; ctx->r[0] = FONT_OBJ; ctx->r[1] = buf2; ctx->r[2] = strp; ctx->r[3] = 0xFFFFFFFFu; ctx->r[14] = lr;
                    ctx->r[15] = 0x0052C690u; ctx->thumb = 0; CALL(f_0052C690);
                    w = h = f6 = f7 = 0;
                    n = (uint32_t)fr_measure_core(ctx, FONT_OBJ, buf2, &w, &h, &f6, &f7);
                }
                res[which][0] = n; res[which][1] = w; res[which][2] = h; res[which][3] = f6; res[which][4] = f7;
                res[which][5] = fr_rd(ctx, FO_CHARW); res[which][6] = fr_rd(ctx, FO_CHARH);
            }
            total++;
            if (memcmp(res[0], res[1], 7 * 4)) {
                if (bad < 12)
                    fprintf(stderr, "[selftest] MISMATCH str#%d cw=%d wrap=%d sp=%d: orig n=%u w=%u h=%u f6=%u f7=%u cw'=%u | port n=%u w=%u h=%u f6=%u f7=%u cw'=%u\n",
                            t, cw, wrap, spc, res[0][0], res[0][1], res[0][2], res[0][3], res[0][4], res[0][5],
                            res[1][0], res[1][1], res[1][2], res[1][3], res[1][4], res[1][5]);
                bad++;
            }
        }
    }
    fr_legacy_mode = 0; fr_wrap_disabled = 0;
    ctx->r[13] = sp0; ctx->r[14] = lr;
    ctx->budget = old_budget;
    fprintf(stderr, "[selftest] measure port vs original: %d cases, %d mismatches\n", total, bad);
}

/* Draw French text through the real engine path and log the quads. */
static void selftest_draw(Context *ctx) {
    int32_t old_budget = ctx->budget; ctx->budget = 0x3FFFFFFF;
    uint32_t lr = ctx->r[14], sp0 = ctx->r[13];
    uint32_t strp = (sp0 - 0x2000) & ~7u;
    const char *s = "\xC3\x89l\xC3\xA9phant \xC3\xA0 l'\xC3\xA9" "cole ; ~ ! \xC2\xAB oui \xC2\xBB \xE2\x80\xA6";
    for (size_t i = 0; i <= strlen(s); i++) mem_write8(ctx, strp + i, (uint8_t)s[i]);
    fr_init(ctx);
    fr_wr(ctx, FO_CHARW, 16); fr_wr(ctx, FO_CHARH, 16); fr_wr(ctx, FO_SPACING, 0xFFFFFFFFu); fr_wr(ctx, FO_WRAP, 0x7FFFFFFF);
    uint32_t q0 = fr_rd(ctx, 0xBD4);
    fr_quad_log = stderr;
    fprintf(stderr, "[selftest] draw: quads before=%u\n", q0);
    ctx->r[13] = sp0 - 0x2100;
    ctx->r[0] = FONT_OBJ; ctx->r[1] = strp; ctx->r[2] = 20; ctx->r[3] = 40; ctx->r[14] = lr;
    mem_write32(ctx, sp0 - 0x2100, 0);                /* z (5th arg, stack) */
    ctx->r[15] = 0x0052DC28u; ctx->thumb = 0; CALL(f_0052DC28);
    fr_quad_log = NULL;
    ctx->budget = old_budget;
    ctx->r[13] = sp0; ctx->r[14] = lr;
    fprintf(stderr, "[selftest] draw: quads after=%u (ret r0=%d)\n", fr_rd(ctx, 0xBD4), (int)ctx->r[0]);
    for (uint32_t i = q0; i < fr_rd(ctx, 0xBD4); i++) {
        uint32_t nd = fr_rd(ctx, 4 + i * 4);
        fprintf(stderr, "[selftest] QUAD %f %f %f %f uv %f %f %f %f tex=%08X\n",
                fr_f(mem_read32(ctx, nd + 0x20)), fr_f(mem_read32(ctx, nd + 0x24)), fr_f(mem_read32(ctx, nd + 0x28)), fr_f(mem_read32(ctx, nd + 0x2c)),
                fr_f(mem_read32(ctx, nd + 0x40)), fr_f(mem_read32(ctx, nd + 0x44)), fr_f(mem_read32(ctx, nd + 0x48)), fr_f(mem_read32(ctx, nd + 0x4c)),
                mem_read32(ctx, nd + 0x50));
    }
}

/* wrap + typewriter through the real overrides: FUN_0052D340(x,y,z, font, maxChars, text, z2) */
static void dump_quads(Context *ctx, uint32_t q0, const char *tag) {
    for (uint32_t i = q0; i < fr_rd(ctx, 0xBD4); i++) {
        uint32_t nd = fr_rd(ctx, 4 + i * 4);
        fprintf(stderr, "[selftest] %s QUAD %f %f %f %f uv %f %f %f %f tex=%08X\n", tag,
                fr_f(mem_read32(ctx, nd + 0x20)), fr_f(mem_read32(ctx, nd + 0x24)), fr_f(mem_read32(ctx, nd + 0x28)), fr_f(mem_read32(ctx, nd + 0x2c)),
                fr_f(mem_read32(ctx, nd + 0x40)), fr_f(mem_read32(ctx, nd + 0x44)), fr_f(mem_read32(ctx, nd + 0x48)), fr_f(mem_read32(ctx, nd + 0x4c)), mem_read32(ctx, nd + 0x50));
    }
}
static void selftest_wrap(Context *ctx) {
    int32_t old_budget = ctx->budget; ctx->budget = 0x3FFFFFFF;
    uint32_t lr = ctx->r[14], sp0 = ctx->r[13];
    uint32_t strp = (sp0 - 0x3000) & ~7u;
    const char *s = "Mais qu'est-ce que c'est que cette histoire de mots tr\xC3\xA8s longs qui doivent passer \xC3\xA0 la ligne ?! Voil\xC3\xA0.";
    for (size_t i = 0; i <= strlen(s); i++) mem_write8(ctx, strp + i, (uint8_t)s[i]);
    int maxcs[] = {-1, 30};
    for (int k = 0; k < 2; k++) {
        fr_wr(ctx, FO_CHARW, 16); fr_wr(ctx, FO_CHARH, 16); fr_wr(ctx, FO_SPACING, 0xFFFFFFFFu); fr_wr(ctx, FO_LINESP, 2);
        fr_wr(ctx, FO_WRAP, 150); fr_wr(ctx, FO_ALIGN, 0);
        uint32_t q0 = fr_rd(ctx, 0xBD4);
        ctx->vfp[0] = fr_bits(10.0f); ctx->vfp[1] = fr_bits(10.0f); ctx->vfp[2] = fr_bits(0.0f);
        ctx->r[13] = sp0 - 0x3100; ctx->r[0] = FONT_OBJ; ctx->r[1] = (uint32_t)maxcs[k]; ctx->r[2] = strp; ctx->r[3] = 0; ctx->r[14] = lr;
        ctx->r[15] = 0x0052D340u; ctx->thumb = 0; CALL(f_0052D340);
        fprintf(stderr, "[selftest] wrap(150) maxc=%d: ret=%d quads=%u\n", maxcs[k], (int)ctx->r[0], fr_rd(ctx, 0xBD4) - q0);
        dump_quads(ctx, q0, k ? "W30" : "WALL");
    }
    fr_wr(ctx, FO_WRAP, 0x7FFFFFFFu);
    ctx->budget = old_budget; ctx->r[13] = sp0; ctx->r[14] = lr;
}

/* ---- phase 4: run the game's own window layout functions on corpus strings and log the geometry ------------------
 * widget fields: +0x24 x +0x28 y +0x2C w +0x30 h (box) ; +0x254/+0x258 text x/y ; +0x26C/+0x270 measured w/h ; +0x260 charW */
typedef struct { uint32_t addr; void (*orig)(Context *); void (*fn)(Context *); const char *name; } box_fn;
void override_0x00533D70(Context *); void override_0x005586CC(Context *); void override_0x0055833C(Context *);
void override_0x00265900(Context *); void override_0x00272E60(Context *); void override_0x002C7F7C(Context *); void override_0x00353308(Context *);
static const box_fn box_fns[] = {
    { 0x00533D70, f_00533D70, override_0x00533D70, "msg_533D70" }, { 0x005586CC, f_005586CC, override_0x005586CC, "msg_5586CC" },
    { 0x0055833C, f_0055833C, override_0x0055833C, "msg_55833C" }, { 0x00265900, f_00265900, override_0x00265900, "msg_265900" },
    { 0x00272E60, f_00272E60, override_0x00272E60, "msg_272E60" }, { 0x002C7F7C, f_002C7F7C, override_0x002C7F7C, "msg_2C7F7C" },
    { 0x00353308, f_00353308, override_0x00353308, "msg_353308" }, { 0x00541794, f_00541794, f_00541794, "msg_541794" },
};
static void selftest_boxes(Context *ctx) {
    const char *path = getenv("FR_BOXFILE");
    FILE *fp = path ? fopen(path, "rb") : NULL;
    if (!fp) { fprintf(stderr, "[box] no FR_BOXFILE\n"); return; }
    fseek(fp, 0, SEEK_END); long sz = ftell(fp); fseek(fp, 0, SEEK_SET);
    uint8_t *all = malloc(sz); if (fread(all, 1, sz, fp) != (size_t)sz) return; fclose(fp);
    int32_t old_budget = ctx->budget; ctx->budget = 0x3FFFFFFF;
    uint32_t lr = ctx->r[14], sp0 = ctx->r[13];
    uint32_t wid = (sp0 - 0x6000) & ~7u, strp = wid + 0x800, stk = wid - 0x200;
    for (unsigned f = 0; f < sizeof(box_fns) / sizeof(box_fns[0]); f++) {
        int nmodes = 2, ntypes = (box_fns[f].addr == 0x00353308) ? 9 : 1;
        for (int mode = 0; mode < nmodes; mode++) for (int type = 0; type < ntypes; type++) {
            for (long p = 0; p < sz;) {
                uint8_t *in = all + p; int L = (int)strlen((char *)in); p += L + 1;
                for (uint32_t i = 0; i < 0x400; i += 4) mem_write32(ctx, wid + i, 0);
                for (int i = 0; i <= L; i++) mem_write8(ctx, strp + i, in[i]);
                for (int v = 0; v < 40; v++) mem_write32(ctx, wid + 0x500 + v * 4, 0x0010003C);   /* fake vtable: every slot = bx lr */
                mem_write32(ctx, wid, wid + 0x500);
                mem_write32(ctx, wid + 0x48, mode); mem_write32(ctx, wid + 0x2A4, type);
                fr_wr(ctx, FO_WRAP, 0x7FFFFFFFu);
                ctx->r[13] = stk; ctx->r[0] = wid; ctx->r[1] = strp; ctx->r[2] = 0; ctx->r[3] = 0; ctx->r[14] = lr;
                ctx->r[15] = box_fns[f].addr; ctx->thumb = 0;
                if (getenv("FR_BOXORIG")) box_fns[f].orig(ctx); else box_fns[f].fn(ctx);
                if (ctx->exit) { fprintf(stderr, "[box] exit during %s\n", box_fns[f].name); ctx->exit = 0; }
                int mh = (int)mem_read32(ctx, wid + 0x270), cw = (int)mem_read32(ctx, wid + 0x260);
                fprintf(stderr, "[box] %s mode=%d type=%d len=%d x=%d y=%d w=%d h=%d tx=%d ty=%d mw=%d mh=%d cw=%d\n", box_fns[f].name, mode, type, L,
                        (int)mem_read32(ctx, wid + 0x24), (int)mem_read32(ctx, wid + 0x28), (int)mem_read32(ctx, wid + 0x2C), (int)mem_read32(ctx, wid + 0x30),
                        (int)mem_read32(ctx, wid + 0x254), (int)mem_read32(ctx, wid + 0x258), (int)mem_read32(ctx, wid + 0x26C), mh, cw);
            }
        }
    }
    ctx->budget = old_budget; ctx->r[13] = sp0; ctx->r[14] = lr;
    fprintf(stderr, "[box] done\n");
}

void override_0x0052CEA4(Context *);
/* bubble measure: spoof the return address of a bubble call site and measure a long string at charW 14 */
static void selftest_bubble(Context *ctx) {
    int32_t old_budget = ctx->budget; ctx->budget = 0x3FFFFFFF;
    uint32_t sp0 = ctx->r[13], lr0 = ctx->r[14], strp = (sp0 - 0x3000) & ~7u, nsp = strp - 0x400;
    const char *s = "Mais qu'est-ce que c'est que cette histoire de mots tr\xC3\xA8s longs qui doivent passer \xC3\xA0 la ligne dans une bulle de dialogue ?!";
    for (size_t i = 0; i <= strlen(s); i++) mem_write8(ctx, strp + i, (uint8_t)s[i]);
    uint32_t sites[2] = { 0x23634C + 4, 0x1234 };
    for (int k = 0; k < 2; k++) {
        fr_wr(ctx, FO_CHARW, 14); fr_wr(ctx, FO_CHARH, 14); fr_wr(ctx, FO_LINESP, 7); fr_wr(ctx, FO_WRAP, 0x7FFFFFFFu); fr_wr(ctx, FO_ALIGN, 0);
        mem_write32(ctx, nsp, 1); mem_write32(ctx, nsp + 4, 0); mem_write32(ctx, nsp + 8, 0);
        ctx->r[13] = nsp; ctx->r[0] = FONT_OBJ; ctx->r[1] = strp; ctx->r[2] = nsp + 0x20; ctx->r[3] = nsp + 0x24; ctx->r[14] = sites[k];
        override_0x0052CEA4(ctx);
        fprintf(stderr, "[selftest] bubble site=%s: w=%u h=%u lines=%u\n", k ? "other" : "bubble", mem_read32(ctx, nsp + 0x20), mem_read32(ctx, nsp + 0x24), (mem_read32(ctx, nsp + 0x24) + 7) / 21);
    }
    ctx->r[13] = sp0; ctx->r[14] = lr0; ctx->budget = old_budget;
}

RECOMP_OVERRIDE(0x00112FDC) {
    static int n;
    n++;
    if (n == 2) dump_textures(ctx);
    if (n >= 1 && getenv("FR_TRACE")) fprintf(stderr, "[diag] 00112FDC call %d budget=%d depth=%u\n", n, ctx->budget, ctx->depth);
    if (n == 4 && getenv("FR_SELFTEST")) { selftest_measure(ctx); selftest_draw(ctx); selftest_wrap(ctx); selftest_bubble(ctx); }
    if (n == 4 && getenv("FR_BOXFILE")) selftest_boxes(ctx);
    CALL(RECOMP_ORIGINAL(0x00112FDC));
}
