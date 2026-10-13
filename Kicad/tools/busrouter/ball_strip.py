"""Strip the copper hanging off given BGA balls back to the dog-bone (run with KiCad's bundled python3), leaving the
net's other islands (routes elsewhere on the board) alone, so bga_escape.py can re-escape just those balls.
usage: [WIN=x0,y0,x1,y1] ball_strip.py in.kicad_pcb out.kicad_pcb A1,D12,...   (with WIN only the part of the island
inside the box goes - the escape - and the net's routes beyond it stay for the continuation step)"""
import sys, os, math, pcbnew
from pcbnew import ToMM
IN, OUT, BALLS = sys.argv[1], sys.argv[2], set(sys.argv[3].split(','))
WIN = [float(v) for v in os.environ['WIN'].split(',')] if os.environ.get('WIN') else None   # WIN=x0,y0,x1,y1: only the island's items inside this box go (the escape), its routes beyond stay
def inside(t):
    if not WIN: return True
    if t.Type() == pcbnew.PCB_VIA_T: x0 = x1 = ToMM(t.GetPosition().x); y0 = y1 = ToMM(t.GetPosition().y)
    else: x0, x1 = sorted((ToMM(t.GetStart().x), ToMM(t.GetEnd().x))); y0, y1 = sorted((ToMM(t.GetStart().y), ToMM(t.GetEnd().y)))
    return x1 > WIN[0] and x0 < WIN[2] and y1 > WIN[1] and y0 < WIN[3]
b = pcbnew.LoadBoard(IN); b.BuildConnectivity(); conn = b.GetConnectivity()
u1 = [f for f in b.GetFootprints() if f.GetReference() == 'U1'][0]
rm = {}; kept = 0
for p in u1.Pads():
    if p.GetNumber() not in BALLS: continue
    bx, by = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y); net = p.GetNetname()
    seen = {p.m_Uuid.AsString()}; todo = [p]
    while todo:
        x = todo.pop()
        for y in conn.GetConnectedItems(x):
            y = y.Cast(); k = y.m_Uuid.AsString()
            if y.Type() in (pcbnew.PCB_ZONE_T, pcbnew.PCB_PAD_T) or k in seen: continue
            seen.add(k); todo.append(y)
            if y.Type() == pcbnew.PCB_VIA_T:
                vx, vy = ToMM(y.GetPosition().x), ToMM(y.GetPosition().y)
                if abs(abs(vx - bx) - 0.4) < 0.02 and abs(abs(vy - by) - 0.4) < 0.02: kept += 1; continue        # the fan-out via
            else:
                a, c = (ToMM(y.GetStart().x), ToMM(y.GetStart().y)), (ToMM(y.GetEnd().x), ToMM(y.GetEnd().y))
                if math.hypot(a[0] - c[0], a[1] - c[1]) < 0.6 and any(math.hypot(q[0] - bx, q[1] - by) < 0.02 for q in (a, c)): kept += 1; continue   # the dog-bone
            if inside(y): rm[k] = y
    print('  %-4s %-16s island: %d items, %d removed' % (p.GetNumber(), net, len(seen) - 1, len([1 for k in seen if k in rm])))
for t in rm.values(): b.Remove(t)
pcbnew.SaveBoard(OUT, b); print('removed %d items, kept %d fan-out items -> %s' % (len(rm), kept, OUT))
