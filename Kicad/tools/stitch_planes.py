"""Stage 2 (run with KiCad's bundled python3, see build_board.py; edits Kicad/Nosh.kicad_pcb in place, back it up first).
Stage 2e: a via next to every SMD pad on a plane net, where that plane exists. Edits the saved board in place."""
import math, collections, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
import os
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
VIA_D, VIA_H, TRK, CLR, HOLE_CLR = 0.45, 0.3, 0.15, 0.13, 0.2
W, H = 153.9, 81.8
# plane net -> region (x0, y0, x1, y1) where a zone of that net exists
PLANES = {'GND': (0, 0, W, H), '+3V3': (0, 0, W, H), '+5V': (0.5, 58.5, 40.0, 81.3), 'SDRAM_3V3': (26.0, 15.0, 54.5, 58.0),
          'WL_3V3': (110.0, 6.0, 140.0, 48.0), 'VDD_SOC_IN': (66.5, 36.5, 77.5, 47.5)}
nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}

# obstacles: every pad (bbox) and every via/track, with the net so same-net items are allowed to touch
obst = []        # (x0, y0, x1, y1, net, has_hole)
for f in board.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox(); obst.append((ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()), p.GetNetname(), ToMM(p.GetDrillSize().x)))
for t in board.GetTracks():
    bb = t.GetBoundingBox(); obst.append((ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()), t.GetNetname(), ToMM(t.GetDrill()) if t.Type() == pcbnew.PCB_VIA_T else 0.0))
def rect_free(rx0, ry0, rx1, ry1, net, own):
    # a copper rectangle of `net` must keep CLR from other nets and HOLE_CLR from other nets' holes; same net may touch
    for x0, y0, x1, y1, n, hole in obst:
        if (x0, y0, x1, y1) == own: continue
        if n == net: continue
        gap = max(CLR, HOLE_CLR + 0.03) if hole else CLR
        if rx0 - gap < x1 and rx1 + gap > x0 and ry0 - gap < y1 and ry1 + gap > y0: return False
    return True
def via_ok(x, y, net, px, py, own):
    r = VIA_D / 2
    if x - r < 0.6 or y - r < 0.6 or x + r > W - 0.6 or y + r > H - 0.6: return False
    if not rect_free(x - r, y - r, x + r, y + r, net, own): return False
    # the via's own hole against every other hole: 0.254 same net, HOLE_CLR + copper otherwise (covered above for other nets)
    for x0, y0, x1, y1, n, hole in obst:
        if hole and n == net:
            cxo, cyo = (x0 + x1) / 2, (y0 + y1) / 2
            if math.hypot(x - cxo, y - cyo) < VIA_H / 2 + hole / 2 + 0.3: return False
    # the stub track from the pad centre to the via centre
    hw = TRK / 2
    return rect_free(min(px, x) - hw, min(py, y) - hw, max(px, x) + hw, max(py, y) + hw, net, own)
added = collections.Counter(); skipped = collections.Counter()
for f in board.GetFootprints():
    fx, fy = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y)
    for p in f.Pads():
        net = p.GetNetname()
        if net not in PLANES or p.GetDrillSize().x > 0 or f.GetReference() in ('U1', 'U9', 'U10'): continue      # U1: fan-out; U9/U10: power vias from sdram_prebuild.py
        px, py = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        x0, y0, x1, y1 = PLANES[net]
        if not (x0 <= px <= x1 and y0 <= py <= y1): skipped['no plane here'] += 1; continue
        bb = p.GetBoundingBox(); hw, hh = ToMM(bb.GetWidth()) / 2, ToMM(bb.GetHeight()) / 2
        ux, uy = px - fx, py - fy
        axis = (1 if ux > 0 else -1, 0) if abs(ux) >= abs(uy) else (0, 1 if uy > 0 else -1)   # outward, snapped to an axis
        dirs = [axis] + [d for d in ((1, 0), (-1, 0), (0, 1), (0, -1)) if d != axis] + [(0.707, 0.707), (-0.707, 0.707), (0.707, -0.707), (-0.707, -0.707)]
        own = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        layer = pcbnew.B_Cu if f.GetLayer() == pcbnew.B_Cu else pcbnew.F_Cu
        placed = False
        for dx, dy in dirs:
            for extra in (0.15, 0.35, 0.6):
                d = (abs(dx) * hw + abs(dy) * hh) + VIA_D / 2 + extra
                vx, vy = px + dx * d, py + dy * d
                if via_ok(vx, vy, net, px, py, own):
                    v = pcbnew.PCB_VIA(board); v.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_H)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(p.GetNet()); v.SetLocked(True); board.Add(v)
                    t = pcbnew.PCB_TRACK(board); t.SetStart(p.GetPosition()); t.SetEnd(v.GetPosition()); t.SetWidth(FromMM(TRK)); t.SetLayer(layer); t.SetNet(p.GetNet()); t.SetLocked(True); board.Add(t)
                    r = VIA_D / 2; obst.append((vx - r, vy - r, vx + r, vy + r, net, VIA_H)); obst.append((min(px, vx) - TRK / 2, min(py, vy) - TRK / 2, max(px, vx) + TRK / 2, max(py, vy) + TRK / 2, net, 0.0))
                    added[net] += 1; placed = True; break
            if placed: break
        if not placed: skipped['no room: ' + f.GetReference()] += 1
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
for z in board.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)     # outer pours stay unfilled until routing is done
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
print('vias added:', dict(added), 'total', sum(added.values()))
print('skipped:', dict(skipped))
