"""One-off (2026-10-09, run with KiCad's bundled python3; edits Kicad/Nosh.kicad_pcb in place): board outline from
155 x 83.5 to the RK055 carrier's measured 153.9 x 81.8 mm, origin kept at the NW corner. Holes re-centred on the
EVKB 147.253 x 72.905 pattern, J7 kept 6.3 mm west of the new centre line, east-edge parts moved 1.1 mm west,
south-edge parts 1.7 mm north, zones clipped, routed pairs removed (regenerate with route_pairs.py after
optimise_placement.py)."""
import os, re, sys, subprocess, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
board = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
W, H = 153.9, 81.8; DXE, DYS = -1.1, -1.7
PHASE = sys.argv[1] if len(sys.argv) > 1 else 'moves'    # pcbnew's SWIG layer breaks when the two phases share one process
fps = {f.GetReference(): f for f in board.GetFootprints()}
if PHASE == 'edges':
    for d in [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]: board.Remove(d)
    for (x0, y0), (x1, y1) in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
        sh = pcbnew.PCB_SHAPE(board); sh.SetShape(pcbnew.SHAPE_T_SEGMENT); sh.SetLayer(pcbnew.Edge_Cuts); sh.SetWidth(FromMM(0.1))
        sh.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); sh.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1))); board.Add(sh)
    pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board); print('outline rewritten %.1f x %.1f' % (W, H)); sys.exit(0)
assert abs(ToMM(board.GetBoardEdgesBoundingBox().GetWidth()) - 155.0) < 0.2, 'outline is not 155 wide; already shrunk?'
def mv(ref, x=None, y=None, dx=0.0, dy=0.0):
    f = fps[ref]; px, py = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y)
    nx, ny = (x if x is not None else px) + dx, (y if y is not None else py) + dy
    f.SetPosition(VECTOR2I(FromMM(nx), FromMM(ny))); print('  %-4s (%.3f, %.3f) -> (%.3f, %.3f)' % (ref, px, py, nx, ny))
hx0, hx1 = (W - 147.253) / 2, (W + 147.253) / 2; hy0, hy1 = (H - 72.905) / 2, (H + 72.905) / 2
mv('H1', hx0, hy0); mv('H2', hx1, hy0); mv('H3', hx1, hy1); mv('H4', hx0, hy1)
mv('J7', W / 2 - 6.3, None)                                   # stays aligned with the carrier's FPC connector
for r in ('J2', 'J3', 'L3', 'L4', 'U4', 'U5'): mv(r, dx=DXE)   # east edge and the USB parts pinned to it
for r in ('J8', 'J9'): mv(r, dy=DYS)                          # south edge
for z in board.Zones():
    o = z.Outline()
    for i in range(o.VertexCount()):
        v = o.CVertex(i); x, y = ToMM(v.x), ToMM(v.y)
        o.SetVertex(i, VECTOR2I(FromMM(min(x, W - 0.5)), FromMM(min(y, H - 0.5))))
    z.UnFill(); z.SetIsFilled(False)
u1 = fps['U1']; cx, cy = ToMM(u1.GetPosition().x), ToMM(u1.GetPosition().y); rm = 0
PAIR = re.compile(r'^(MIPI_DSI_|USB[12]_(DP|DN|CON_DP|CON_DN)$)')
for t in list(board.GetTracks()):
    if not PAIR.match(t.GetNetname()): continue
    inside = abs(ToMM(t.GetPosition().x) - cx) < 7.5 and abs(ToMM(t.GetPosition().y) - cy) < 7.5
    fan = inside and (t.Type() == pcbnew.PCB_VIA_T or abs(ToMM(t.GetWidth()) - 0.1) < 0.001)
    if not fan: board.Remove(t); rm += 1
print('pair routing items removed:', rm)
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board); print('moves saved')
subprocess.run([sys.executable, os.path.abspath(__file__), 'edges'])          # may segfault at interpreter exit, after saving
