"""Stage 3a (run with KiCad's bundled python3; edits Kicad/Nosh.kicad_pcb in place, back it up first): hand-routed differential pairs (MIPI DSI x3, USB x2). Edits the saved board in place. Idempotent-guarded."""
import math, collections, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
import os
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
nets = board.GetNetInfo().NetsByName()
import re
assert not any(re.match(r'MIPI_DSI_|USB[12]_(CON_)?D[PN]$', t.GetNetname()) for t in board.GetTracks()), 'pairs already routed'
F, B = pcbnew.F_Cu, pcbnew.B_Cu
W_MIPI, W_USB = 0.11, 0.13
added = []
def seg(layer, a, b, net, w):
    t = pcbnew.PCB_TRACK(board); t.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1]))); t.SetEnd(VECTOR2I(FromMM(b[0]), FromMM(b[1])))
    t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNet(nets[net]); t.SetLocked(True); board.Add(t); added.append(t)
def poly(layer, pts, net, w):
    for a, b in zip(pts, pts[1:]):
        if a != b: seg(layer, a, b, net, w)
def via(x, y, net):
    v = pcbnew.PCB_VIA(board); v.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(FromMM(0.45)); v.SetDrill(FromMM(0.3)); v.SetLayerPair(F, B); v.SetNet(nets[net]); v.SetLocked(True); board.Add(v); added.append(v)
pad = {}
for f in board.GetFootprints():
    for p in f.Pads(): pad[(f.GetReference(), p.GetNumber())] = (round(ToMM(p.GetPosition().x), 3), round(ToMM(p.GetPosition().y), 3))
P = lambda r, n: pad[(r, n)]

# ------------------------------------------------------------------ pair geometry helpers
def offset(pts, d):
    """Offset a polyline by d along the left-hand normal (west when heading north), mitred corners."""
    segs = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        L = math.hypot(x2 - x1, y2 - y1); nx, ny = (y2 - y1) / L, -(x2 - x1) / L
        segs.append(((x1 + nx * d, y1 + ny * d), (x2 + nx * d, y2 + ny * d)))
    out = [segs[0][0]]
    for (a1, a2), (b1, b2) in zip(segs, segs[1:]):
        # intersection of the two offset lines
        x1, y1 = a1; x2, y2 = a2; x3, y3 = b1; x4, y4 = b2
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-9: out.append(a2); continue
        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
        out.append((px, py))
    out.append(segs[-1][1]); return [(round(x, 4), round(y, 4)) for x, y in out]
def plen(pts): return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
def bump(pts, ya, yb, h):
    """Insert a square detour of depth h (toward -x) into the vertical segment of pts that spans y in [yb, ya] (ya > yb). Adds 2h."""
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        if abs(a[0] - b[0]) < 1e-6 and max(a[1], b[1]) >= ya and min(a[1], b[1]) <= yb:
            x = a[0]; down = a[1] > b[1]
            ins = [(x, ya), (x - h, ya), (x - h, yb), (x, yb)] if down else [(x, yb), (x - h, yb), (x - h, ya), (x, ya)]
            return pts[:i + 1] + ins + pts[i + 1:]
    raise ValueError('no vertical segment spans the bump range')

# ------------------------------------------------------------------ MIPI DSI: U1 rows A (N) / B (P), north, to J7 on the back
# pair, N ball, P ball, channel x for P between row-A balls, top run x (pair centre), jog start y, bottom run x, via y, J7 pads (N, P), bump y-range
MIPI = [('D0', 'A8', 'B8', 71.6, 71.32, 32.0, 63.70, 12.0, '5', '6', (18.0, 16.0)),
        ('CLK', 'A9', 'B9', 72.4, 72.12, 26.0, 66.70, 18.0, '11', '12', (30.0, 28.0)),
        ('D1', 'A10', 'B10', 73.2, 72.92, 18.0, 65.20, 9.0, '8', '9', (24.0, 22.0))]
HALF = 0.12                                              # 0.24 mm pitch: 0.11 track, 0.13 gap
for name, bn, bp, chan, xc, yjog, xb, yvia, jn, jp, (ba, bb) in MIPI:
    nN, nP = f'MIPI_DSI_{name}N', f'MIPI_DSI_{name}P'
    (nx, ny), (px, py) = P('U1', bn), P('U1', bp)
    y0 = 34.6; dx = xc - xb
    centre = [(xc, y0), (xc, yjog), (xb, yjog - dx), (xb, yvia + 0.6)]
    N, Pp = offset(centre, HALF), offset(centre, -HALF)
    (jnx, jny), (jpx, jpy) = P('J7', jn), P('J7', jp)
    def full(top_pts, esc, vx, jx, jy):
        return esc + top_pts, [(vx, yvia), (vx, yvia - 0.6), (jx, 7.3), (jx, jy + 0.45)]
    escN = [(nx, ny), (nx, y0 + 0.4)]
    escP = [(px, py), (chan, py - 0.4), (chan, y0 + 0.6)]
    topN = escN + N + [(xb - 0.5, yvia)]; topP = escP + Pp + [(xb + 0.5, yvia)]
    botN = [(xb - 0.5, yvia), (xb - 0.5, yvia - 0.6), (jnx, 7.3), (jnx, jny + 0.45)]
    botP = [(xb + 0.5, yvia), (xb + 0.5, yvia - 0.6), (jpx, 7.3), (jpx, jpy + 0.45)]
    skew = (plen(topP) + plen(botP)) - (plen(topN) + plen(botN))
    if skew > 0.1: topN = bump(topN, ba, bb, round(skew / 2, 3))
    poly(F, topN, nN, W_MIPI); poly(F, topP, nP, W_MIPI); via(xb - 0.5, yvia, nN); via(xb + 0.5, yvia, nP)
    poly(B, botN, nN, W_MIPI); poly(B, botP, nP, W_MIPI)

# ------------------------------------------------------------------ USB1: U1 E17 (DP) / E16 (DN) -> bottom -> L4 -> U5 -> J3
dp, dn = P('U1', 'E17'), P('U1', 'E16')                  # (78.4, 38.8), (77.6, 38.8)
# top escape: DP east on its row; DN through the channel south of E17 (between rows E and F), then 0.24 pitch
poly(F, [dp, (82.3, dp[1]), (83.0, 38.3)], 'USB1_DP', W_USB)
poly(F, [dn, (dn[0] + 0.4, dn[1] + 0.4), (79.3, dn[1] + 0.4), (79.6, dp[1] + 0.24), (82.3, dp[1] + 0.24), (83.0, 39.5)], 'USB1_DN', W_USB)
via(83.0, 38.3, 'USB1_DP'); via(83.0, 39.5, 'USB1_DN')
# bottom: converge, run east, 45-degree descent to the choke row, into L4 pins 2 (DP) / 3 (DN)
l4dp, l4dn = P('L4', '2'), P('L4', '3')                  # (136.65, 49.6), (136.65, 50.4)
yd, yn = 38.6, 38.84
poly(B, [(83.0, 38.3), (83.6, yd), (96.0, yd), (96.0 + (l4dp[1] - yd), l4dp[1]), l4dp], 'USB1_DP', W_USB)
poly(B, [(83.0, 39.5), (83.6, yn), (95.4, yn), (95.4 + (l4dn[1] - yn), l4dn[1]), l4dn], 'USB1_DN', W_USB)
# choke east pins -> ESD pins (DP y 49.25 north, DN 49.75 south) with vias on the way up to the top
c4dp, c4dn = P('L4', '1'), P('L4', '4')                  # (138.35, 49.6), (138.35, 50.4)
e5dp, e5dn = P('U5', '2'), P('U5', '1')                  # (142.24, 49.25), (142.24, 49.75)
poly(B, [c4dp, (c4dp[0] + 0.7, c4dp[1]), (c4dp[0] + 0.7 + (c4dp[1] - e5dp[1]), e5dp[1]), e5dp], 'USB1_CON_DP', W_USB)
poly(B, [c4dn, (c4dn[0] + 0.9, c4dn[1]), (c4dn[0] + 0.9 + (c4dn[1] - e5dn[1]), e5dn[1]), e5dn], 'USB1_CON_DN', W_USB)
via(141.3, e5dp[1], 'USB1_CON_DP'); via(140.3, e5dn[1], 'USB1_CON_DN')
# top: straight to J3 B6 (DP, y 49.25) and A7 (DN, y 49.75); A6 / B7 joined through vias and short bottom links
j = lambda n: P('J3', n)
pad_end = lambda n: (j(n)[0] - 0.575, j(n)[1])
poly(F, [(141.3, e5dp[1]), pad_end('B6')], 'USB1_CON_DP', W_USB)
poly(F, [(140.3, e5dn[1]), pad_end('A7')], 'USB1_CON_DN', W_USB)
poly(F, [pad_end('A6'), (145.8, j('A6')[1])], 'USB1_CON_DP', W_USB); via(145.8, j('A6')[1], 'USB1_CON_DP'); via(145.8, j('B6')[1], 'USB1_CON_DP')
poly(B, [(145.8, j('A6')[1]), (145.8, j('B6')[1])], 'USB1_CON_DP', W_USB)
poly(F, [pad_end('B7'), (145.0, j('B7')[1])], 'USB1_CON_DN', W_USB); via(145.0, j('B7')[1], 'USB1_CON_DN'); via(145.0, j('A7')[1], 'USB1_CON_DN')
poly(B, [(145.0, j('B7')[1]), (145.0, j('A7')[1])], 'USB1_CON_DN', W_USB)

# ------------------------------------------------------------------ USB2: U1 C17 (DP) / C16 (DN) -> bottom -> L3 -> U4 -> J2
dp, dn = P('U1', 'C17'), P('U1', 'C16')                  # (78.4, 37.2), (77.6, 37.2)
# top: DN through the channel north of C17 (DN north, DP south); DP via first, DN crosses over it on top and vias further east
poly(F, [dp, (81.8, dp[1]), (82.3, dp[1] + 0.5)], 'USB2_DP', W_USB); via(82.3, dp[1] + 0.5, 'USB2_DP')             # (82.3, 37.7)
poly(F, [dn, (dn[0] + 0.4, dn[1] - 0.4), (83.5, dn[1] - 0.4), (84.5, dn[1] + 0.6), (84.8, 38.0)], 'USB2_DN', W_USB); via(84.8, 38.0, 'USB2_DN')
# bottom: DP becomes the north trace, DN the south one, 0.24 pitch, east to L3 pins 2 (DP) / 3 (DN)
l3dp, l3dn = P('L3', '2'), P('L3', '3')                  # (136.65, 35.3), (136.65, 36.1)
yd, yn = 36.6, 36.84
poly(B, [(82.3, 37.7), (83.4, yd), (120.0, yd), (120.0 + (yd - l3dp[1]), l3dp[1]), l3dp], 'USB2_DP', W_USB)
poly(B, [(84.8, 38.0), (85.96, yn), (120.6, yn), (120.6 + (yn - l3dn[1]), l3dn[1]), l3dn], 'USB2_DN', W_USB)
c3dp, c3dn = P('L3', '1'), P('L3', '4')                  # (138.35, 35.3), (138.35, 36.1)
e4dp, e4dn = P('U4', '2'), P('U4', '1')                  # (142.24, 35.35), (142.24, 35.85)
poly(B, [c3dp, (c3dp[0] + 0.7, c3dp[1]), (c3dp[0] + 0.7 + abs(c3dp[1] - e4dp[1]), e4dp[1]), e4dp], 'USB2_CON_DP', W_USB)
poly(B, [c3dn, (c3dn[0] + 0.9, c3dn[1]), (c3dn[0] + 0.9 + abs(c3dn[1] - e4dn[1]), e4dn[1]), e4dn], 'USB2_CON_DN', W_USB)
via(140.2, e4dp[1], 'USB2_CON_DP'); via(141.4, e4dn[1], 'USB2_CON_DN')
# top to J2 pads 2 (DN, north) / 3 (DP, south): DP dives south first, DN goes straight to its pad
j2dn, j2dp = P('J2', '2'), P('J2', '3')                  # (148.73, 35.35), (148.73, 36.0); pads 1.35 long in x -> west end 148.055
poly(F, [(140.2, e4dp[1]), (141.4, e4dp[1] + 1.2), (146.5, e4dp[1] + 1.2), (147.2, j2dp[1]), (j2dp[0] - 0.675, j2dp[1])], 'USB2_CON_DP', W_USB)
poly(F, [(141.4, e4dn[1]), (147.0, j2dn[1]), (j2dn[0] - 0.675, j2dn[1])], 'USB2_CON_DN', W_USB)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
# length report per net and pair skew
L = collections.Counter()
for t in board.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T: L[t.GetNetname()] += ToMM(t.GetLength())
pairs = [('MIPI_DSI_D0N', 'MIPI_DSI_D0P'), ('MIPI_DSI_CLKN', 'MIPI_DSI_CLKP'), ('MIPI_DSI_D1N', 'MIPI_DSI_D1P'), ('USB1_DN', 'USB1_DP'), ('USB2_DN', 'USB2_DP'), ('USB1_CON_DN', 'USB1_CON_DP'), ('USB2_CON_DN', 'USB2_CON_DP')]
for a, b in pairs: print(f'{a[:-1]:16s} {L[a]:6.2f} / {L[b]:6.2f} mm   skew {L[b] - L[a]:+.2f} mm')
print('items added:', len(added))
