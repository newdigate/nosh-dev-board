/* Grid A* core for the Nosh SDRAM bus router (Kicad/tools/busrouter).
 * Three routing layers on a regular grid; negotiated-congestion costs (PathFinder style).
 * Called from KiCad's bundled Python through ctypes; ctypes releases the GIL, so several nets can be searched at
 * once on separate threads, each with its own Work buffers.
 * Build: clang -O3 -shared -fPIC -o libastar.dylib astar.c
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

typedef struct {
    int nx, ny; float g, x0, y0;
    uint8_t *stat[3];            /* hard obstacles per layer (other nets' fixed copper + clearance) */
    uint16_t *cnt[3];            /* SDRAM-net copper + clearance, counted (all nets, incl. the routed one) */
    uint16_t *hist[3];           /* congestion history */
    uint16_t *fixc[3];           /* fixed SDRAM-net copper (pads, prebuilt, fan-out) + clearance, counted: hard for other nets */
    uint8_t *via_static;         /* no via at all */
    uint16_t *via_soft;          /* routed SDRAM vias / tracks: soft via exclusion, counted */
    uint16_t *via_fix;           /* prebuilt SDRAM copper: hard via exclusion for other nets, counted */
    float *fac[3];               /* per x column: layer cost factor, < 0 = layer not allowed */
    float *viacost;              /* per x column */
    float pres, histw, turn;
    int esc_i0, esc_i1;          /* x columns of the top-layer escape band (vertical moves penalised x6) */
} Grid;

typedef struct {
    double *dist; int32_t *prev; uint8_t *dir;
    uint16_t *own_cnt;           /* 3 * N: the routed net's own contribution to cnt */
    uint16_t *own_vsoft, *own_vfix;
    uint16_t *own_fix;           /* 3 * N: the routed net's own fixed copper */
    uint8_t *tmask;              /* 3 * N target flags */
} Work;

typedef struct { double f, g; int32_t node; } HeapItem;
typedef struct { HeapItem *a; int n, cap; } Heap;
static void hpush(Heap *h, double f, double g, int32_t node) {
    if (h->n == h->cap) { h->cap = h->cap ? h->cap * 2 : 1 << 16; h->a = realloc(h->a, (size_t)h->cap * sizeof(HeapItem)); }
    int i = h->n++;
    while (i > 0) { int p = (i - 1) >> 1; if (h->a[p].f <= f) break; h->a[i] = h->a[p]; i = p; }
    h->a[i].f = f; h->a[i].g = g; h->a[i].node = node;
}
static HeapItem hpop(Heap *h) {
    HeapItem top = h->a[0], last = h->a[--h->n]; int i = 0;
    for (;;) { int c = 2 * i + 1; if (c >= h->n) break; if (c + 1 < h->n && h->a[c + 1].f < h->a[c].f) c++;
               if (h->a[c].f >= last.f) break; h->a[i] = h->a[c]; i = c; }
    if (h->n) h->a[i] = last;
    return top;
}

/* own spans: quintuples (type, layer, j, a, b); type 0 = cnt (layer), 1 = via_soft, 2 = via_fix, 3 = fixc (layer) */
static void apply_own(const Grid *G, Work *W, int nown, const int32_t *own, int d) {
    int N = G->nx * G->ny;
    for (int s = 0; s < nown; s++) {
        int t = own[5 * s], l = own[5 * s + 1], j = own[5 * s + 2], a = own[5 * s + 3], b = own[5 * s + 4];
        uint16_t *arr = t == 0 ? W->own_cnt + (size_t)l * N : (t == 1 ? W->own_vsoft : (t == 2 ? W->own_vfix : W->own_fix + (size_t)l * N));
        for (int i = a; i <= b; i++) arr[(size_t)j * G->nx + i] += d;
    }
}

static const int DX[8] = {1, -1, 0, 0, 1, 1, -1, -1}, DY[8] = {0, 0, 1, -1, 1, -1, 1, -1};
static const float STEP[8] = {1, 1, 1, 1, 1.41421356f, 1.41421356f, 1.41421356f, 1.41421356f};

int route(const Grid *G, Work *W, int nsrc, const int32_t *src, int ntgt, const int32_t *tgt, int nown, const int32_t *own,
          float hx, float hy, int maxexp, int32_t *out, int outcap, int *outlen, int *expanded) {
    const int NX = G->nx, N = G->nx * G->ny;
    for (int k = 0; k < 3 * N; k++) { W->dist[k] = INFINITY; W->prev[k] = -1; }
    apply_own(G, W, nown, own, +1);
    for (int t = 0; t < ntgt; t++) W->tmask[(size_t)tgt[3 * t] * N + (size_t)tgt[3 * t + 2] * NX + tgt[3 * t + 1]] = 1;
#define OTHER(l, k) (G->cnt[l][k] > W->own_cnt[(size_t)(l) * N + (k)])
#define FIXED(l, k) (G->fixc[l][k] > W->own_fix[(size_t)(l) * N + (k)])
#define HEUR(i, j) (hypot(G->x0 + (i) * G->g - hx, G->y0 + (j) * G->g - hy) * 0.98)
    Heap H = {0};
    for (int s = 0; s < nsrc; s++) {
        int l = src[3 * s], i = src[3 * s + 1], j = src[3 * s + 2], k = j * NX + i;
        if (G->stat[l][k]) continue;
        int node = l * N + k; W->dist[node] = 0; W->dir[node] = 9; hpush(&H, HEUR(i, j), 0, node);
    }
    int best = -1, exp = 0;
    while (H.n) {
        HeapItem it = hpop(&H); int node = it.node; double g = it.g;
        if (g > W->dist[node]) continue;
        if (W->tmask[node]) { best = node; break; }
        if (++exp > maxexp) break;
        int l = node / N, k = node % N, i = k % NX, j = k / NX, d0 = W->dir[node];
        for (int di = 0; di < 8; di++) {
            int ni = i + DX[di], nj = j + DY[di];
            if (ni < 1 || nj < 1 || ni >= NX - 1 || nj >= G->ny - 1) continue;
            int nk = nj * NX + ni, nn = l * N + nk;
            if (G->stat[l][nk] || FIXED(l, nk)) continue;
            float fc = G->fac[l][ni];
            if (fc < 0) { if (!W->tmask[nn]) continue; fc = 1.0f; }
            float pen = (l == 0 && DY[di] != 0 && i >= G->esc_i0 && i <= G->esc_i1) ? 6.0f : 1.0f;
            double ng = g + STEP[di] * G->g * fc * pen + ((d0 != di && d0 != 9) ? G->turn : 0.0f)
                       + (OTHER(l, nk) ? G->pres : 0.0f) + G->histw * G->hist[l][nk];
            if (ng < W->dist[nn]) { W->dist[nn] = ng; W->prev[nn] = node; W->dir[nn] = di; hpush(&H, ng + HEUR(ni, nj), ng, nn); }
        }
        if (!G->via_static[k] && !(G->via_fix[k] > W->own_vfix[k])) {
            double vc = G->viacost[i] + ((G->via_soft[k] > W->own_vsoft[k]) ? 3.0f * G->pres : 0.0f);
            for (int l2 = 0; l2 < 3; l2++) {
                if (l2 == l || G->stat[l2][k] || FIXED(l2, k)) continue;
                int nn = l2 * N + k;
                if (G->fac[l2][i] < 0 && !W->tmask[nn]) continue;
                double ng = g + vc * (abs(l2 - l) == 1 ? 1.0f : 1.3f) + (OTHER(l2, k) ? G->pres : 0.0f) + G->histw * G->hist[l2][k];
                if (ng < W->dist[nn]) { W->dist[nn] = ng; W->prev[nn] = node; W->dir[nn] = 9; hpush(&H, ng + HEUR(i, j), ng, nn); }
            }
        }
    }
    *expanded = exp; int n = 0;
    if (best >= 0) {
        for (int v = best; v >= 0; v = W->prev[v]) n++;
        if (n > outcap) n = -2;
        else { int p = n; for (int v = best; v >= 0; v = W->prev[v]) { p--; int kk = v % N; out[3 * p] = v / N; out[3 * p + 1] = kk % NX; out[3 * p + 2] = kk / NX; } }
    } else n = -1;
    *outlen = n;
    for (int t = 0; t < ntgt; t++) W->tmask[(size_t)tgt[3 * t] * N + (size_t)tgt[3 * t + 2] * NX + tgt[3 * t + 1]] = 0;
    apply_own(G, W, nown, own, -1);
    free(H.a);
    return n;
}
