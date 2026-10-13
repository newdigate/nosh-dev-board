"""Strip a net back to its BGA fan-out (run with KiCad's bundled python3): every track and via of the net goes except
the fan-out via on a lattice cell (ball + (0.4, 0.4)) and the dog-bone from the ball to it, so bga_escape.py can
re-escape the ball. usage: net_strip.py in.kicad_pcb out.kicad_pcb NET[,NET...]"""
import sys, math, pcbnew
from pcbnew import ToMM
IN, OUT, NETS = sys.argv[1], sys.argv[2], set(sys.argv[3].split(','))
b = pcbnew.LoadBoard(IN)
balls = {}
for f in b.GetFootprints():
    if f.GetReference() != 'U1': continue
    for p in f.Pads():
        if p.GetNetname() in NETS: balls.setdefault(p.GetNetname(), []).append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)))
def on_lattice(x, y): return abs((x - 66.0) / 0.8 - round((x - 66.0) / 0.8)) < 0.02 and abs((y - 36.0) / 0.8 - round((y - 36.0) / 0.8)) < 0.02 and 65.5 < x < 78.5 and 35.5 < y < 48.5
rm = []; kept = 0
for t in list(b.GetTracks()):
    net = t.GetNetname()
    if net not in NETS: continue
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        if on_lattice(x, y) and any(abs(abs(x - bx) - 0.4) < 0.02 and abs(abs(y - by) - 0.4) < 0.02 for bx, by in balls.get(net, ())): kept += 1; continue
    else:
        a, c = (ToMM(t.GetStart().x), ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
        if any(math.hypot(a[0] - bx, a[1] - by) < 0.02 or math.hypot(c[0] - bx, c[1] - by) < 0.02 for bx, by in balls.get(net, ())) and math.hypot(a[0] - c[0], a[1] - c[1]) < 0.6: kept += 1; continue   # dog-bone
    rm.append(t)
for t in rm: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b); print('stripped %d items of %s, kept %d fan-out items -> %s' % (len(rm), sorted(NETS), kept, OUT))
