"""Clear the copper under and around U1 so the escapes can be rebuilt (run with KiCad's bundled python3).
usage: bga_strip.py in.kicad_pcb out.kicad_pcb [x0 y0 x1 y1]
Inside the window (default 63,33 .. 81,51 = the 14 mm package plus 2 mm) every track and via is removed except:
  - SEMC_* copper (the routed SDRAM bus stays as it is)
  - the fan-out vias: a via on a lattice cell (ball + (0.4, 0.4)) carrying the net of a diagonal ball
  - the dog-bone stubs from a ball to its fan-out via
Copper outside the window is not touched; pieces left without a pad are removed by bga_escape.py."""
import sys, os, math, collections, pcbnew
from pcbnew import ToMM
IN, OUT = sys.argv[1], sys.argv[2]
R = tuple(float(v) for v in sys.argv[3:7]) if len(sys.argv) > 6 else (63.0, 33.0, 81.0, 51.0)
b = pcbnew.LoadBoard(IN)
u1 = next(f for f in b.GetFootprints() if f.GetReference() == 'U1')
balls = {(round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)): p.GetNetname() for p in u1.Pads()}
def cell_nets(x, y):
    return {balls[k] for dx in (-0.4, 0.4) for dy in (-0.4, 0.4) for k in [(round(x + dx, 2), round(y + dy, 2))] if k in balls}
def on_lattice(x, y):
    return abs((x - 66.0) / 0.8 - round((x - 66.0) / 0.8)) < 0.03 and abs((y - 36.0) / 0.8 - round((y - 36.0) / 0.8)) < 0.03
def in_r(x, y): return R[0] <= x <= R[2] and R[1] <= y <= R[3]
def seg_hits(x0, y0, x1, y1):
    n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 0.1))
    return any(in_r(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1))
rm = []; kept = collections.Counter(); removed = collections.Counter()
for t in b.GetTracks():
    net = t.GetNetname()
    if net.startswith('SEMC'): continue
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        if not in_r(x, y): continue
        if on_lattice(x, y) and net in cell_nets(x, y): kept['fan-out via'] += 1; continue
        rm.append(t); removed['via ' + net] += 1
    else:
        x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
        if not seg_hits(x0, y0, x1, y1): continue
        a, c = (round(x0, 2), round(y0, 2)), (round(x1, 2), round(y1, 2))
        if t.GetLayer() == pcbnew.F_Cu and math.hypot(x1 - x0, y1 - y0) < 0.6 and ((a in balls and on_lattice(*c)) or (c in balls and on_lattice(*a))) and balls.get(a if a in balls else c) == net:
            kept['dog-bone'] += 1; continue
        rm.append(t); removed['track ' + net] += 1
if os.environ.get('WHOLE') == '1':                       # remove the whole route chains that touch the window, not just the pieces inside
    b.BuildConnectivity(); conn = b.GetConnectivity()
    def is_fanout(t):
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y); return on_lattice(x, y) and t.GetNetname() in cell_nets(x, y)
        if t.GetLayer() != pcbnew.F_Cu or ToMM(t.GetLength()) >= 0.6: return False
        a, c = (round(ToMM(t.GetStart().x), 2), round(ToMM(t.GetStart().y), 2)), (round(ToMM(t.GetEnd().x), 2), round(ToMM(t.GetEnd().y), 2))
        return a in balls or c in balls
    seen = {t.m_Uuid.AsString() for t in rm}; todo = list(rm); grown = 0
    while todo:
        t = todo.pop()
        for u in conn.GetConnectedItems(t):
            u = u.Cast()
            if u.Type() not in (pcbnew.PCB_TRACE_T, pcbnew.PCB_VIA_T, pcbnew.PCB_ARC_T) or u.GetNetname().startswith('SEMC') or is_fanout(u): continue
            k = u.m_Uuid.AsString()
            if k not in seen: seen.add(k); rm.append(u); todo.append(u); grown += 1
    print('whole chains: %d more items outside the window' % grown)
for t in rm: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b)
nets = {k.split(' ', 1)[1] for k in removed}
print('window %s: removed %d items on %d nets, kept %s' % (R, len(rm), len(nets), dict(kept)))
print('removed most:', removed.most_common(12))
