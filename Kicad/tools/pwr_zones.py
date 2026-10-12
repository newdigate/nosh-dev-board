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
    pts = rect if len(rect) != 4 or isinstance(rect[0], tuple) else [(rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])]
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(nets[net]); z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.15)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(FromMM(x), FromMM(y))
    z.SetZoneName(name); board.Add(z); return z
zone('PWR_3V3', '+3V3', (0.5, 0.5, 153.4, 81.3), 0)                 # base plane
zone('PWR_5V', '+5V', (0.5, 58.5, 40.0, 81.3), 1)                  # supply corner: jack, fuse, buck input
zone('PWR_SDRAM_3V3', 'SDRAM_3V3', [(26.0, 15.0), (54.5, 15.0), (54.5, 58.0), (22.3, 58.0), (22.3, 53.6), (24.2, 53.6), (24.2, 51.9), (22.3, 51.9), (22.3, 31.5), (26.0, 31.5)], 1)    # under U9/U10 and their decoupling to the west; notch keeps C82's +3V3 via on the +3V3 plane
zone('PWR_WL_3V3', 'WL_3V3', (110.0, 6.0, 140.0, 48.0), 1)         # M.2 socket and card
zone('PWR_VDD_SOC', 'VDD_SOC_IN', (66.5, 36.5, 77.5, 47.5), 2)     # MCU core balls, inside the fan-out field
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
for z in board.Zones(): print(z.GetZoneName(), z.GetNetname(), board.GetLayerName(z.GetFirstLayer()), 'filled area mm2', round(z.GetFilledArea() / 1e12, 1))

# 2026-10-12 (fanout-first branch): the islands were reshaped on the board itself, not here:
#   PWR_5V      - tongue north to D2 (x 17-22), south-centre strip for U6/U7/D4, tongue to J10.2, 2 mm corridor
#                 x 78.5-80.5 up to a patch x 79.5-83.6 x 29.5-43 for U3/D3 (keeps clear of +3V3 pads and vias)
#   PWR_WL_3V3  - west extension x 85.6-110 x 38-48 for U11/U12, south lip to y 50.4 for FB10/R51/R52
#   PWR_VDD_SOC - trimmed to x >= 69.6, lobe to R6, north pocket for C16/C18/C21/C22 (tools/dcdc_block2.py)
#   PWR_DCDC_IN / _ANA / _DIG - fanout2.py / dcdc_block2.py
#   PWR_5V      - stops at x 23.2 south-west (the 1.8 V regulator block there is +3V3); D2 tongue x 17-21
#   PWR_SDRAM_3V3 - bottom strip y > 56.2 (x < 41) given back to +3V3; notch x 42.5-45 y 15-16.6 for R36;
#                 C82 notch widened to x 24.9
