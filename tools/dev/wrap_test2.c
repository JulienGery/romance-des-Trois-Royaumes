/* properties of reflow + balance (docs/dev/PLAN_correctifs_texte.md B.4) on the whole translated corpus */
#include <stdio.h>
#include <stdlib.h>
#include "../../src/overrides/frwrap.h"
static int lines_info(const uint8_t *o, int ol, int cw, int *maxw, int *lastw) {
    int lines = 1, pos = 0, curcw = cw, lw = 0; *maxw = 0;
    while (pos < ol) {
        uint32_t c = frw_next(o, ol, &pos);
        if (c == 0x0A) { if (lw > *maxw) *maxw = lw; lines++; lw = 0; continue; }
        if (c == 0x10) { pos++; lw += curcw; continue; }
        if (c == 0x12) { pos++; continue; }
        if (c == 0x13 || c == 0x17) continue;
        if (c == 0x14) { curcw = cw; continue; } if (c == 0x15) { curcw = 22; continue; } if (c == 0x16) { curcw = 12; continue; }
        int idx = frw_lookup(c); lw += idx >= 0 ? frw_adv(idx, curcw) : (c < 0x100 ? curcw / 2 : curcw);
    }
    if (lw > *maxw) *maxw = lw; *lastw = lw; return lines;
}
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *all = malloc(sz); fread(all, 1, sz, f);
    int waps[] = {252, 301}; int cw = 16;
    for (int wi = 0; wi < 2; wi++) {
        int W = waps[wi]; long recs = 0, lostc = 0, over = 0, mism = 0, orphN = 0, orphO = 0, more = 0, tl_n = 0, tl_o = 0, badstart = 0;
        for (long p = 0; p < sz;) {
            uint8_t *in = all + p; int L = strlen((char *)in); p += L + 1;
            uint8_t o0[2048], o1[2048], o2[2048]; int c0, c1, c2;
            int l0 = fr_wrap_text2(in, L, o0, 1024, W, cw, 0, -1, &c0, 0);
            int l1 = fr_wrap_text(in, L, o1, 1024, W, cw, 0, -1, &c1);
            if (l0 < 0 || l1 < 0) continue; recs++;
            uint8_t a[2048], b[2048]; int na = 0, nb = 0;
            for (int i = 0; i < L; i++) if (in[i] != '\n' && in[i] != ' ') a[na++] = in[i];
            for (int i = 0; i < l1; i++) if (o1[i] != '\n' && o1[i] != ' ') b[nb++] = o1[i];
            if (na != nb || memcmp(a, b, na)) { if (!lostc++) printf("LOST %.70s\n", in); }
            int mw0, lw0, mw1, lw1, mw2, lw2;
            int n0 = lines_info(o0, l0, cw, &mw0, &lw0), n1 = lines_info(o1, l1, cw, &mw1, &lw1);
            if (n1 > n0) { more++; if (more < 4) printf("MORE %d>%d %.60s\n", n1, n0, in); }
            if (mw1 > W && n1 > 1) over++;
            tl_o += n0; tl_n += n1;
            if (n0 > 1 && lw0 * 4 < W) orphO++;
            if (n1 > 1 && lw1 * 4 < W) { orphN++; if (orphN < 4) printf("ORPH %.80s\n", in); }
            l1 = fr_wrap_text(in, L, o2, 1024, mw1 > 0 ? mw1 : W, cw, 0, -1, &c2);     /* draw wraps at the measured width */
            if (l1 != strlen((char *)o1) || memcmp(o1, o2, l1 + 1)) { if (!mism++ && mism < 4) printf("MISMATCH %.70s\n  %s\n  %s\n", in, o1, o2); }
            (void)mw2; (void)lw2; (void)c2; (void)badstart;
        }
        printf("W=%d recs=%ld lost=%ld lines old=%ld new=%ld more-lines=%ld over=%ld orphans old=%ld new=%ld measure/draw mismatch=%ld\n", W, recs, lostc, tl_o, tl_n, more, over, orphO, orphN, mism);
    }
    return 0;
}
