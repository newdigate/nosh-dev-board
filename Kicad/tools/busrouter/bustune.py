"""Serpentine length tuning for the SDRAM bus (run with KiCad's bundled python3).
usage: bustune.py in.kicad_pcb out.kicad_pcb requests.json
requests.json: {"NET": extra_mm, ...}  - length to add to each net's route.
Builds the router's obstacle grids (busroute.py, nothing routed), then for each net tries its routed straight
segments, longest first, both sides, decreasing amplitude, and replaces the first one that fits with rectangular
meanders (legs 0.5 mm apart). Every new centreline cell must be clear of hard obstacles and of other nets' copper
plus clearance; accepted meanders are added to the grids so later ones respect them. Prints what it achieved.
"""
import sys, json, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
T_IN, T_OUT, T_REQ = sys.argv[1], sys.argv[2], sys.argv[3]
sys.argv = [os.path.join(HERE, 'busroute.py'), T_IN, '/dev/null', 'all', '0', '1']
src = open(sys.argv[0]).read(); src = src[:src.index('todo = set(all_nets);')]
__file__ = sys.argv[0]; exec(src)
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
want = json.load(open(T_REQ))
LEG = 0.5                                        # centre spacing of meander legs
MARGIN = 0.4                                     # straight run kept at each end of the replaced segment
FIELD = (64.6, 34.9, 80.0, 49.3)                 # never meander inside the BGA
def sample(x0, y0, x1, y1, step=0.02):
    L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / step))
    return {(gx(x0 + (x1 - x0) * k / n), gy(y0 + (y1 - y0) * k / n)) for k in range(n + 1)}
def own_mask(net):
    m = [set() for _ in range(3)]
    for key, cells in item_cells.items():
        if key[0] != net: continue
        for l, spans in cells:
            for j, a, b_ in spans: m[l].update(range(j * NX + a, j * NX + b_ + 1))
    return m
def clear(net, l, pts, mask):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for i, j in sample(x0, y0, x1, y1):
            if not (0 < i < NX - 1 and 0 < j < NY - 1): return False
            k = idx(i, j)
            if static[l][k]: return False
            if cnt[l][k] and k not in mask[l]: return False
    return True
def meander(P, Q, n, A, side):
    (px, py), (qx, qy) = P, Q; L = math.hypot(qx - px, qy - py); ux, uy = (qx - px) / L, (qy - py) / L
    vx, vy = -uy * side, ux * side; a0 = (L - n * 2 * LEG) / 2; pts = [P]
    for k in range(n):
        s0 = a0 + 2 * LEG * k
        b = (px + ux * s0, py + uy * s0)
        pts += [b, (b[0] + vx * A, b[1] + vy * A), (b[0] + ux * LEG + vx * A, b[1] + uy * LEG + vy * A), (b[0] + ux * LEG, b[1] + uy * LEG)]
    pts.append(Q); return pts
done_report = {}
for net, extra in sorted(want.items(), key=lambda kv: -kv[1]):
    if extra <= 0.2: continue
    mask = own_mask(net)
    segs = []
    for t in board.GetTracks():
        if t.GetNetname() != net or t.Type() == pcbnew.PCB_VIA_T: continue
        L = next((k for k, v in LAY.items() if v == t.GetLayer()), None)
        if L is None: continue
        x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
        if all(FIELD[0] <= x <= FIELD[2] and FIELD[1] <= y <= FIELD[3] for x, y in ((x0, y0), (x1, y1))): continue
        if t.IsLocked() and max(x0, x1) < 52 and abs(ToMM(t.GetWidth()) - 0.1) < 1e-6 and LIDX[L] == 2 and abs(x0 - x1) < 1e-6 and abs(y1 - y0) > 5: continue   # prebuilt address links stay straight
        segs.append((math.hypot(x1 - x0, y1 - y0), t, LIDX[L], (x0, y0), (x1, y1)))
    segs.sort(key=lambda s: -s[0]); got = 0.0; remaining = extra
    for Lseg, t, l, P, Q in segs:
        if remaining <= 0.2: break
        best = None
        for A in (2.5, 2.0, 1.5, 1.0, 0.75, 0.5):
            n_need = int(math.ceil(remaining / (2 * A)))
            n_fit = int((Lseg - 2 * MARGIN) / (2 * LEG))
            n = min(n_need, n_fit)
            if n < 1: continue
            Ause = min(A, remaining / (2 * n)) if n == n_need else A        # exact height when one segment can take it all
            if Ause < 0.3: continue
            for side in (1, -1):
                pts = meander(P, Q, n, Ause, side)
                if clear(net, l, pts, mask): best = (pts, 2 * Ause * n); break
            if best: break
        if not best: continue
        pts, add = best
        nt = t.GetNet(); w = t.GetWidth(); layer = t.GetLayer(); board.Remove(t)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if math.hypot(x1 - x0, y1 - y0) < 1e-6: continue
            s = pcbnew.PCB_TRACK(board); s.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); s.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
            s.SetWidth(w); s.SetLayer(layer); s.SetNet(nt); s.SetLocked(True); board.Add(s)
            sp = capsule_cells(x0, y0, x1, y1, TRK / 2 + TRK_R); bump(cnt[l], sp, 1); item_cells[(net, 'trk', x0, y0, x1, y1)] = [(l, sp)]
            for jj, a_, b_ in sp: mask[l].update(range(jj * NX + a_, jj * NX + b_ + 1))
        got += add; remaining -= add
    done_report[net] = (extra, got)
    print('  %-10s wanted +%5.1f mm, added +%5.1f mm %s' % (net, extra, got, '' if got >= extra - 0.5 else '  << short'), flush=True)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
for z in board.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(T_OUT, board); print('saved', T_OUT)
