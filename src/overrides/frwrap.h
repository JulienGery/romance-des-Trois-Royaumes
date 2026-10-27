/* Phase 3: French-aware line breaking on the engine's PRE-PROCESSED text buffer (output of FUN_0052C690).
 * Pure host C (no guest access) so it can be unit-tested on the whole translation corpus.
 *
 * Buffer format (verified in FUN_0052C690): UTF-8 codes; 0x0A newline; 0x10 + 1 byte = icon; 0x12 + 1 byte = colour;
 * 0x13 colour reset; 0x14/0x15/0x16/0x17 size tags (restore / 22px / 12px / ?); 0x11 = ruby (NOT handled here, callers skip).
 * Advances are the same as the draw and measure overrides use: Latin glyph = fr_adv, other = charW + spacing. */
#ifndef FRWRAP_H
#define FRWRAP_H
#include <stdint.h>
#include <string.h>
#include "font_sml.h"

#ifndef FR_TEXT_MAX
#define FR_TEXT_MAX 1024
#endif

static int frw_lookup(uint32_t code) {
    if (code == 0xE291AFu) return -1;     /* U+246F: the HOME button icon of the game's own font (our atlas only has a circled 16) */
    int lo = 0, hi = FR_SML_COUNT - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1; uint32_t v = fr_sml_codes[mid];
        if (code == v) return mid;
        if (code < v) hi = mid - 1; else lo = mid + 1;
    }
    return -1;
}
static inline int frw_adv(int idx, int cw) { return (fr_sml_adv[idx] * cw + 8) / 16; }

typedef struct { uint32_t code; int start, end, adv, cw; uint8_t nl; } frw_tok;   /* nl: a soft newline turned into a space */

static uint32_t frw_next(const uint8_t *b, int len, int *p) {
    uint32_t c = b[(*p)++];
    if (c > 0xBF) {
        int n;
        if (c < 0xE0) n = 2; else { if (c > 0xEF) return c; n = 3; }
        for (int i = 1; i < n && *p < len; i++) c = (c << 8) | b[(*p)++];
    }
    return c;
}

static int frw_is_letter(uint32_t c) {
    return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= 0xC380 && c <= 0xC3BF) || c == 0xC592 || c == 0xC593;
}
/* cannot start a line */
static int frw_no_start(uint32_t c) {
    switch (c) {
    case '!': case '?': case ':': case ';': case '%': case ')': case ']': case '}': case ',': case '.':
    case 0xC2BB: case 0xC2B0:                      /* » ° */
    case 0xE280A6: case 0xE28099:                  /* … ’ */
    case 0xE38081: case 0xE38082: case 0xE3808D: case 0xE3808F: case 0xE383BC:   /* 、 。 」 』 ー */
    case 0xEFBC81: case 0xEFBC9F: case 0xEFBC89: case 0xEFBC8C: case 0xEFBC8E: return 1;
    }
    return 0;
}
/* cannot end a line */
static int frw_no_end(uint32_t c) {
    switch (c) {
    case '(': case '[': case '{': case 0xC2AB: case 0xE3808C: case 0xE3808E: case 0xEFBC88: return 1;
    }
    return 0;
}
static int frw_is_cjk(uint32_t c) { return c >= 0x100 && frw_lookup(c) < 0; }

/* option flags of fr_wrap_text2 */
#define FRW_REFLOW      1       /* soft explicit newlines (mid-sentence) become spaces */
#define FRW_REFLOW_ALL  2       /* every explicit newline becomes a space (text fit) */
#define FRW_BALANCE     4       /* narrowest width giving the same number of lines per paragraph */

/* visible token before/after i, skipping colour/size tags (0x12 p, 0x13..0x17) */
static uint32_t frw_prev_vis(const frw_tok *t, int i) {
    for (i--; i >= 0; i--) { uint32_t c = t[i].code; if (c == 0x12 || (c >= 0x13 && c <= 0x17)) continue; return c; }
    return 0;
}
static uint32_t frw_next_vis(const frw_tok *t, int n, int i) {
    for (i++; i < n; i++) { uint32_t c = t[i].code; if (c == 0x12 || (c >= 0x13 && c <= 0x17)) continue; return c; }
    return 0;
}
/* an explicit newline the translator meant (end of sentence, list/dialogue dash...) */
static int frw_hard_break(const frw_tok *t, int n, int i) {
    uint32_t pv = frw_prev_vis(t, i), nx = frw_next_vis(t, n, i);
    if (!pv || !nx || pv == 0x0A || nx == 0x0A || pv == 0x10 || nx == 0x10) return 1;
    switch (pv) {
    case '.': case '!': case '?': case ':': case ';': case ')': case '"': case '-':
    case 0xC2BB: case 0xE280A6: case 0xE2809D: case 0xE38082: case 0xEFBC81: case 0xEFBC9F: return 1;
    }
    if (nx == '-' || nx == '"' || nx == '*' || nx == 0xC2AB || nx == 0xE28094 || nx == 0xE280A2 || nx == 0xE2809C) return 1;
    if (nx >= '0' && nx <= '9') { int j = i + 1; while (j < n && t[j].code != nx) j++; if (j + 1 < n && (t[j + 1].code == '.' || t[j + 1].code == ')')) return 1; }
    if (frw_is_cjk(pv) || frw_is_cjk(nx)) return 1;
    return 0;
}

/* greedy break of tokens [a,b) (no newline inside) at width `wrap`; fills brk/rep for that range, returns the line count */
static int frw_greedy(const frw_tok *t, const int *cum, int n, int a, int b, int wrap, uint8_t *brk, uint8_t *rep) {
    memset(brk + a, 0, b - a); memset(rep + a, 0, b - a);
    int s = a, opp = -1, oppSpace = 0, lines = 1;
    for (int i = a; i < b; i++) {
        uint32_t c = t[i].code;
        if (c == ' ') {
            uint32_t nx = (i + 1 < n) ? t[i + 1].code : 0, pv = (i > s) ? t[i - 1].code : 0;
            int valid = i > s && !frw_no_end(pv) && nx && nx != 0x0A && nx != ' ' && !frw_no_start(nx);
            if (valid && cum[i + 1] - cum[s] > wrap) { rep[i] = 1; s = i + 1; opp = -1; lines++; continue; }   /* trailing space overflows: break here */
            if (!valid || cum[i + 1] - cum[s] <= wrap) {
                if (valid) { opp = i; oppSpace = 1; }
                if (cum[i + 1] - cum[s] <= wrap) continue;
            }
            /* an unbreakable space that overflows: fall through, an earlier opportunity will be used */
        }
        while (i > s && cum[i + 1] - cum[s] > wrap) {
            if (opp >= s) {
                if (oppSpace) { rep[opp] = 1; s = opp + 1; } else { brk[opp + 1] = 1; s = opp + 1; }
                opp = -1;
            } else { brk[i] = 1; s = i; }
            lines++;
        }
        /* new break opportunities after this token */
        uint32_t nx = (i + 1 < n) ? t[i + 1].code : 0;
        if (c == '-' && i > s && frw_is_letter(t[i - 1].code) && frw_is_letter(nx)) { opp = i; oppSpace = 0; }
        else if (frw_is_cjk(c) && frw_is_cjk(nx) && !frw_no_start(nx) && !frw_no_end(c)) { opp = i; oppSpace = 0; }
    }
    return lines;
}

/* returns the new length (without NUL), -1 if the text contains ruby (caller must not use the result) */
static int fr_wrap_text2(const uint8_t *in, int inlen, uint8_t *out, int outcap, int wrap, int cw0, int spacing, int maxc, int *complete, int flags) {
    static frw_tok t[FR_TEXT_MAX]; int n = 0, p = 0, cw = cw0;
    while (p < inlen && n < FR_TEXT_MAX) {
        frw_tok *k = &t[n]; k->start = p; k->code = frw_next(in, inlen, &p); k->adv = 0; k->cw = cw; k->nl = 0;
        uint32_t c = k->code;
        if (c == 0) break;
        if (c == 0x11) return -1;
        if (c == 0x10) { uint32_t a = (p < inlen) ? in[p] : 0; p++; k->adv = (a - 0x40 == 0x4E || a - 0x40 == 0x4F) ? cw * 2 : cw; }
        else if (c == 0x12) { p++; }
        else if (c == 0x13 || c == 0x17) { }
        else if (c == 0x14) cw = cw0;
        else if (c == 0x15) cw = 22;
        else if (c == 0x16) cw = 12;
        else if (c == 0x0A) { }
        else {
            int idx = frw_lookup(c);
            if (idx >= 0) k->adv = frw_adv(idx, cw);
            else if (c < 0x100) k->adv = cw / 2;
            else k->adv = cw + spacing;
        }
        k->end = p; n++;
    }
    /* reflow: soft explicit newlines become spaces (dropped when a space is already there) */
    if (flags & (FRW_REFLOW | FRW_REFLOW_ALL)) {
        int idxsp = frw_lookup(' '), m = 0;
        for (int i = 0; i < n; i++) {
            if (t[i].code == 0x0A && i > 0 && i + 1 < n) {
                int all = (flags & FRW_REFLOW_ALL) != 0;
                if (all ? 1 : !frw_hard_break(t, n, i)) {
                    uint32_t pv = m > 0 ? t[m - 1].code : 0, nx = t[i + 1].code;
                    if (pv == ' ' || pv == 0x0A || nx == ' ' || nx == 0x0A) continue;          /* drop */
                    t[i].code = ' '; t[i].nl = 1; t[i].adv = idxsp >= 0 ? frw_adv(idxsp, t[i].cw) : t[i].cw / 2;
                }
            }
            t[m++] = t[i];
        }
        n = m;
    }
    /* cumulative widths */
    static int cum[FR_TEXT_MAX + 1]; cum[0] = 0;
    for (int i = 0; i < n; i++) cum[i + 1] = cum[i] + t[i].adv;
    /* break decisions: brk[i] = 1 -> newline inserted BEFORE token i ; rep[i] = 1 -> token i (a space) replaced by newline */
    static uint8_t brk[FR_TEXT_MAX], rep[FR_TEXT_MAX];
    memset(brk, 0, n); memset(rep, 0, n);
    for (int a = 0; a <= n;) {                          /* paragraphs: runs of tokens between hard newlines */
        int b = a; while (b < n && t[b].code != 0x0A) b++;
        if (b > a) {
            int lines = frw_greedy(t, cum, n, a, b, wrap, brk, rep);
            if ((flags & FRW_BALANCE) && lines > 1) {
                int lo = 1, hi = wrap;
                for (int i = a; i < b; i++) if (t[i].adv > lo) lo = t[i].adv;
                while (lo < hi) { int mid = (lo + hi) >> 1; if (frw_greedy(t, cum, n, a, b, mid, brk, rep) <= lines) hi = mid; else lo = mid + 1; }
                if (frw_greedy(t, cum, n, a, b, lo, brk, rep) > lines) frw_greedy(t, cum, n, a, b, wrap, brk, rep);
            }
        }
        a = b + 1;
    }
    /* rebuild; typewriter limit: stop before the first token once `maxc` counted codes are out (as FUN_0052C690 does) */
    int o = 0, counted = 0, done = 1;
    for (int i = 0; i < n; i++) {
        if (maxc >= 0 && counted >= maxc) { done = 0; break; }
        if (brk[i]) { if (o + 1 >= outcap) { done = 0; break; } out[o++] = 0x0A; }
        uint32_t c = t[i].code;
        if (rep[i]) { if (o + 1 >= outcap) { done = 0; break; } out[o++] = 0x0A; counted++; continue; }
        if (t[i].nl) { if (o + 1 >= outcap) { done = 0; break; } out[o++] = ' '; counted++; continue; }
        int L = t[i].end - t[i].start;
        if (o + L >= outcap) { done = 0; break; }
        memcpy(out + o, in + t[i].start, L); o += L;
        if (!(c == 0x10 || (c >= 0x12 && c <= 0x17))) counted++;
    }
    out[o] = 0;
    if (complete) *complete = done;
    return o;
}
/* widest line (px) of a pre-processed buffer, lines separated by 0x0A; 0 for ruby (caller must not use it) */
static int frw_max_line(const uint8_t *in, int inlen, int cw0, int spacing) {
    int p = 0, cw = cw0, lw = 0, mx = 0;
    while (p < inlen) {
        uint32_t c = frw_next(in, inlen, &p);
        if (c == 0) break;
        if (c == 0x11) return 0;
        if (c == 0x0A) { if (lw > mx) mx = lw; lw = 0; continue; }
        if (c == 0x10) { uint32_t a = (p < inlen) ? in[p] : 0; p++; lw += (a - 0x40 == 0x4E || a - 0x40 == 0x4F) ? cw * 2 : cw; continue; }
        if (c == 0x12) { p++; continue; }
        if (c == 0x13 || c == 0x17) continue;
        if (c == 0x14) { cw = cw0; continue; } if (c == 0x15) { cw = 22; continue; } if (c == 0x16) { cw = 12; continue; }
        int idx = frw_lookup(c);
        lw += idx >= 0 ? frw_adv(idx, cw) : (c < 0x100 ? cw / 2 : cw + spacing);
    }
    if (lw > mx) mx = lw;
    return mx;
}

/* default for windows and bubbles */
static int fr_wrap_text(const uint8_t *in, int inlen, uint8_t *out, int outcap, int wrap, int cw0, int spacing, int maxc, int *complete) {
    return fr_wrap_text2(in, inlen, out, outcap, wrap, cw0, spacing, maxc, complete, FRW_REFLOW | FRW_BALANCE);
}



/* ---- per-line draw of multi-line widgets (FUN_005412E0 -> FUN_0052CAF8 "GetLine" -> draw): the engine cuts the RAW text at explicit
 * newlines only, then draws every cut as its own line at y0 + i * pitch, so a paragraph that wraps (a long place name) overlaps the next
 * line. This returns line `idx` of the text wrapped by us (same wrap as the measure), in RAW form (【r】..【e】 tags): a colour open at the
 * end of a line is closed there and reopened at the start of the next one (every line is drawn on its own).
 * returns -1 when the text holds tags we do not handle (the caller then keeps the original behaviour), else 1 if a line follows, 0 if not. */
static const char frw_cols[] = "brgpBRGy";           /* colour tag letters, same order as the engine's 0x12 argument */
static int frw_put_tag(uint8_t *out, int o, int cap, uint8_t c) {      /* appends 【c】 (UTF-8), returns the new length */
    static const uint8_t tg[7] = { 0xE3, 0x80, 0x90, 0, 0xE3, 0x80, 0x91 };
    for (int i = 0; i < 7 && o < cap - 9; i++) out[o++] = i == 3 ? c : tg[i];
    return o;
}
static int fr_getline_core(const uint8_t *raw, int len, int wrap, int cw, int spacing, int idx, uint8_t *out, int outcap) {
    static uint8_t in[1100], wr[1100]; int n = 0, k;
    if (len > 1000) return -1;
    for (int i = 0; i < len;) {
        uint8_t c = raw[i];
        if (c == 0xE3 && i + 6 < len && raw[i + 1] == 0x80 && raw[i + 2] == 0x90) {       /* 【x】: only one-letter tags */
            if (raw[i + 4] != 0xE3 || raw[i + 5] != 0x80 || raw[i + 6] != 0x91) return -1;
            c = raw[i + 3]; i += 7;
            if (c == 'e') in[n++] = 0x13;
            else { for (k = 0; k < 8 && (uint8_t)frw_cols[k] != c; k++) ; if (k == 8) return -1; in[n++] = 0x12; in[n++] = (uint8_t)k; }
        } else { if (c == 0x11 || (c < 0x20 && c != '\n')) return -1; in[n++] = c; i++; }
    }
    int ol = fr_wrap_text2(in, n, wr, 1024, wrap, cw, spacing, -1, NULL, FRW_REFLOW | FRW_BALANCE);
    if (ol < 0) return -1;
    int line = 0, open = -1, p = 0, o = 0;
    for (; p < ol && line < idx; p++) {               /* skip to line idx, tracking the colour state */
        if (wr[p] == '\n') line++; else if (wr[p] == 0x12) open = wr[++p]; else if (wr[p] == 0x13) open = -1;
    }
    if (line < idx) { out[0] = 0; return 0; }
    if (open >= 0) o = frw_put_tag(out, o, outcap, frw_cols[open]);
    for (; p < ol; p++) {
        uint8_t b = wr[p];
        if (b == '\n') { if (open >= 0) o = frw_put_tag(out, o, outcap, 'e'); out[o] = 0; return 1; }
        if (b == 0x12 || b == 0x13) { open = b == 0x12 ? wr[++p] & 7 : -1; o = frw_put_tag(out, o, outcap, b == 0x12 ? frw_cols[open] : 'e'); }
        else if (o < outcap - 9) out[o++] = b;
    }
    if (open >= 0) o = frw_put_tag(out, o, outcap, 'e');
    out[o] = 0;
    return 0;
}

#endif
