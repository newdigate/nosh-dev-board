"""SDRAM fixed geometry for the EVKB-style stack (run with KiCad's bundled python3).
usage: sdram_prebuild.py <in.kicad_pcb> <out.kicad_pcb>

Both TSOPs (U9 north, U10 south) are rot 270: pins 1-27 on each chip's north row, 28-54 on its south row, and pin n of
U9 sits at the same x as pin n of U10. The channel between the chips faces U9's south row and U10's north row.

Built here, so the bus router only has to connect the MCU side:
- every power pin (SDRAM_3V3, GND): a via just outside the pad, on the side away from the chip body
- outer-row data pins (U9 north: D0-D7, DM0; U10 south: D24-D31, DM3): the same via, the router's target
- address group A (pins 16-26: north rows of both chips; outer on U9, channel side on U10): vias at both pads,
  joined by a straight bottom-layer track at the pin's x
- address group B (pins 29-37: south rows; channel side on U9, outer on U10): the same, but the via and the
  bottom track sit 0.4 mm east of the pin so they interleave with group A where both cross the channel
Channel-side data (D8-D15, DM1 on U9; D16-D23, DM2 on U10) and the clock pins are left to the router.
"""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

SRC, OUT = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(SRC)
VIA_D, VIA_H, TRK, VIA_GAP = 0.45, 0.20, 0.10, 0.40      # via centre this far beyond the pad end
nets = board.GetNetInfo().NetsByName()
fps = {f.GetReference(): f for f in board.GetFootprints()}
ADDR_A = range(16, 27); ADDR_B = range(29, 38)
OUTER_DATA = {'U9': set(range(2, 16)), 'U10': set(range(39, 54))}
items = []                                                # (kind, net, geometry) collected, added at the end
def via(x, y, net): items.append(('via', net, (x, y)))
def trk(pts, net, layer): items.append(('trk', net, (pts, layer)))

for ref in ('U9', 'U10'):
    f = fps[ref]; cy = ToMM(f.GetPosition().y)
    assert abs(f.GetOrientationDegrees() + 90) < 0.1 or abs(f.GetOrientationDegrees() - 270) < 0.1, (ref, f.GetOrientationDegrees())
    for p in f.Pads():
        n = int(p.GetNumber()); net = p.GetNetname(); x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        half = ToMM(p.GetBoundingBox().GetHeight()) / 2; out = -1 if y < cy else 1      # north row -> outward is north
        edge = y + out * half; vy = edge + out * VIA_GAP
        if net in ('SDRAM_3V3', 'GND') or (n in OUTER_DATA[ref] and net.startswith('SEMC_')):
            via(x, vy, net); trk([(x, y), (x, vy)], net, pcbnew.F_Cu)
        elif n in ADDR_A:
            via(x, vy, net); trk([(x, y), (x, vy)], net, pcbnew.F_Cu)
            if ref == 'U9':                               # U9 north-row via -> U10 north-row (channel) via, bottom, at x
                q = next(q for q in fps['U10'].Pads() if q.GetNumber() == str(n)); assert q.GetNetname() == net
                qy = ToMM(q.GetPosition().y) - ToMM(q.GetBoundingBox().GetHeight()) / 2 - VIA_GAP
                trk([(x, vy), (x, qy)], net, pcbnew.B_Cu)
        elif n in ADDR_B:
            via(x + 0.4, vy, net); trk([(x, y), (x, edge), (x + 0.4, vy)], net, pcbnew.F_Cu)
            if ref == 'U9':                               # U9 south-row (channel) via -> U10 south-row via, bottom, at x + 0.4
                q = next(q for q in fps['U10'].Pads() if q.GetNumber() == str(n)); assert q.GetNetname() == net
                qy = ToMM(q.GetPosition().y) + ToMM(q.GetBoundingBox().GetHeight()) / 2 + VIA_GAP
                trk([(x + 0.4, vy), (x + 0.4, qy)], net, pcbnew.B_Cu)

n_v = n_t = 0
for kind, net, g in items:
    ni = nets[net]
    if kind == 'via':
        v = pcbnew.PCB_VIA(board); v.SetPosition(VECTOR2I(FromMM(g[0]), FromMM(g[1]))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_H)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(ni); v.SetLocked(True); board.Add(v); n_v += 1
    else:
        pts, layer = g
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6: continue
            t = pcbnew.PCB_TRACK(board); t.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); t.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
            t.SetWidth(FromMM(TRK)); t.SetLayer(layer); t.SetNet(ni); t.SetLocked(True); board.Add(t); n_t += 1
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
for z in board.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, board)
print('SDRAM prebuild: %d vias, %d track segments -> %s' % (n_v, n_t, OUT))
