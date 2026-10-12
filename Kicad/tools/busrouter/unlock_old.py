"""Lock only the copper that must stay for Freerouting (run with KiCad's bundled python3):
SEMC_* (the SDRAM bus), the U1 fan-out vias and dog-bones, and anything not present in the base board
(the escapes and re-joined lanes). Everything else is unlocked so the autorouter may rip it up.
usage: unlock_old.py board.kicad_pcb base.kicad_pcb out.kicad_pcb"""
import sys, math, pcbnew
from pcbnew import ToMM
IN, BASE, OUT = sys.argv[1:4]
def key(t):
    if t.Type() == pcbnew.PCB_VIA_T: return ('v', t.GetNetname(), round(ToMM(t.GetPosition().x), 3), round(ToMM(t.GetPosition().y), 3))
    a = (round(ToMM(t.GetStart().x), 3), round(ToMM(t.GetStart().y), 3)); c = (round(ToMM(t.GetEnd().x), 3), round(ToMM(t.GetEnd().y), 3))
    return ('t', t.GetNetname(), t.GetLayer(), min(a, c), max(a, c))
base = {key(t) for t in pcbnew.LoadBoard(BASE).GetTracks()}
b = pcbnew.LoadBoard(IN)
u1 = next(f for f in b.GetFootprints() if f.GetReference() == 'U1')
balls = {(round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in u1.Pads()}
FIELD = (65.0, 35.0, 79.0, 49.0)
n = {'locked': 0, 'unlocked': 0}
for t in b.GetTracks():
    k = key(t); keep = t.GetNetname().startswith('SEMC') or k not in base
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        if FIELD[0] <= x <= FIELD[2] and FIELD[1] <= y <= FIELD[3]: keep = True
    elif t.GetLayer() == pcbnew.F_Cu and ToMM(t.GetLength()) < 0.6:
        a = (round(ToMM(t.GetStart().x), 2), round(ToMM(t.GetStart().y), 2)); c = (round(ToMM(t.GetEnd().x), 2), round(ToMM(t.GetEnd().y), 2))
        if a in balls or c in balls: keep = True
    t.SetLocked(keep); n['locked' if keep else 'unlocked'] += 1
pcbnew.SaveBoard(OUT, b); print(n, '->', OUT)
