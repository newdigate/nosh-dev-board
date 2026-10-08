"""Stage 2 (run with KiCad's bundled python3, see build_board.py; edits Kicad/Nosh.kicad_pcb in place, back it up first).
Stage 2a: dog-bone fan-out for U1 (MAPBGA-289, 0.8 mm). Edits Nosh.kicad_pcb in place (loads the saved board, never rebuilds)."""
import math, collections, sys
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

import os
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
u1 = next(f for f in board.GetFootprints() if f.GetReference() == 'U1')
assert not [t for t in board.GetTracks() if t.GetNetname() and u1.GetBoundingBox().Contains(t.GetPosition())], 'fan-out already present'
ROWS = 'ABCDEFGHJKLMNPRTU'; PITCH = 0.8; N = 17
VIA_D, VIA_H, TRK = 0.45, 0.2, 0.1
cx, cy = ToMM(u1.GetPosition().x), ToMM(u1.GetPosition().y)
pads = {}
for p in u1.Pads():
    n = p.GetNumber(); r, c = ROWS.index(n[0]), int(n[1:]) - 1
    pads[(r, c)] = p
# ring index from the edge (0 = outer ring)
ring = lambda r, c: min(r, c, N - 1 - r, N - 1 - c)
# cell (i, j) is the square between rows i,i+1 and cols j,j+1; its centre:
cell_xy = lambda i, j: (cx + (j + 0.5 - 8) * PITCH, cy + (i + 0.5 - 8) * PITCH)
taken = set(); plan = []; skipped = []
need = [(r, c, p) for (r, c), p in pads.items() if p.GetNetname() and not p.GetNetname().startswith('unconnected') and ring(r, c) >= 2]
# innermost first: they have the fewest alternatives
need.sort(key=lambda t: -ring(t[0], t[1]))
for r, c, p in need:
    dr = -1 if r < 8 else 1; dc = -1 if c < 8 else 1          # outward quadrant
    cands = [(r + (dr - 1) // 2, c + (dc - 1) // 2)]           # outward diagonal cell first
    cands += [(r + (dr - 1) // 2, c + (-dc - 1) // 2), (r + (-dr - 1) // 2, c + (dc - 1) // 2), (r + (-dr - 1) // 2, c + (-dc - 1) // 2)]
    for i, j in cands:
        if 0 <= i < N - 1 and 0 <= j < N - 1 and (i, j) not in taken:
            taken.add((i, j)); plan.append((p, i, j)); break
    else:
        skipped.append(p.GetNumber())
print('balls needing vias:', len(need), '| planned:', len(plan), '| no free cell:', skipped)
for p, i, j in plan:
    vx, vy = cell_xy(i, j); net = p.GetNet()
    v = pcbnew.PCB_VIA(board); v.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_H)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); board.Add(v)
    t = pcbnew.PCB_TRACK(board); t.SetStart(p.GetPosition()); t.SetEnd(v.GetPosition()); t.SetWidth(FromMM(TRK)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); board.Add(t)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
by_net = collections.Counter(p.GetNetname() for p, i, j in plan)
print('vias by net (top 8):', by_net.most_common(8))
print('saved')
