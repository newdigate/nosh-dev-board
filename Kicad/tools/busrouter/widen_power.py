"""Widen the power-net tracks wherever the neighbours allow (run with KiCad's bundled python3).
usage: widen_power.py in.kicad_pcb out.kicad_pcb [max_width_mm]
Every F.Cu/B.Cu segment of a power net that lies outside U1's ball field is set to the widest width (in 0.05 mm
steps, up to max_width, default 0.3) that keeps 0.1 mm from other nets' tracks, vias and pads (0.2 mm from
through-hole pads). Segments inside the field keep their width. Run DRC afterwards."""
import sys, re, math, pcbnew
from pcbnew import FromMM, ToMM
IN, OUT = sys.argv[1], sys.argv[2]; MAXW = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3
POWER = re.compile(r'^(GND$|\+|VDD|NVCC|DCDC_(IN|DIG|ANA|LP|LN)$|SDRAM_3V3|WL_3V3|USB\d_VBUS|ADC_VREFH)')
CLR, PTH_CLR = 0.10, 0.20
b = pcbnew.LoadBoard(IN)
u1 = next(f for f in b.GetFootprints() if f.GetReference() == 'U1'); ub = u1.GetBoundingBox()
FX0, FY0, FX1, FY1 = ToMM(ub.GetLeft()) - 0.3, ToMM(ub.GetTop()) - 0.3, ToMM(ub.GetRight()) + 0.3, ToMM(ub.GetBottom()) + 0.3
def seg_seg(a, b_, c, d):
    """distance between segments a-b and c-d"""
    def pt_seg(p, s, e):
        dx, dy = e[0] - s[0], e[1] - s[1]; L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((p[0] - s[0]) * dx + (p[1] - s[1]) * dy) / L2))
        return math.hypot(p[0] - (s[0] + t * dx), p[1] - (s[1] + t * dy))
    def cross(o, p, q): return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b_, c) * cross(a, b_, d) < 0) and (cross(c, d, a) * cross(c, d, b_) < 0): return 0.0
    return min(pt_seg(a, c, d), pt_seg(b_, c, d), pt_seg(c, a, b_), pt_seg(d, a, b_))
def seg_rect(a, b_, r):
    x0, y0, x1, y1 = r
    if True:
        edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
        inside = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
        if inside(a) or inside(b_): return 0.0
        return min(seg_seg(a, b_, e0, e1) for e0, e1 in edges)
# obstacles per layer: (kind, geometry, half-width/extra clearance)
tracks = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}; vias = []; pads = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T: vias.append((t.GetNetname(), (ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
    elif t.GetLayer() in tracks: tracks[t.GetLayer()].append([t.GetNetname(), (ToMM(t.GetStart().x), ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)), ToMM(t.GetWidth()) / 2, t])
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox(); r = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        pth = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        for l in pads:
            if p.IsOnLayer(l) or pth: pads[l].append((p.GetNetname() if not pth or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else '', r, PTH_CLR if pth else CLR))
changed = 0; widths = {}
for l, segs in tracks.items():
    for seg in segs:
        net, a, c, hw, t = seg
        if not POWER.match(net): continue
        if FX0 <= a[0] <= FX1 and FY0 <= a[1] <= FY1 and FX0 <= c[0] <= FX1 and FY0 <= c[1] <= FY1: continue   # inside the field
        room = MAXW / 2
        for n2, a2, c2, hw2, t2 in segs:
            if n2 == net: continue
            room = min(room, seg_seg(a, c, a2, c2) - hw2 - CLR)
        for n2, p2, r2 in vias:
            if n2 == net: continue
            room = min(room, seg_seg(a, c, p2, p2) - r2 - CLR)
        for n2, r2, clr in pads[l]:
            if n2 == net: continue
            room = min(room, seg_rect(a, c, r2) - clr)
        w = math.floor(max(0, room) * 2 / 0.05 + 1e-6) * 0.05
        if w > hw * 2 + 1e-6: t.SetWidth(FromMM(round(w, 2))); seg[3] = w / 2; changed += 1; widths[round(w, 2)] = widths.get(round(w, 2), 0) + 1   # later segments see the new width
pcbnew.SaveBoard(OUT, b)
print('widened %d segments: %s -> %s' % (changed, dict(sorted(widths.items())), OUT))
