"""Local changes so the DCDC pins (south-west corner) and A4/A5 (north edge) can leave the ball field:
 - C145 (the SEMC_DQS loop-back cap) moves east out of the way; its lane is cut back to the ball column
 - SEMC_D30's top-layer run under U3/U4 and SEMC_A3's top-layer run over A4/A5 are cut (genroute re-joins them)
 - temporary keep-outs on F.Cu hold the U3/U4 and A4/A5 exits open while genroute re-joins
 - DCDC_IN gets a PWR island under its three balls down to C23/C24; VDD_SOC's island is trimmed to its vias
usage: sw_rework.py in.kicad_pcb out.kicad_pcb"""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(IN)
nets = b.GetNetInfo().NetsByName()
def seg_key(t):
    a = (round(ToMM(t.GetStart().x), 2), round(ToMM(t.GetStart().y), 2)); c = (round(ToMM(t.GetEnd().x), 2), round(ToMM(t.GetEnd().y), 2))
    return (t.GetNetname(), b.GetLayerName(t.GetLayer()), min(a, c), max(a, c))
CUT = {('SEMC_DQS', 'B.Cu', (67.1, 49.55), (68.8, 47.85)), ('SEMC_DQS', 'B.Cu', (67.1, 49.55), (67.1, 49.67)), ('SEMC_DQS', 'B.Cu', (67.02, 49.75), (67.1, 49.67)),
       ('SEMC_D30', 'F.Cu', (66.95, 49.15), (67.55, 48.55)), ('SEMC_D30', 'F.Cu', (65.85, 49.15), (66.95, 49.15)), ('SEMC_D30', 'F.Cu', (65.8, 49.1), (65.85, 49.15)),
       ('SEMC_A3', 'F.Cu', (68.85, 35.15), (69.15, 35.45)), ('SEMC_A3', 'F.Cu', (67.5, 35.15), (68.85, 35.15))}
CUT_VIA = {('SEMC_A3', 67.5, 35.15)}
rm = []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        if (t.GetNetname(), round(ToMM(t.GetPosition().x), 2), round(ToMM(t.GetPosition().y), 2)) in CUT_VIA: rm.append(t)
    elif seg_key(t) in CUT: rm.append(t)
assert len(rm) == len(CUT) + len(CUT_VIA), 'found %d of %d items to cut' % (len(rm), len(CUT) + len(CUT_VIA))
for t in rm: b.Remove(t)
c145 = next(f for f in b.GetFootprints() if f.GetReference() == 'C145')
c145.SetPosition(VECTOR2I(FromMM(68.6), FromMM(50.8)))
print('C145 pads now', [(p.GetNumber(), round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in c145.Pads()])
def keepout(name, x0, y0, x1, y1):
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
    z.SetLayer(pcbnew.F_Cu); ol = z.Outline(); ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): ol.Append(FromMM(x), FromMM(y))
    z.SetZoneName(name); b.Add(z)
keepout('TMP_U3U4_EXIT', 66.9, 48.65, 68.6, 51.0)
keepout('TMP_A4A5_EXIT', 67.7, 33.0, 68.95, 35.2)
vs = next(z for z in b.Zones() if z.GetZoneName() == 'PWR_VDD_SOC')
ol = vs.Outline(); ol.RemoveAllContours(); ol.NewOutline()
for x, y in ((69.6, 36.5), (77.5, 36.5), (77.5, 47.5), (69.6, 47.5)): ol.Append(FromMM(x), FromMM(y))
z = pcbnew.ZONE(b); z.SetLayer(b.GetLayerID('PWR')); z.SetNet(nets['DCDC_IN']); z.SetAssignedPriority(3)
z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.15)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
ol = z.Outline(); ol.NewOutline()
for x, y in ((67.9, 43.3), (69.3, 43.3), (69.3, 49.5), (72.2, 49.5), (72.2, 53.3), (68.2, 53.3), (68.2, 49.5), (67.9, 49.5)): ol.Append(FromMM(x), FromMM(y))
z.SetZoneName('PWR_DCDC_IN'); b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for zz in b.Zones():
    if zz.GetZoneName() in ('GND_F', 'GND_B'): zz.UnFill(); zz.SetIsFilled(False)
    if zz.GetZoneName() in ('PWR_DCDC_IN', 'PWR_VDD_SOC'): print(zz.GetZoneName(), 'filled mm2', round(zz.GetFilledArea() / 1e12, 2))
pcbnew.SaveBoard(OUT, b)
print('cut %d items, saved %s' % (len(rm), OUT))
