"""Fan-out, power first (run with KiCad's bundled python3; edits Kicad/Nosh.kicad_pcb in place on a board with no tracks).
1. The DC-DC block moves to U1's south edge and the parts in its way are pushed out.
2. PWR-layer islands for DCDC_IN, DCDC_ANA and DCDC_DIG run from their balls' fan-out vias straight south through
   the via lattice; VDD_SOC's island gets a lobe for R6. The lattice cells in those corridors are reserved.
3. Every ball of ring >= 2 with a net gets a 0.45/0.2 via on a free lattice cell (power balls at fixed cells, then
   innermost first, outward diagonal preferred) and a dog-bone (0.2 mm for the DC-DC/VDD_SOC nets, else 0.1).
Rings 0 and 1 are left for top-layer escapes. Reports balls without a cell and the island areas."""
import os, math, collections, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
assert not list(board.GetTracks()), 'board must have no tracks or vias'
nets = board.GetNetInfo().NetsByName()
fps = {f.GetReference(): f for f in board.GetFootprints()}
# ---- 1. placement: (x, y, rotation, side)
MOVES = {'L1': (67.2, 52.5, 0, 'F'), 'R5': (71.3, 51.15, 0, 'F'), 'R7': (70.6, 53.3, 90, 'F'), 'R6': (73.0, 53.2, 0, 'F'),
         'R90': (74.0, 50.9, 0, 'F'), 'R99': (75.9, 52.6, 0, 'F'), 'FB5': (71.0, 31.5, 90, 'F'), 'R37': (63.0, 51.2, 0, 'F'), 'R13': (63.0, 52.9, 0, 'F'),
         'C23': (68.4, 52.9, -90, 'B'), 'C24': (69.8, 52.9, -90, 'B'), 'C30': (71.9, 51.9, 180, 'B'), 'C32': (74.0, 52.0, 90, 'B'),
         'C28': (71.3, 53.5, 180, 'B'), 'C27': (70.9, 54.9, 180, 'B'), 'C31': (72.8, 58.9, 0, 'B'), 'C33': (72.8, 60.3, 0, 'B'),
         'C1': (74.5, 53.9, 0, 'B'), 'C7': (66.6, 50.6, 180, 'B'), 'C145': (64.6, 49.8, 0, 'B')}
for ref, (x, y, rot, side) in MOVES.items():
    f = fps[ref]
    if (side == 'B') != f.IsFlipped(): f.Flip(f.GetPosition(), False)
    f.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); f.SetOrientationDegrees(rot)
# ---- 2. PWR islands
def zone(name, net, pts, prio):
    for z in list(board.Zones()):
        if z.GetZoneName() == name: board.Remove(z)
    z = pcbnew.ZONE(board); z.SetLayer(board.GetLayerID('PWR')); z.SetNet(nets[net]); z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.15)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(FromMM(x), FromMM(y))
    z.SetZoneName(name); board.Add(z); return z
zone('PWR_VDD_SOC', 'VDD_SOC_IN', [(69.6, 36.5), (77.5, 36.5), (77.5, 47.5), (73.5, 47.5), (73.5, 54.0), (72.9, 54.0), (72.9, 47.5), (69.6, 47.5)], 2)
zone('PWR_DCDC_IN', 'DCDC_IN', [(68.1, 43.7), (68.7, 43.7), (68.7, 49.5), (70.3, 49.5), (70.3, 54.5), (67.9, 54.5), (67.9, 49.5), (68.1, 49.5)], 3)
zone('PWR_DCDC_ANA', 'DCDC_ANA', [(69.65, 44.45), (71.1, 44.45), (71.1, 49.5), (71.5, 49.5), (71.5, 55.7), (70.5, 55.7), (70.5, 45.2), (69.65, 45.2)], 3)
zone('PWR_DCDC_DIG', 'DCDC_DIG', [(71.3, 42.9), (72.7, 42.9), (72.7, 60.8), (71.7, 60.8), (71.7, 49.5), (72.1, 49.5), (72.1, 44.3), (71.3, 44.3)], 3)
# ---- 3. via cells
u1 = fps['U1']; ROWS = 'ABCDEFGHJKLMNPRTU'; PITCH = 0.8; N = 17
cx, cy = ToMM(u1.GetPosition().x), ToMM(u1.GetPosition().y)
pads = {}
for p in u1.Pads():
    n = p.GetNumber(); pads[(ROWS.index(n[0]), int(n[1:]) - 1)] = p
ring = lambda r, c: min(r, c, N - 1 - r, N - 1 - c)
cell_xy = lambda i, j: (round(cx + (j + 0.5 - 8) * PITCH, 2), round(cy + (i + 0.5 - 8) * PITCH, 2))   # cell (i, j): between rows i,i+1 and cols j,j+1
def cell_of(x, y): return (int(round((y - cy) / PITCH + 7.5)), int(round((x - cx) / PITCH + 7.5)))
RESERVED = {cell_of(68.4, y) for y in (46.4, 47.2, 48.0, 48.8)} | {cell_of(70.8, y) for y in (45.6, 46.4, 47.2, 48.0, 48.8)} | {cell_of(71.6, 44.8)} \
         | {cell_of(72.4, y) for y in (44.0, 44.8, 45.6, 46.4, 47.2, 48.0, 48.8)} | {cell_of(73.2, y) for y in (44.0, 44.8, 45.6, 46.4, 47.2, 48.0, 48.8)}   # VDD_SOC's channel to its lobe
FIXED = {'L5': (68.4, 44.0), 'M5': (68.4, 44.8), 'N5': (68.4, 45.6), 'M7': (70.0, 44.8), 'M8': (70.8, 44.8), 'K8': (71.6, 43.2), 'K9': (72.4, 43.2),
         'L8': (71.6, 44.0), 'K10': (73.2, 43.2), 'N8': (71.6, 45.6), 'N7': (70.0, 45.6), 'P7': (70.0, 46.4), 'R7': (70.0, 47.2),
         'N4': (67.6, 45.6), 'J8': (70.8, 42.4), 'J9': (72.4, 42.4)}
WIDE = ('DCDC_IN', 'DCDC_ANA', 'DCDC_DIG', 'VDD_SOC_IN')
taken = set(RESERVED); plan = []; skipped = []
for name, (x, y) in FIXED.items():
    r, c = ROWS.index(name[0]), int(name[1:]) - 1; ij = cell_of(x, y); p = pads[(r, c)]
    assert ij not in taken and abs(ij[0] - r + 0.5) <= 0.5 and abs(ij[1] - c + 0.5) <= 0.5, (name, ij)
    taken.add(ij); plan.append((p, ij))
need = [(r, c, p) for (r, c), p in pads.items() if p.GetNetname() and not p.GetNetname().startswith('unconnected') and ring(r, c) >= 2 and p.GetNumber() not in FIXED and p.GetNumber() != 'L10']
need.sort(key=lambda t: -ring(t[0], t[1]))
for r, c, p in need:
    dr = -1 if r < 8 else 1; dc = -1 if c < 8 else 1
    cands = [(r + (dr - 1) // 2, c + (dc - 1) // 2), (r + (dr - 1) // 2, c + (-dc - 1) // 2), (r + (-dr - 1) // 2, c + (dc - 1) // 2), (r + (-dr - 1) // 2, c + (-dc - 1) // 2)]
    for ij in cands:
        if 0 <= ij[0] < N - 1 and 0 <= ij[1] < N - 1 and ij not in taken: taken.add(ij); plan.append((p, ij)); break
    else: skipped.append(p.GetNumber() + ' ' + p.GetNetname())
# L10 (GND) has no free cell: tie it to L11 on top, which has a via
l10, l11 = pads[(ROWS.index('L'), 9)], pads[(ROWS.index('L'), 10)]
t = pcbnew.PCB_TRACK(board); t.SetStart(l10.GetPosition()); t.SetEnd(l11.GetPosition()); t.SetWidth(FromMM(0.1)); t.SetLayer(pcbnew.F_Cu); t.SetNet(l10.GetNet()); t.SetLocked(True); board.Add(t)
for p, (i, j) in plan:
    vx, vy = cell_xy(i, j); net = p.GetNet(); w = 0.2 if p.GetNetname() in WIDE else 0.1
    v = pcbnew.PCB_VIA(board); v.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(FromMM(0.45)); v.SetDrill(FromMM(0.2)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); v.SetLocked(True); board.Add(v)
    t = pcbnew.PCB_TRACK(board); t.SetStart(p.GetPosition()); t.SetEnd(v.GetPosition()); t.SetWidth(FromMM(w)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); t.SetLocked(True); board.Add(t)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
for z in board.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
print('vias placed: %d (fixed %d), balls without a free cell: %s' % (len(plan), len(FIXED), skipped or 'none'))
PWR = board.GetLayerID('PWR')
for z in board.Zones():
    if z.GetZoneName().startswith('PWR_') and z.GetZoneName() != 'PWR_3V3':
        polys = z.GetFilledPolysList(PWR); n_in = sum(1 for p_, ij in plan if p_.GetNetname() == z.GetNetname() and polys.Contains(VECTOR2I(FromMM(cell_xy(*ij)[0]), FromMM(cell_xy(*ij)[1]))))
        print('  %-14s %-11s %5.1f mm2, %d of its fan-out vias inside' % (z.GetZoneName(), z.GetNetname(), z.GetFilledArea() / 1e12, n_in))
for ref in MOVES: print('  %-5s %s at (%.2f, %.2f) pads %s' % (ref, 'B' if fps[ref].IsFlipped() else 'F', ToMM(fps[ref].GetPosition().x), ToMM(fps[ref].GetPosition().y), [(p.GetNumber(), round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in fps[ref].Pads()]))
