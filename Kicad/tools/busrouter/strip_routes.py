"""Remove the routed copper of some SDRAM nets, keeping their prebuilt chip-side geometry and the BGA fan-out.
usage: strip_routes.py routed.kicad_pcb prebuilt.kicad_pcb out.kicad_pcb NET[,NET...]
Anything of those nets that is not in the prebuilt board (same layer and end points / position) is removed.
"""
import sys, pcbnew
from pcbnew import ToMM
routed, pre, out, nets = sys.argv[1], sys.argv[2], sys.argv[3], set(sys.argv[4].split(','))
def key(t):
    if t.Type() == pcbnew.PCB_VIA_T: return ('via', t.GetNetname(), round(ToMM(t.GetPosition().x), 3), round(ToMM(t.GetPosition().y), 3))
    a = (round(ToMM(t.GetStart().x), 3), round(ToMM(t.GetStart().y), 3)); b = (round(ToMM(t.GetEnd().x), 3), round(ToMM(t.GetEnd().y), 3))
    return ('trk', t.GetNetname(), t.GetLayer(), min(a, b), max(a, b))
keep = {key(t) for t in pcbnew.LoadBoard(pre).GetTracks() if t.GetNetname() in nets}
b = pcbnew.LoadBoard(routed)
gone = [t for t in b.GetTracks() if t.GetNetname() in nets and key(t) not in keep]
for t in gone: b.Remove(t)
pcbnew.SaveBoard(out, b); print('removed %d routed items of %d nets -> %s' % (len(gone), len(nets), out))
