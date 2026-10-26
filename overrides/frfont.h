/* French proportional font support for Yo-kai Watch Sangokushi (title 000400000018B000).
 *
 * Header-only, included by the override files. Everything here is host C operating on guest memory.
 *
 * Guest facts (see rapport/RAPPORT_police_variable.md):
 *   font object            0x007DAA28
 *     +0x11E0 texture group, +0x1214 proportional-ASCII flag, +0x1218 align, +0x1220 charW, +0x1224 charH,
 *     +0x1228 spacing, +0x122C line spacing, +0x1238 wrap width
 *   text is UTF-8 packed big-endian into a u32 by UTF8_iter (0x0052D79C)
 *   French glyph pages live in texture slots 6 (ft_sml 16x16 cells) and 7 (ft_nrm 16x18 cells) of LINKDATA entry 0
 */
#ifndef FRFONT_H
#define FRFONT_H

#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "overrides.h"
#include "font_sml.h"

#define FONT_OBJ        0x007DAA28u
#define FO_TEXGROUP     0x11E0u
#define FO_ASCII_FLAG   0x1214u
#define FO_ALIGN        0x1218u
#define FO_CHARW        0x1220u
#define FO_CHARH        0x1224u
#define FO_SPACING      0x1228u
#define FO_LINESP       0x122Cu
#define FO_WRAP         0x1238u
#define FR_TEX_SML      6u
#define FR_PAGE         256

/* LESSON (phase 5, real game): when the instruction budget runs out inside a nested CALL, the host unwinds and later resumes the
 * CALLED function; the rest of the override (restoring r13, writing results, restoring state) is silently skipped, which corrupted the
 * guest stack ("branch to unmapped 0x6F63206C" = text used as a return address). Every override that does anything AFTER a CALL
 * must top the budget up first. */
#define FR_ENSURE_BUDGET(c) do { if ((c)->budget < 4000000) (c)->budget = 4000000; } while (0)

/* env-gated diagnostics: FR_TRACE_FILE=/path appends one line per event (see rapport/PLAN_correctifs_texte.md) */
#ifdef FR_NATIVE
static inline FILE *fr_logf(void) { return 0; }
#else
static FILE *fr_logf(void) {
    static FILE *f; static int init;
    if (!init) { init = 1; const char *p = getenv("FR_TRACE_FILE"); if (p) f = fopen(p, "a"); }
    return f;
}
#endif
#define FR_LOG(...) do { FILE *f_ = fr_logf(); if (f_) { fprintf(f_, __VA_ARGS__); fflush(f_); } } while (0)
static void fr_text_head(Context *c, uint32_t p, char *out, int n) {   /* printable head of a guest string */
    int i = 0; for (; i < n - 1; i++) { uint8_t b = mem_read8(c, p + i); if (!b) break; out[i] = (b == '\n') ? '|' : (b >= 32 ? b : '?'); } out[i] = 0;
}

/* when set, the C measure uses the game's own tables (used by the self test to compare against the original) */
static int fr_legacy_mode = 0;
/* set while measuring text that FrWrap already broke into lines: the Japanese automatic wrap must not fire */
static int fr_skip_wrap = 0;

static inline float fr_f(uint32_t bits) { float f; memcpy(&f, &bits, 4); return f; }
static inline uint32_t fr_bits(float f) { uint32_t b; memcpy(&b, &f, 4); return b; }

/* ------------------------------------------------------------------ glyph table */
static int fr_lookup(uint32_t code) {
    int lo = 0, hi = FR_SML_COUNT - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        uint32_t v = fr_sml_codes[mid];
        if (code == v) return mid;
        if (code < v) hi = mid - 1; else lo = mid + 1;
    }
    return -1;
}

/* advance in pixels for glyph idx at character width charW (ft_sml is authored at 16) */
static inline int fr_adv(int idx, int charW) { return (fr_sml_adv[idx] * charW + 8) / 16; }

/* ------------------------------------------------------------------ guest text helpers */
/* UTF8_iter 0x0052D79C: advances *p, returns the packed code */
static uint32_t fr_u8next(Context *c, uint32_t *p) {
    uint32_t b = mem_read8(c, *p), code = b;
    (*p)++;
    if (b > 0xBF) {
        int n;
        if (b < 0xE0) n = 2;
        else { if (b > 0xEF) return code; n = 3; }
        for (int i = 1; i < n; i++) { code = (code << 8) | mem_read8(c, *p); (*p)++; }
    }
    return code;
}

static inline uint32_t fr_rd(Context *c, uint32_t off) { return mem_read32(c, FONT_OBJ + off); }
static inline void fr_wr(Context *c, uint32_t off, uint32_t v) { mem_write32(c, FONT_OBJ + off, v); }

/* the proportional-ASCII dispatch of the engine is only reachable when this flag is set */
static void fr_init(Context *c) {
    if (fr_rd(c, FO_ASCII_FLAG) != 1) fr_wr(c, FO_ASCII_FLAG, 1);
}

/* ------------------------------------------------------------------ legacy tables (original ASCII font) */
#define LEG_DESC 0x0061BFBCu
static int fr_legacy_bs(Context *c, uint32_t code, uint32_t fallback) {
    uint32_t tbl = mem_read32(c, LEG_DESC);
    int lo = 0, hi = (int)mem_read16(c, LEG_DESC + 0x14), mid = 0;
    uint32_t v = 0;
    for (;;) {
        mid = lo + ((hi - lo) >> 1);
        v = mem_read32(c, tbl + mid * 4);
        if (code > v) lo = mid + 1;
        if (code < v) hi = mid - 1;
        if (code == v || !(lo <= hi)) break;
    }
    if (code == v) return mid;
    if (hi < lo && fallback != 0xFFFFFFFFu) return fr_legacy_bs(c, fallback, 0xFFFFFFFFu);
    return 0;
}
static int fr_legacy_adv(Context *c, uint32_t code, int charW) {
    int idx = fr_legacy_bs(c, code, 0x3F);
    uint32_t wtab = mem_read32(c, LEG_DESC + 4);
    int cellw = (int16_t)mem_read16(c, LEG_DESC + 0xC);
    if (!wtab) return charW / 2;
    return ((charW / 2) * (int)mem_read8(c, wtab + idx)) / cellw;
}

/* ------------------------------------------------------------------ measure: port of FUN_0052CEA4 (post-preprocess part)
 * Same algorithm and same outputs as the original. The only differences are the width of Latin glyphs
 * (fr_adv instead of the game's tables) when fr_legacy_mode == 0. */
static int fr_measure_core(Context *c, uint32_t font, uint32_t s, uint32_t *out_w, uint32_t *out_h,
                           uint32_t *f6, uint32_t *f7) {
    #define R(o) mem_read32(c, font + (o))
    #define W(o, v) mem_write32(c, font + (o), (v))
    int count = 0, y = 0, cur = 0, maxw = 0;
    uint32_t svW = R(FO_CHARW), svH = R(FO_CHARH);
    if (f6) *f6 = 0;
    if (f7) *f7 = 0;
    for (;;) {
        uint32_t code = fr_u8next(c, &s);
        if (code == 0) {
            if (out_w) *out_w = maxw;
            if (out_h) {
                if (cur < 1) { if (y > 0) y -= (int)R(FO_LINESP); }
                else y += (int)R(FO_CHARH);
                *out_h = y;
            }
            return count;
        }
        if (code == 10) {
            cur = 0;
            y += (int)R(FO_LINESP) + (int)R(FO_CHARH);
        } else {
            uint32_t lo8 = code & 0xFF;
            if (lo8 - 0x10 < 0x10) {
                switch (code) {
                case 0x10: {
                    uint32_t k = fr_u8next(c, &s);
                    if (k == 0x4E || k == 0x4F) cur = (int)R(FO_CHARW) << 1;
                    else cur += (int)R(FO_CHARW);
                    count++;
                    break;
                }
                case 0x11: {
                    uint32_t b1 = mem_read8(c, s + 1);
                    uint32_t pb = s + 3;
                    int n = 0;
                    int total = (int)mem_read8(c, s) + (int)b1;
                    cur = cur + ((int)R(FO_CHARW) + (int)R(FO_SPACING)) * (int)b1;
                    do {
                        uint32_t k = fr_u8next(c, &pb);
                        int nn = total;
                        if (k != 0) nn = n;
                        n = nn;
                        if (k != 0 && k != 0x11) {
                            if (k == 0x12) pb++;
                            else if (k != 0x13) n++;
                        }
                    } while (n < total);
                    s = pb;
                    fr_u8next(c, &s);
                    if (f7) *f7 = 1;
                    count += (int)b1;
                    break;
                }
                case 0x12: s += 1; break;
                case 0x14: W(FO_CHARW, svW); W(FO_CHARH, svH); break;
                case 0x15: W(FO_CHARW, 0x16); W(FO_CHARH, 0x16); if (f6) *f6 = 1; break;
                case 0x16: W(FO_CHARW, 0xC); W(FO_CHARH, 0xC); break;
                default: break;
                }
            } else {
                int fullwidth = 1;          /* goes through LAB_0052D248 */
                int adv = 0, wrapAdv = 0;
                int isFr = !fr_legacy_mode && code >= 0x20 && code <= 0x7E;
                if (isFr) {
                    int idx = fr_lookup(code), cw = (int)R(FO_CHARW);
                    adv = (idx >= 0) ? fr_adv(idx, cw) : cw / 2;
                    cur += adv;
                    fullwidth = 0;
                } else if (code < 0x100) {
                    uint32_t u6 = lo8 - 0x20;
                    int inAscii = (u6 <= 0x5D) || (lo8 - 0xA1 <= 0x31);
                    if (inAscii) {
                        fullwidth = 0;
                        int cw = (int)R(FO_CHARW);
                        if (R(FO_ASCII_FLAG) == 0) {
                            if (code != 0x20) adv = cw + (int)R(FO_SPACING);
                            else adv = (int)R(FO_SPACING) + cw / 2;
                        } else {
                            adv = fr_legacy_adv(c, code, cw);
                        }
                        cur += adv;
                    }
                }
                if (fullwidth) {
                    int idx = -1;
                    int cw = (int)R(FO_CHARW);
                    if (!fr_legacy_mode) idx = fr_lookup(code);
                    if (idx >= 0) { wrapAdv = fr_adv(idx, cw); cur += wrapAdv; }
                    else { wrapAdv = cw + (int)R(FO_SPACING); cur += wrapAdv; }
                    /* automatic wrap (Japanese rules, kept until phase 3) */
                    if (!fr_skip_wrap && (int)R(FO_WRAP) < cur + wrapAdv) {
                        uint32_t nb = mem_read8(c, s);
                        if (nb != 0x27) {
                            int test;
                            if ((int8_t)nb < '(') test = (nb != 10 && nb != 0x13) && (nb != 0x20 && nb != 0x21);
                            else test = (nb != 0x2C && nb != 0x2E) && nb != 0x3F;
                            if (test) {
                                uint32_t p = s, nc = fr_u8next(c, &p);
                                if (nc != 0xE3808Du) {
                                    int nobreak;
                                    if ((int)nc < (int)0xE3808Du) {
                                        int t = (int)(0xFF1D7F67u + nc);
                                        nobreak = (t == 0);
                                        if (!nobreak) { t -= 0xFFE8; nobreak = (t == 0); }
                                        if (!nobreak) nobreak = (t == 1);
                                    } else {
                                        nobreak = (nc - 0xE3808Du) == 2;
                                        uint32_t u3 = 0xE3808Du;
                                        if (!nobreak) { u3 = 0xFFF3C40Cu + (nc - 0xE3808Du); nobreak = (u3 == 0); }
                                        if (!nobreak) nobreak = (u3 == 0x1E);
                                    }
                                    if (!nobreak) {
                                        if (maxw < cur) maxw = cur;
                                        cur = 0;
                                        if (mem_read8(c, s) != 0) cur = (int)R(FO_SPACING) + wrapAdv;
                                        else cur = 0;
                                        y += (int)R(FO_CHARH) + (int)R(FO_LINESP);
                                    }
                                }
                            }
                        }
                    }
                }
                count++;
            }
        }
        if (maxw < cur) maxw = cur;
    }
    #undef R
    #undef W
}

/* ------------------------------------------------------------------ draw one French glyph through the engine's quad path
 * FR_EMIT expands inside a void override (CALL returns from the enclosing function on host exit).
 * result: okvar = 1 when the engine accepted the quad. */
#define FR_EMIT(c, X, Y, Z, IDX, okvar) do { \
    float x_ = (X), y_ = (Y); int idx_ = (IDX); \
    int cw_ = (int)fr_rd(c, FO_CHARW), ch_ = (int)fr_rd(c, FO_CHARH); \
    float sx_ = (float)cw_ / 16.0f, sy_ = (float)ch_ / 16.0f; \
    float x0_ = x_ + (float)fr_sml_bearing[idx_] * sx_, y0_ = y_; \
    float x1_ = x0_ + 16.0f * sx_, y1_ = y0_ + 16.0f * sy_; \
    int col_ = idx_ % FR_SML_COLS, row_ = idx_ / FR_SML_COLS; \
    float u0_ = (float)(col_ * FR_SML_CELL_W) / FR_PAGE, v0_ = (float)(row_ * FR_SML_CELL_H) / FR_PAGE; \
    float u1_ = (float)((col_ + 1) * FR_SML_CELL_W) / FR_PAGE, v1_ = (float)((row_ + 1) * FR_SML_CELL_H) / FR_PAGE; \
    FR_ENSURE_BUDGET(c); \
    uint32_t lr_ = (c)->r[14], sp_ = (c)->r[13]; \
    uint32_t q_ = (sp_ - 0x60) & ~7u; \
    uint32_t w_[13] = { fr_bits(x0_), fr_bits(y0_), fr_bits(x1_), fr_bits(y1_), (Z), fr_rd(c, FO_TEXGROUP), FR_TEX_SML, \
                        fr_bits(u0_), fr_bits(v0_), fr_bits(u1_), fr_bits(v1_), 0, 0 }; \
    for (int i_ = 0; i_ < 13; i_++) mem_write32(c, q_ + i_ * 4, w_[i_]); \
    fr_log_quad(c, w_); \
    (c)->r[13] = q_; (c)->r[0] = FONT_OBJ; (c)->r[1] = q_; (c)->r[14] = lr_; \
    ctx->r[15] = 0x0052D848u; ctx->thumb = 0; CALL(f_0052D848); \
    (okvar) = (c)->r[0] != 0; \
    (c)->r[13] = sp_; (c)->r[14] = lr_; \
} while (0)

/* optional quad capture for the self test / offline preview */
static FILE *fr_quad_log = NULL;
static void fr_log_quad(Context *c, const uint32_t *w) {
    (void)c;
    if (fr_quad_log) fprintf(fr_quad_log, "QUAD %f %f %f %f tex=%u uv=%f %f %f %f\n", fr_f(w[0]), fr_f(w[1]), fr_f(w[2]), fr_f(w[3]), w[6], fr_f(w[7]), fr_f(w[8]), fr_f(w[9]), fr_f(w[10]));
}

#endif
