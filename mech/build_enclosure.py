"""Build the Nosh enclosure document from params.py, board.json and Nosh.step.

Headless:
  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
      /Users/nicholasnewdigate/Development/nosh-dev-board/mech/build_enclosure.py
In the FreeCAD GUI (Python console):
  p = '/Users/nicholasnewdigate/Development/nosh-dev-board/mech/build_enclosure.py'
  exec(open(p).read(), {'__file__': p, '__name__': '__main__'})

Writes Nosh-enclosure.FCStd and out/{tray,lid}.{step,stl}. Never touches Kicad/.
Model frame: board x east, y south, z up with the display on top, z = 0 at the table.
"""
import importlib
import json
import os
import sys

import FreeCAD as App
import Part
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import params  # noqa: E402

importlib.reload(params)
P = params.P
Z = params.levels(P)
BOARD = json.load(open(os.path.join(HERE, 'board.json')))
W, H = P['board_w'], P['board_h']
C = P['clear']
O = P['clear'] + P['wall']
OUT = 30.0  # how far plug keep-outs reach outside the board edge


# ---------------------------------------------------------------- primitives
def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl_z(x, y, r, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))


def slab(edge, u0, u1, z0, z1, s0, s1):
    """Box on a board edge. u along the edge, s = distance outward from the edge."""
    if edge == 'E':
        return box(W + s0, u0, z0, W + s1, u1, z1)
    if edge == 'W':
        return box(-s1, u0, z0, -s0, u1, z1)
    if edge == 'S':
        return box(u0, H + s0, z0, u1, H + s1, z1)
    return box(u0, -s1, z0, u1, -s0, z1)  # N


def rod(edge, u, zc, r, s0, s1):
    """Cylinder with its axis pointing outward from a board edge."""
    base, d = {
        'E': (V(W + s0, u, zc), V(1, 0, 0)), 'W': (V(-s0, u, zc), V(-1, 0, 0)),
        'S': (V(u, H + s0, zc), V(0, 1, 0)), 'N': (V(u, -s0, zc), V(0, -1, 0)),
    }[edge]
    return Part.makeCylinder(r, s1 - s0, base, d)


def rbox(off, z0, z1):
    """Box `off` outside the board outline with vertical corners rounded to radius `off`,
    so it stays concentric with the shell's outer corner radius."""
    b = box(-off, -off, z0, W + off, H + off, z1)
    edges = [e for e in b.Edges if abs(e.Vertexes[0].X - e.Vertexes[1].X) < 1e-6
             and abs(e.Vertexes[0].Y - e.Vertexes[1].Y) < 1e-6]
    return b.makeFillet(off, edges)


def fuse(shapes):
    s = shapes[0]
    for t in shapes[1:]:
        s = s.fuse(t)
    return s.removeSplitter()


# ---------------------------------------------------------------- board import
def load_board(doc):
    """Import Nosh.step, turn it display-up and name the parts by reference."""
    before = set(o.Name for o in doc.Objects)
    if App.GuiUp:
        import ImportGui
        ImportGui.insert(os.path.join(HERE, 'Nosh.step'), doc.Name)
    else:
        import Import
        Import.insert(os.path.join(HERE, 'Nosh.step'), doc.Name)
    doc.recompute()
    new = [o for o in doc.Objects if o.Name not in before]
    root = [o for o in new if not o.InList and o.TypeId == 'App::Part'][0]
    # label each component container with its reference designator (matched by position)
    fps = list(BOARD['footprints'])
    used = set()
    for o in root.Group:
        b = o.Placement.Base
        best = None
        for i, (ref, x, y, side) in enumerate(fps):
            if i in used:
                continue
            if abs(b.x - x) < 0.02 and abs(-b.y - y) < 0.02:
                best = i
                break
        if best is not None:
            used.add(best)
            o.Label = '%s_%s' % (fps[best][0], o.Label)
    # STEP: y north-positive, component side +z. Model: y south-positive, display side +z.
    zt = Z['comp'] + P['step_comp_face_z']
    root.Placement = App.Placement(V(0, 0, zt), App.Rotation(V(1, 0, 0), 180))
    root.Label = 'Nosh_board'
    doc.recompute()
    return root


def board_solids(root):
    """[(label, shape in model frame)] for every solid of the imported board."""
    out = []

    def walk(o):
        if o.TypeId == 'Part::Feature':
            s = o.Shape.copy()
            s.Placement = o.getGlobalPlacement()
            lab = o.Label
            for p in o.InList:
                if p.TypeId == 'App::Part' and p is not root:
                    lab = p.Label
            out.append((lab, s))
        for c in getattr(o, 'Group', []):
            walk(c)
    walk(root)
    return out


def measure_parts(solids):
    """Heights above the board face from the STEP, written back to board.json."""
    info = {}
    for ref, d in BOARD['parts'].items():
        x0, y0, x1, y1 = d['body']
        zs = []
        big = None
        for lab, s in solids:
            b = s.BoundBox
            c = b.Center
            top = c.z < Z['comp']
            if 'PCB' in lab or (d['side'] == 'TOP') != top:
                continue
            if x0 - 0.2 <= c.x <= x1 + 0.2 and y0 - 0.2 <= c.y <= y1 + 0.2:
                zs += [b.ZMin, b.ZMax]
                if big is None or s.Volume > big.Volume:
                    big = s
        if zs and d['side'] == 'TOP':
            d['height'] = round(Z['comp'] - min(zs), 2)
            d['height_src'] = 'STEP'
            info[ref] = big
    json.dump(BOARD, open(os.path.join(HERE, 'board.json'), 'w'), indent=1, sort_keys=True)
    return info


# ---------------------------------------------------------------- reference stack
def plug_axis_z(pl, info):
    if pl['d'] is not None:
        return Z['comp'] - pl['d']
    # shell sits on the board: axis at half the height measured from the STEP
    return Z['comp'] - BOARD['parts'][pl['ref']]['height'] / 2.0


def plug_solid(pl, zc, grow=0.0, s0=0.0, s1=OUT):
    if 'dia' in pl:
        return rod(pl['edge'], pl['u'], zc, pl['dia'] / 2 + grow, s0, s1)
    w, h = pl['rect']
    return slab(pl['edge'], pl['u'] - w / 2 - grow, pl['u'] + w / 2 + grow,
                zc - h / 2 - grow, zc + h / 2 + grow, s0, s1)


def sd_card(grow=0.0, s1=OUT):
    sd = params.SD
    j5 = BOARD['parts']['J5']
    u = j5['at'][0]
    zc = Z['comp'] - sd['card_d']
    return slab('N', u - sd['card_w'] / 2 - grow, u + sd['card_w'] / 2 + grow,
                zc - sd['card_t'] / 2 - grow, zc + sd['card_t'] / 2 + grow, 0.0, s1)


def make_stack(info):
    st = {}
    st['carrier'] = box(0, 0, Z['car0'], W, H, Z['car1'])
    gx0, gy0 = P['glass_x0'], P['glass_y0']
    st['panel'] = box(gx0, gy0, Z['car1'], gx0 + P['glass_w'], gy0 + P['glass_h'], Z['glass'])
    st['standoffs'] = Part.makeCompound([
        cyl_z(x, y, P['standoff_d'] / 2, Z['split'], Z['car0']) for x, y in BOARD['holes'].values()])
    rx, rw = P['ribbon_x'], P['ribbon_w']
    st['ribbon_keepout'] = slab('N', rx - rw / 2, rx + rw / 2, Z['split'] + 0.5, Z['car0'] - 0.5, -5.0, 35.0)
    plugs = {}
    for pl in params.PLUGS:
        plugs[pl['ref']] = plug_solid(pl, plug_axis_z(pl, info))
    plugs['J5'] = sd_card()
    st['plugs'] = plugs
    boxes = {}
    for ref, h in params.BOXES.items():
        d = BOARD['parts'][ref]
        x0, y0, x1, y1 = d['body']
        if d['edge'] == 'E':
            x1 = min(x1, W + d['protrude'])
        if ref == 'J2':
            x1 = W + 0.70  # mouth 0.70 over the edge (board notes); the Fab box also holds the plug
        if ref in ('J8', 'J9'):
            y1 = H
        if d['side'] == 'TOP':
            boxes[ref] = box(x0, y0, Z['comp'] - h, x1, y1, Z['comp'])
        else:
            boxes[ref] = box(x0, y0, Z['split'], x1, y1, Z['split'] + h)
    m = params.M2_CARD
    boxes['M2_card'] = box(m['x0'], m['y0'], Z['comp'] - m['z_off'] - m['t'], m['x1'], m['y1'], Z['comp'] - m['z_off'])
    st['boxes'] = boxes
    return st


# ---------------------------------------------------------------- shells
def shell_block(z0, z1):
    b = box(-O, -O, z0, W + O, H + O, z1)
    edges = [e for e in b.Edges if abs(e.Vertexes[0].X - e.Vertexes[1].X) < 1e-6
             and abs(e.Vertexes[0].Y - e.Vertexes[1].Y) < 1e-6]
    return b.makeFillet(P['corner_r'], edges)


def notch_tools(info):
    """(tray tools, lid tools): plug overmoulds grown by the notch margin."""
    m = P['notch_margin']
    top = Z['tongue'] + 1.0
    tray, lid = [], []
    for pl in params.PLUGS:
        zc = plug_axis_z(pl, info)
        # from the board edge itself: the barrel plug dips below the cavity floor level
        g = plug_solid(pl, zc, grow=m, s0=0.0, s1=O + 1.0)
        lid.append(g)
        if 'dia' in pl:
            r = pl['dia'] / 2 + m
            tray.append(g.fuse(slab(pl['edge'], pl['u'] - r, pl['u'] + r, zc, top, 0.0, O + 1.0)))
        else:
            w, h = pl['rect']
            tray.append(slab(pl['edge'], pl['u'] - w / 2 - m, pl['u'] + w / 2 + m,
                             zc - h / 2 - m, top, 0.2, O + 1.0))
    # two notches closer than merge_gap would leave a fragile post between them: join them
    spans = {}
    for pl in params.PLUGS:
        half = (pl['dia'] / 2 if 'dia' in pl else pl['rect'][0] / 2) + m
        zc = plug_axis_z(pl, info)
        z0 = zc if 'dia' in pl else zc - pl['rect'][1] / 2 - m
        spans.setdefault(pl['edge'], []).append((pl['u'] - half, pl['u'] + half, z0))
    for edge, lst in spans.items():
        lst.sort()
        for (a0, a1, az), (b0, b1, bz) in zip(lst, lst[1:]):
            if 0 < b0 - a1 < P['merge_gap']:
                tray.append(slab(edge, a1 - 0.01, b0 + 0.01, max(az, bz), top, 0.0, O + 1.0))
    # microSD finger slot: the full width of the J5 body
    x0, _, x1, _ = BOARD['parts']['J5']['body']
    xc, hw = (x0 + x1) / 2, max(P['sd_slot_w'], x1 - x0 + 2 * m) / 2
    tray.append(slab('N', xc - hw, xc + hw, Z['comp'] - P['sd_notch_depth'], top, 0.2, O + 1.0))
    # shallow pocket in the outer face so a fingertip reaches the card through a thick wall
    if P.get('sd_relief', 0) > 0:
        e = P['sd_relief_side']
        tray.append(slab('N', xc - hw - e, xc + hw + e, max(1.0, Z['comp'] - P['sd_notch_depth'] - 3.0), top,
                         O - P['sd_relief'], O + 1.0))
    return tray, lid


def ribbon_span():
    half = P['ribbon_w'] / 2 + P['ribbon_margin']
    return P['ribbon_x'] - half, P['ribbon_x'] + half


def make_tray(info):
    t = shell_block(0.0, Z['split'])
    t = t.cut(box(-C, -C, Z['floor'], W + C, H + C, Z['split'] + 1))
    tt = P['tongue_t']
    tongue = rbox(C + tt, Z['split'], Z['tongue']).cut(
        box(-C, -C, Z['split'] - 1, W + C, H + C, Z['tongue'] + 1))
    parts = [t, tongue]
    r = P['boss_d'] / 2
    for x, y in BOARD['holes'].values():
        parts.append(cyl_z(x, y, r, Z['floor'], Z['comp']))
        # webs that tie the boss into the two corner walls
        xw = -C if x < W / 2 else W + C
        yw = -C if y < H / 2 else H + C
        parts.append(box(min(x, xw), y - r, Z['floor'], max(x, xw), y + r, Z['comp']))
        parts.append(box(x - r, min(y, yw), Z['floor'], x + r, max(y, yw), Z['comp']))
    t = fuse(parts)
    cuts = []
    for x, y in BOARD['holes'].values():
        cuts.append(cyl_z(x, y, P['screw_hole'] / 2, -1, Z['comp'] + 1))
        cuts.append(Part.makeCone(P['csk_d'] / 2, P['screw_hole'] / 2, P['csk_depth'], V(x, y, 0), V(0, 0, 1)))
    vx, vy = P['vent_at']
    n = P['vent_n']
    for i in range(n):
        x = vx + (i - (n - 1) / 2.0) * P['vent_pitch']
        cuts.append(box(x - P['vent_w'] / 2, vy - P['vent_l'] / 2, -1, x + P['vent_w'] / 2, vy + P['vent_l'] / 2, Z['floor'] + 1))
    tray_tools, _ = notch_tools(info)
    cuts += tray_tools
    u0, u1 = ribbon_span()  # the tongue must not stand in the ribbon's way
    cuts.append(slab('N', u0, u1, Z['split'], Z['tongue'] + 1, 0.2, O + 1.0))
    for c in cuts:
        t = t.cut(c)
    return t.removeSplitter()


def make_lid(info):
    l = shell_block(Z['lid0'], Z['face'])
    l = l.cut(box(-C, -C, Z['lid0'] - 1, W + C, H + C, Z['plate0']))
    pads = []
    r = P['pad_d'] / 2
    for x, y in BOARD['holes'].values():
        pads.append(cyl_z(x, y, r, Z['car1'], Z['plate0'] + 0.1))
        # webs to the two corner walls, so no thin slot is left beside the pad
        xw = -C if x < W / 2 else W + C
        yw = -C if y < H / 2 else H + C
        pads.append(box(min(x, xw), y - r, Z['car1'], max(x, xw), y + r, Z['plate0'] + 0.1))
        pads.append(box(x - r, min(y, yw), Z['car1'], x + r, max(y, yw), Z['plate0'] + 0.1))
    l = fuse([l] + pads)
    g = P['window_gap']
    gx0, gy0 = P['glass_x0'], P['glass_y0']
    cuts = [box(gx0 - g, gy0 - g, Z['plate0'] - 1, gx0 + P['glass_w'] + g, gy0 + P['glass_h'] + g, Z['face'] + 1)]
    for x, y in BOARD['holes'].values():
        cuts.append(cyl_z(x, y, P['screw_hole'] / 2, Z['car1'] - 1, Z['face'] + 1))
        cuts.append(Part.makeCone(P['screw_hole'] / 2, P['csk_d'] / 2, P['csk_depth'],
                                  V(x, y, Z['face'] - P['csk_depth']), V(0, 0, 1)))
    rt = P['tongue_t'] + P['tongue_fit']
    cuts.append(rbox(C + rt, Z['lid0'] - 1, Z['tongue'] + P['tongue_fit']))
    u0, u1 = ribbon_span()
    cuts.append(slab('N', u0, u1, Z['lid0'] - 1, Z['car0'], 0.2, O + 1.0))
    _, lid_tools = notch_tools(info)
    cuts += lid_tools
    for c in cuts:
        l = l.cut(c)
    return l.removeSplitter()


# ---------------------------------------------------------------- document
def add(doc, name, shape, color=None, transparency=0):
    o = doc.addObject('Part::Feature', name)
    o.Shape = shape
    if App.GuiUp and color:
        o.ViewObject.ShapeColor = color
        o.ViewObject.Transparency = transparency
    return o


def add_sheet(doc):
    sh = doc.addObject('Spreadsheet::Sheet', 'Params')
    sh.set('A1', 'name')
    sh.set('B1', 'value')
    sh.set('C1', 'note: mirror of mech/params.py; edit that file and re-run build_enclosure.py')
    row = 2
    items = [(k, v) for k, v in sorted(P.items()) if isinstance(v, (int, float))]
    items += [('z_' + k, v) for k, v in sorted(Z.items())]
    for k, v in items:
        sh.set('A%d' % row, k)
        sh.set('B%d' % row, str(v))
        sh.setAlias('B%d' % row, k)
        row += 1
    return sh


def export(tray, lid):
    out = os.path.join(HERE, 'out')
    if not os.path.isdir(out):
        os.makedirs(out)
    import MeshPart
    lid_print = lid.copy()
    lid_print.Placement = App.Placement(V(0, 0, Z['face']), App.Rotation(V(1, 0, 0), 180))
    for name, s in (('tray', tray), ('lid', lid_print)):
        s.exportStep(os.path.join(out, name + '.step'))
        m = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.05, AngularDeflection=0.26, Relative=False)
        m.write(os.path.join(out, name + '.stl'))
        b = s.BoundBox
        print('export %s: %.2f x %.2f x %.2f, z %.2f..%.2f, %d facets' % (
            name, b.XLength, b.YLength, b.ZLength, b.ZMin, b.ZMax, m.CountFacets))


def main():
    name = 'Nosh_enclosure'
    if name in App.listDocuments():
        App.closeDocument(name)
    doc = App.newDocument(name)
    add_sheet(doc)
    root = load_board(doc)
    solids = board_solids(root)
    info = measure_parts(solids)
    print('levels', {k: round(v, 3) for k, v in sorted(Z.items())})
    for pl in params.PLUGS:
        print('plug %s axis z %.2f (%.2f below the board face)' % (
            pl['ref'], plug_axis_z(pl, info), Z['comp'] - plug_axis_z(pl, info)))
    st = make_stack(info)
    add(doc, 'Carrier', st['carrier'], (0.10, 0.45, 0.20))
    add(doc, 'Panel', st['panel'], (0.05, 0.05, 0.06))
    add(doc, 'Standoffs', st['standoffs'], (0.80, 0.65, 0.20))
    add(doc, 'RibbonKeepout', st['ribbon_keepout'], (0.95, 0.95, 0.95), 60)
    for ref, s in sorted(st['plugs'].items()):
        add(doc, 'Plug_' + ref, s, (0.90, 0.30, 0.10), 70)
    for ref, s in sorted(st['boxes'].items()):
        add(doc, 'Box_' + ref, s, (0.55, 0.55, 0.60))
    tray = make_tray(info)
    lid = make_lid(info)
    add(doc, 'Tray', tray, (0.20, 0.22, 0.25))
    add(doc, 'Lid', lid, (0.20, 0.22, 0.25))
    doc.recompute()
    for nm, s in (('Tray', tray), ('Lid', lid)):
        b = s.BoundBox
        print('%s: valid %s, solids %d, bbox %.2f x %.2f x %.2f, z %.2f..%.2f, volume %.0f mm3' % (
            nm, s.isValid(), len(s.Solids), b.XLength, b.YLength, b.ZLength, b.ZMin, b.ZMax, s.Volume))
    export(tray, lid)
    doc.saveAs(os.path.join(HERE, 'Nosh-enclosure.FCStd'))
    print('saved')
    return doc


# freecadcmd does not set __name__ to '__main__'; check_enclosure.py sets NOSH_IMPORT to import this file.
if not os.environ.get('NOSH_IMPORT'):
    main()
