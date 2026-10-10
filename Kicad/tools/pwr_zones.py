"""Stage 2 (run with KiCad's bundled python3, see build_board.py; edits Kicad/Nosh.kicad_pcb in place, back it up first).
Stage 2c: PWR layer (In3) zones. Edits the saved board in place."""
import pcbnew
from pcbnew import FromMM, VECTOR2I
import os
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
assert not [z for z in board.Zones() if board.GetLayerName(z.GetFirstLayer()) == 'PWR'], 'PWR zones already present'
nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}
def zone(name, net, rect, prio, layer=pcbnew.In3_Cu):
    x0, y0, x1, y1 = rect
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(nets[net]); z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.15)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline(); ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): ol.Append(FromMM(x), FromMM(y))
    z.SetZoneName(name); board.Add(z); return z
zone('PWR_3V3', '+3V3', (0.5, 0.5, 153.4, 81.3), 0)                 # base plane
zone('PWR_5V', '+5V', (0.5, 58.5, 40.0, 81.3), 1)                  # supply corner: jack, fuse, buck input
zone('PWR_SDRAM_3V3', 'SDRAM_3V3', (26.0, 15.0, 54.5, 58.0), 1)    # under U9/U10 (EVKB-style stack)
zone('PWR_WL_3V3', 'WL_3V3', (110.0, 6.0, 140.0, 48.0), 1)         # M.2 socket and card
zone('PWR_VDD_SOC', 'VDD_SOC_IN', (66.5, 36.5, 77.5, 47.5), 2)     # MCU core balls, inside the fan-out field
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
for z in board.Zones(): print(z.GetZoneName(), z.GetNetname(), board.GetLayerName(z.GetFirstLayer()), 'filled area mm2', round(z.GetFilledArea() / 1e12, 1))
