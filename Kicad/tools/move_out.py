"""Move small parts out of a routing corridor (run with KiCad's bundled python3).
usage: move_out.py in out REF[@deg],REF,... x0 y0 x1 y1 [base.kicad_pcb]
Each part goes to the first free spot of a 0.5 mm scan over the target box (its courtyard plus 0.25 mm must clear
every other courtyard, through-hole pad and the board edge; the part keeps its side and rotation). Routed copper of
other nets under the new courtyard is dropped, and the moved parts' own nets lose their routed copper that is not
in the base board (default: the BGA fan-out only), so the next routing pass starts from the escapes. GND and +3V3
copper is left alone (plane_vias.py gives the moved pads new vias)."""
import sys, math, collections, pcbnew
from pcbnew import ToMM, FromMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]; REFS = sys.argv[3].split(','); X0, Y0, X1, Y1 = map(float, sys.argv[4:8]); BASE = sys.argv[8] if len(sys.argv) > 8 else None
def key(t):
    if t.Type() == pcbnew.PCB_VIA_T: return ('v', t.GetNetname(), round(ToMM(t.GetPosition().x), 3), round(ToMM(t.GetPosition().y), 3))
    a = (round(ToMM(t.GetStart().x), 3), round(ToMM(t.GetStart().y), 3)); c = (round(ToMM(t.GetEnd().x), 3), round(ToMM(t.GetEnd().y), 3))
    return ('t', t.GetNetname(), t.GetLayer(), min(a, c), max(a, c))
base = {key(t) for t in pcbnew.LoadBoard(BASE).GetTracks()} if BASE else set()
b = pcbnew.LoadBoard(IN); fps = {f.GetReference(): f for f in b.GetFootprints()}
def crt(f):
    bb = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
    if bb.GetWidth() < 1000: bb = f.GetBoundingBox(False, False); bb.Inflate(FromMM(0.25))          # no courtyard drawn: pads + 0.25 mm
    return [ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())]
pth = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), ToMM(p.GetBoundingBox().GetWidth()) / 2) for f in b.GetFootprints() for p in f.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and f.GetReference() not in [r.split('@')[0] for r in REFS]]
REFS = [r.split('@')[0] for r in REFS]; ROT = {r.split('@')[0]: r for r in sys.argv[3].split(',')}
others = {r: crt(f) for r, f in fps.items() if r not in REFS}
eb = b.GetBoardEdgesBoundingBox(); EX0, EY0, EX1, EY1 = ToMM(eb.GetLeft()) + 1, ToMM(eb.GetTop()) + 1, ToMM(eb.GetRight()) - 1, ToMM(eb.GetBottom()) - 1
balls = collections.defaultdict(list)
for p in fps['U1'].Pads(): balls[p.GetNetname()].append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)))
def fanout(t):
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        return any(abs(abs(x - bx) - 0.4) < 0.02 and abs(abs(y - by) - 0.4) < 0.02 for bx, by in balls.get(net, ()))
    a, c = (ToMM(t.GetStart().x), ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
    return math.hypot(a[0] - c[0], a[1] - c[1]) < 0.6 and any(math.hypot(q[0] - bx, q[1] - by) < 0.02 for q in (a, c) for bx, by in balls.get(net, ()))
M = 0.25; moved_nets = set(); new_crts = []; old_pads = []
for ref in REFS:
    if '@' in ROT[ref]: fps[ref].SetOrientationDegrees(float(ROT[ref].split('@')[1]))             # REF@deg: rotate before placing
    f = fps[ref]; c = crt(f); w, h = c[2] - c[0], c[3] - c[1]; cx, cy = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y); dx, dy = cx - (c[0] + c[2]) / 2, cy - (c[1] + c[3]) / 2
    spot = None
    for yy in [Y0 + h / 2 + k * 0.5 for k in range(int((Y1 - Y0 - h) / 0.5) + 1)]:
        for xx in [X0 + w / 2 + k * 0.5 for k in range(int((X1 - X0 - w) / 0.5) + 1)]:
            r = [xx - w / 2 - M, yy - h / 2 - M, xx + w / 2 + M, yy + h / 2 + M]
            if r[0] < EX0 or r[1] < EY0 or r[2] > EX1 or r[3] > EY1: continue
            if any(r[0] < o[2] and r[2] > o[0] and r[1] < o[3] and r[3] > o[1] for o in list(others.values()) + new_crts): continue
            if any(r[0] - pr < px < r[2] + pr and r[1] - pr < py < r[3] + pr for px, py, pr in pth): continue
            spot = (xx, yy); break
        if spot: break
    if not spot: print('  %s: no room in the box' % ref); continue
    f.SetPosition(VECTOR2I(FromMM(spot[0] + dx), FromMM(spot[1] + dy))); nc = crt(f); new_crts.append(nc); others[ref] = nc
    moved_nets |= {p.GetNetname() for p in f.Pads()}; old_pads += [(p.GetNetname(), ToMM(p.GetPosition().x) - (ToMM(f.GetPosition().x) - cx), ToMM(p.GetPosition().y) - (ToMM(f.GetPosition().y) - cy)) for p in f.Pads()]
    print('  %-5s (%.1f,%.1f) -> (%.1f,%.1f)  nets %s' % (ref, cx, cy, ToMM(f.GetPosition().x), ToMM(f.GetPosition().y), sorted({p.GetNetname() for p in f.Pads()})))
rm = []
for t in b.GetTracks():
    net = t.GetNetname()
    if net in ('GND', '+3V3') or net.startswith('SEMC') or fanout(t): continue
    if t.Type() == pcbnew.PCB_VIA_T: qx0 = qx1 = ToMM(t.GetPosition().x); qy0 = qy1 = ToMM(t.GetPosition().y)
    else: qx0, qx1 = sorted((ToMM(t.GetStart().x), ToMM(t.GetEnd().x))); qy0, qy1 = sorted((ToMM(t.GetStart().y), ToMM(t.GetEnd().y)))
    if any(qx1 > r[0] - 0.2 and qx0 < r[2] + 0.2 and qy1 > r[1] - 0.2 and qy0 < r[3] + 0.2 for r in new_crts): rm.append(t); continue   # under a moved part
    if net in moved_nets and key(t) not in base: rm.append(t)                                                                      # the moved parts' old routes
for t in b.GetTracks():                                                                                                           # the plane stubs (GND/+3V3 via + short track) that fed the old pads
    if t.GetNetname() not in ('GND', '+3V3') or fanout(t): continue
    if t.Type() == pcbnew.PCB_VIA_T: x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
    else: x, y = ToMM(t.GetStart().x), ToMM(t.GetStart().y)
    if any(n == t.GetNetname() and math.hypot(x - px, y - py) < 1.0 for n, px, py in old_pads) and t not in rm: rm.append(t)
for t in rm: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b); print('removed %d routed items -> %s' % (len(rm), OUT))
