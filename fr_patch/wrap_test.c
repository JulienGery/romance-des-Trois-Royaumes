#include <stdio.h>
#include <stdlib.h>
#include "../overrides/frwrap.h"
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *all = malloc(sz); fread(all, 1, sz, f);
    int waps[] = {120, 200, 301, 400}; int cws[] = {16, 14, 12};
    for (int wi = 0; wi < 4; wi++) for (int ci = 0; ci < 3; ci++) {
        int wrap = waps[wi], cw = cws[ci], recs = 0, over = 0, badstart = 0, lost = 0, maxlines = 0, trunc = 0; long hist[12] = {0};
        for (long p = 0; p < sz;) {
            uint8_t *in = all + p; int L = strlen((char *)in); p += L + 1; recs++;
            uint8_t out[FR_TEXT_MAX * 2]; int comp;
            int ol = fr_wrap_text(in, L, out, FR_TEXT_MAX, wrap, cw, 0, -1, &comp);
            if (ol < 0) continue;
            if (!comp) trunc++;
            /* content preserved: strip newlines and spaces from both */
            uint8_t a[FR_TEXT_MAX], b[FR_TEXT_MAX]; int na = 0, nb = 0;
            for (int i = 0; i < L; i++) if (in[i] != '\n' && in[i] != ' ') a[na++] = in[i];
            for (int i = 0; i < ol; i++) if (out[i] != '\n' && out[i] != ' ') b[nb++] = out[i];
            if (na != nb || memcmp(a, b, na)) { lost++; if (lost < 3) printf("LOST: %.60s\n", in); }
            /* measure each output line */
            int lines = 1, pos = 0, curcw = cw, lw = 0; int linestart = 1;
            while (pos < ol) {
                uint32_t c = frw_next(out, ol, &pos);
                if (c == 0x0A) { lines++; lw = 0; linestart = 1; continue; }
                if (c == 0x10) { pos++; lw += curcw; linestart = 0; continue; }
                if (c == 0x12) { pos++; continue; }
                if (c == 0x13 || c == 0x17) continue;
                if (c == 0x14) { curcw = cw; continue; } if (c == 0x15) { curcw = 22; continue; } if (c == 0x16) { curcw = 12; continue; }
                if (linestart && frw_no_start(c) && lines > 1) badstart++;
                linestart = 0;
                int idx = frw_lookup(c); lw += idx >= 0 ? frw_adv(idx, curcw) : (c < 0x100 ? curcw / 2 : curcw);
                if (lw > wrap && c != ' ') { /* single word longer than the line is tolerated only if no space inside this line */ over++; }
            }
            hist[lines > 11 ? 11 : lines]++; if (lines > maxlines) maxlines = lines;
        }
        printf("wrap=%3d cw=%2d: records=%d lines>wrap(chars)=%d forbidden-start=%d content-lost=%d truncated=%d maxlines=%d hist:", wrap, cw, recs, over, badstart, lost, trunc, maxlines);
        for (int i = 1; i < 12; i++) printf(" %ld", hist[i]); printf("\n");
    }
    return 0;
}
