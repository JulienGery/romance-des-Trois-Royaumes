/* Phase 2: French glyphs + proportional advance.
 *  - 0x0052DA8C  ASCII glyph    (engine reaches it for every ASCII char once font+0x1214 == 1)
 *  - 0x0052DC54  other glyph    (accents, « », … : French atlas first, original Japanese path otherwise)
 *  - 0x0052CEA4  text measure   (C port, same results as the original, Latin widths from the French table)
 *  - 0x0052D340  draw entry     (sets the ASCII flag)
 * Registers (verified in the ARM prologues): s0,s1,s2 = x,y,z (floats) ; r0 = font ; r1 = code. Return r0 = advance in px, -1 when the quad list is full. */
#include <stdlib.h>
#include "frfont.h"
#include "frwrap.h"

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
static int fr_ctr_active; static float fr_ctr_x, fr_ctr_y; static uint32_t fr_ctr_xb;
static int fr_ctr_xi, fr_ctr_yi;       /* integer copies of the draw position: the code that uses them can stay Thumb (no VFP) */
static FR_ARM int fr_ftoi(uint32_t bits) { return (int)fr_f(bits); }
static FR_ARM uint32_t fr_itof(int v) { return fr_bits((float)v); }
static FR_ARM void fr_ctr_set(Context *ctx) {
    fr_ctr_x = fr_f(ctx->vfp[0]); fr_ctr_y = fr_f(ctx->vfp[1]); fr_ctr_xb = ctx->vfp[0]; fr_ctr_xi = (int)fr_ctr_x; fr_ctr_yi = (int)fr_ctr_y;
}
RECOMP_OVERRIDE(0x0052D340) {
    FR_ENSURE_BUDGET(ctx);
    fr_init(ctx);
    uint32_t lr = ctx->r[14], sv[3] = { fr_rd(ctx, FO_CHARW), fr_rd(ctx, FO_CHARH), fr_rd(ctx, FO_LINESP) };
    fr_ctr_set(ctx); fr_ctr_active = 1;
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

/* the NUL-terminated guest buffer -> in[]; returns its length, -1 when it holds ruby (left untouched, original behaviour) */
static int fr_read_guest(Context *c, uint32_t buf, uint8_t *in) {
    int len = 0;
    while (len < 1030) { uint8_t b = mem_read8(c, buf + len); if (!b) break; if (b == 0x11) return -1; in[len++] = b; }
    return len;
}
static int fr_count_lines(const uint8_t *b, int len) { int n = 1; for (int i = 0; i < len; i++) if (b[i] == '\n') n++; return n; }

/* the layouts the text-fit family tries, in order: the first whose wrapped text fits availH (one line always fits) is written into the
 * guest buffer; the last one when none does. Returns its index, -1 for ruby. */
typedef struct { int size, lsp, flags; } fr_step;
static int fr_pick_step(Context *c, uint32_t buf, const uint8_t *in, int len, int W, int availH, const fr_step *st, int ns, int sp, int maxc, int *complete) {
    static uint8_t out[1100]; int pick = ns - 1, ol;
    for (int k = 0; k < ns; k++) {
        ol = fr_wrap_text2(in, len, out, 1024, W, st[k].size, sp, -1, NULL, st[k].flags);
        if (ol < 0) return -1;
        int n = fr_count_lines(out, ol);
        if (n == 1 || n * st[k].size + (n - 1) * st[k].lsp <= availH) { pick = k; break; }
    }
    ol = fr_wrap_text2(in, len, out, 1024, W, st[pick].size, sp, maxc, complete, st[pick].flags);
    if (ol < 0) return -1;
    for (int i = 0; i <= ol; i++) mem_write8(c, buf + i, out[i]);
    return pick;
}
/* wraps the buffer at guest address buf in place. returns 1 when done, 0 when the text has ruby. *complete = typewriter "everything shown" result */
static int fr_wrap_guest(Context *c, uint32_t buf, int maxc, int *complete) {
    static uint8_t in[1100], out[1100];
    int len = fr_read_guest(c, buf, in);
    if (len < 0) return 0;
    int W = (int)fr_rd(c, FO_WRAP), cw = (int)fr_rd(c, FO_CHARW), sp = (int)fr_rd(c, FO_SPACING), fl = FRW_REFLOW | FRW_BALANCE, ol;
    if (W == FR_BUBBLE_W && (ol = fr_wrap_text2(in, len, out, 1024, W, cw, sp, -1, NULL, fl)) >= 0 && fr_count_lines(out, ol) > 4) fl = FRW_REFLOW_ALL | FRW_BALANCE;   /* a dialogue bubble holds 4 lines */
    ol = fr_wrap_text2(in, len, out, 1024, W, cw, sp, maxc, complete, fl);
    if (ol < 0) return 0;
    for (int i = 0; i <= ol; i++) mem_write8(c, buf + i, out[i]);
    return 1;
}

/* ---- text fit: fixed-box windows (no layout function sizes them, e.g. Whisper's bottom dialogue box 2,166,396,72).
 * 0x005412E0 sets fr_fit_h (text height available in the box) around the draw; the preprocess then picks the first layout that fits:
 * normal wrap, full reflow, tighter line spacing, then 14 and 12 px. Deterministic: same input -> same output every frame. */
static int fr_fit_w;                                  /* wrap width used by the fixed-box fit when it differs from the widget's */
static int fr_fit_h;                                  /* >0 while a fixed-box widget draws */
static int fr_fit_base_valid, fr_fit_base_cw, fr_fit_base_lsp, fr_fit_ap_cw, fr_fit_ap_lsp;   /* font params before / after our change */
static uint32_t fr_managed[64]; static int fr_managed_n;   /* widgets sized by a layout function or bubble init: never fitted */
static void fr_mark_managed(uint32_t wd) { for (int i = 0; i < 64; i++) if (fr_managed[i] == wd) return; fr_managed[fr_managed_n++ & 63] = wd; }
static int fr_is_managed(uint32_t wd) { for (int i = 0; i < 64; i++) if (fr_managed[i] == wd) return 1; return 0; }

static int fr_fit_guest(Context *c, uint32_t buf, int maxc, int *complete) {
    static uint8_t in[1100];
    int len = fr_read_guest(c, buf, in);
    if (len < 0) return 0;
    int cw = (int)fr_rd(c, FO_CHARW), lsp = (int)fr_rd(c, FO_LINESP);
    if (fr_fit_base_valid && cw == fr_fit_ap_cw && lsp == fr_fit_ap_lsp) { cw = fr_fit_base_cw; lsp = fr_fit_base_lsp; }   /* second preprocess of the same draw */
    int tight = lsp < 2 ? lsp : 2, ns = 0;
    fr_step st[8];
    st[ns++] = (fr_step){ cw, lsp, FRW_REFLOW | FRW_BALANCE };
    st[ns++] = (fr_step){ cw, lsp, FRW_REFLOW_ALL | FRW_BALANCE };
    st[ns++] = (fr_step){ cw, tight, FRW_REFLOW_ALL | FRW_BALANCE };
    for (int sz = 14; sz >= 12; sz -= 2) if (sz < cw) {
        st[ns++] = (fr_step){ sz, tight, FRW_REFLOW | FRW_BALANCE };
        st[ns++] = (fr_step){ sz, tight, FRW_REFLOW_ALL | FRW_BALANCE };
    }
    int pick = fr_pick_step(c, buf, in, len, fr_fit_w ? fr_fit_w : (int)fr_rd(c, FO_WRAP), fr_fit_h, st, ns, (int)fr_rd(c, FO_SPACING), maxc, complete);
    if (pick < 0) return 0;
    if (st[pick].size != cw || st[pick].lsp != lsp) {
        fr_fit_base_valid = 1; fr_fit_base_cw = cw; fr_fit_base_lsp = lsp; fr_fit_ap_cw = st[pick].size; fr_fit_ap_lsp = st[pick].lsp;
        fr_wr(c, FO_CHARW, st[pick].size); fr_wr(c, FO_CHARH, st[pick].size); fr_wr(c, FO_LINESP, st[pick].lsp);
    }
    if (pick) FR_LOG("FIT step=%d size=%d lsp=%d flags=%d inner=%d\n", pick + 1, st[pick].size, st[pick].lsp, st[pick].flags, fr_fit_h);
    return 1;
}

#define FR_CTR_MAXW 284
/* Medallium page 3 slots (centred, y fixed): the name plate (y 73, ~90 px wide) and the tagline above the white rule (y 101, ~330 px, one line high:
 * the rule is at y ~ 111). A tagline that does not fit on one line at 12 px is set on two 11 px lines, moved up by a last line holding one space (the block is centred; a truly empty last line is not counted). */
static int fr_center_guest(Context *c, uint32_t buf, int maxc, int *complete) {   /* 1 = rewrapped, 0 = nothing to do */
    static uint8_t in[1100];
    int len = fr_read_guest(c, buf, in);
    if (len < 0) return 0;
    int cw = (int)fr_rd(c, FO_CHARW), lsp = (int)fr_rd(c, FO_LINESP), sp = (int)fr_rd(c, FO_SPACING);
    int ty = fr_ctr_yi, tag = ty == 101 && cw == 14, plate = ty == 73 && cw == 14;
    int hx = fr_ctr_xi < 400 - fr_ctr_xi ? fr_ctr_xi : 400 - fr_ctr_xi, hy = ty < 240 - ty ? ty : 240 - ty;
    int W = 2 * hx - 12; if (W > FR_CTR_MAXW) W = FR_CTR_MAXW;
    if (tag) W = 330; else if (plate) W = 90; else if (W < 120) return 0;
    int mx = frw_max_line(in, len, cw, sp);
    if (mx <= W) return 0;
    if (fr_count_lines(in, len) == 1) {         /* a one-line label/banner: no room for a second line, shrink it instead (down to 11 px, 12 for a tagline) */
        int sz = cw * W / mx;
        if (sz >= (tag ? 12 : 11)) { if (sz < cw) { fr_wr(c, FO_CHARW, sz); fr_wr(c, FO_CHARH, sz); FR_LOG("LABELFIT centre=%.0f W=%d widest=%d size %d->%d\n", fr_ctr_x, W, mx, cw, sz); } return 0; }
    }
    fr_step st[3]; int ns = 0;
    if (tag) st[ns++] = (fr_step){ 11, 1, FRW_REFLOW | FRW_BALANCE };
    else {
        st[ns++] = (fr_step){ cw, lsp, FRW_REFLOW | FRW_BALANCE };
        for (int sz = 14; sz >= 12; sz -= 2) if (sz < cw) st[ns++] = (fr_step){ sz, lsp < 2 ? lsp : (lsp * sz / cw > 2 ? lsp * sz / cw : 2), FRW_REFLOW | FRW_BALANCE };
    }
    int pick = fr_pick_step(c, buf, in, len, W, 2 * hy - 8, st, ns, sp, maxc, complete);
    if (pick < 0) return 0;
    if (tag) { int o = 0; while (mem_read8(c, buf + o)) o++; mem_write8(c, buf + o, '\n'); mem_write8(c, buf + o + 1, ' '); mem_write8(c, buf + o + 2, 0); }
    if (st[pick].size != cw || st[pick].lsp != lsp) { fr_wr(c, FO_CHARW, st[pick].size); fr_wr(c, FO_CHARH, st[pick].size); fr_wr(c, FO_LINESP, st[pick].lsp); }
    FR_LOG("CENTERFIT centre=(%.0f,%.0f) W=%d size=%d lsp=%d\n", fr_ctr_x, fr_ctr_y, W, st[pick].size, st[pick].lsp);
    return 1;
}

/* left-aligned text drawn with NO wrap width inside a panel of the Medallium pages (the Japanese lines were short, the French sentences
 * run past the panel / below it). The panel is found from the draw position (x, y), which is fixed per page:
 *   page 1 description (x 216, y 59) and skill text (x 216, y 182) ; page 2 ability texts (x 23 and 213, y ~168) ; page 3 biography (x 33, y ~126).
 * Wrap to the panel, then, when the block is too tall for the space left, join the sentences, tighten the spacing, finally shrink to 11/10 px. */
static int fr_edge_r, fr_edge_b;
static int fr_edge_rule(void) {
    int x = fr_ctr_xi, y = fr_ctr_yi;
    if (x >= 100 && x <= 115 && y >= 60 && y <= 68) { fr_edge_r = 376; fr_edge_b = 0; return 1; }   /* quest title: one line, shrink */
    if (x >= 200 && x < 300) { fr_edge_r = 376; fr_edge_b = y < 150 ? 156 : 222; return 1; }
    if (x >= 16 && x < 40 && y >= 160 && y < 200) { fr_edge_r = 196; fr_edge_b = 224; return 1; }
    if (x >= 20 && x < 40 && y >= 100 && y < 150) { fr_edge_r = 378; fr_edge_b = 210; return 1; }
    return 0;
}
/* Medallium page 3 (biography): drawn left-aligned with a real wrap width (339) from (31, 122) inside a panel that ends at y ~ 210: five wrapped lines
 * (14 px + 7) run below it. Same text fit as the fixed boxes, with the height left in the panel. */
static int fr_bio_avail(int wrap, int cw) {
    int y = fr_ctr_yi;
    if (cw == 14 && wrap >= 255 && wrap <= 265 && y >= 188 && y <= 194) { fr_fit_w = 304; return 238 - y; }   /* quest description, bottom of the screen */
    return cw == 14 && wrap >= 330 && wrap <= 345 && y >= 118 && y <= 126 ? 210 - y : 0;
}
static int fr_edge_guest(Context *c, uint32_t buf, int maxc, int *complete) {
    static uint8_t in[1100];
    int len = fr_read_guest(c, buf, in);
    if (len < 0) return 0;
    int cw = (int)fr_rd(c, FO_CHARW), lsp = (int)fr_rd(c, FO_LINESP), sp = (int)fr_rd(c, FO_SPACING);
    int W = fr_edge_r - fr_ctr_xi; if (W < 100) return 0;
    if (!fr_edge_b) { int mx = frw_max_line(in, len, cw, sp), sz = cw * W / (mx ? mx : 1); if (mx > W) { if (sz < 11) sz = 11; fr_wr(c, FO_CHARW, sz); fr_wr(c, FO_CHARH, sz); } return 0; }
    int availH = fr_edge_b - fr_ctr_yi, n0 = fr_count_lines(in, len);
    if (frw_max_line(in, len, cw, sp) <= W && n0 * cw + (n0 - 1) * lsp <= availH) return 0;
    int tight = lsp < 2 ? lsp : 2, ns = 0;
    fr_step st[5];                                   /* normal wrap; join sentences; tight spacing; 11 px; 10 px */
    st[ns++] = (fr_step){ cw, lsp, FRW_REFLOW | FRW_BALANCE };
    st[ns++] = (fr_step){ cw, lsp, FRW_REFLOW_ALL | FRW_BALANCE };
    st[ns++] = (fr_step){ cw, tight, FRW_REFLOW_ALL | FRW_BALANCE };
    for (int sz = 11; sz >= 10; sz--) st[ns++] = (fr_step){ sz < cw ? sz : cw, tight, FRW_REFLOW_ALL | FRW_BALANCE };
    int pick = fr_pick_step(c, buf, in, len, W, availH, st, ns, sp, maxc, complete);
    if (pick < 0) return 0;
    if (st[pick].lsp != lsp) fr_wr(c, FO_LINESP, st[pick].lsp);
    if (st[pick].size != cw) { fr_wr(c, FO_CHARW, st[pick].size); fr_wr(c, FO_CHARH, st[pick].size); }
    FR_LOG("EDGEFIT x=%.0f y=%.0f W=%d step=%d size=%d lsp=%d\n", fr_ctr_x, fr_ctr_y, W, pick + 1, st[pick].size, st[pick].lsp);
    return 1;
}

/* one line of a panel text: shrink uniformly so the widest line fits around the centre */
static void fr_panel_shrink(Context *ctx) {
    int hx = fr_ctr_xi < 400 - fr_ctr_xi ? fr_ctr_xi : 400 - fr_ctr_xi; int W = 2 * hx - 12; if (W > 380) W = 380;
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
    if (!fr_wrap_disabled && font == FONT_OBJ && (int)fr_rd(ctx, FO_WRAP) >= 0x7FFFFFFF && fr_ctr_active && !fr_fit_h && fr_rd(ctx, FO_ALIGN) == 0
        && fr_edge_rule() && !getenv("FR_NOEDGE")) {
        ctx->r[3] = 0xFFFFFFFFu; CALL(RECOMP_ORIGINAL(0x0052C690));
        int complete = 1;
        if (fr_edge_guest(ctx, buf, (int)maxc, &complete)) { fr_prewrapped = 1; ctx->r[0] = complete ? 1 : 0; ctx->r[14] = lr; RETURN_TO(lr); }
        ctx->r[0] = font; ctx->r[1] = buf; ctx->r[2] = str; ctx->r[3] = maxc; ctx->r[14] = lr; CALL(RECOMP_ORIGINAL(0x0052C690)); return;
    }
    if (fr_wrap_disabled || font != FONT_OBJ || (int)fr_rd(ctx, FO_WRAP) >= 0x7FFFFFFF) { CALL(RECOMP_ORIGINAL(0x0052C690)); return; }
    ctx->r[3] = 0xFFFFFFFFu;                  /* wrap the whole text first, then apply the typewriter limit */
    CALL(RECOMP_ORIGINAL(0x0052C690));
    int complete = 1, bio = !fr_fit_h && fr_ctr_active && fr_rd(ctx, FO_ALIGN) == 0 ? fr_bio_avail((int)fr_rd(ctx, FO_WRAP), (int)fr_rd(ctx, FO_CHARW)) : 0;
    if (bio) fr_fit_h = bio;
    int done = fr_fit_h > 0 ? fr_fit_guest(ctx, buf, (int)maxc, &complete) : fr_wrap_guest(ctx, buf, (int)maxc, &complete);
    if (bio) fr_fit_h = 0;
    fr_fit_w = 0;
    if (done) {
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
static int fr_fix_message_box(Context *ctx, uint32_t fn, uint32_t wd, uint32_t txt, int fixed_h) {
    #define WF(o) ((int)mem_read32(ctx, wd + (o)))
    int bx = WF(0x24), by = WF(0x28), bw = WF(0x2C), bh = WF(0x30), tx = WF(0x254), ty = WF(0x258);
    int mw = WF(0x26C), mh = WF(0x270), cw = WF(0x260);
    int lsp = fr_ftoi(mem_read32(ctx, wd + 0x268));
    (void)bx;
    { char h_[64]; fr_text_head(ctx, txt, h_, 64);
      FR_LOG("LAYOUT fn=%08X wd=%08X mode=%d type=%d box=(%d,%d,%d,%d) text@(%d,%d) meas=(%d,%d) cw=%d lsp=%d fixed=%d '%s'\n", fn, wd, WF(0x48), WF(0x2A4), bx, by, bw, bh, tx, ty, mw, mh, cw, lsp, fixed_h, h_); }
    int fits = by >= 0 && by + bh <= FR_SCREEN_H + FR_TOL && ty + mh <= bh && tx >= 0 && tx + mw <= bw;
    if (getenv("FR_TRACE")) fprintf(stderr, "[fr] fixbox by=%d bh=%d ty=%d mh=%d tx=%d mw=%d bw=%d fits=%d txt=%08X\n", by, bh, ty, mh, tx, mw, bw, fits, txt);
    if (fits || !txt) return 0;
    int bpad = bh - ty - mh; if (bpad < 6) bpad = 6; if (bpad > 12 && fixed_h) bpad = 12; if (bpad > 40) bpad = 40;
    int wrapW = bw - 16; if (wrapW > 301) wrapW = 301;
    uint32_t saved[6] = { fr_rd(ctx, FO_CHARW), fr_rd(ctx, FO_CHARH), fr_rd(ctx, FO_LINESP), fr_rd(ctx, FO_WRAP), fr_rd(ctx, FO_ALIGN), fr_rd(ctx, FO_SPACING) };
    static const int sizes[3] = { 16, 14, 12 };
    int best = -1, nbh = bh, nby = by, ntx = tx, nmw = mw, nmh = mh, nlsp = lsp, ncw = cw;
    for (int k = 0; k < 3; k++) {
        int s = sizes[k], ls = (lsp * s + 8) / 16;
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
    mem_write32(ctx, wd + 0x260, ncw); mem_write32(ctx, wd + 0x264, ncw); mem_write32(ctx, wd + 0x268, fr_itof(nlsp));
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

/* pass-through overrides: reserved so the next phases can be edited with tools/fast_build.sh (no full rebuild) */
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
/* GetLine(font, out, text, i): line i of a multi-line widget (FUN_005412E0 draws them one by one). The original cuts at explicit newlines
 * only, so a paragraph that our wrap splits in two overlaps the next line: from the widget draw, return the lines of the WRAPPED text. */
RECOMP_OVERRIDE(0x0052CAF8) {
    FR_ENSURE_BUDGET(ctx);
    uint32_t lr = ctx->r[14], font = ctx->r[0], outp = ctx->r[1], txt = ctx->r[2]; int idx = (int)ctx->r[3];
    if (!fr_wrap_disabled && font == FONT_OBJ && lr > 0x005412E0u && lr < 0x00541630u && (int)fr_rd(ctx, FO_WRAP) < 0x7FFFFFFF && idx >= 0 && !getenv("FR_NOGETLINE")) {
        static uint8_t raw[1100], res[1100]; int len = 0;
        while (len < 1050) { uint8_t b = mem_read8(ctx, txt + len); if (!b) break; raw[len++] = b; }
        int more = len < 1050 ? fr_getline_core(raw, len, (int)fr_rd(ctx, FO_WRAP), (int)fr_rd(ctx, FO_CHARW), (int)fr_rd(ctx, FO_SPACING), idx, res, 1024) : -1;
        if (more >= 0) {
            for (int i = 0; ; i++) { mem_write8(ctx, outp + i, res[i]); if (!res[i]) break; }
            ctx->r[0] = (uint32_t)more; ctx->r[14] = lr; RETURN_TO(lr);
        }
    }
    CALL(RECOMP_ORIGINAL(0x0052CAF8));
}
RECOMP_OVERRIDE(0x00120E0C) { CALL(RECOMP_ORIGINAL(0x00120E0C)); }
