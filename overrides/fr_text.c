/* Phase 2: French glyphs + proportional advance.
 *  - 0x0052DA8C  ASCII glyph    (engine reaches it for every ASCII char once font+0x1214 == 1)
 *  - 0x0052DC54  other glyph    (accents, « », … : French atlas first, original Japanese path otherwise)
 *  - 0x0052CEA4  text measure   (C port, same results as the original, Latin widths from the French table)
 *  - 0x0052D340  draw entry     (sets the ASCII flag)
 * Registers (verified in the ARM prologues): s0,s1,s2 = x,y,z (floats) ; r0 = font ; r1 = code. Return r0 = advance in px, -1 when the quad list is full. */
#include <stdlib.h>
#include "/Users/juliengery/Documents/yokai_watch_claude/overrides/frfont.h"
#include "/Users/juliengery/Documents/yokai_watch_claude/overrides/frwrap.h"

/* native ARM build: everything is compiled as Thumb (about 25 % smaller, the cavities are tiny) except the functions that use the FPU, which
 * must stay in ARM mode (ARM11 has no Thumb VFP) */
#ifdef FR_NATIVE
#define FR_ARM __attribute__((target("arm"), noinline))
#else
#define FR_ARM
#endif

/* both glyph functions do the same thing: French table first, original (Japanese) path otherwise */
static FR_ARM void fr_glyph(Context *ctx, void (*orig)(Context *)) {
    float x = fr_f(ctx->vfp[0]), y = fr_f(ctx->vfp[1]);
    uint32_t z = ctx->vfp[2], code = ctx->r[1], lr = ctx->r[14];
    int idx = fr_lookup(code);
    if (idx < 0) { orig(ctx); return; }
    int adv = fr_adv(idx, (int)fr_rd(ctx, FO_CHARW)), ok = 1;
    if (fr_sml_inkw[idx]) { FR_EMIT(ctx, x, y, z, idx, ok); }
    ctx->r[0] = ok ? (uint32_t)adv : 0xFFFFFFFFu;
    RETURN_TO(lr);
}
RECOMP_OVERRIDE(0x0052DA8C) { fr_glyph(ctx, RECOMP_ORIGINAL(0x0052DA8C)); }
RECOMP_OVERRIDE(0x0052DC54) { fr_glyph(ctx, RECOMP_ORIGINAL(0x0052DC54)); }

/* centred text drawn with NO wrap width (intro/tutorial/clock/name-entry screens: the Japanese lines were short, French lines overflow
 * their panel or the screen). FUN_0052D340 gets the centre (x,y) in s0/s1; the preprocess then wraps to what fits around that centre. */
static int fr_last_meas_w;      /* width of the last measure (widest line) */
static int fr_blk_maxw, fr_blk_left;   /* per-line panel text (FUN_002B8C30): widest line of the block, lines still to draw */
static int fr_ctr_active; static float fr_ctr_x, fr_ctr_y;
RECOMP_OVERRIDE(0x0052D340) {
    FR_ENSURE_BUDGET(ctx);
    fr_init(ctx);
    uint32_t lr = ctx->r[14], sv[3] = { fr_rd(ctx, FO_CHARW), fr_rd(ctx, FO_CHARH), fr_rd(ctx, FO_LINESP) };
    fr_ctr_x = fr_f(ctx->vfp[0]); fr_ctr_y = fr_f(ctx->vfp[1]); fr_ctr_active = 1;
    CALL(RECOMP_ORIGINAL(0x0052D340));
    fr_ctr_active = 0;
    if (fr_blk_left > 0 && --fr_blk_left == 0) fr_blk_maxw = 0;
    if (fr_rd(ctx, FO_CHARW) != sv[0] || fr_rd(ctx, FO_LINESP) != sv[2]) { fr_wr(ctx, FO_CHARW, sv[0]); fr_wr(ctx, FO_CHARH, sv[1]); fr_wr(ctx, FO_LINESP, sv[2]); }
    ctx->r[14] = lr;
}

/* ---- phase 3: French line breaking ------------------------------------------------------------
 * FUN_0052C690 builds the internal text buffer for both the measure and the draw. We break lines there, once, so that
 * measure, draw and the typewriter see the same text. The engine's own wrap (Japanese rules) is then bypassed. */
/* ---- phase 4: bubbles */
#define FR_BUBBLE_W 252u            /* text width of a speech bubble (px) */
static int fr_is_bubble_site(uint32_t lr) {   /* return addresses after the `bl FUN_0052CEA4` of the bubble code */
    static const uint32_t sites[] = { 0x23634C, 0x23652C, 0x23795C, 0x2DEB78, 0x2DFBBC, 0x2DFCB4 };
    for (unsigned i = 0; i < sizeof(sites) / sizeof(sites[0]); i++) if (lr == sites[i] + 4) return 1;
    return 0;
}
static int fr_cb_textw;         /* text width measured by the combat bubble code (see 0x00222FE8 below) */
static int fr_prewrapped;       /* the buffer built by the last preprocess was wrapped by us */
int fr_wrap_disabled;           /* test switch (shared with diag_font.c) */

/* wraps the NUL-terminated buffer at guest address buf in place. returns 1 when done, 0 when the text has ruby
 * (left untouched, original behaviour). *complete = typewriter "everything shown" result */
static int fr_wrap_guest(Context *c, uint32_t buf, int maxc, int *complete) {
    static uint8_t in[1100], out[1100];
    int len = 0;
    while (len < 1030) { uint8_t b = mem_read8(c, buf + len); if (!b) break; if (b == 0x11) return 0; in[len++] = b; }
    int ol = fr_wrap_text(in, len, out, 1024, (int)fr_rd(c, FO_WRAP), (int)fr_rd(c, FO_CHARW), (int)fr_rd(c, FO_SPACING), maxc, complete);
    if (ol < 0) return 0;
    for (int i = 0; i <= ol; i++) mem_write8(c, buf + i, out[i]);
    return 1;
}

/* ---- text fit: fixed-box windows (no layout function sizes them, e.g. Whisper's bottom dialogue box 2,166,396,72).
 * 0x005412E0 sets fr_fit_h (text height available in the box) around the draw; the preprocess then picks the first layout that fits:
 * normal wrap, full reflow, tighter line spacing, then 14 and 12 px. Deterministic: same input -> same output every frame. */
static int fr_fit_h;                                  /* >0 while a fixed-box widget draws */
static int fr_fit_base_valid, fr_fit_base_cw, fr_fit_base_lsp, fr_fit_ap_cw, fr_fit_ap_lsp;   /* font params before / after our change */
static uint32_t fr_managed[64]; static int fr_managed_n;   /* widgets sized by a layout function or bubble init: never fitted */
static void fr_mark_managed(uint32_t wd) { for (int i = 0; i < 64; i++) if (fr_managed[i] == wd) return; fr_managed[fr_managed_n++ & 63] = wd; }
static int fr_is_managed(uint32_t wd) { for (int i = 0; i < 64; i++) if (fr_managed[i] == wd) return 1; return 0; }

static int fr_count_lines(const uint8_t *b, int len) { int n = 1; for (int i = 0; i < len; i++) if (b[i] == '\n') n++; return n; }

static int fr_fit_guest(Context *c, uint32_t buf, int maxc, int *complete) {
    static uint8_t in[1100], out[1100], best[1100];
    int len = 0;
    while (len < 1030) { uint8_t b = mem_read8(c, buf + len); if (!b) break; if (b == 0x11) return 0; in[len++] = b; }
    int cw = (int)fr_rd(c, FO_CHARW), lsp = (int)fr_rd(c, FO_LINESP);
    if (fr_fit_base_valid && cw == fr_fit_ap_cw && lsp == fr_fit_ap_lsp) { cw = fr_fit_base_cw; lsp = fr_fit_base_lsp; }   /* second preprocess of the same draw */
    int wrap = (int)fr_rd(c, FO_WRAP), spacing = (int)fr_rd(c, FO_SPACING);
    struct { int size, lsp, flags; } cand[12]; int nc = 0;
    int tight = lsp < 2 ? lsp : 2;
    cand[nc].size = cw; cand[nc].lsp = lsp;   cand[nc++].flags = FRW_REFLOW | FRW_BALANCE;
    cand[nc].size = cw; cand[nc].lsp = lsp;   cand[nc++].flags = FRW_REFLOW_ALL | FRW_BALANCE;
    cand[nc].size = cw; cand[nc].lsp = tight; cand[nc++].flags = FRW_REFLOW_ALL | FRW_BALANCE;
    static const int small[2] = { 14, 12 };
    for (int k = 0; k < 2; k++) if (small[k] < cw) {
        cand[nc].size = small[k]; cand[nc].lsp = tight; cand[nc++].flags = FRW_REFLOW | FRW_BALANCE;
        cand[nc].size = small[k]; cand[nc].lsp = tight; cand[nc++].flags = FRW_REFLOW_ALL | FRW_BALANCE;
    }
    int pick = nc - 1;
    for (int k = 0; k < nc; k++) {
        int ol = fr_wrap_text2(in, len, out, 1024, wrap, cand[k].size, spacing, -1, NULL, cand[k].flags);
        if (ol < 0) return 0;
        int n = fr_count_lines(out, ol), h = n * cand[k].size + (n - 1) * cand[k].lsp;
        if (n == 1 || h <= fr_fit_h) { pick = k; break; }
    }
    int ol = fr_wrap_text2(in, len, best, 1024, wrap, cand[pick].size, spacing, maxc, complete, cand[pick].flags);
    if (ol < 0) return 0;
    for (int i = 0; i <= ol; i++) mem_write8(c, buf + i, best[i]);
    if (cand[pick].size != cw || cand[pick].lsp != lsp) {
        fr_fit_base_valid = 1; fr_fit_base_cw = cw; fr_fit_base_lsp = lsp; fr_fit_ap_cw = cand[pick].size; fr_fit_ap_lsp = cand[pick].lsp;
        fr_wr(c, FO_CHARW, cand[pick].size); fr_wr(c, FO_CHARH, cand[pick].size); fr_wr(c, FO_LINESP, cand[pick].lsp);
    }
    if (pick) FR_LOG("FIT step=%d size=%d lsp=%d flags=%d inner=%d lines=%d\n", pick + 1, cand[pick].size, cand[pick].lsp, cand[pick].flags, fr_fit_h, fr_count_lines(best, ol));
    return 1;
}

#define FR_CTR_MAXW 284
static FR_ARM int fr_center_guest(Context *c, uint32_t buf, int maxc, int *complete) {   /* 1 = rewrapped, 0 = nothing to do */
    static uint8_t in[1100], out[1100];
    int len = 0;
    while (len < 1030) { uint8_t b = mem_read8(c, buf + len); if (!b) break; if (b == 0x11) return 0; in[len++] = b; }
    int cw = (int)fr_rd(c, FO_CHARW), lsp = (int)fr_rd(c, FO_LINESP), sp = (int)fr_rd(c, FO_SPACING);
    float hx = fr_ctr_x < 400 - fr_ctr_x ? fr_ctr_x : 400 - fr_ctr_x, hy = fr_ctr_y < 240 - fr_ctr_y ? fr_ctr_y : 240 - fr_ctr_y;
    int W = (int)(2 * hx) - 12; if (W > FR_CTR_MAXW) W = FR_CTR_MAXW; if (W < 120) return 0;
    int availH = (int)(2 * hy) - 8;
    int mx = frw_max_line(in, len, cw, sp);
    if (mx <= W) return 0;
    if (fr_count_lines(in, len) == 1) {         /* a one-line label/banner: no room for a second line, shrink it instead (down to 11 px) */
        int sz = cw * W / mx;
        if (sz >= 11) { if (sz < cw) { fr_wr(c, FO_CHARW, sz); fr_wr(c, FO_CHARH, sz); FR_LOG("LABELFIT centre=%.0f W=%d widest=%d size %d->%d\n", fr_ctr_x, W, mx, cw, sz); } return 0; }
    }
    static const int sizes[3] = { 0, 14, 12 };
    int pick = -1, psz = cw, plsp = lsp;
    for (int k = 0; k < 3; k++) {
        int sz = k == 0 ? cw : sizes[k]; if (k && sz >= cw) continue;
        int ls = k == 0 ? lsp : (lsp < 2 ? lsp : (lsp * sz / cw > 2 ? lsp * sz / cw : 2));
        int ol = fr_wrap_text2(in, len, out, 1024, W, sz, sp, -1, NULL, FRW_REFLOW | FRW_BALANCE);
        if (ol < 0) return 0;
        int n = fr_count_lines(out, ol), h = n * sz + (n - 1) * ls;
        pick = k; psz = sz; plsp = ls;
        if (h <= availH) break;
    }
    if (pick < 0) return 0;
    int ol = fr_wrap_text2(in, len, out, 1024, W, psz, sp, maxc, complete, FRW_REFLOW | FRW_BALANCE);
    if (ol < 0) return 0;
    for (int i = 0; i <= ol; i++) mem_write8(c, buf + i, out[i]);
    if (psz != cw || plsp != lsp) { fr_wr(c, FO_CHARW, psz); fr_wr(c, FO_CHARH, psz); fr_wr(c, FO_LINESP, plsp); }
    FR_LOG("CENTERFIT centre=(%.0f,%.0f) W=%d size=%d lsp=%d lines=%d\n", fr_ctr_x, fr_ctr_y, W, psz, plsp, fr_count_lines(out, ol));
    return 1;
}

/* one line of a panel text: shrink uniformly so the widest line fits around the centre */
static FR_ARM void fr_panel_shrink(Context *ctx) {
    float hx = fr_ctr_x < 400 - fr_ctr_x ? fr_ctr_x : 400 - fr_ctr_x; int W = (int)(2 * hx) - 12; if (W > 380) W = 380;
    int cw = (int)fr_rd(ctx, FO_CHARW);
    if (W >= 120 && fr_blk_maxw > W) { int sz = cw * W / fr_blk_maxw; if (sz < 11) sz = 11;
        if (sz < cw) { fr_wr(ctx, FO_CHARW, sz); fr_wr(ctx, FO_CHARH, sz); FR_LOG("PANELFIT centre=%.0f W=%d widest=%d size %d->%d\n", fr_ctr_x, W, fr_blk_maxw, cw, sz); } }
}

RECOMP_OVERRIDE(0x0052C690) {
    FR_ENSURE_BUDGET(ctx);                 /* r0 font, r1 out buffer, r2 text, r3 max counted codes (-1 = all) */
    uint32_t lr = ctx->r[14], font = ctx->r[0], buf = ctx->r[1], str = ctx->r[2], maxc = ctx->r[3];
    fr_prewrapped = 0;
    if (getenv("FR_TRACE")) fprintf(stderr, "[fr] preprocess wrap=%d maxc=%d dis=%d\n", (int)fr_rd(ctx, FO_WRAP), (int)maxc, fr_wrap_disabled);
    if (!fr_wrap_disabled && font == FONT_OBJ && (int)fr_rd(ctx, FO_WRAP) >= 0x7FFFFFFF && fr_ctr_active && !fr_fit_h && fr_rd(ctx, FO_ALIGN) == 2 && !getenv("FR_NOCTR")) {
        ctx->r[3] = 0xFFFFFFFFu; CALL(RECOMP_ORIGINAL(0x0052C690));
        int complete = 1;
        if (fr_blk_left > 0 && fr_blk_maxw > 0) {            /* one line of a panel text: shrink uniformly so the widest line fits around the centre */
            fr_panel_shrink(ctx);
        } else
        if (fr_center_guest(ctx, buf, (int)maxc, &complete)) { fr_prewrapped = 1; ctx->r[0] = complete ? 1 : 0; ctx->r[14] = lr; RETURN_TO(lr); }
        ctx->r[0] = font; ctx->r[1] = buf; ctx->r[2] = str; ctx->r[3] = maxc; ctx->r[14] = lr; CALL(RECOMP_ORIGINAL(0x0052C690)); return;
    }
    if (fr_wrap_disabled || font != FONT_OBJ || (int)fr_rd(ctx, FO_WRAP) >= 0x7FFFFFFF) { CALL(RECOMP_ORIGINAL(0x0052C690)); return; }
    ctx->r[3] = 0xFFFFFFFFu;                  /* wrap the whole text first, then apply the typewriter limit */
    CALL(RECOMP_ORIGINAL(0x0052C690));
    int complete = 1;
    if (fr_fit_h > 0 ? fr_fit_guest(ctx, buf, (int)maxc, &complete) : fr_wrap_guest(ctx, buf, (int)maxc, &complete)) {
        fr_prewrapped = 1;
        ctx->r[0] = complete ? 1 : 0; ctx->r[14] = lr;
        RETURN_TO(lr);
    }
    ctx->r[0] = font; ctx->r[1] = buf; ctx->r[2] = str; ctx->r[3] = maxc; ctx->r[14] = lr;   /* ruby: original behaviour */
    CALL(RECOMP_ORIGINAL(0x0052C690));
}

/* the draw loop: its own wrap check (Japanese rules, fires for accented glyphs) is disabled for text we wrapped,
 * except in right-aligned mode where the engine needs +0x1238 to place the line. */
RECOMP_OVERRIDE(0x0052DEBC) {
    FR_ENSURE_BUDGET(ctx);
    uint32_t wrap = fr_rd(ctx, FO_WRAP);
    int sw = fr_prewrapped && fr_rd(ctx, FO_ALIGN) != 1 && wrap != 0x7FFFFFFFu;
    if (sw) fr_wr(ctx, FO_WRAP, 0x7FFFFFFFu);
    if (fr_logf()) { char h_[64]; fr_text_head(ctx, ctx->r[1], h_, 64); FR_LOG("DRAWFMT align=%u wrap=%d sw=%d prewrapped=%d cw=%u lsp=%u xyz=(%.0f,%.0f,%.0f) '%s'\n", fr_rd(ctx, FO_ALIGN), (int)wrap, sw, fr_prewrapped, fr_rd(ctx, FO_CHARW), fr_rd(ctx, FO_LINESP), fr_f(ctx->vfp[0]), fr_f(ctx->vfp[1]), fr_f(ctx->vfp[2]), h_); }
    if (fr_logf()) {            /* call-stack scan, once per distinct text: identifies the game function that draws it */
        char h_[48]; fr_text_head(ctx, ctx->r[1], h_, 48);
        uint32_t hk = 5381; for (char *q = h_; *q; q++) hk = hk * 33 + (uint8_t)*q;
        static uint32_t seen[128]; static int ns; int dup = 0; for (int i = 0; i < 128; i++) if (seen[i] == hk) dup = 1;
        if (!dup) { seen[ns++ & 127] = hk; char b_[900]; int o = 0; uint32_t sp = ctx->r[13];
            for (int i = 0; i < 300 && o < 850; i++) { uint32_t v = mem_read32(ctx, sp + i * 4); if (v >= 0x100000 && v < 0x560000) o += snprintf(b_ + o, sizeof b_ - o, " %X", v); }
            b_[o] = 0; FR_LOG("STACK '%s' lr=%X:%s\n", h_, ctx->r[14], b_); }
    }
    CALL(RECOMP_ORIGINAL(0x0052DEBC));
    if (sw) fr_wr(ctx, FO_WRAP, wrap);
    fr_prewrapped = 0;
}

RECOMP_OVERRIDE(0x0052CEA4) {
    FR_ENSURE_BUDGET(ctx);
    if (getenv("FR_NOMEASURE")) { CALL(RECOMP_ORIGINAL(0x0052CEA4)); return; }
    uint32_t lr = ctx->r[14], sp = ctx->r[13];
    uint32_t font = ctx->r[0], str = ctx->r[1], p3 = ctx->r[2], p4 = ctx->r[3];
    uint32_t p5 = mem_read32(ctx, sp), p6 = mem_read32(ctx, sp + 4), p7 = mem_read32(ctx, sp + 8);
    int saved = fr_prewrapped;
    if (getenv("FR_TRACE")) { fprintf(stderr, "[fr]  stack:"); for (int i = 0; i < 24; i++) fprintf(stderr, " %08X", mem_read32(ctx, sp + i * 4)); fprintf(stderr, "\n"); }
    if (getenv("FR_TRACE")) { char t[48] = {0}; for (int i = 0; i < 40; i++) { uint8_t c = mem_read8(ctx, str + i); if (!c) break; t[i] = c >= 32 && c < 127 ? c : '?'; } fprintf(stderr, "[fr] measure sp=%08X lr=%08X str=%08X p5=%u '%s'\n", sp, lr, str, p5, t); }
    fr_init(ctx);
    /* speech bubbles (FUN_00236170, FUN_00237858, FUN_002DEA30, FUN_002DFAD8) measure their text with no wrap width at all:
     * the Japanese strings carried explicit line breaks. Give those call sites a bubble width. */
    uint32_t bubble_wrap_saved = fr_rd(ctx, FO_WRAP); int bubble = 0;
    if (p5 && bubble_wrap_saved == 0x7FFFFFFFu && fr_is_bubble_site(lr)) { bubble = 1; fr_wr(ctx, FO_WRAP, FR_BUBBLE_W); }
    if (p5) {                                   /* the engine's own tag/ruby preprocessing into a 1 KiB buffer */
        uint32_t buf = (sp - 0x440) & ~7u;
        ctx->r[13] = buf; ctx->r[0] = font; ctx->r[1] = buf; ctx->r[2] = str; ctx->r[3] = 0xFFFFFFFFu; ctx->r[14] = lr;
        ctx->r[15] = 0x0052C690u; ctx->thumb = 0; CALL(f_0052C690);
        ctx->r[13] = sp;
        str = buf;
        if (getenv("FR_TRACE")) fprintf(stderr, "[fr]  preprocessed ok buf=%08X\n", buf);
        fr_prewrapped = (!fr_wrap_disabled && !getenv("FR_NOWRAP") && (int)fr_rd(ctx, FO_WRAP) < 0x7FFFFFFF && font == FONT_OBJ) ? fr_wrap_guest(ctx, buf, -1, NULL) : 0;
    }
    if (getenv("FR_TRACE")) fprintf(stderr, "[fr]  wrapped=%d\n", fr_prewrapped);
    fr_skip_wrap = fr_prewrapped;
    uint32_t w = 0, h = 0, f6 = 0, f7 = 0;
    int n = fr_measure_core(ctx, font, str, &w, &h, &f6, &f7);
    fr_skip_wrap = 0;
    if (bubble) fr_wr(ctx, FO_WRAP, bubble_wrap_saved);
    if (p5) fr_prewrapped = saved;
    fr_last_meas_w = (int)w;
    if (lr > 0x005514F4u && lr < 0x00551870u) fr_cb_textw = (int)w;      /* combat bubble text (FUN_005514F4) */
    if (p3) mem_write32(ctx, p3, w);
    if (p4) mem_write32(ctx, p4, h);
    if (p6) mem_write32(ctx, p6, f6);
    if (p7) mem_write32(ctx, p7, f7);
    if (!p5) FR_LOG("MEASURE(p5=0, inside draw) n=%d w=%u h=%u cw=%u skipwrap=%d\n", n, w, h, fr_rd(ctx, FO_CHARW), fr_skip_wrap);
    if (getenv("FR_TRACE")) fprintf(stderr, "[fr] measure done n=%d w=%u h=%u p3=%08X p4=%08X lr=%08X sp=%08X\n", n, w, h, p3, p4, lr, sp);
    ctx->r[0] = (uint32_t)n; ctx->r[13] = sp; ctx->r[14] = lr;
    RETURN_TO(lr);
}

/* ======================================================================================================
 * Phase 4: message windows.
 * The game's 8 window layout functions pick the box (y, height) from the number of lines with fixed tables; beyond ~7 lines
 * the box leaves the 240 px screen (or the text leaves its box). We let the original run, then check the result and, only when
 * it does not fit, re-measure with a smaller character size (16 -> 14 -> 12) and a wrap width that fits the box, keep the
 * original paddings, re-centre the box vertically and clamp it to the screen.
 * Widget fields (verified on the layout functions): +0x24 x, +0x28 y, +0x2C w, +0x30 h, +0x254/+0x258 text x/y (box relative),
 * +0x260/+0x264 char w/h, +0x268 float line spacing, +0x26C/+0x270 measured w/h, +0x274 align.
 * The draw method (FUN_005412E0) reads these fields every frame, so changing them here changes what is drawn. */
#define FR_SCREEN_H 240
#define FR_TOL 1

static void fr_measure_via_override(Context *ctx, uint32_t txt, uint32_t *w, uint32_t *h) {
    uint32_t sr[4] = { ctx->r[0], ctx->r[1], ctx->r[2], ctx->r[3] }, sp = ctx->r[13], lr = ctx->r[14];
    uint32_t nsp = (sp - 0x200) & ~7u;
    mem_write32(ctx, nsp, 1); mem_write32(ctx, nsp + 4, 0); mem_write32(ctx, nsp + 8, 0);
    mem_write32(ctx, nsp + 0x20, 0); mem_write32(ctx, nsp + 0x24, 0);
    ctx->r[13] = nsp; ctx->r[0] = FONT_OBJ; ctx->r[1] = txt; ctx->r[2] = nsp + 0x20; ctx->r[3] = nsp + 0x24; ctx->r[14] = lr;
    override_0x0052CEA4(ctx);
    *w = mem_read32(ctx, nsp + 0x20); *h = mem_read32(ctx, nsp + 0x24);
    ctx->r[13] = sp; ctx->r[14] = lr; ctx->r[0] = sr[0]; ctx->r[1] = sr[1]; ctx->r[2] = sr[2]; ctx->r[3] = sr[3];
}

/* returns 1 when the widget geometry was changed */
static FR_ARM int fr_fix_message_box(Context *ctx, uint32_t fn, uint32_t wd, uint32_t txt, int fixed_h) {
    #define WF(o) ((int)mem_read32(ctx, wd + (o)))
    int bx = WF(0x24), by = WF(0x28), bw = WF(0x2C), bh = WF(0x30), tx = WF(0x254), ty = WF(0x258);
    int mw = WF(0x26C), mh = WF(0x270), cw = WF(0x260);
    float lsp = fr_f(mem_read32(ctx, wd + 0x268));
    (void)bx;
    { char h_[64]; fr_text_head(ctx, txt, h_, 64);
      FR_LOG("LAYOUT fn=%08X wd=%08X mode=%d type=%d box=(%d,%d,%d,%d) text@(%d,%d) meas=(%d,%d) cw=%d lsp=%.1f fixed=%d '%s'\n", fn, wd, WF(0x48), WF(0x2A4), bx, by, bw, bh, tx, ty, mw, mh, cw, lsp, fixed_h, h_); }
    int fits = by >= 0 && by + bh <= FR_SCREEN_H + FR_TOL && ty + mh <= bh && tx >= 0 && tx + mw <= bw;
    if (getenv("FR_TRACE")) fprintf(stderr, "[fr] fixbox by=%d bh=%d ty=%d mh=%d tx=%d mw=%d bw=%d fits=%d txt=%08X\n", by, bh, ty, mh, tx, mw, bw, fits, txt);
    if (fits || !txt) return 0;
    int bpad = bh - ty - mh; if (bpad < 6) bpad = 6; if (bpad > 12 && fixed_h) bpad = 12; if (bpad > 40) bpad = 40;
    int wrapW = bw - 16; if (wrapW > 301) wrapW = 301;
    uint32_t saved[6] = { fr_rd(ctx, FO_CHARW), fr_rd(ctx, FO_CHARH), fr_rd(ctx, FO_LINESP), fr_rd(ctx, FO_WRAP), fr_rd(ctx, FO_ALIGN), fr_rd(ctx, FO_SPACING) };
    static const int sizes[3] = { 16, 14, 12 };
    int best = -1, nbh = bh, nby = by, ntx = tx, nmw = mw, nmh = mh, nlsp = (int)lsp, ncw = cw;
    for (int k = 0; k < 3; k++) {
        int s = sizes[k], ls = (int)(lsp * s / 16.0f + 0.5f);
        fr_wr(ctx, FO_CHARW, s); fr_wr(ctx, FO_CHARH, s); fr_wr(ctx, FO_LINESP, ls); fr_wr(ctx, FO_WRAP, wrapW);
        fr_wr(ctx, FO_ALIGN, mem_read32(ctx, wd + 0x274));
        uint32_t w2, h2; fr_measure_via_override(ctx, txt, &w2, &h2);
        int hn = ty + (int)h2 + bpad; if (fixed_h && hn < bh) hn = bh;
        int yn = by + bh / 2 - hn / 2;
        int tn = tx + (mw - (int)w2) / 2; if (tn < 0) tn = 0;
        if (yn + hn > FR_SCREEN_H) yn = FR_SCREEN_H - hn;
        if (yn < 0) yn = 0;
        best = k; nbh = hn; nby = yn; ntx = tn; nmw = (int)w2; nmh = (int)h2; nlsp = ls; ncw = s;
        if (yn >= 0 && yn + hn <= FR_SCREEN_H + FR_TOL && ty + (int)h2 <= hn && tn + (int)w2 <= bw) break;
    }
    fr_wr(ctx, FO_CHARW, saved[0]); fr_wr(ctx, FO_CHARH, saved[1]); fr_wr(ctx, FO_LINESP, saved[2]);
    fr_wr(ctx, FO_WRAP, saved[3]); fr_wr(ctx, FO_ALIGN, saved[4]); fr_wr(ctx, FO_SPACING, saved[5]);
    if (best < 0) return 0;
    FR_LOG("LAYOUT-FIX fn=%08X size=%d box.y %d->%d box.h %d->%d meas=(%d,%d) tx %d->%d\n", fn, ncw, by, nby, bh, nbh, nmw, nmh, tx, ntx);
    mem_write32(ctx, wd + 0x260, ncw); mem_write32(ctx, wd + 0x264, ncw); mem_write32(ctx, wd + 0x268, fr_bits((float)nlsp));
    mem_write32(ctx, wd + 0x26C, nmw); mem_write32(ctx, wd + 0x270, nmh);
    mem_write32(ctx, wd + 0x28, nby); mem_write32(ctx, wd + 0x30, nbh); mem_write32(ctx, wd + 0x254, ntx);
    return 1;
    #undef WF
}

/* one override per layout function (the override scanner needs the literal address in RECOMP_OVERRIDE(...)) */
static void fr_box_epilogue(Context *ctx, uint32_t fn, uint32_t wd, uint32_t txt, int fixed, int recalc, int *recalc_now) {
    fr_mark_managed(wd);
    *recalc_now = fr_fix_message_box(ctx, fn, wd, txt, fixed) && recalc;
}
/* shared body of the seven window layout wrappers (one copy of the code: the ARM cavities are small) */
static void fr_box_wrap(Context *ctx, uint32_t fn, void (*orig)(Context *), int fixed, int recalc) {
    FR_ENSURE_BUDGET(ctx);
    uint32_t wd = ctx->r[0], txt = ctx->r[1], lr = ctx->r[14]; int rc;
    orig(ctx);
    ctx->r[14] = lr;
    fr_box_epilogue(ctx, fn, wd, txt, fixed, recalc, &rc);
    if (rc) { ctx->r[0] = wd; ctx->r[14] = lr; ctx->r[15] = 0x0014C094u; ctx->thumb = 0; CALL(f_0014C094); }
    ctx->r[0] = wd; ctx->r[14] = lr;
}
RECOMP_OVERRIDE(0x00533D70) { fr_box_wrap(ctx, 0x00533D70u, RECOMP_ORIGINAL(0x00533D70), 0, 0); }
RECOMP_OVERRIDE(0x005586CC) { fr_box_wrap(ctx, 0x005586CCu, RECOMP_ORIGINAL(0x005586CC), 0, 1); }
RECOMP_OVERRIDE(0x0055833C) { fr_box_wrap(ctx, 0x0055833Cu, RECOMP_ORIGINAL(0x0055833C), 0, 0); }
RECOMP_OVERRIDE(0x00265900) { fr_box_wrap(ctx, 0x00265900u, RECOMP_ORIGINAL(0x00265900), 1, 1); }
RECOMP_OVERRIDE(0x00272E60) { fr_box_wrap(ctx, 0x00272E60u, RECOMP_ORIGINAL(0x00272E60), 0, 1); }
RECOMP_OVERRIDE(0x002C7F7C) { fr_box_wrap(ctx, 0x002C7F7Cu, RECOMP_ORIGINAL(0x002C7F7C), 1, 0); }
RECOMP_OVERRIDE(0x00353308) { fr_box_wrap(ctx, 0x00353308u, RECOMP_ORIGINAL(0x00353308), 0, 0); }

/* the bubble widget initialiser sets its text-block width (+0x26C, used as the draw wrap width by FUN_005412E0) to 320:
 * make it the same width the measure used, so measure and draw break the lines identically. */
RECOMP_OVERRIDE(0x002DFA54) {
    FR_ENSURE_BUDGET(ctx);
    uint32_t wd = ctx->r[0], lr = ctx->r[14];
    CALL(RECOMP_ORIGINAL(0x002DFA54));
    mem_write32(ctx, wd + 0x26C, FR_BUBBLE_W);
    fr_mark_managed(wd);
    ctx->r[14] = lr;
}

/* Combat speech bubbles are drawn by FUN_005514F4 (found with the STACK log): it measures the text (size 12, FUN_0052CEA4, p5=1),
 * sets the frame width to clamp(max(textW + 32, texture width), 160) and draws the 3-slice frame with FUN_00222FE8(x0,y0,x1,y1,...)
 * (s0 = x0, s2 = x1; the text is then centred on the frame centre). The 160 px cap is an immediate of the ARM code, so French lines
 * (e.g. 194 px) spill out. We remember the width measured at that call site, then widen the frame symmetrically (centre kept, so the
 * text stays centred) when it is drawn from FUN_005514F4. */
#define FR_CB_FN_LO 0x005514F4u
#define FR_CB_FN_HI 0x00551870u
#define FR_CB_MARGIN 32
#define FR_CB_MAXW   340
FR_ARM RECOMP_OVERRIDE(0x00222FE8) {
    uint32_t lr = ctx->r[14];
    if (lr >= FR_CB_FN_LO && lr < FR_CB_FN_HI && fr_cb_textw > 0 && !getenv("FR_NOCB")) {
        float x0 = fr_f(ctx->vfp[0]), x1 = fr_f(ctx->vfp[2]), cur = x1 - x0, want = (float)(fr_cb_textw + FR_CB_MARGIN);
        if (want > FR_CB_MAXW) want = FR_CB_MAXW;
        if (want > cur) {
            float d = (want - cur) / 2;
            if (x0 - d < 0) d = x0 > 0 ? x0 : 0;                       /* stay inside the 400 px wide top screen */
            if (x1 + d > 400) d = 400 - x1 > 0 ? 400 - x1 : 0;
            ctx->vfp[0] = fr_bits(x0 - d); ctx->vfp[2] = fr_bits(x1 + d);
            FR_LOG("COMBATBUBBLE textw=%d frame x %.1f..%.1f (w %.1f) -> %.1f..%.1f\n", fr_cb_textw, x0, x1, cur, x0 - d, x1 + d);
        }
    }
    CALL(RECOMP_ORIGINAL(0x00222FE8));
}
RECOMP_OVERRIDE(0x002DEA30) { CALL(RECOMP_ORIGINAL(0x002DEA30)); }
RECOMP_OVERRIDE(0x002DFAD8) { CALL(RECOMP_ORIGINAL(0x002DFAD8)); }

/* pass-through overrides: reserved so the next phases can be edited with fr_patch/fast_build.sh (no full rebuild) */
RECOMP_OVERRIDE(0x002373E0) { CALL(RECOMP_ORIGINAL(0x002373E0)); }
RECOMP_OVERRIDE(0x002372A4) { CALL(RECOMP_ORIGINAL(0x002372A4)); }
RECOMP_OVERRIDE(0x00541794) { CALL(RECOMP_ORIGINAL(0x00541794)); }
RECOMP_OVERRIDE(0x002DE710) { CALL(RECOMP_ORIGINAL(0x002DE710)); }
RECOMP_OVERRIDE(0x00236170) { CALL(RECOMP_ORIGINAL(0x00236170)); }
RECOMP_OVERRIDE(0x00237858) { CALL(RECOMP_ORIGINAL(0x00237858)); }
RECOMP_OVERRIDE(0x00542430) { CALL(RECOMP_ORIGINAL(0x00542430)); }
RECOMP_OVERRIDE(0x005412E0) {              /* text widget draw, runs every frame: log only when the widget/text changes */
    if (fr_logf()) {
        uint32_t wd = ctx->r[0]; char h_[64]; fr_text_head(ctx, wd + 0x54, h_, 64);
        uint32_t key = wd ^ (mem_read32(ctx, wd + 0x54) * 2654435761u) ^ (mem_read32(ctx, wd + 0x27C) << 3);
        static uint32_t last[8]; static int ln; int seen = 0;
        for (int i = 0; i < 8; i++) if (last[i] == key) seen = 1;
        if (!seen) { last[ln++ & 7] = key;
            FR_LOG("WIDGETDRAW wd=%08X box=(%d,%d,%d,%d) text@(%d,%d) meas=(%d,%d) cw=%d ch=%d lsp=%.1f align=%d multi=%d chars=%d '%s'\n", wd,
                   (int)mem_read32(ctx, wd + 0x24), (int)mem_read32(ctx, wd + 0x28), (int)mem_read32(ctx, wd + 0x2C), (int)mem_read32(ctx, wd + 0x30),
                   (int)mem_read32(ctx, wd + 0x254), (int)mem_read32(ctx, wd + 0x258), (int)mem_read32(ctx, wd + 0x26C), (int)mem_read32(ctx, wd + 0x270),
                   (int)mem_read32(ctx, wd + 0x260), (int)mem_read32(ctx, wd + 0x264), fr_f(mem_read32(ctx, wd + 0x268)), (int)mem_read32(ctx, wd + 0x274),
                   (int)mem_read32(ctx, wd + 0x278), (int)mem_read32(ctx, wd + 0x27C), h_); }
    }
    FR_ENSURE_BUDGET(ctx);
    uint32_t wd = ctx->r[0], lr = ctx->r[14];
    int bh = (int)mem_read32(ctx, wd + 0x30), ty = (int)mem_read32(ctx, wd + 0x258), inner = bh - ty - 6;
    fr_fit_h = (!fr_managed_n || !fr_is_managed(wd)) && bh > 0 && bh <= FR_SCREEN_H && inner >= 24 && !getenv("FR_NOFIT") ? inner : 0;
    fr_fit_base_valid = 0;
    uint32_t sv[3] = { fr_rd(ctx, FO_CHARW), fr_rd(ctx, FO_CHARH), fr_rd(ctx, FO_LINESP) };
    CALL(RECOMP_ORIGINAL(0x005412E0));
    if (fr_fit_base_valid) { fr_wr(ctx, FO_CHARW, sv[0]); fr_wr(ctx, FO_CHARH, sv[1]); fr_wr(ctx, FO_LINESP, sv[2]); }
    fr_fit_h = 0; fr_fit_base_valid = 0;
    ctx->r[14] = lr;
}
RECOMP_OVERRIDE(0x00541710) { CALL(RECOMP_ORIGINAL(0x00541710)); }
RECOMP_OVERRIDE(0x0021B87C) { CALL(RECOMP_ORIGINAL(0x0021B87C)); }
RECOMP_OVERRIDE(0x0052D44C) { CALL(RECOMP_ORIGINAL(0x0052D44C)); }
RECOMP_OVERRIDE(0x0052CE38) {              /* CountLines(font, text, preprocess, ?) */
    FR_ENSURE_BUDGET(ctx);
    uint32_t txt = ctx->r[1];
    uint32_t lr0 = ctx->r[14];
    CALL(RECOMP_ORIGINAL(0x0052CE38));
    if (lr0 >= 0x002B8C30u && lr0 < 0x002B9200u) { fr_blk_maxw = fr_last_meas_w; fr_blk_left = (int)ctx->r[0]; }   /* panel text drawn line by line */
    { char h_[64]; fr_text_head(ctx, txt, h_, 64); FR_LOG("COUNTLINES n=%d wrap=%d cw=%u lsp=%u '%s'\n", (int)ctx->r[0], (int)fr_rd(ctx, FO_WRAP), fr_rd(ctx, FO_CHARW), fr_rd(ctx, FO_LINESP), h_); }
}
RECOMP_OVERRIDE(0x0052CAF8) { CALL(RECOMP_ORIGINAL(0x0052CAF8)); }
RECOMP_OVERRIDE(0x00120E0C) { CALL(RECOMP_ORIGINAL(0x00120E0C)); }
