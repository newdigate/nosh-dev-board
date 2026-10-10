"""Independent connectivity check of the SDRAM nets: union-find over pads, tracks and vias by geometric contact.
usage: busconn.py board.kicad_pcb"""
import sys, re, math, collections, pcbnew
from pcbnew import ToMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
SD = re.compile(r'^(SEMC_|U9_CLK$|U10_CLK$)')
items = collections.defaultdict(list)       # net -> [(kind, obj)]
for f in b.GetFootprints():
    for p in f.Pads():
        if SD.match(p.GetNetname()): items[p.GetNetname()].append(('pad', p))
for t in b.GetTracks():
    if SD.match(t.GetNetname()): items[t.GetNetname()].append(('via' if t.Type() == pcbnew.PCB_VIA_T else 'trk', t))
def layers(kind, o):
    if kind == 'via': return {pcbnew.F_Cu, b.GetLayerID('SIG'), pcbnew.B_Cu, b.GetLayerID('GND1'), b.GetLayerID('PWR'), b.GetLayerID('GND2')}
    if kind == 'trk': return {o.GetLayer()}
    return {l for l in (pcbnew.F_Cu, pcbnew.B_Cu, b.GetLayerID('SIG')) if o.IsOnLayer(l)}
def pts(kind, o):
    if kind == 'trk': return [o.GetStart(), o.GetEnd()]
    return [o.GetPosition()]
def touches(a, b_):
    (ka, oa), (kb, ob) = a, b_
    if not (layers(ka, oa) & layers(kb, ob)): return False
    for P in pts(ka, oa):
        if kb == 'pad' and ob.HitTest(P): return True
        if kb == 'via' and math.hypot(ToMM(P.x - ob.GetPosition().x), ToMM(P.y - ob.GetPosition().y)) < ToMM(ob.GetWidth(pcbnew.F_Cu)) / 2: return True
        if kb == 'trk':
            for Q in pts(kb, ob):
                if abs(P.x - Q.x) < 1000 and abs(P.y - Q.y) < 1000: return True
            # endpoint lying on the other segment
            s, e = ob.GetStart(), ob.GetEnd(); dx, dy = e.x - s.x, e.y - s.y; L2 = dx * dx + dy * dy
            if L2:
                t = max(0, min(1, ((P.x - s.x) * dx + (P.y - s.y) * dy) / L2)); cx, cy = s.x + t * dx, s.y + t * dy
                if math.hypot(P.x - cx, P.y - cy) < ob.GetWidth() / 2: return True
    return False
bad = {}
for net, its in items.items():
    par = list(range(len(its)))
    def find(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i in range(len(its)):
        for j in range(i + 1, len(its)):
            if find(i) != find(j) and (touches(its[i], its[j]) or touches(its[j], its[i])): par[find(i)] = find(j)
    pads = [i for i, (k, _) in enumerate(its) if k == 'pad']
    groups = {find(i) for i in pads}
    if len(groups) > 1:
        bad[net] = ['+'.join('%s-%s' % (its[i][1].GetParentFootprint().GetReference(), its[i][1].GetNumber()) for i in pads if find(i) == g) for g in groups]
print('SDRAM nets checked:', len(items), '| nets whose pads are not all joined:', len(bad))
for n, g in sorted(bad.items()): print('  %-10s %s' % (n, '  |  '.join(g)))
