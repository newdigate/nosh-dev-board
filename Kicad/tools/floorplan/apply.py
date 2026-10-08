"""Apply a macro placement (place.py json) to a copy of the board, move the MCU fan-out with U1, re-place the
passives / test points with the detail optimiser, save, and report the full rats-nest (same metric as before).
usage: apply.py <placement.json> <out.kicad_pcb>"""
import os, math, collections, json, sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..') + '/'
PL = json.load(open(sys.argv[1])); OUT = sys.argv[2]
W, H = 155.0, 83.5; GAP = 0.5
PLANES = {'GND', '+3V3', 'SDRAM_3V3', 'WL_3V3', 'VDD_SOC_IN', '+5V'}
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
fps = {f.GetReference(): f for f in board.GetFootprints()}
u1 = fps['U1']; ox, oy, orot = ToMM(u1.GetPosition().x), ToMM(u1.GetPosition().y), u1.GetOrientationDegrees()
# 1. macro positions
for r, (x, y, rot) in PL['state'].items():
    f = fps[r]
    if r.startswith(('H', 'FID', 'J7')) and r != 'H5': continue                      # fixed items keep their side and place
    if f.GetLayer() == pcbnew.B_Cu: f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)   # macro model is top-side
    f.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); f.SetOrientationDegrees(rot)
# 2. fan-out items follow U1 (translate + rotate about the old centre)
nx, ny, nrot = ToMM(u1.GetPosition().x), ToMM(u1.GetPosition().y), u1.GetOrientationDegrees()
drot = nrot - orot; th = math.radians(drot); c, s = math.cos(th), math.sin(th)
def xf(p):
    dx, dy = ToMM(p.x) - ox, ToMM(p.y) - oy
    return VECTOR2I(FromMM(nx + dx * c + dy * s), FromMM(ny - dx * s + dy * c))
moved = 0
for t in board.GetTracks():
    if abs(ToMM(t.GetPosition().x) - ox) < 7.5 and abs(ToMM(t.GetPosition().y) - oy) < 7.5:
        if t.Type() == pcbnew.PCB_VIA_T: t.SetPosition(xf(t.GetPosition()))
        else: t.SetStart(xf(t.GetStart())); t.SetEnd(xf(t.GetEnd()))
        moved += 1
    else: board.Remove(t)
print('fan-out items moved with U1:', moved, '| U1 now', (nx, ny, nrot))
cx, cy = nx, ny
FIXED = set(PL['state']) | {r for r in fps if r.startswith(('H', 'FID'))}
ROT_ONLY = set()
FREE = [r for r in fps if r not in FIXED]
def side(f): return 'bottom' if f.GetLayer() == pcbnew.B_Cu else 'top'
def tht(f): return any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in f.Pads())
def bbox(f):
    poly = f.GetCourtyard(pcbnew.B_CrtYd if side(f) == 'bottom' else pcbnew.F_CrtYd)
    bb = poly.BBox() if poly.OutlineCount() else f.GetBoundingBox(False, False)
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
def pads(f): return [(p.GetNetname(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in f.Pads()]
occ = {'top': {}, 'bottom': {}}
def occupy(f):
    r = bbox(f)
    for s_ in (('top', 'bottom') if tht(f) else (side(f),)): occ[s_][f.GetReference()] = r
def release(f):
    for s_ in occ: occ[s_].pop(f.GetReference(), None)
KEEP = [(x - 2.5, y - 2.5, x + 2.5, y + 2.5) for (x, y) in ((3.8735, 5.2975), (151.1265, 5.2975), (151.1265, 78.2025), (3.8735, 78.2025))]
VIAFIELD = (cx - 7.2, cy - 7.2, cx + 7.2, cy + 7.2)
MCUZONE = (cx - 12.0, cy - 12.0, cx + 12.0, cy + 12.0)
# M.2 card region from J6 (local lx in [-11,11], ly in [0,32])
j6 = fps['J6']; jx, jy, jr = ToMM(j6.GetPosition().x), ToMM(j6.GetPosition().y), j6.GetOrientationDegrees(); tj = math.radians(jr)
cpts = [(jx + lx * math.cos(tj) + ly * math.sin(tj), jy - lx * math.sin(tj) + ly * math.cos(tj)) for lx, ly in ((-11, 0), (11, 0), (11, 32), (-11, 32))]
M2CARD = (min(p[0] for p in cpts), min(p[1] for p in cpts), max(p[0] for p in cpts), max(p[1] for p in cpts))
# J7 region: nothing on the bottom under the FPC connector's neighbourhood (its pads) is handled by occupancy; on top keep TPs away
def free(rect, s_, ref, is_tp=False):
    x0, y0, x1, y1 = rect
    if x0 < 1.0 or y0 < 1.0 or x1 > W - 1.0 or y1 > H - 1.0: return False
    for a0, b0, a1, b1 in KEEP + ([VIAFIELD] if s_ == 'bottom' else []) + ([M2CARD, MCUZONE] if (is_tp and s_ == 'top') else []):
        if x0 < a1 and x1 > a0 and y0 < b1 and y1 > b0: return False
    for r2, (a0, b0, a1, b1) in occ[s_].items():
        if r2 == ref: continue
        if x0 < a1 + GAP and x1 > a0 - GAP and y0 < b1 + GAP and y1 > b0 - GAP: return False
    return True
for f in fps.values(): occupy(f)
def net_pads(exclude_ref):
    d = collections.defaultdict(list); u1p = collections.defaultdict(list)
    for f in fps.values():
        if f.GetReference() == exclude_ref: continue
        for n, x, y in pads(f):
            if n and n not in PLANES and not n.startswith('unconnected'):
                (u1p if f.GetReference() == 'U1' else d)[n].append((x, y))
    if exclude_ref and exclude_ref.startswith('TP'):
        for n, pts in u1p.items():
            if n not in d: d[n] = pts
    else:
        for n, pts in u1p.items(): d[n].extend(pts)
    return d
def cost(f, npads):
    c_ = 0.0
    for n, x, y in pads(f):
        if n in PLANES or not n or n.startswith('unconnected'): continue
        pts = npads.get(n)
        if pts: c_ += min(math.hypot(x - a, y - b) for a, b in pts)
    return c_
def ideal(f, npads):
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
def nconn(f): return sum(1 for n, x, y in pads(f) if n and n not in PLANES and not n.startswith('unconnected'))
order = sorted(FREE, key=lambda r: (r.startswith('TP'), -nconn(fps[r]), -(bbox(fps[r])[2] - bbox(fps[r])[0])))
def place_best(f, is_tp=False, nfree=14, rmax=45.0):
    ref = f.GetReference(); s_ = side(f); release(f)
    npads = net_pads(ref); ix, iy = ideal(f, npads)
    best = None; seen = 0
    for i in range(0, int(rmax / 0.5)):
        rad = 0.5 * i; n = max(1, int(2 * math.pi * rad / 0.6))
        for k in range(n):
            a = 2 * math.pi * k / n; x = round((ix + rad * math.cos(a)) * 4) / 4; y = round((iy + rad * math.sin(a)) * 4) / 4
            for rot in (0, 90, 180, 270):
                setpos(f, x, y, rot)
                if free(bbox(f), s_, ref, is_tp):
                    c_ = cost(f, npads); seen += 1
                    if best is None or c_ < best[0]: best = (c_, x, y, rot)
            if best and seen >= nfree: break
        if best and seen >= nfree: break
    if best: setpos(f, best[1], best[2], best[3])
    occupy(f); return best is not None
failed = [r for r in order if not place_best(fps[r], r.startswith('TP'))]
print('placed', len(order) - len(failed), 'free parts; failed:', failed)
for sweep in range(2):
    moved = 0
    for r in FREE:
        f = fps[r]; s_ = side(f); x0, y0, r0 = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y), f.GetOrientationDegrees()
        release(f); npads = net_pads(r); best = (cost(f, npads), x0, y0, r0)
        for dx, dy in ((0, 0), (0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5), (1, 0), (-1, 0), (0, 1), (0, -1), (1.5, 0), (-1.5, 0), (0, 1.5), (0, -1.5)):
            for rot in (0, 90, 180, 270):
                setpos(f, x0 + dx, y0 + dy, rot)
                if free(bbox(f), s_, r, r.startswith('TP')):
                    c_ = cost(f, npads)
                    if c_ < best[0] - 0.05: best = (c_, x0 + dx, y0 + dy, rot)
        setpos(f, best[1], best[2], best[3]); occupy(f)
        if (best[1], best[2], best[3]) != (x0, y0, r0): moved += 1
    print('sweep', sweep + 1, 'moved', moved)
for f in fps.values():
    ref = f.Reference(); x0, y0, x1, y1 = bbox(f); back = side(f) == 'bottom'
    if ref.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        ref.SetTextAngleDegrees(0); ref.SetPosition(VECTOR2I(FromMM((x0 + x1) / 2), FromMM((y1 + 0.8) if back else (y0 - 0.8))))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(OUT, board)
print('TOTAL rats-nest: %.0f mm' % total_cost(), '| saved', OUT)
