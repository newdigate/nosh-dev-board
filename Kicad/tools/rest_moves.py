"""Placement changes made for the rest-of-board routing (run with KiCad's bundled python3).
usage: rest_moves.py in.kicad_pcb out.kicad_pcb
- R74/R75 (LPI2C5 pull-ups) 0.5 mm west of U15: at x 96.0 they left a 0.65 mm corridor in front of the codec's west
  pads (two 0.1 mm tracks), so pad 17 (SAI1_TXD0) could never leave; their old +3V3 stubs and vias are removed
  (plane_vias.py gives the moved pads new ones).
- VDD_SOC_IN tongue: the PWR island gets 73.5-78.3 x 50.0-52.8 so C17/R8 (x 77.3-78.0) can drop into it; only GND
  vias sit there and the +3V3 strip between the island and +5V reconnects north of y 50 and south of y 65."""
import sys, math, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(IN); fps = {f.GetReference(): f for f in b.GetFootprints()}
MOVES = {'R74': (95.5, 69.75, 90, 'F'), 'R75': (95.5, 67.25, -90, 'F')}   # J10's courtyard ends at x 94.9
old_pads = []
for ref, (x, y, rot, side) in MOVES.items():
    f = fps[ref]; old_pads += [(p.GetNetname(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in f.Pads()]
    if (side == 'B') != f.IsFlipped(): f.Flip(f.GetPosition(), False)
    f.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); f.SetOrientationDegrees(rot)
    print('  %s -> (%.2f, %.2f) pads %s' % (ref, x, y, [(p.GetNumber(), round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in f.Pads()]))
rm = []
for t in b.GetTracks():                                           # stubs and vias that fed the old pad positions
    if t.GetNetname() != '+3V3': continue
    for net, px, py in old_pads:
        if net != '+3V3': continue
        if t.Type() == pcbnew.PCB_VIA_T and math.hypot(ToMM(t.GetPosition().x) - px, ToMM(t.GetPosition().y) - py) < 1.0: rm.append(t)
        elif t.Type() == pcbnew.PCB_TRACE_T and any(math.hypot(ToMM(q.x) - px, ToMM(q.y) - py) < 0.3 for q in (t.GetStart(), t.GetEnd())): rm.append(t)
for ref in MOVES:                                                  # routed copper of other nets under the new position goes (re-routed later)
    f = fps[ref]; bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox(); x0, y0, x1, y1 = ToMM(bb.GetLeft()) - 0.2, ToMM(bb.GetTop()) - 0.2, ToMM(bb.GetRight()) + 0.2, ToMM(bb.GetBottom()) + 0.2
    pnets = {p.GetNetname() for p in f.Pads()}
    for t in b.GetTracks():
        if t.GetNetname() in ('GND', '+3V3') or t.GetNetname().startswith('SEMC'): continue
        if t.Type() == pcbnew.PCB_VIA_T: qx0 = qx1 = ToMM(t.GetPosition().x); qy0 = qy1 = ToMM(t.GetPosition().y)
        else: qx0, qx1 = sorted((ToMM(t.GetStart().x), ToMM(t.GetEnd().x))); qy0, qy1 = sorted((ToMM(t.GetStart().y), ToMM(t.GetEnd().y)))
        if qx1 > x0 and qx0 < x1 and qy1 > y0 and qy0 < y1: rm.append(t); print('  dropping %s %s under %s' % (t.GetNetname(), 'via' if t.Type() == pcbnew.PCB_VIA_T else 'track', ref))
rm = list({t.m_Uuid.AsString(): t for t in rm}.values())
for t in rm: b.Remove(t)
print('  removed %d old +3V3 items' % len(rm))
for z in b.Zones():
    if z.GetZoneName() == 'PWR_VDD_SOC':
        pts = [(69.6, 36.5), (71.2, 36.5), (71.2, 35.3), (71.6, 35.3), (71.6, 33.8), (69.0, 33.8), (69.0, 30.3), (74.3, 30.3), (74.3, 33.8), (72.0, 33.8), (72.0, 36.5),
               (77.5, 36.5), (77.5, 47.5), (73.5, 47.5), (73.5, 50.0), (78.3, 50.0), (78.3, 52.8), (73.6, 52.8), (73.6, 65.2), (72.5, 65.2), (72.5, 51.0), (72.9, 50.0), (72.9, 47.5), (69.6, 47.5)]
        ol = z.Outline(); ol.RemoveAllContours(); ol.NewOutline()
        for x, y in pts: ol.Append(FromMM(x), FromMM(y))
        print('  PWR_VDD_SOC outline rebuilt with the C17/R8 tongue')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b); print('-> ' + OUT)
