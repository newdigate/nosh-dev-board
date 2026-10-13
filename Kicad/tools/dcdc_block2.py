"""DC-DC block, second placement (run with KiCad's bundled python3): the caps and R6 move south of the escape fan
(y 58-63), and the four PWR islands get 1.1 mm wide lobes that jog under L1 into side-by-side columns there,
so every cap has via sites. usage: dcdc_block2.py in.kicad_pcb out.kicad_pcb"""
import sys, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(IN); nets = b.GetNetInfo().NetsByName(); fps = {f.GetReference(): f for f in b.GetFootprints()}
MOVES = {'C23': (68.1, 59.2, -90, 'B'), 'C24': (68.1, 62.0, -90, 'B'),                          # DCDC_IN column
         'C27': (69.75, 59.2, -90, 'B'), 'C28': (69.75, 62.0, -90, 'B'),                        # DCDC_ANA column
         'C30': (71.4, 59.2, -90, 'B'), 'C31': (71.4, 62.3, -90, 'B'), 'C32': (73.05, 59.3, 90, 'B'), 'C33': (73.05, 61.3, 90, 'B'), 'C19': (73.05, 57.2, 90, 'B'),   # DCDC_DIG
         'R6': (73.05, 62.7, -90, 'F'), 'R5': (69.75, 63.3, 0, 'F'), 'R7': (69.0, 55.2, 90, 'F'),
         'L1': (65.9, 52.5, 0, 'F'), 'R37': (61.0, 51.2, 0, 'F'), 'R13': (61.0, 52.9, 0, 'F'), 'R90': (61.0, 54.6, 0, 'F'),   # off the top exits of the south edge
         'TP40': (64.0, 57.2, 0, 'F'), 'C144': (68.8, 56.6, 0, 'B'), 'C44': (65.2, 56.5, 0, 'B'), 'C50': (67.0, 55.45, 0, 'B')}
for ref, (x, y, rot, side) in MOVES.items():
    f = fps[ref]
    if (side == 'B') != f.IsFlipped(): f.Flip(f.GetPosition(), False)
    f.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); f.SetOrientationDegrees(rot)
def zone(name, net, pts, prio):
    for z in list(b.Zones()):
        if z.GetZoneName() == name: b.Remove(z)
    z = pcbnew.ZONE(b); z.SetLayer(b.GetLayerID('PWR')); z.SetNet(nets[net]); z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.15)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(FromMM(x), FromMM(y))
    z.SetZoneName(name); b.Add(z)
# corridors through the lattice as before; below y = 49.6 each widens to 1.1 mm and jogs into its column
zone('PWR_DCDC_IN', 'DCDC_IN', [(68.1, 43.7), (68.7, 43.7), (68.7, 49.6), (68.65, 49.6), (68.65, 63.8), (67.55, 63.8), (67.55, 49.6), (68.1, 49.6)], 3)
zone('PWR_DCDC_ANA', 'DCDC_ANA', [(69.65, 44.45), (71.1, 44.45), (71.1, 49.6), (70.3, 50.8), (70.3, 63.8), (69.2, 63.8), (69.2, 50.6), (70.5, 49.6), (70.5, 45.2), (69.65, 45.2)], 3)
zone('PWR_DCDC_DIG', 'DCDC_DIG', [(71.3, 42.9), (72.7, 42.9), (72.7, 49.6), (71.95, 51.2), (71.95, 64.6), (70.85, 64.6), (70.85, 51.0), (72.1, 49.6), (72.1, 44.3), (71.3, 44.3)], 3)
zone('PWR_VDD_SOC', 'VDD_SOC_IN', [(69.6, 36.5), (71.2, 36.5), (71.2, 35.3), (71.6, 35.3), (71.6, 33.8), (69.0, 33.8), (69.0, 30.3), (74.3, 30.3), (74.3, 33.8), (72.0, 33.8), (72.0, 36.5),   # north neck + pocket for C16/C18/C21/C22
      (77.5, 36.5), (77.5, 47.5), (73.5, 47.5), (73.5, 50.0), (78.3, 50.0), (78.3, 52.8), (73.6, 52.8), (73.6, 65.2), (72.5, 65.2), (72.5, 51.0), (72.9, 50.0), (72.9, 47.5), (69.6, 47.5)], 2)   # + tongue for C17/R8 (rest_moves.py)
for z in list(b.Zones()):
    if z.GetZoneName() == 'KO_DCDC_JOG': b.Remove(z)
ko = pcbnew.ZONE(b); ko.SetIsRuleArea(True); ko.SetDoNotAllowVias(True); ko.SetDoNotAllowTracks(False)
for fn in ('SetDoNotAllowPads', 'SetDoNotAllowFootprints', 'SetDoNotAllowZoneFills', 'SetDoNotAllowCopperPour'):
    if hasattr(ko, fn): getattr(ko, fn)(False)
ls = pcbnew.LSET(); [ls.addLayer(l) for l in (pcbnew.F_Cu, b.GetLayerID('SIG'), pcbnew.B_Cu)]; ko.SetLayerSet(ls)
ol = ko.Outline(); ol.NewOutline()
for x, y in ((67.4, 49.0), (73.8, 49.0), (73.8, 64.5), (67.4, 64.5)): ol.Append(FromMM(x), FromMM(y))   # the whole lobe region: only the islands' own vias (plane_vias.py) go here
ko.SetZoneName('KO_DCDC_JOG'); b.Add(ko)
for z in list(b.Zones()):
    if z.GetZoneName() == 'KO_SOC_NECK': b.Remove(z)
kn = pcbnew.ZONE(b); kn.SetIsRuleArea(True); kn.SetDoNotAllowVias(True); kn.SetDoNotAllowTracks(False)
for fn in ('SetDoNotAllowPads', 'SetDoNotAllowFootprints', 'SetDoNotAllowZoneFills', 'SetDoNotAllowCopperPour'):
    if hasattr(kn, fn): getattr(kn, fn)(False)
ls = pcbnew.LSET(); [ls.addLayer(l) for l in (pcbnew.F_Cu, b.GetLayerID('SIG'), pcbnew.B_Cu)]; kn.SetLayerSet(ls)
ol = kn.Outline(); ol.NewOutline()
for x, y in ((71.0, 33.6), (72.2, 33.6), (72.2, 36.6), (71.0, 36.6)): ol.Append(FromMM(x), FromMM(y))
kn.SetZoneName('KO_SOC_NECK'); b.Add(kn)                         # the VDD_SOC neck to its north pocket: no other vias
for z in list(b.Zones()):
    if z.GetZoneName() == 'KO_DCDC_TOP': b.Remove(z)
kt = pcbnew.ZONE(b); kt.SetIsRuleArea(True); kt.SetDoNotAllowTracks(True); kt.SetDoNotAllowVias(False)
for fn in ('SetDoNotAllowPads', 'SetDoNotAllowFootprints', 'SetDoNotAllowZoneFills', 'SetDoNotAllowCopperPour'):
    if hasattr(kt, fn): getattr(kt, fn)(False)
kt.SetLayer(pcbnew.F_Cu); ol = kt.Outline(); ol.NewOutline()
for x, y in ((67.3, 56.0), (74.0, 56.0), (74.0, 62.0), (67.3, 62.0)): ol.Append(FromMM(x), FromMM(y))
kt.SetZoneName('KO_DCDC_TOP'); b.Add(kt)                          # the cap columns: no top-layer through-traffic
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b)
PWR = b.GetLayerID('PWR')
for z in b.Zones():
    if z.GetZoneName() in ('PWR_DCDC_IN', 'PWR_DCDC_ANA', 'PWR_DCDC_DIG', 'PWR_VDD_SOC'):
        ps = z.GetFilledPolysList(PWR); bb = ps.BBox()
        print('  %-13s outlines %d, %.1f mm2, y %.1f..%.1f' % (z.GetZoneName(), ps.OutlineCount(), z.GetFilledArea() / 1e12, ToMM(bb.GetTop()), ToMM(bb.GetBottom())))
for ref in MOVES: print('  %-5s %s (%.2f, %.2f) pads %s' % (ref, 'B' if fps[ref].IsFlipped() else 'F', ToMM(fps[ref].GetPosition().x), ToMM(fps[ref].GetPosition().y), [(p.GetNumber(), round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in fps[ref].Pads()]))
