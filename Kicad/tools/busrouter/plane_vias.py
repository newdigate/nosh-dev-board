"""Plane-via placer (run with KiCad's bundled python3): a via into the plane for every pad of a plane net that
is not yet connected to it, wherever one fits.
usage: plane_vias.py in.kicad_pcb out.kicad_pcb [NET,NET...]
Plane nets are those with a filled zone on GND1 / PWR / GND2. For each SMD pad of such a net whose connected copper
holds no via inside the plane, the 0.05 mm grid round the pad (out to 3 mm) is searched, nearest first, for a via
site that lies inside the net's filled plane, keeps 0.1 mm from other nets' tracks and vias (0.2 mm from holes),
0.127 mm from other nets' pads (0.2 mm from through-hole pads), 0.554 mm from the net's own vias, is outside
no-via rule areas, and can be reached from the pad by a straight track on the pad's layer that is clear of other
copper. The via is 0.45/0.3 mm, the track 0.15 mm (0.2 mm for the DC-DC and VDD_SOC nets). New items are locked.
"""
import sys, math, collections, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]; ONLY = set(sys.argv[3].split(',')) if len(sys.argv) > 3 else None
VIA_D, VIA_H, CLR, PAD_CLR, PTH_CLR, HOLE_CLR, SAME_HOLE = 0.45, 0.30, 0.10, 0.127, 0.20, 0.20, 0.554
WIDE = ('DCDC_IN', 'DCDC_ANA', 'DCDC_DIG', 'VDD_SOC_IN')
b = pcbnew.LoadBoard(IN); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
LAYS = [pcbnew.F_Cu, b.GetLayerID('SIG'), pcbnew.B_Cu]; PLANE_L = [b.GetLayerID(n) for n in ('GND1', 'PWR', 'GND2')]
planes = collections.defaultdict(list)
for z in b.Zones():
    if z.GetIsRuleArea() or not z.GetNetname(): continue
    for l in PLANE_L:
        if z.IsOnLayer(l):
            ps = z.GetFilledPolysList(l)
            if ps.OutlineCount(): planes[z.GetNetname()].append((ps, max(range(ps.OutlineCount()), key=lambda i: ps.Outline(i).Area())))   # the main outline only: islands of fill round a stray via do not count
def in_plane(net, x, y): return any(ps.Contains(VECTOR2I(FromMM(x), FromMM(y)), main) for ps, main in planes.get(net, ()))
novia = [z for z in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
def in_novia(x, y, own_plane=False): return any(z.Outline().Collide(VECTOR2I(FromMM(x), FromMM(y)), FromMM(VIA_D / 2 + CLR)) for z in novia if not (own_plane and z.GetZoneName() == 'KO_DCDC_JOG'))
eb = b.GetBoardEdgesBoundingBox(); EX0, EY0, EX1, EY1 = ToMM(eb.GetLeft()) + 0.6, ToMM(eb.GetTop()) + 0.6, ToMM(eb.GetRight()) - 0.6, ToMM(eb.GetBottom()) - 0.6
# ---- spatial buckets of copper: tracks per layer, vias, pads per layer
B = 1.0
buck = collections.defaultdict(list)                         # (kind, layer, i, j) -> items
def cells(x0, y0, x1, y1, m):
    for i in range(int((min(x0, x1) - m) // B), int((max(x0, x1) + m) // B) + 1):
        for j in range(int((min(y0, y1) - m) // B), int((max(y0, y1) + m) // B) + 1): yield i, j
own_vias = collections.defaultdict(list)
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y); own_vias[t.GetNetname()].append((x, y))
        for i, j in cells(x, y, x, y, 1.0): buck[('via', None, i, j)].append((t.GetNetname(), x, y, ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, ToMM(t.GetDrill()) / 2))
    elif t.GetLayer() in LAYS:
        x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
        for i, j in cells(x0, y0, x1, y1, 1.0): buck[('trk', t.GetLayer(), i, j)].append((t.GetNetname(), x0, y0, x1, y1, ToMM(t.GetWidth()) / 2))
pad_of = {}
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox(); r = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        pth = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        for l in (LAYS if pth else [l for l in LAYS if p.IsOnLayer(l)]):
            for i, j in cells(r[0], r[1], r[2], r[3], 1.0): buck[('pad', l, i, j)].append((p.GetNetname() if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH else '', r, pth, f.GetReference() + '.' + p.GetNumber()))
        pad_of[f.GetReference() + '.' + p.GetNumber()] = p
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
def via_ok(net, x, y, own_pad):
    if not (EX0 <= x <= EX1 and EY0 <= y <= EY1): return WHY('edge')
    if not in_plane(net, x, y): return WHY('no plane')
    if in_novia(x, y, True): return WHY('no-via area')
    i, j = int(x // B), int(y // B)
    for it in buck.get(('via', None, i, j), ()):
        n2, vx, vy, vr, vh = it; d = math.hypot(x - vx, y - vy)
        if d < (SAME_HOLE if n2 == net else max(VIA_D / 2 + vr + PAD_CLR, VIA_H / 2 + vh + HOLE_CLR)): return WHY('via ' + n2)
    for l in LAYS:
        for n2, x0, y0, x1, y1, hw in buck.get(('trk', l, i, j), ()):
            if n2 != net and pt_seg(x, y, x0, y0, x1, y1) < max(VIA_D / 2 + CLR, VIA_H / 2 + HOLE_CLR) + hw: return WHY('trk %s %s' % (b.GetLayerName(l), n2))   # hole-to-copper 0.2 is the tighter rule
        for n2, r, pth, ref in buck.get(('pad', l, i, j), ()):
            cx, cy = min(max(x, r[0]), r[2]), min(max(y, r[1]), r[3]); d = math.hypot(x - cx, y - cy)
            if n2 != net and d < max(VIA_D / 2 + (PTH_CLR if pth else PAD_CLR), VIA_H / 2 + HOLE_CLR): return WHY('pad ' + ref)
            if n2 == net and ref != own_pad and d < VIA_D / 2 + 0.05 and pth: return WHY('own pth')
    return True
WHYC = collections.Counter(); DEBUG = __import__('os').environ.get('DEBUG')
def WHY(r):
    WHYC[r] += 1; return False
def track_ok(net, layer, a, c, w):
    for i, j in cells(a[0], a[1], c[0], c[1], 0.0):
        for n2, x0, y0, x1, y1, hw in buck.get(('trk', layer, i, j), ()):
            if n2 != net and seg_seg(a, c, (x0, y0), (x1, y1)) < w / 2 + hw + CLR: return WHY('track vs trk ' + n2)
        for n2, r, pth, ref in buck.get(('pad', layer, i, j), ()):
            if n2 != net and seg_rect(a, c, r) < w / 2 + (PTH_CLR if pth else PAD_CLR): return WHY('track vs pad ' + ref)
        for n2, vx, vy, vr, vh in buck.get(('via', None, i, j), ()):
            if n2 != net and pt_seg(vx, vy, *a, *c) < w / 2 + vr + CLR: return WHY('track vs via ' + n2)
    return True
# ---- which pads need a via: connected copper without a via inside the plane
b.BuildConnectivity(); conn = b.GetConnectivity()
def cluster_has_plane_via(p, net):
    seen = {p.m_Uuid.AsString()}; todo = [p]
    while todo:
        x = todo.pop()
        for y in conn.GetConnectedItems(x):
            y = y.Cast()
            if y.Type() == pcbnew.PCB_ZONE_T: continue
            k = y.m_Uuid.AsString()
            if k in seen: continue
            seen.add(k)
            if y.Type() == pcbnew.PCB_VIA_T and in_plane(net, ToMM(y.GetPosition().x), ToMM(y.GetPosition().y)): return True
            if y.Type() == pcbnew.PCB_PAD_T and y.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and in_plane(net, ToMM(y.GetPosition().x), ToMM(y.GetPosition().y)): return True
            todo.append(y)
    return False
nets_by_name = b.GetNetInfo().NetsByName(); placed = collections.Counter(); failed = []; new_items = []
for f in b.GetFootprints():
    for p in f.Pads():
        net = p.GetNetname()
        if net not in planes or (ONLY and net not in ONLY) or p.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_PTH): continue
        pth = p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
        if pth and in_plane(net, ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)): continue       # a through-hole pad inside its plane is connected already
        if cluster_has_plane_via(p, net): continue
        ref = f.GetReference() + '.' + p.GetNumber(); layer = pcbnew.F_Cu if (pth or not f.IsFlipped()) else pcbnew.B_Cu
        px, py = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y); w = 0.2 if net in WIDE else 0.15
        best = None; WHYC.clear()
        for r in [k * 0.05 for k in range(6, 61)]:                                   # rings 0.3 .. 3.0 mm
            n = max(8, int(2 * math.pi * r / 0.1))
            for k in range(n):
                a = 2 * math.pi * k / n; x, y = round(px + r * math.cos(a), 2), round(py + r * math.sin(a), 2)
                if via_ok(net, x, y, ref) and track_ok(net, layer, (px, py), (x, y), w): best = (x, y); break
            if best: break
        if not best:
            failed.append(ref + ' ' + net)
            if DEBUG and ref in DEBUG.split(','): print('  %s: no site; rejections %s' % (ref, WHYC.most_common(8)))
            continue
        x, y = best; ni = nets_by_name[net]
        v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_H)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(ni); v.SetLocked(True); new_items.append(v)
        t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(FromMM(px), FromMM(py))); t.SetEnd(VECTOR2I(FromMM(x), FromMM(y))); t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNet(ni); t.SetLocked(True); new_items.append(t)
        for i, j in cells(x, y, x, y, 1.0): buck[('via', None, i, j)].append((net, x, y, VIA_D / 2, VIA_H / 2))
        for i, j in cells(px, py, x, y, 1.0): buck[('trk', layer, i, j)].append((net, px, py, x, y, w / 2))
        placed[net] += 1
for it in new_items: b.Add(it)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b)
print('plane vias placed: %s (total %d) -> %s' % (dict(placed), sum(placed.values()), OUT))
print('no site within 3 mm: %d %s' % (len(failed), failed[:40]))
