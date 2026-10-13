"""Local links (run with KiCad's bundled python3): close the short ratsnest lines of a DRC report with a straight
track, or with a via and two short tracks when the two ends sit on different layers (a decoupling cap under its
test point or ferrite, a connector shell tab, a pad beside the end of a locked track).
usage: local_links.py in.kicad_pcb out.kicad_pcb drc.json [max_mm] [NET,NET...]
Every unconnected pair of the report whose ends lie within max_mm (default 3; 5 for the USB shield nets) is tried:
first a track on a layer both ends share (0.2 mm, 0.15 mm for signal nets) that clears other copper by the board's
rules, else the nearest free via site round the midpoint (0.45/0.3 mm; not inside another net's PWR island, not in
a pad, hole-to-copper 0.2 mm) with a track from each end. Nothing is ripped up; new items are locked. The pairs are
a spanning tree, so closing them never doubles a connection; rerun the DRC afterwards for the pairs that are left."""
import sys, re, math, json, collections, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT, DRC = sys.argv[1], sys.argv[2], sys.argv[3]; MAXD = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
ONLY = set(sys.argv[5].split(',')) if len(sys.argv) > 5 else None
VIA_D, VIA_H, CLR, PAD_CLR, PTH_CLR, HOLE_CLR, SAME_HOLE = 0.45, 0.30, 0.10, 0.127, 0.20, 0.20, 0.554
POWER = re.compile(r'^(GND$|\+|VDD|NVCC|DCDC|SDRAM_3V3|WL_3V3|USB\d_VBUS|ADC_VREFH|USB\d_SHIELD)')
b = pcbnew.LoadBoard(IN); LAYS = [pcbnew.F_Cu, b.GetLayerID('SIG'), pcbnew.B_Cu]; PWR = b.GetLayerID('PWR')
allz = list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]
novia = [z for z in allz if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
notrk = [(z, [l for l in LAYS if z.IsOnLayer(l)]) for z in allz if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
narrow = [(z, z.GetNetname()) for z in allz if not z.GetIsRuleArea() and z.IsOnLayer(PWR) and z.GetNetname() in ('DCDC_IN', 'DCDC_ANA', 'DCDC_DIG', 'VDD_SOC_IN')]   # 1.1 mm lobes: a foreign via cuts them
eb = b.GetBoardEdgesBoundingBox(); EX0, EY0, EX1, EY1 = ToMM(eb.GetLeft()) + 0.6, ToMM(eb.GetTop()) + 0.6, ToMM(eb.GetRight()) - 0.6, ToMM(eb.GetBottom()) - 0.6
B = 1.0; buck = collections.defaultdict(list)
def cells(x0, y0, x1, y1, m):
    for i in range(int((min(x0, x1) - m) // B), int((max(x0, x1) + m) // B) + 1):
        for j in range(int((min(y0, y1) - m) // B), int((max(y0, y1) + m) // B) + 1): yield i, j
tracks = collections.defaultdict(list)                                                    # (net, layer) -> [(x0,y0,x1,y1)]
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        for i, j in cells(x, y, x, y, 1.0): buck[('via', None, i, j)].append((t.GetNetname(), x, y, ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, ToMM(t.GetDrill()) / 2))
    elif t.GetLayer() in LAYS:
        x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
        tracks[(t.GetNetname(), t.GetLayer())].append((x0, y0, x1, y1))
        for i, j in cells(x0, y0, x1, y1, 1.0): buck[('trk', t.GetLayer(), i, j)].append((t.GetNetname(), x0, y0, x1, y1, ToMM(t.GetWidth()) / 2))
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox(); r = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        pth = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH); ref = f.GetReference() + '.' + p.GetNumber()
        net = p.GetNetname() if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH else ''
        dr = ToMM(p.GetDrillSize().x) / 2 if pth else 0.0; cx, cy = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        for l in (LAYS if pth else [l for l in LAYS if p.IsOnLayer(l)]):
            for i, j in cells(r[0], r[1], r[2], r[3], 1.0): buck[('pad', l, i, j)].append((net, r, pth, ref, cx, cy, dr))
def pt_seg(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / L2)); return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
def seg_seg(a, b_, c, d):
    def cross(o, p, q): return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b_, c) * cross(a, b_, d) < 0) and (cross(c, d, a) * cross(c, d, b_) < 0): return 0.0
    return min(pt_seg(*a, *c, *d), pt_seg(*b_, *c, *d), pt_seg(*c, *a, *b_), pt_seg(*d, *a, *b_))
def seg_rect(a, b_, r):
    x0, y0, x1, y1 = r
    if (x0 <= a[0] <= x1 and y0 <= a[1] <= y1) or (x0 <= b_[0] <= x1 and y0 <= b_[1] <= y1): return 0.0
    return min(seg_seg(a, b_, e0, e1) for e0, e1 in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))))
WHYC = collections.Counter()
def WHY(r): WHYC[r] += 1; return False
def via_ok(net, x, y):
    if not (EX0 <= x <= EX1 and EY0 <= y <= EY1): return WHY('edge')
    P = VECTOR2I(FromMM(x), FromMM(y))
    if any(z.Outline().Collide(P, FromMM(VIA_D / 2 + CLR)) for z in novia): return WHY('no-via area')
    R = VIA_D / 2 + 0.2
    for z, zn in narrow:
        if zn == net or not z.Outline().Collide(P, FromMM(R)): continue
        if z.Outline().Contains(P):                                                            # inside: fine in a wide region, not in a lobe
            ok = lambda dx, dy: z.Outline().Contains(VECTOR2I(FromMM(x + dx), FromMM(y + dy)))
            if not ((ok(R + 0.5, 0) or ok(-R - 0.5, 0)) and (ok(0, R + 0.5) or ok(0, -R - 0.5))): return WHY('PWR island')
        elif z.Outline().Collide(P, FromMM(R - 0.2)): return WHY("PWR island")               # outside: a bite of 0.2 mm at most (lobes stay >= 0.9 mm)
    i, j = int(x // B), int(y // B)
    for n2, vx, vy, vr, vh in buck.get(('via', None, i, j), ()):
        if math.hypot(x - vx, y - vy) < (SAME_HOLE if n2 == net else max(VIA_D / 2 + vr + PAD_CLR, VIA_H / 2 + vh + HOLE_CLR)): return WHY('via')
    for l in LAYS:
        for n2, x0, y0, x1, y1, hw in buck.get(('trk', l, i, j), ()):
            if n2 != net and pt_seg(x, y, x0, y0, x1, y1) < max(VIA_D / 2 + CLR, VIA_H / 2 + HOLE_CLR) + hw: return WHY('trk ' + b.GetLayerName(l))
        for n2, r, pth, ref, cx, cy, dr in buck.get(('pad', l, i, j), ()):
            qx, qy = min(max(x, r[0]), r[2]), min(max(y, r[1]), r[3]); d = math.hypot(x - qx, y - qy)
            if n2 != net and d < max(VIA_D / 2 + (PTH_CLR if pth else PAD_CLR), VIA_H / 2 + HOLE_CLR): return WHY('pad')
            if n2 == net and not pth and d < VIA_H / 2 + 0.05: return WHY('own pad')                                      # the hole stays outside the pad copper
            if pth and math.hypot(x - cx, y - cy) < VIA_H / 2 + dr + (0.254 if n2 == net else HOLE_CLR): return WHY('hole')
    return True
def track_ok(net, layer, a, c, w):
    if any(layer in ls and (z.Outline().Collide(VECTOR2I(FromMM(a[0]), FromMM(a[1])), FromMM(w / 2)) or z.Outline().Collide(VECTOR2I(FromMM(c[0]), FromMM(c[1])), FromMM(w / 2))) for z, ls in notrk): return WHY('no-track area')
    for i, j in cells(a[0], a[1], c[0], c[1], 0.0):
        for n2, x0, y0, x1, y1, hw in buck.get(('trk', layer, i, j), ()):
            if n2 != net and seg_seg(a, c, (x0, y0), (x1, y1)) < w / 2 + hw + CLR: return WHY('trk ' + b.GetLayerName(layer))
        for n2, r, pth, ref, cx, cy, dr in buck.get(('pad', layer, i, j), ()):
            if n2 != net and seg_rect(a, c, r) < w / 2 + (PTH_CLR if pth else PAD_CLR): return WHY('pad ' + ref)
        for n2, vx, vy, vr, vh in buck.get(('via', None, i, j), ()):
            if n2 != net and pt_seg(vx, vy, *a, *c) < w / 2 + vr + CLR: return WHY('via')
    return True
# ---- the report's open pairs
LNAME = {b.GetLayerName(l): l for l in LAYS}
def end(it):
    d = it['description']; net = d.split('[')[1].split(']')[0]; x, y = it['pos']['x'], it['pos']['y']
    m = re.search(r' on ([A-Za-z0-9_.]+)', d); kind = d.split(' [')[0]
    if kind.startswith('Via') or kind.startswith('PTH') or kind.startswith('Through'): lays = list(LAYS)
    elif m and m.group(1) in LNAME: lays = [LNAME[m.group(1)]]
    else: lays = list(LAYS)
    if kind.startswith('Track') and len(lays) == 1:                                       # snap to the nearest end of that track
        best = min(((math.hypot(x - ex, y - ey), ex, ey) for x0, y0, x1, y1 in tracks.get((net, lays[0]), ()) for ex, ey in ((x0, y0), (x1, y1))), default=None)
        if best and best[0] < 0.3: x, y = best[1], best[2]
    return net, (round(x, 3), round(y, 3)), lays, kind + (' ' + d.split(' of ')[1].split(' on ')[0] if ' of ' in d else '')
pairs = []
for v in json.load(open(DRC))['unconnected_items']:
    na, pa, la, ka = end(v['items'][0]); nb, pb, lb, kb = end(v['items'][1])
    if na != nb or (ONLY and na not in ONLY): continue
    d = math.hypot(pa[0] - pb[0], pa[1] - pb[1]); lim = 5.0 if na.endswith('_SHIELD') else MAXD
    if d <= lim: pairs.append((d, na, pa, la, ka, pb, lb, kb))
nets_by_name = b.GetNetInfo().NetsByName(); new_items = []; done = collections.Counter(); left = []
def add_track(net, layer, a, c, w):
    if math.hypot(a[0] - c[0], a[1] - c[1]) < 0.02: return
    t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1]))); t.SetEnd(VECTOR2I(FromMM(c[0]), FromMM(c[1]))); t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNet(nets_by_name[net]); t.SetLocked(True); new_items.append(t)
    for i, j in cells(a[0], a[1], c[0], c[1], 1.0): buck[('trk', layer, i, j)].append((net, a[0], a[1], c[0], c[1], w / 2))
def add_via(net, x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_H)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets_by_name[net]); v.SetLocked(True); new_items.append(v)
    for i, j in cells(x, y, x, y, 1.0): buck[('via', None, i, j)].append((net, x, y, VIA_D / 2, VIA_H / 2))
ORDER = [pcbnew.F_Cu, pcbnew.B_Cu, b.GetLayerID('SIG')]
for d, net, a, la, ka, c, lb, kb in sorted(pairs, key=lambda q: q[0]):
    w = 0.2 if POWER.match(net) else 0.15; WHYC.clear(); how = None
    for L in ORDER:                                                                        # a shared layer first: straight, then an L
        if L in la and L in lb and track_ok(net, L, a, c, w): add_track(net, L, a, c, w); how = 'track ' + b.GetLayerName(L); break
        if L in la and L in lb:
            for k in ((a[0], c[1]), (c[0], a[1])):
                if track_ok(net, L, a, k, w) and track_ok(net, L, k, c, w): add_track(net, L, a, k, w); add_track(net, L, k, c, w); how = 'L-track ' + b.GetLayerName(L); break
            if how: break
    if not how:                                                                            # else a via beside the midpoint
        mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2; LA = [L for L in ORDER if L in la]; LB = [L for L in ORDER if L in lb]
        for r in [k * 0.05 for k in range(0, 41)]:
            n = max(1, int(2 * math.pi * r / 0.1)); hit = None
            for k in range(n):
                th = 2 * math.pi * k / n; x, y = round(mx + r * math.cos(th), 2), round(my + r * math.sin(th), 2)
                if not via_ok(net, x, y): continue
                for L1 in LA:
                    for L2 in LB:
                        if track_ok(net, L1, a, (x, y), w) and track_ok(net, L2, (x, y), c, w): hit = (x, y, L1, L2); break
                    if hit: break
                if hit: break
            if hit: x, y, L1, L2 = hit; add_via(net, x, y); add_track(net, L1, a, (x, y), w); add_track(net, L2, (x, y), c, w); how = 'via (%.2f,%.2f)' % (x, y); break
    if how: done[net] += 1; print('  %-13s %s (%.2f,%.2f) - %s (%.2f,%.2f)  %.2f mm  %s' % (net, ka, *a, kb, *c, d, how))
    else: left.append('%s %s-%s %.1f mm: %s' % (net, ka, kb, d, WHYC.most_common(3)))
for it in new_items: b.Add(it)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b)
print('links made: %d of %d pairs within reach (%s) -> %s' % (sum(done.values()), len(pairs), dict(done), OUT))
for l in left: print('  failed  ' + l)
