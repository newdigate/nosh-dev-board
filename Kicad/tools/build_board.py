"""Nosh PCB, stage 1: board setup, netlist import and floor plan.

Rebuilds Kicad/Nosh.kicad_pcb FROM SCRATCH: every run discards manual board edits.
Run with KiCad's bundled Python, which provides pcbnew:

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 Kicad/tools/build_board.py

Design rules and net classes live in Nosh.kicad_pro (see README, "PCB layout").
"""
import re, json, math, collections, sys, os, subprocess, tempfile
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
SCR = tempfile.mkdtemp() + '/'
KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
subprocess.run([KICAD_CLI, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', SCR + 'nosh_layout.net', K + 'Nosh.kicad_sch'], check=True, capture_output=True)
STOCK = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'
W, H = 155.0, 83.5                      # board outline (RK055 carrier, user measured; refine from the NXP drawing)
HOLE_DX, HOLE_DY = 147.253, 72.905      # EVKB SS1-SS4 pattern, centred on the outline
EDGE_INSET = 0.3                        # connector courtyards stop this far inside the edge
GAP = 0.3                               # courtyard to courtyard spacing for auto-packed parts

# ------------------------------------------------------------------ netlist
T = open(SCR + 'nosh_layout.net').read()
comps = {}
ci = T.index('(components'); ni = T.index('(nets')
for m in re.finditer(r'\n\t\t\(comp\n([\s\S]*?)\n\t\t\)', T[ci:ni]):
    b = m.group(1)
    g = lambda k: (re.search(r'\(' + k + r' "([^"]*)"\)', b) or [None, ''])[1]
    props = dict(re.findall(r'\(property\s*\(name "([^"]+)"\)(?:\s*\(value "([^"]*)"\))?', b))
    sheet_names = re.search(r'\(sheetpath\s*\(names "([^"]*)"\)\s*\(tstamps "([^"]*)"\)', b)
    comps[g('ref')] = dict(value=g('value'), fp=g('footprint'), desc=g('description'), sheet=sheet_names.group(1).strip('/'), path=sheet_names.group(2).rstrip('/') + '/' + g('tstamps'),
                           fields={k: v for k, v in re.findall(r'\(field\s*\(name "([^"]+)"\)(?: "([^"]*)")?\)', b) if k not in ('Reference', 'Value', 'Footprint', 'Description')},
                           dnp='dnp' in props, no_bom='exclude_from_bom' in props, no_pos='exclude_from_pos_files' in props)
nets = {}
for blk in re.split(r'\(net\s', T[ni:])[1:]:
    name = re.search(r'\(name "([^"]*)"', blk).group(1)
    nets[name] = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', blk)
padnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
print('netlist:', len(comps), 'components,', len(nets), 'nets')

# ------------------------------------------------------------------ board + layers + rules
board = pcbnew.BOARD()
board.SetCopperLayerCount(6)
for lay, name in ((pcbnew.In1_Cu, 'GND1'), (pcbnew.In2_Cu, 'SIG'), (pcbnew.In3_Cu, 'PWR'), (pcbnew.In4_Cu, 'GND2')):
    board.SetLayerName(lay, name)
ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.09); ds.m_ViasMinSize = FromMM(0.45); ds.m_MinThroughDrill = FromMM(0.3)
ds.m_MinClearance = FromMM(0.09); ds.m_CopperEdgeClearance = FromMM(0.3); ds.m_HoleClearance = FromMM(0.2); ds.m_HoleToHoleMin = FromMM(0.5)
ds.m_SolderMaskMinWidth = FromMM(0.1)
for w in (0.1, 0.13, 0.15, 0.2, 0.3, 0.5, 1.0): ds.m_TrackWidthList.push_back(FromMM(w))
for d, dr in ((0.5, 0.3), (0.45, 0.3), (0.4, 0.2)): ds.m_ViasDimensionsList.push_back(pcbnew.VIA_DIMENSION(FromMM(d), FromMM(dr)))
# diff pair list is not wrapped in SWIG; it is written to the .kicad_pro instead
stackup_ok = False
try:
    su = ds.GetStackupDescriptor(); su.RemoveAll(); su.BuildDefaultStackupList(ds, 6)
    diel = [(0.0994, 'prepreg', '3313', 4.1), (0.55, 'core', 'NP-155F', 4.6), (0.1088, 'prepreg', '2116', 4.1), (0.55, 'core', 'NP-155F', 4.6), (0.0994, 'prepreg', '3313', 4.1)]
    di = 0
    for it in su.GetList():
        if it.GetType() == pcbnew.BS_ITEM_TYPE_COPPER:
            it.SetThickness(FromMM(0.035 if it.GetBrdLayerId() in (pcbnew.F_Cu, pcbnew.B_Cu) else 0.0152))
        elif it.GetType() == pcbnew.BS_ITEM_TYPE_DIELECTRIC:
            th, tn, mat, er = diel[di]; di += 1
            it.SetThickness(FromMM(th)); it.SetTypeName(tn); it.SetMaterial(mat); it.SetEpsilonR(er); it.SetLossTangent(0.02)
    su.m_FinishType = 'ENIG'; su.m_HasDielectricConstrains = False
    ds.m_HasStackup = True; stackup_ok = di == 5
except Exception as e:
    print('stackup API failed:', e)
print('stackup via API:', stackup_ok)

# ------------------------------------------------------------------ nets
netinfo = {}
for name in nets:
    item = pcbnew.NETINFO_ITEM(board, name); board.Add(item); netinfo[name] = item

# ------------------------------------------------------------------ footprints
def libpath(lib): return K + 'Nosh.pretty' if lib == 'Nosh' else STOCK + lib + '.pretty'
fps = {}
for ref, c in comps.items():
    lib, name = c['fp'].split(':', 1)
    fp = pcbnew.FootprintLoad(libpath(lib), name); assert fp is not None, (ref, c['fp'])
    fp.SetReference(ref); fp.SetValue(c['value']); fp.SetPath(pcbnew.KIID_PATH(c['path'])); fp.SetFPID(pcbnew.LIB_ID(lib, name))
    for k, v in list(c['fields'].items()) + [('Description', c['desc'])]:
        fp.SetField(k, v)
    for f in fp.GetFields():
        if f.GetName() not in ('Reference', 'Value'): f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
    for gi in list(fp.GraphicalItems()):          # some library connectors draw a suggested board edge; keep our outline the only one
        if gi.GetLayer() == pcbnew.Edge_Cuts: fp.Remove(gi)
    a = fp.GetAttributes()
    if c['no_bom']: a |= pcbnew.FP_EXCLUDE_FROM_BOM
    if c['no_pos']: a |= pcbnew.FP_EXCLUDE_FROM_POS_FILES
    if c['dnp']: a |= pcbnew.FP_DNP
    fp.SetAttributes(a)
    board.Add(fp)
    for pad in fp.Pads():
        n = padnet.get((ref, pad.GetNumber()))
        if n: pad.SetNet(netinfo[n])
    fps[ref] = fp
print('footprints placed on board:', len(fps))

# ------------------------------------------------------------------ geometry helpers
def bbox(fp, side=None):
    side = side or ('bottom' if fp.GetLayer() == pcbnew.B_Cu else 'top')
    poly = fp.GetCourtyard(pcbnew.B_CrtYd if side == 'bottom' else pcbnew.F_CrtYd)
    bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False, False)
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
def place(ref, x, y, rot=0, side='top'):
    fp = fps[ref]
    fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); fp.SetOrientationDegrees(rot)
    if side == 'bottom' and fp.GetLayer() != pcbnew.B_Cu:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    return fp
def place_edge(ref, edge, along, rot, inset=EDGE_INSET):
    """Put the footprint's courtyard `inset` inside `edge` ('N','S','E','W'), centred at `along` on that edge."""
    fp = place(ref, 0, 0, rot); x0, y0, x1, y1 = bbox(fp)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if edge == 'E': px, py = (W - inset) - x1, along - cy
    elif edge == 'W': px, py = inset - x0, along - cy
    elif edge == 'S': px, py = along - cx, (H - inset) - y1
    else: px, py = along - cx, inset - y0
    fp.SetPosition(VECTOR2I(FromMM(px), FromMM(py))); return fp
def place_centre(ref, cx, cy, rot=0, side='top'):
    fp = place(ref, 0, 0, rot, side); x0, y0, x1, y1 = bbox(fp)
    fp.SetPosition(VECTOR2I(FromMM(cx - (x0 + x1) / 2), FromMM(cy - (y0 + y1) / 2))); return fp

# ------------------------------------------------------------------ floor plan (explicit parts)
hx0, hy0 = (W - HOLE_DX) / 2, (H - HOLE_DY) / 2
holes = {'H1': (hx0, hy0), 'H2': (W - hx0, hy0), 'H3': (W - hx0, H - hy0), 'H4': (hx0, H - hy0)}   # SS1 NW, SS2 NE, SS3 SE, SS4 SW
for r, (x, y) in holes.items(): place(r, x, y)
MCU = (72.0, 42.0)
place('U1', *MCU)
place_centre('U9', 53.5, 42.0); place_centre('U10', 38.5, 42.0)                 # SDRAM, west of the MCU (SEMC balls west)
place_centre('U2', 90.0, 44.0)                                                   # QSPI flash, east (FlexSPI balls east)
place_centre('U11', 97.0, 24.0); place_centre('U12', 97.0, 34.0)                 # M.2 level shifters
place_centre('L1', 63.0, 54.5)                                                   # DCDC inductor, MCU south-west
place_centre('Y1', 82.5, 52.5); place_centre('Y2', 82.5, 56.5)                   # crystals, MCU south-east
place('J6', 125.0, 40.0, 180)                                                    # M.2 socket, card extends north
place('H5', 125.0, 10.0)                                                         # retention nut, 30 mm up the card
place_edge('J5', 'E', 19.0, 90)                                                  # microSD
place_edge('J2', 'E', 36.0, 90)                                                  # USB2 micro-AB
place_edge('J3', 'E', 50.0, 90)                                                  # USB1 USB-C
place_edge('J8', 'S', 118.0, 180); place_edge('J9', 'S', 131.0, 180)             # audio jacks, south edge (EVKB audio side)
place_centre('U15', 124.0, 58.0)                                                 # codec
place_centre('J10', 100.0, 62.0)                                                 # expansion header
place_edge('J1', 'S', 60.0, 0); place_edge('J11', 'S', 72.0, 90)                 # SWD, debug UART
place_edge('J4', 'W', 62.0, 270)                                                 # barrel jack, opening west
for r, (x, y) in {'F1': (20.0, 56.0), 'D2': (20.0, 61.5), 'U6': (28.5, 56.0), 'L5': (28.5, 62.0), 'U7': (20.0, 67.5), 'U8': (29.0, 69.5), 'Q3': (36.0, 56.0)}.items():
    place_centre(r, x, y)
for r, x in (('SW1', 14.0), ('SW2', 22.0), ('SW3', 30.0)): place_centre(r, x, 77.0)       # reset, on/off, wakeup
place_centre('SW4', 46.0, 27.0)                                                  # boot DIP
place('J7', 71.2, 5.0, 0, 'bottom')                                              # display FPC, bottom, opening north
for r, (x, y) in {'FID1': (6.0, 10.0), 'FID2': (143.0, 6.5), 'FID3': (6.0, 72.0)}.items(): place(r, x, y)
for r, (x, y) in {'FID4': (147.0, 73.0), 'FID5': (8.0, 73.0), 'FID6': (143.0, 6.5)}.items(): place(r, x, y, 0, 'bottom')
explicit = set(holes) | {'U1', 'U9', 'U10', 'U2', 'U11', 'U12', 'L1', 'Y1', 'Y2', 'J6', 'H5', 'J5', 'J2', 'J3', 'J8', 'J9', 'U15', 'J10', 'J1', 'J11', 'J4',
                         'F1', 'D2', 'U6', 'L5', 'U7', 'U8', 'Q3', 'SW1', 'SW2', 'SW3', 'SW4', 'J7', 'FID1', 'FID2', 'FID3', 'FID4', 'FID5', 'FID6'}
# sanity: connector openings at the right edges
for r, e in (('J5', 'E'), ('J2', 'E'), ('J3', 'E'), ('J4', 'W'), ('J8', 'S'), ('J9', 'S')):
    x0, y0, x1, y1 = bbox(fps[r]); edge_pos = {'E': x1, 'W': x0, 'S': y1}[e]; target = {'E': W, 'W': 0, 'S': H}[e]
    assert abs(edge_pos - target) < 0.35, (r, e, edge_pos)
j6 = fps['J6']; mod_txt = [t for t in j6.GraphicalItems() if isinstance(t, pcbnew.PCB_TEXT) and 'MODULE' in t.GetText()]
assert mod_txt and ToMM(mod_txt[0].GetPosition().y) < 40.0, 'M.2 module text should be north of the socket after rotation'

# ------------------------------------------------------------------ packer for everything else
occ = {'top': [], 'bottom': []}
def is_tht(fp): return any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH for p in fp.Pads())
def occupy(fp):
    side = 'bottom' if fp.GetLayer() == pcbnew.B_Cu else 'top'; r = bbox(fp)
    for s in (('top', 'bottom') if is_tht(fp) else (side,)): occ[s].append(r)
for r in explicit: occupy(fps[r])
for (x, y) in holes.values():                       # standoff bodies, both sides
    for s in occ: occ[s].append((x - 2.4, y - 2.4, x + 2.4, y + 2.4))
def free(r, side):
    x0, y0, x1, y1 = r
    if x0 < 0.6 or y0 < 0.6 or x1 > W - 0.6 or y1 > H - 0.6: return False
    for a0, b0, a1, b1 in occ[side]:
        if x0 < a1 + GAP and x1 > a0 - GAP and y0 < b1 + GAP and y1 > b0 - GAP: return False
    return True
shape_cache = {}
def shape(ref, rot, side):
    key = (comps[ref]['fp'], rot, side)
    if key not in shape_cache:
        lib, name = comps[ref]['fp'].split(':', 1); tmp = pcbnew.FootprintLoad(libpath(lib), name)
        board.Add(tmp); tmp.SetPosition(VECTOR2I(0, 0)); tmp.SetOrientationDegrees(rot)
        if side == 'bottom': tmp.Flip(tmp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        shape_cache[key] = bbox(tmp, side); board.Remove(tmp)
    return shape_cache[key]
def pack(ref, ax, ay, side='top', rots=(0, 90), rmax=70.0):
    fp = fps[ref]
    for i in range(0, int(rmax / 0.5)):
        rad = 0.5 * i; n = max(1, int(2 * math.pi * rad / 0.75))
        for k in range(n):
            ang = 2 * math.pi * k / n; x = round((ax + rad * math.cos(ang)) * 4) / 4; y = round((ay + rad * math.sin(ang)) * 4) / 4
            for rot in rots:
                sx0, sy0, sx1, sy1 = shape(ref, rot, side); r = (x + sx0, y + sy0, x + sx1, y + sy1)
                if free(r, side) and (side == 'top' or free(r, 'top') or not is_tht(fp)):
                    place(ref, x, y, rot, side); occupy(fp); return True
    print('PACK FAILED', ref); return False

# association: which explicit part does a small part belong to?
RAIL = re.compile(r'^(GND|\+|VDD|VCC|DCDC|.*VBUS|CODEC_1V8|WL_3V3|AUD_VDDA|SW_3V3|NVCC)')
def is_rail(n): return n.startswith('unconnected') or RAIL.match(n.split('/')[-1]) or len(nets[n]) > 10
pins_of = collections.defaultdict(list)
for (r, p), n in padnet.items(): pins_of[r].append(n)
SHEET_DEFAULT = {'Power': 'U1', 'Core': 'U1', 'GPIO': 'U1', 'USB': 'J3', 'Supply': 'U6', 'SDRAM': 'U9', 'M.2': 'J6', 'SD card': 'J5', 'LCD': 'J7', 'Audio': 'U15', 'Test points': None}
anchor = {}
small = [r for r in comps if r not in explicit and not r.startswith('TP')]
for _ in range(3):
    for r in small:
        if r in anchor: continue
        c = collections.Counter()
        for n in pins_of[r]:
            if is_rail(n): continue
            for r2, _p in nets[n]:
                if r2 != r and r2 in explicit: c[r2] += 2
                elif r2 != r and r2 in anchor: c[anchor[r2]] += 1
        if not c:
            for n in pins_of[r]:
                if n.startswith('unconnected') or n.split('/')[-1] == 'GND': continue
                for r2, _p in nets[n]:
                    if r2 != r and r2 in explicit and comps[r2]['sheet'] == comps[r]['sheet']: c[r2] += 1
        if c: anchor[r] = c.most_common(1)[0][0]
for r in small:
    if r not in anchor: anchor[r] = SHEET_DEFAULT.get(comps[r]['sheet'], 'U1')
# anchor points: U1 bottom for its capacitors, otherwise the anchor footprint centre on the top
def centre(ref): x0, y0, x1, y1 = bbox(fps[ref]); return (x0 + x1) / 2, (y0 + y1) / 2
order = sorted(small, key=lambda r: (anchor[r] != 'U1', -shape(r, 0, 'top')[2]))   # MCU parts first, big parts first
summary = collections.Counter()
for r in order:
    a = anchor[r]
    if a == 'J7':   # LCD-sheet parts go on the top above the display connector area
        ax, ay, side = 71.0, 14.0, 'top'
    else:
        ax, ay = centre(a); side = 'bottom' if (a == 'U1' and r.startswith('C')) else 'top'
    if pack(r, ax, ay, side): summary[(a, side)] += 1
# test points: rows along the north edge, top side, away from the M.2 card (x 112-138) and J7's THT shadow
tps = sorted([r for r in comps if r.startswith('TP')], key=lambda r: int(r[2:]))
slots = [(x, y) for y in (10.0, 14.6, 19.2) for x in [8.0 + 4.0 * k for k in range(25)]]   # 75 slots for 72 TPs, clear of the M.2 card (x > 112)
si = 0
for r in tps:
    while si < len(slots):
        x, y = slots[si]; si += 1
        sx0, sy0, sx1, sy1 = shape(r, 0, 'top')
        if free((x + sx0, y + sy0, x + sx1, y + sy1), 'top'): place(r, x, y); occupy(fps[r]); break
    else:
        pack(r, 60.0, 20.0)
print('auto-packed by anchor/side:', dict(summary))

# ------------------------------------------------------------------ outline, zones
def seg(x0, y0, x1, y1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.05))
    s.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); s.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1))); board.Add(s)
R = 1.5
seg(R, 0, W - R, 0); seg(W, R, W, H - R); seg(W - R, H, R, H); seg(0, H - R, 0, R)
for (cx, cy, a0) in ((R, R, 180), (W - R, R, 270), (W - R, H - R, 0), (R, H - R, 90)):
    a = pcbnew.PCB_SHAPE(board); a.SetShape(pcbnew.SHAPE_T_ARC); a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(FromMM(0.05))
    p = lambda deg: VECTOR2I(FromMM(cx + R * math.cos(math.radians(deg))), FromMM(cy + R * math.sin(math.radians(deg))))
    a.SetArcGeometry(p(a0), p(a0 + 45), p(a0 + 90)); board.Add(a)
for lay in (pcbnew.In1_Cu, pcbnew.In4_Cu):
    z = pcbnew.ZONE(board); z.SetLayer(lay); z.SetNet(netinfo['GND']); z.SetAssignedPriority(0)
    z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.15)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in ((0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)): ol.Append(FromMM(x), FromMM(y))
    z.SetZoneName('GND_' + board.GetLayerName(lay)); board.Add(z)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
t = pcbnew.PCB_TEXT(board); t.SetText('Nosh  rev A  2026-10'); t.SetLayer(pcbnew.F_SilkS); t.SetTextSize(VECTOR2I(FromMM(1.5), FromMM(1.5))); t.SetTextThickness(FromMM(0.25))
t.SetPosition(VECTOR2I(FromMM(40.0), FromMM(4.5))); board.Add(t)

# reference labels: small passives keep theirs on the fab layer (assembly works from the CPL); others sit just above their courtyard
moved = 0
for fp in board.GetFootprints():
    ref = fp.Reference(); x0, y0, x1, y1 = bbox(fp); back = fp.GetLayer() == pcbnew.B_Cu
    if (x1 - x0) * (y1 - y0) < 6.0 and not fp.GetReference().startswith(('TP', 'FID', 'H')):
        ref.SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab); moved += 1
    else:
        ref.SetTextSize(VECTOR2I(FromMM(1.0), FromMM(1.0))); ref.SetTextThickness(FromMM(0.15)); ref.SetTextAngleDegrees(0)
        ref.SetPosition(VECTOR2I(FromMM((x0 + x1) / 2), FromMM((y1 + 0.8) if back else (y0 - 0.8))))
print('small-part references moved to the fab layer:', moved)
board.BuildListOfNets()
pcbnew.SaveBoard(K + 'Nosh.kicad_pcb', board)
if not stackup_ok:   # JLC06161H-3313, written as text
    L = lambda n, ty, th=None, extra='': '\t\t\t(layer "%s"\n\t\t\t\t(type "%s")\n%s%s\t\t\t)\n' % (n, ty, ('\t\t\t\t(thickness %g)\n' % th) if th is not None else '', extra)
    D = lambda n, ty, th, mat, er: L(n, ty, th, '\t\t\t\t(material "%s")\n\t\t\t\t(epsilon_r %g)\n\t\t\t\t(loss_tangent 0.02)\n' % (mat, er))
    su = ('\t\t(stackup\n' + L('F.SilkS', 'Top Silk Screen') + L('F.Paste', 'Top Solder Paste') + L('F.Mask', 'Top Solder Mask', 0.01) + L('F.Cu', 'copper', 0.035)
          + D('dielectric 1', 'prepreg', 0.0994, '3313 FR4', 4.1) + L('In1.Cu', 'copper', 0.0152) + D('dielectric 2', 'core', 0.55, 'NP-155F FR4', 4.6) + L('In2.Cu', 'copper', 0.0152)
          + D('dielectric 3', 'prepreg', 0.1088, '2116 FR4', 4.1) + L('In3.Cu', 'copper', 0.0152) + D('dielectric 4', 'core', 0.55, 'NP-155F FR4', 4.6) + L('In4.Cu', 'copper', 0.0152)
          + D('dielectric 5', 'prepreg', 0.0994, '3313 FR4', 4.1) + L('B.Cu', 'copper', 0.035) + L('B.Mask', 'Bottom Solder Mask', 0.01) + L('B.Paste', 'Bottom Solder Paste') + L('B.SilkS', 'Bottom Silk Screen')
          + '\t\t\t(copper_finish "ENIG")\n\t\t\t(dielectric_constraints no)\n\t\t)\n')
    txt = open(K + 'Nosh.kicad_pcb').read(); i = txt.index('\n\t(setup\n') + len('\n\t(setup\n'); open(K + 'Nosh.kicad_pcb', 'w').write(txt[:i] + su + txt[i:])
    print('stackup written as text')
print('saved', K + 'Nosh.kicad_pcb')

# ------------------------------------------------------------------ verification data
chk = {}
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetname(): chk[fp.GetReference() + '.' + pad.GetNumber()] = pad.GetNetname()
want = {f'{r}.{p}': n for (r, p), n in padnet.items()}
missing = {k: v for k, v in want.items() if chk.get(k) != v}
extra = {k: v for k, v in chk.items() if k not in want}
print('pad-net check: wanted', len(want), 'missing/mismatched', len(missing), 'extra', len(extra), list(missing.items())[:5], list(extra.items())[:5])
j7 = fps['J7']; P = {p.GetNumber(): (round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in j7.Pads()}
print('J7 on', j7.GetLayerName(), 'pin1', P['1'], 'pin40', P['40'], 'courtyard', [round(v, 2) for v in bbox(j7)])
json.dump({r: (round(ToMM(fps[r].GetPosition().x), 2), round(ToMM(fps[r].GetPosition().y), 2), fps[r].GetOrientationDegrees(), fps[r].GetLayerName(), anchor.get(r)) for r in fps}, open(SCR + 'placement.json', 'w'), indent=0)
