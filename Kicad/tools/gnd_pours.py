"""Stage 3 (run with KiCad's bundled python3; edits Kicad/Nosh.kicad_pcb in place, back it up first):
GND pours on F.Cu and B.Cu. Left unfilled (fill in KiCad with B when routing is done); priority 0, below any
other outer-layer zone; 0.25 mm clearance, 0.2 mm minimum width, all islands removed, thermal reliefs.
Skips if a zone named GND_F or GND_B already exists."""
import os, pcbnew
from pcbnew import FromMM, VECTOR2I
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
have = {z.GetZoneName() for z in board.Zones()}
gnd = board.GetNetInfo().NetsByName()['GND']
W, H, INSET = 155.0, 83.5, 0.5
for name, layer in (('GND_F', pcbnew.F_Cu), ('GND_B', pcbnew.B_Cu)):
    if name in have: print(name, 'exists, skipped'); continue
    z = pcbnew.ZONE(board); z.SetZoneName(name); z.SetLayer(layer); z.SetNet(gnd); z.SetAssignedPriority(0)
    z.SetLocalClearance(FromMM(0.25)); z.SetMinThickness(FromMM(0.2))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(FromMM(0.25)); z.SetThermalReliefSpokeWidth(FromMM(0.3))
    z.SetIsFilled(False)
    o = z.Outline(); o.NewOutline()
    for x, y in ((INSET, INSET), (W - INSET, INSET), (W - INSET, H - INSET), (INSET, H - INSET)):
        o.Append(VECTOR2I(FromMM(x), FromMM(y)))
    board.Add(z); print(name, 'added')
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
print('saved')
