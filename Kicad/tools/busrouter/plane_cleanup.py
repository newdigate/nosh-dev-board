"""Remove a plane net's floating copper (run with KiCad's bundled python3): track/via clusters that reach no via
inside the net's plane and no through-hole pad can never connect (typically vias dropped inside another net's
island). The pads they touched are left for plane_vias.py.   usage: plane_cleanup.py in out NET[,NET...]"""
import sys, collections, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT, NETS = sys.argv[1], sys.argv[2], set(sys.argv[3].split(','))
b = pcbnew.LoadBoard(IN); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
PLANE_L = [b.GetLayerID(n) for n in ('GND1', 'PWR', 'GND2')]
planes = collections.defaultdict(list)
for z in b.Zones():
    if z.GetIsRuleArea() or not z.GetNetname(): continue
    for l in PLANE_L:
        if z.IsOnLayer(l):
            ps = z.GetFilledPolysList(l)
            if ps.OutlineCount(): planes[z.GetNetname()].append((ps, max(range(ps.OutlineCount()), key=lambda i: ps.Outline(i).Area())))   # the main outline only: islands of fill round a stray via do not count
def in_plane(net, x, y): return any(ps.Contains(VECTOR2I(FromMM(x), FromMM(y)), main) for ps, main in planes.get(net, ()))
b.BuildConnectivity(); conn = b.GetConnectivity()
seen = set(); rm = []; report = collections.Counter()
for t in list(b.GetTracks()):
    net = t.GetNetname()
    if net not in NETS or t.m_Uuid.AsString() in seen: continue
    cluster = []; todo = [t]; seen.add(t.m_Uuid.AsString()); anchored = False; pads = set()
    while todo:
        x = todo.pop(); cluster.append(x)
        for y in conn.GetConnectedItems(x):
            y = y.Cast()
            if y.Type() == pcbnew.PCB_ZONE_T: continue
            if y.Type() == pcbnew.PCB_PAD_T:
                pads.add(y.GetParentFootprint().GetReference() + '.' + y.GetNumber())
                if y.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and in_plane(net, ToMM(y.GetPosition().x), ToMM(y.GetPosition().y)): anchored = True   # a through-hole pad only where the plane exists
                continue
            k = y.m_Uuid.AsString()
            if k in seen: continue
            seen.add(k); todo.append(y)
        if x.Type() == pcbnew.PCB_VIA_T and in_plane(net, ToMM(x.GetPosition().x), ToMM(x.GetPosition().y)): anchored = True
    if not anchored:
        rm += cluster; report[net] += 1
        print('  floating %-8s %2d items, pads %s' % (net, len(cluster), sorted(pads)[:6]))
for t in rm: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b)
print('removed %d floating clusters (%d items) -> %s' % (sum(report.values()), len(rm), OUT))
