"""Take parts off the board to free routing room (run with KiCad's bundled python3): the expansion header J10 and
every test point by default, recorded in <out>.removed.json (ref, footprint, position, rotation, side, pads) so
they can be put back. usage: strip_parts.py in.kicad_pcb out.kicad_pcb [REF,REF,...]
Copper that only served the removed pads goes too: a net left with fewer than two pads keeps only its BGA fan-out
(via + dog-bone), and dangling branches of the other nets are pruned back to the next junction (vias of plane nets
are left alone: a lone plane via is stitching). The phases run in fresh interpreters because pcbnew cannot iterate
a board after Remove(), nor reload a board it has just saved."""
import sys, os, json, math, collections, subprocess, pcbnew
from pcbnew import ToMM
IN, OUT = sys.argv[1], sys.argv[2]
PHASE = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3].startswith('--') else None
REFS = set(sys.argv[3].split(',')) if len(sys.argv) > 3 and not PHASE else None
b = pcbnew.LoadBoard(IN)
PL = [b.GetLayerID(n) for n in ('GND1', 'PWR', 'GND2')]
plane_nets = {z.GetNetname() for z in b.Zones() if not z.GetIsRuleArea() and any(z.IsOnLayer(l) for l in PL)}
def save(msg, code=0, fill=False):
    if fill:
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        for z in b.Zones():
            if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
    pcbnew.SaveBoard(OUT, b); print(msg); sys.exit(code)
def rerun(phase):
    r = subprocess.run([sys.executable, os.path.abspath(__file__), OUT, OUT, phase], capture_output=True, text=True)
    print('\n'.join(l for l in (r.stdout + r.stderr).splitlines() if not any(k in l for k in ('traits', 'memory leak', 'Debug')))); return r.returncode
if PHASE is None:
    refs = REFS or {f.GetReference() for f in b.GetFootprints() if f.GetReference() == 'J10' or f.GetReference().startswith('TP')}
    gone = []; touched = set()
    for f in list(b.GetFootprints()):
        if f.GetReference() not in refs: continue
        pads = []
        for p in f.Pads():
            bb = p.GetBoundingBox(); pads.append({'num': p.GetNumber(), 'net': p.GetNetname(), 'x': ToMM(p.GetPosition().x), 'y': ToMM(p.GetPosition().y), 'box': [ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())],
                         'layers': [l for l in ('F.Cu', 'B.Cu') if p.IsOnLayer(b.GetLayerID(l))]})
        gone.append({'ref': f.GetReference(), 'fpid': f.GetFPIDAsString(), 'value': f.GetValue(), 'x': ToMM(f.GetPosition().x), 'y': ToMM(f.GetPosition().y), 'rot': f.GetOrientationDegrees(),
                     'side': 'B' if f.IsFlipped() else 'F', 'pads': pads})
        touched |= {p['net'] for p in pads}; b.Remove(f)
    json.dump({'parts': gone, 'nets': sorted(touched)}, open(OUT + '.removed.json', 'w'), indent=1)
    pcbnew.SaveBoard(OUT, b); print('removed %d footprints (%s ...)' % (len(gone), ', '.join(g['ref'] for g in gone[:6])))
    rerun('--join'); rerun('--onepad')
    for k in range(25):
        if rerun('--prune') == 3: break
    sys.exit(0)
touched = set(json.load(open(OUT + '.removed.json'))['nets'])
if PHASE == '--join':
    # a removed pad that was a junction (routes met at it) is replaced by tracks from each track end on it to its centre
    nets = b.GetNetInfo().NetsByName(); joins = 0
    gone = json.load(open(OUT + '.removed.json'))['parts']
    for g in gone:
        for pd in g['pads']:
            x0, y0, x1, y1 = pd['box']; ends = {}
            for t in b.GetTracks():
                if t.Type() != pcbnew.PCB_TRACE_T or t.GetNetname() != pd['net'] or b.GetLayerName(t.GetLayer()) not in pd['layers']: continue
                for q in (t.GetStart(), t.GetEnd()):
                    if x0 - 0.01 <= ToMM(q.x) <= x1 + 0.01 and y0 - 0.01 <= ToMM(q.y) <= y1 + 0.01: ends[(round(ToMM(q.x), 3), round(ToMM(q.y), 3), t.GetLayer())] = ToMM(t.GetWidth())
            if len(ends) < 2: continue
            for (ex, ey, l), w in ends.items():
                if math.hypot(ex - pd['x'], ey - pd['y']) < 0.01: continue
                t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(ex), pcbnew.FromMM(ey))); t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(pd['x']), pcbnew.FromMM(pd['y']))); t.SetWidth(pcbnew.FromMM(w)); t.SetLayer(l); t.SetNet(nets[pd['net']]); t.SetLocked(True); b.Add(t); joins += 1
            if len({l for _, _, l in ends}) > 1:                                        # ends on both sides: a via where the pad was (a through-hole pad)
                v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(pd['x']), pcbnew.FromMM(pd['y']))); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetWidth(pcbnew.FromMM(0.45)); v.SetDrill(pcbnew.FromMM(0.3)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets[pd['net']]); v.SetLocked(True); b.Add(v); joins += 1
    save('%d junction items keep the routes that met at removed pads' % joins)
npads = collections.Counter(); balls = collections.defaultdict(list); pads_xy = collections.defaultdict(list)
for f in b.GetFootprints():
    for p in f.Pads():
        npads[p.GetNetname()] += 1; pads_xy[p.GetNetname()].append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), p))
        if f.GetReference() == 'U1': balls[p.GetNetname()].append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)))
def fanout(t):
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        return any(abs(abs(x - bx) - 0.4) < 0.02 and abs(abs(y - by) - 0.4) < 0.02 for bx, by in balls.get(net, ()))
    a, c = (ToMM(t.GetStart().x), ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
    return math.hypot(a[0] - c[0], a[1] - c[1]) < 0.6 and any(math.hypot(q[0] - bx, q[1] - by) < 0.02 for q in (a, c) for bx, by in balls.get(net, ()))
if PHASE == '--onepad':
    rm = [t for t in b.GetTracks() if t.GetNetname() in touched and npads[t.GetNetname()] < 2 and not fanout(t) and not t.GetNetname().startswith('SEMC')]
    for t in rm: b.Remove(t)
    save('nets left with one pad: %s; %d items removed' % (sorted(n for n in touched if npads[n] < 2), len(rm)))
def on_pad(net, x, y):
    P = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return any(abs(x - px) < 2 and abs(y - py) < 2 and p.HitTest(P) for px, py, p in pads_xy.get(net, ()))
def pt_seg(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy; u = 0 if L2 == 0 else max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / L2)); return math.hypot(px - (x0 + u * dx), py - (y0 + u * dy))
loose_all = []
for net in sorted(touched):
    if npads[net] < 2 or net.startswith('SEMC'): continue
    items = [t for t in b.GetTracks() if t.GetNetname() == net]
    segs = [(t, t.GetLayer(), ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y), ToMM(t.GetWidth()) / 2) for t in items if t.Type() == pcbnew.PCB_TRACE_T]
    vias = [(t, ToMM(t.GetPosition().x), ToMM(t.GetPosition().y), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2) for t in items if t.Type() == pcbnew.PCB_VIA_T]
    def attached(t, x, y, l):                                   # the end touches a pad, a via, or another track (its end or its middle)
        if 63.0 <= x <= 81.0 and 33.0 <= y <= 51.0: return True   # escapes end free in the band by design: never pruned
        if on_pad(net, x, y): return True
        if any(math.hypot(x - vx, y - vy) <= vr + 0.01 for v, vx, vy, vr in vias): return True
        return any(s is not t and sl == l and pt_seg(x, y, x0, y0, x1, y1) <= hw + 0.01 for s, sl, x0, y0, x1, y1, hw in segs)
    for t, l, x0, y0, x1, y1, hw in segs:
        if not fanout(t) and (not attached(t, x0, y0, l) or not attached(t, x1, y1, l)): loose_all.append(t)
    for v, vx, vy, vr in vias:
        if fanout(v) or net in plane_nets or (63.0 <= vx <= 81.0 and 33.0 <= vy <= 51.0): continue
        if not any(pt_seg(vx, vy, x0, y0, x1, y1) <= hw + vr for s, sl, x0, y0, x1, y1, hw in segs): loose_all.append(v)   # a via no track reaches
if not loose_all: save('no dangling copper left -> ' + OUT, 3, fill=True)
for t in loose_all: b.Remove(t)
save('dangling items pruned: %d' % len(loose_all))
