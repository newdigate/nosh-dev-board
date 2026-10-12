"""Fixed top-layer exits for the ring-1 balls of U1's west column (run with KiCad's bundled python3).
usage: west_stubs.py in.kicad_pcb out.kicad_pcb
Each ring-1 ball in column 2 (rows B..T) leaves through the gap above it between the column-1 balls: a 0.1 mm
track from the ball diagonally to the gap centre (x = 66.0, y = ball y - 0.4) and west to x = 65.0. The bus
router then continues from the stub ends; the gaps are no longer negotiated (a chain of 15 balls into 16 gaps
that the negotiation never settled on its own)."""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(IN)
u1 = next(f for f in b.GetFootprints() if f.GetReference() == 'U1'); ROWS = 'ABCDEFGHJKLMNPRTU'
def track(net, x0, y0, x1, y1):
    t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); t.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
    t.SetWidth(FromMM(0.1)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); t.SetLocked(True); b.Add(t)
n = 0
for p in u1.Pads():
    name = p.GetNumber(); net = p.GetNetname()
    if name[1:] != '2' or name[0] in 'AU' or not net or net.startswith('unconnected'): continue
    x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y); gy = round(y - 0.4, 2)
    track(p.GetNet(), x, y, 66.0, gy); track(p.GetNet(), 66.0, gy, 65.0, gy); n += 1
pcbnew.SaveBoard(OUT, b)
print('west stubs for %d ring-1 balls -> %s' % (n, OUT))
