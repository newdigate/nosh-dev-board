"""Stage 2d (run with KiCad's bundled python3; edits Kicad/Nosh.kicad_pcb in place, back it up first): placement optimisation on the saved board.
Pins the USB chokes/ESD arrays on the bottom in line with the USB pairs and U2 beside the MIPI corridor, keeps routing corridors clear,
- test points move next to the net they probe
- free parts are re-placed near the centroid of their connections, trying 4 rotations, with wider spacing
- improvement sweeps: rotate / nudge each free part if its rats-nest length drops
Rats-nest length of a part = sum over its pads on non-plane nets of the distance to the nearest other pad of that net.
"""
import os, math, collections, json, sys
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
SCR = K + 'tools/'
W, H = 153.9, 81.8
GAP = 0.5                                   # courtyard to courtyard
PLANES = {'GND', '+3V3', 'SDRAM_3V3', 'WL_3V3', 'VDD_SOC_IN', '+5V'}
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
fps = {f.GetReference(): f for f in board.GetFootprints()}
u1 = fps['U1']; cx, cy = ToMM(u1.GetPosition().x), ToMM(u1.GetPosition().y)
_rm = [t for t in board.GetTracks() if not (abs(ToMM(t.GetPosition().x) - cx) < 7.0 and abs(ToMM(t.GetPosition().y) - cy) < 7.0)]
for t in _rm: board.Remove(t)
print('removed stale stitching items:', len(_rm))

FIXED = {r for r in fps if r.startswith(('J', 'SW', 'H', 'FID')) or r in ('U1', 'U9', 'U10', 'Y1', 'Y2', 'L3', 'L4', 'U4', 'U5', 'U2', 'R41', 'R42')}
# USB chokes and ESD arrays on the bottom, in line with the pairs, MCU-side choke pins (2, 3) facing west
def put(ref, x, y, rot, back):
    f = fps[ref]; f.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); f.SetOrientationDegrees(rot)
    if (f.GetLayer() == pcbnew.B_Cu) != back: f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)   # either way
    f.SetOrientationDegrees(rot)
for ref, (x, y) in (('L3', (136.4, 35.7)), ('L4', (136.4, 50.0))):
    put(ref, x, y, 0, True); f = fps[ref]
    px = {p.GetNumber(): ToMM(p.GetPosition().x) for p in f.Pads()}
    if px['2'] > px['1']: f.SetOrientationDegrees(180)          # pins 2/3 must be the west end
put('U4', 141.9, 35.35, 0, True); put('U5', 141.9, 49.25, 0, True)
put('U2', 78.5, 24.05, -90, False)
# SDRAM as on the EVKB (U13/U25 relative to U19): both TSOPs rot 270 (pins 1-27 on the north row, pin 1 at the east end),
# stacked north-south 32 mm west of the MCU; D0-D15 chip (U9) north, D16-D31 chip (U10) south; the address bus runs in the channel between
put('U9', 40.100, 24.850, -90, False); put('U10', 40.100, 48.850, -90, False)     # EVKB offsets rounded onto the 0.05 mm grid (pins at 29.70 + 0.8k)
put('R41', 54.0, 36.4, 180, False); put('R42', 54.0, 38.2, 180, False)  # clock series resistors at the channel's east end, between the two data bundles (pad 1 east)
ROT_ONLY = {'U2', 'U11', 'U12', 'U15', 'U6', 'U7', 'U8', 'U3', 'L1', 'L5'}
FREE = [r for r in fps if r not in FIXED and r not in ROT_ONLY]

def side(f): return 'bottom' if f.GetLayer() == pcbnew.B_Cu else 'top'
def tht(f): return any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in f.Pads())
def bbox(f):
    poly = f.GetCourtyard(pcbnew.B_CrtYd if side(f) == 'bottom' else pcbnew.F_CrtYd)
    bb = poly.BBox() if poly.OutlineCount() else f.GetBoundingBox(False, False)
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
def pads(f): return [(p.GetNetname(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in f.Pads()]

# ---- occupancy
occ = {'top': {}, 'bottom': {}}          # ref -> rect
def occupy(f):
    r = bbox(f)
    for s in (('top', 'bottom') if tht(f) else (side(f),)): occ[s][f.GetReference()] = r
def release(f):
    for s in occ: occ[s].pop(f.GetReference(), None)
KEEP = [(x - 2.5, y - 2.5, x + 2.5, y + 2.5) for (x, y) in ((3.3235, 4.4475), (150.5765, 4.4475), (150.5765, 77.3525), (3.3235, 77.3525))]
VIAFIELD = (cx - 7.2, cy - 7.2, cx + 7.2, cy + 7.2)       # bottom side: fan-out vias
M2CARD = (112.0, 8.0, 138.0, 42.0)                         # top: under the M.2 card, no test points
MCUZONE = (cx - 12.0, cy - 12.0, cx + 12.0, cy + 12.0)     # top: BGA escape zone, no test points
CORRIDOR = {'top': [(61.45, 6.0, 75.45, 34.6), (79.5, 35.5, 85.5, 40.5), (137.9, 33.0, 147.4, 38.5), (137.9, 47.5, 145.9, 52.5), (28.0, 31.4, 52.5, 42.4), (51.6, 15.5, 64.0, 57.0), (28.5, 16.9, 52.0, 18.4), (28.5, 55.4, 52.0, 56.6)],   # MIPI run; USB via landings; SDRAM channel, SDRAM approach from the BGA, via strips beside both outer pin rows
            'bottom': [(61.45, 5.0, 68.45, 19.0), (79.5, 33.0, 148.9, 52.5), (28.5, 16.9, 65.0, 56.6)]}                                                         # SDRAM: address links and outer data lanes under the chips, bottom approach              # MIPI vias/J7 approach; USB run; SDRAM data lanes on the bottom under U9/U10              # MIPI vias/J7 approach; USB run to the connectors
def free(rect, s, ref, is_tp=False):
    x0, y0, x1, y1 = rect
    if x0 < 1.0 or y0 < 1.0 or x1 > W - 1.0 or y1 > H - 1.0: return False
    for a0, b0, a1, b1 in KEEP + CORRIDOR[s] + ([VIAFIELD] if s == 'bottom' else []) + ([M2CARD, MCUZONE] if (is_tp and s == 'top') else []):
        if x0 < a1 and x1 > a0 and y0 < b1 and y1 > b0: return False
    for r2, (a0, b0, a1, b1) in occ[s].items():
        if r2 == ref: continue
        if x0 < a1 + GAP and x1 > a0 - GAP and y0 < b1 + GAP and y1 > b0 - GAP: return False
    return True
for f in fps.values(): occupy(f)

# ---- rats-nest cost
def net_pads(exclude_ref):
    d = collections.defaultdict(list); u1 = collections.defaultdict(list)
    for f in fps.values():
        if f.GetReference() == exclude_ref: continue
        for n, x, y in pads(f):
            if n and n not in PLANES and not n.startswith('unconnected'):
                (u1 if f.GetReference() == 'U1' else d)[n].append((x, y))
    if exclude_ref and exclude_ref.startswith('TP'):      # a test point belongs at the far end of its net, not on the BGA
        for n, pts in u1.items():
            if n not in d: d[n] = pts
    else:
        for n, pts in u1.items(): d[n].extend(pts)
    return d
def cost(f, npads):
    c = 0.0
    for n, x, y in pads(f):
        if n in PLANES or not n or n.startswith('unconnected'): continue
        pts = npads.get(n)
        if pts: c += min(math.hypot(x - a, y - b) for a, b in pts)
    return c
def ideal(f, npads):
    # mean of the NEAREST other pad on each of the part's signal nets (nearest to where the part is now),
    # so rails with many pads do not drag decoupling parts to the middle of the board
    xs, ys = [], []
    for n, x, y in pads(f):
        if n in PLANES or not n or n.startswith('unconnected'): continue
        pts = npads.get(n)
        if pts:
            a, b = min(pts, key=lambda q: math.hypot(x - q[0], y - q[1])); xs.append(a); ys.append(b)
    if not xs: return ToMM(f.GetPosition().x), ToMM(f.GetPosition().y)
    return sum(xs) / len(xs), sum(ys) / len(ys)
def setpos(f, x, y, rot): f.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); f.SetOrientationDegrees(rot)
def total_cost():
    npads_all = net_pads(None); t = 0.0
    for f in fps.values():
        for n, x, y in pads(f):
            if n in PLANES or not n or n.startswith('unconnected'): continue
            pts = [p for p in npads_all[n] if p != (x, y)]
            if pts: t += min(math.hypot(x - a, y - b) for a, b in pts)
    return t / 2
before = {r: cost(fps[r], net_pads(r)) for r in fps}
print('total rats-nest before: %.0f mm' % total_cost())

# ---- placement: free parts (ICs with most connections first, test points last)
def nconn(f): return sum(1 for n, x, y in pads(f) if n and n not in PLANES and not n.startswith('unconnected'))
order = sorted(FREE, key=lambda r: (r.startswith('TP'), -nconn(fps[r]), -(bbox(fps[r])[2] - bbox(fps[r])[0])))
def place_best(f, is_tp=False, nfree=14, rmax=45.0):
    ref = f.GetReference(); s = side(f); release(f)
    npads = net_pads(ref); ix, iy = ideal(f, npads)
    best = None; seen = 0
    for i in range(0, int(rmax / 0.5)):
        rad = 0.5 * i; n = max(1, int(2 * math.pi * rad / 0.6))
        for k in range(n):
            a = 2 * math.pi * k / n; x = round((ix + rad * math.cos(a)) * 4) / 4; y = round((iy + rad * math.sin(a)) * 4) / 4
            for rot in (0, 90, 180, 270):
                setpos(f, x, y, rot)
                if free(bbox(f), s, ref, is_tp):
                    c = cost(f, npads); seen += 1
                    if best is None or c < best[0]: best = (c, x, y, rot)
            if best and seen >= nfree: break
        if best and seen >= nfree: break
    if best: setpos(f, best[1], best[2], best[3])
    occupy(f); return best is not None
failed = [r for r in order if not place_best(fps[r], r.startswith('TP'))]
print('placed', len(order) - len(failed), 'free parts; failed:', failed)
# rotation-only parts: pick the best of 4 rotations in place
for r in ROT_ONLY:
    f = fps[r]; x, y = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y); release(f); npads = net_pads(r); best = None
    for rot in (0, 90, 180, 270):
        setpos(f, x, y, rot)
        if free(bbox(f), side(f), r):
            c = cost(f, npads)
            if best is None or c < best[0]: best = (c, rot)
    setpos(f, x, y, best[1] if best else 0); occupy(f)
# ---- improvement sweeps
for sweep in range(2):
    moved = 0
    for r in FREE:
        f = fps[r]; s = side(f); x0, y0, r0 = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y), f.GetOrientationDegrees()
        release(f); npads = net_pads(r); best = (cost(f, npads), x0, y0, r0)
        for dx, dy in ((0, 0), (0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5), (1, 0), (-1, 0), (0, 1), (0, -1), (1.5, 0), (-1.5, 0), (0, 1.5), (0, -1.5)):
            for rot in (0, 90, 180, 270):
                setpos(f, x0 + dx, y0 + dy, rot)
                if free(bbox(f), s, r, r.startswith('TP')):
                    c = cost(f, npads)
                    if c < best[0] - 0.05: best = (c, x0 + dx, y0 + dy, rot)
        setpos(f, best[1], best[2], best[3]); occupy(f)
        if (best[1], best[2], best[3]) != (x0, y0, r0): moved += 1
    print('sweep', sweep + 1, 'moved', moved)
after = {r: cost(fps[r], net_pads(r)) for r in fps}
print('total rats-nest after: %.0f mm' % total_cost())
# reference labels: keep small-part refs on fab, others above the courtyard (as in stage 1)
for f in fps.values():
    ref = f.Reference(); x0, y0, x1, y1 = bbox(f); back = side(f) == 'bottom'
    if ref.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        ref.SetTextAngleDegrees(0); ref.SetPosition(VECTOR2I(FromMM((x0 + x1) / 2), FromMM((y1 + 0.8) if back else (y0 - 0.8))))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
worst = sorted(after.items(), key=lambda kv: -kv[1])[:15]
print('largest rats-nest after (mm):', [(r, round(c, 1), round(before[r], 1)) for r, c in worst])
json.dump({'before': before, 'after': after}, open(SCR + 'ratsnest.json', 'w'))
print('saved')
