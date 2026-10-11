"""Remove routed copper that is not in a base board and touches a window.
usage: window_strip.py board.kicad_pcb base.kicad_pcb out.kicad_pcb x0 y0 x1 y1"""
import sys, pcbnew
from pcbnew import ToMM
src, base, out = sys.argv[1:4]; X0, Y0, X1, Y1 = map(float, sys.argv[4:8])
def key(t):
    if t.Type() == pcbnew.PCB_VIA_T: return ('v', t.GetNetname(), round(ToMM(t.GetPosition().x), 3), round(ToMM(t.GetPosition().y), 3))
    a = (round(ToMM(t.GetStart().x), 3), round(ToMM(t.GetStart().y), 3)); c = (round(ToMM(t.GetEnd().x), 3), round(ToMM(t.GetEnd().y), 3))
    return ('t', t.GetNetname(), t.GetLayer(), min(a, c), max(a, c))
keep = {key(t) for t in pcbnew.LoadBoard(base).GetTracks()}
b = pcbnew.LoadBoard(src); gone = []
for t in b.GetTracks():
    if key(t) in keep: continue
    pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    xs = [ToMM(p.x) for p in pts]; ys = [ToMM(p.y) for p in pts]
    if max(xs) >= X0 and min(xs) <= X1 and max(ys) >= Y0 and min(ys) <= Y1: gone.append(t)
nets = sorted({t.GetNetname() for t in gone})
for t in gone: b.Remove(t)
pcbnew.SaveBoard(out, b); print('removed %d items of %d nets inside (%g, %g)-(%g, %g)' % (len(gone), len(nets), X0, Y0, X1, Y1))
