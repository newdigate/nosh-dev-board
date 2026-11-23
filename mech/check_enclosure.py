"""Check the built enclosure and write check_report.md.

  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
      /Users/nicholasnewdigate/Development/nosh-dev-board/mech/check_enclosure.py

Opens Nosh-enclosure.FCStd (run build_enclosure.py first). Every check writes a row:
PASS/FAIL, the value found, the limit, and where the inputs come from
(M measured by the user, B board file / STEP, D datasheet, C design choice, A assumed).
"""
import os
import sys

os.environ['NOSH_IMPORT'] = '1'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
from FreeCAD import Vector as V  # noqa: E402
import build_enclosure as be  # noqa: E402

P, Z, W, H, C, O = be.P, be.Z, be.W, be.H, be.C, be.O
params = be.params
ROWS = []
EPS = 1e-3  # mm3: boolean noise


def row(name, ok, value, limit, src):
    """ok=None records a value for information; it is not counted as a check."""
    res = 'INFO' if ok is None else ('PASS' if ok else 'FAIL')
    ROWS.append((name, res, value, limit, src))
    print('%-4s %-58s %-28s %s' % (res, name, value, limit))


def vol(a, b):
    try:
        return a.common(b).Volume
    except Exception as e:  # a failed boolean is a failed check, not a pass
        return float('inf')


def moved(s, dx=0, dy=0, dz=0):
    t = s.copy()
    t.translate(V(dx, dy, dz))
    return t


def main():
    doc = App.openDocument(os.path.join(HERE, 'Nosh-enclosure.FCStd'))
    g = lambda n: doc.getObject(n).Shape  # noqa: E731
    tray, lid = g('Tray'), g('Lid')
    root = [o for o in doc.Objects if o.Label == 'Nosh_board'][0]
    solids = be.board_solids(root)
    pcb = [s for lab, s in solids if 'PCB' in lab][0]
    comps = [(lab, s) for lab, s in solids if 'PCB' not in lab]
    boxes = [(o.Name[4:], o.Shape) for o in doc.Objects if o.Name.startswith('Box_')]
    plugs = dict((o.Name[5:], o.Shape) for o in doc.Objects if o.Name.startswith('Plug_'))
    import re
    parts = [o for o in root.Group if o.TypeId == 'App::Part']
    n_ref = len([o for o in parts if re.match(r'^[A-Z]+\d+_', o.Label)])
    row('board parts imported and named by reference', n_ref >= 250 and n_ref == len(parts) and len(comps) >= n_ref,
        '%d parts, %d solids + PCB' % (n_ref, len(comps)), '>= 250 (294 footprints, 43 without a model)', 'B')

    # ---- shells are printable solids
    for nm, s in (('Tray', tray), ('Lid', lid)):
        row('%s is one valid closed solid' % nm, s.isValid() and len(s.Solids) == 1 and s.isClosed(),
            '%d solid' % len(s.Solids), '1', 'C')

    # ---- PCB
    row('PCB does not intersect the tray', vol(tray, pcb) < EPS, '%.4f mm3' % vol(tray, pcb), '0', 'B')
    row('PCB does not intersect the lid', vol(lid, pcb) < EPS, '%.4f mm3' % vol(lid, pcb), '0', 'B')
    band = tray.common(be.box(-O - 1, -O - 1, Z['comp'] + 0.01, W + O + 1, H + O + 1, Z['tongue'] + 1))
    d = band.distToShape(pcb)[0]
    row('PCB edge to tray wall', d >= 0.45, '%.3f mm' % d, '>= 0.45', 'B, C')

    # ---- every component and datasheet box against both shells
    r = P['boss_d'] / 2 + 1.0

    def near_shell(b):
        if b.XMin < 1.0 or b.YMin < 1.0 or b.XMax > W - 1.0 or b.YMax > H - 1.0:
            return True
        if b.ZMin < Z['floor'] + 1.0:
            return True
        for x, y in be.BOARD['holes'].values():
            if b.XMin < x + r and b.XMax > x - r and b.YMin < y + r and b.YMax > y - r:
                return True
        return False
    worst = {}
    n_exact = 0
    hit = []
    for lab, s in comps + boxes:
        if not near_shell(s.BoundBox) and s.BoundBox.ZMax < Z['split'] - 0.01:
            continue   # everything on the display side is always checked exactly
        n_exact += 1
        for nm, sh in (('tray', tray), ('lid', lid)):
            d = sh.distToShape(s)[0]
            if d < 1e-6 and vol(sh, s) > EPS:
                hit.append('%s/%s' % (lab, nm))
            if nm not in worst or d < worst[nm][0]:
                worst[nm] = (d, lab)
    row('no component intersects a shell', not hit, ', '.join(hit) or 'none', 'none', 'B')
    for nm in ('tray', 'lid'):
        d, lab = worst[nm]
        row('closest component to the %s' % nm, d >= 0.45, '%.3f mm (%s)' % (d, lab[:30]), '>= 0.45',
            'B (%d parts checked exactly, the rest are > 1 mm inside)' % n_exact)
    j4 = be.BOARD['parts']['J4']['height']
    row('cavity floor to the tallest part (J4)', P['cavity'] - j4 >= 0.9, '%.2f mm' % (P['cavity'] - j4), '>= 0.9', 'B')

    # ---- display stack
    for nm in ('Carrier', 'Panel', 'Standoffs', 'RibbonKeepout'):
        s = g(nm)
        v = vol(tray, s) + vol(lid, s)
        row('%s does not intersect the shells' % nm, v < EPS, '%.4f mm3' % v, '0', 'M')
    panel = g('Panel')
    for dx, dy in ((0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5)):
        v = vol(lid, moved(panel, dx, dy))
        row('glass shifted %+.1f, %+.1f clears the window' % (dx, dy), v < EPS, '%.4f mm3' % v, '0',
            'M +-0.5 (Review Focus 2); gap left %.1f mm' % (P['window_gap'] - 0.5))
    car = g('Carrier')
    row('lid plate above the carrier', None, '%.2f mm' % (Z['plate0'] - Z['car1']), 'A: nothing taller than 1.5', 'M, A')
    pads_touch = lid.distToShape(car)[0]
    row('lid pads bear on the carrier', pads_touch < 1e-6, '%.3f mm' % pads_touch, '0', 'C')

    # ---- plugs (Review Focus 1) and microSD (Review Focus 3)
    for pl in params.PLUGS:
        zc = be.plug_axis_z(pl, None)
        big = be.plug_solid(pl, zc, grow=0.4)
        v = vol(tray, big) + vol(lid, big)
        size = ('dia %.1f' % (pl['dia'] + 0.8)) if 'dia' in pl else ('%.1f x %.1f' % (pl['rect'][0] + 0.8, pl['rect'][1] + 0.8))
        row('%s plug overmould + 0.4 mm clears both shells' % pl['ref'], v < EPS, '%.4f mm3' % v,
            '0 (admits %s)' % size, pl['src'])
        lowest = zc - (pl['dia'] / 2 if 'dia' in pl else pl['rect'][1] / 2)
        row('%s plug overmould above the table' % pl['ref'], lowest > 0.0, '%.2f mm' % lowest, '> 0', pl['src'])
    # independent of params: where the STEP says J3 and J4 really are
    def part_solids(ref):
        bx0, by0, bx1, by1 = be.BOARD['parts'][ref]['body']
        return [s for lab, s in comps if bx0 - 0.2 <= s.BoundBox.Center.x <= bx1 + 0.2
                and by0 - 0.2 <= s.BoundBox.Center.y <= by1 + 0.2 and s.BoundBox.Center.z < Z['comp']]
    # the mouth end of the receptacle only (x > 152): no pegs or pins there
    mouth = be.box(152.0, 40.0, 0.0, 155.0, 60.0, Z['comp'] + 5)
    shell = [q.BoundBox for q in (s.common(mouth) for s in part_solids('J3')) if q.Volume > 0.01]
    zc3 = (min(q.ZMin for q in shell) + max(q.ZMax for q in shell)) / 2
    yc3 = (min(q.YMin for q in shell) + max(q.YMax for q in shell)) / 2
    pl3 = [q for q in params.PLUGS if q['ref'] == 'J3'][0]
    dz, dy = abs(be.plug_axis_z(pl3, None) - zc3), abs(pl3['u'] - yc3)
    row('J3 notch axis vs the shell in the STEP', dz < 0.3 and dy < 0.3, 'dz %.2f, dy %.2f mm' % (dz, dy), '< 0.3', 'B')
    bores = []
    for s in part_solids('J4'):
        for f in s.Faces:
            if f.Surface.__class__.__name__ == 'Cylinder' and abs(f.Surface.Axis.x) > 0.99 and f.Surface.Radius > 2.5:
                bores.append(f.Surface.Center)
    pl4 = [q for q in params.PLUGS if q['ref'] == 'J4'][0]
    dz, dy = abs(be.plug_axis_z(pl4, None) - bores[0].z), abs(pl4['u'] - bores[0].y)
    row('J4 notch axis vs the bore in the STEP', dz < 0.3 and dy < 0.3, 'dz %.2f, dy %.2f mm' % (dz, dy), '< 0.3', 'B')
    for q in params.PLUGS:
        if q['ref'] in ('J2', 'J8', 'J9'):
            fx, fy = be.BOARD['parts'][q['ref']]['at']
            du = abs(q['u'] - (fy if q['edge'] in 'EW' else fx))
            row('%s notch position along the edge vs the footprint' % q['ref'], du < 0.3, '%.2f mm' % du, '< 0.3', 'B; axis height A')
    # thinnest wall of the lid lip beside the tongue rebate
    rt = P['tongue_t'] + P['tongue_fit']
    row('lid lip thickness at the rebate', P['wall'] - rt >= 0.75, '%.2f mm (corners concentric)' % (P['wall'] - rt), '>= 0.75', 'C')
    card = be.sd_card(grow=0.4)
    v = vol(tray, card) + vol(lid, card)
    row('J5 card path + 0.4 mm clears both shells', v < EPS, '%.4f mm3' % v, '0', 'B, card height A')
    x0, _, x1, _ = be.BOARD['parts']['J5']['body']
    wn = x1 - x0 + 2 * P['notch_margin']
    # the slot as built, measured on the tray itself: section through the N wall mid-thickness
    xm = (x0 + x1) / 2
    probe = be.slab('N', x0 - 15, x1 + 15, Z['comp'] - 1.0, Z['split'] - 0.05, C + 0.9, C + 1.1)
    xs = [s.BoundBox for s in tray.common(probe).Solids]
    left = max(b.XMax for b in xs if b.XMax < xm)
    right = min(b.XMin for b in xs if b.XMin > xm)
    wn = right - left
    row('J5 finger slot width (measured on the tray)', wn >= 18.0, '%.2f mm' % wn, '>= 18 (fingertip)', 'B, C')
    col = tray.common(be.slab('N', xm - 0.1, xm + 0.1, -1.0, Z['split'], C + 0.9, C + 1.1))
    sill = col.BoundBox.ZMax if col.Volume > 0 else 0.0
    hn = (Z['comp'] - params.SD['card_d']) - sill
    row('J5 slot height below the card', hn >= 7.0, '%.2f mm' % hn, '>= 7', 'card height A')
    recess = O - P.get('sd_relief', 0) - params.SD['locked_out']   # wall face inside the finger relief
    row('J5 locked card end behind the wall face', recess <= 1.5, '%.2f mm' % recess, '<= 1.5', 'B')
    rec2 = recess + P['sd_overtravel']
    row('J5 card end at push-to-eject over-travel', rec2 <= 2.5, '%.2f mm behind the wall face' % rec2, '<= 2.5', 'B, over-travel A')
    row('J5 card in the board drawing vs slot', left < x0 and right > x1, 'body %.2f..%.2f inside %.2f..%.2f' % (x0, x1, left, right), 'inside', 'B')

    # ---- assembly order (Review Focus 4)
    top_side = [s for lab, s in comps + boxes if s.BoundBox.ZMax > Z['split'] - 0.01]
    upper = Part.makeCompound([pcb, car, panel, g('Standoffs'), g('RibbonKeepout')] + top_side)
    worst_v = max(vol(moved(lid, 0, 0, k), upper) for k in (0.5, 1, 2, 3, 5, 8, 12, 16, 20, 25))
    row('lid lifts straight off over the ribbon', worst_v < EPS, '%.4f mm3' % worst_v, '0', 'C')
    edge = [s for lab, s in comps + boxes if near_shell(s.BoundBox)]
    stack = Part.makeCompound([pcb] + edge)
    worst_v = max(vol(tray, moved(stack, 0, 0, k)) for k in (0.5, 1, 2, 3, 5, 8, 12, 16))
    row('stack lifts straight out of the tray', worst_v < EPS, '%.4f mm3' % worst_v, '0', 'B')

    # ---- closed height and screws (Review Focus 5)
    row('rim gap, 16.0 mm standoff', 0.0 < P['rim_gap'] < 0.5, '%.2f mm' % P['rim_gap'], '0..0.5', 'M, C')
    row('rim gap, 16.1 mm standoff', 0.0 < P['rim_gap'] + 0.1 < 0.5, '%.2f mm' % (P['rim_gap'] + 0.1), '0..0.5', 'D, C')
    tongue_overlap = P['tongue_h'] - P['rim_gap']
    row('tongue engaged in the lid rebate', tongue_overlap >= 1.0, '%.2f mm' % tongue_overlap, '>= 1.0', 'C')
    e_tray = P['tray_screw'] - (Z['split'] - 0.0)
    e_lid = P['lid_screw'] - (Z['face'] - Z['car0'])
    row('tray screw thread in the standoff (M3x%d csk)' % P['tray_screw'], e_tray >= 4.0, '%.1f mm' % e_tray, '>= 4.0', 'A female-female standoff')
    row('lid screw thread in the standoff (M3x%d csk)' % P['lid_screw'], e_lid >= 4.0, '%.1f mm' % e_lid, '>= 4.0', 'A female-female standoff')
    row('screws do not meet inside the standoff', e_tray + e_lid <= P['gap'] - 2, '%.1f mm' % (e_tray + e_lid), '<= %.1f' % (P['gap'] - 2), 'M')
    under_head = (Z['face'] - Z['car1']) - P['csk_depth']
    row('lid plastic under the screw head', under_head >= 2.0, '%.2f mm' % under_head, '>= 2.0', 'C')

    # ---- printability: no face steeper than 45 degrees overhang, no bridges
    def overhangs(s, up):
        bad = []
        bed = s.BoundBox.ZMin if up else s.BoundBox.ZMax
        for f in s.Faces:
            u0, u1, v0, v1 = f.ParameterRange
            for i in (0.2, 0.5, 0.8):
                for j in (0.2, 0.5, 0.8):
                    u, v = u0 + (u1 - u0) * i, v0 + (v1 - v0) * j
                    if not f.isPartOfDomain(u, v):
                        continue
                    n = f.normalAt(u, v)
                    p = f.valueAt(u, v)
                    nz = n.z if up else -n.z   # component toward the build plate is negative
                    if nz < -0.75 and abs(p.z - bed) > 0.05:
                        bad.append((round(p.x, 1), round(p.y, 1), round(p.z, 1)))
        return bad
    for nm, s, up in (('tray (floor down)', tray, True), ('lid (face down)', lid, False)):
        bad = overhangs(s, up)
        row('%s prints without bridges or supports' % nm, not bad,
            'none' if not bad else '%d points, e.g. %s' % (len(bad), bad[:3]), 'no face past 45 deg', 'C')

    b = tray.BoundBox
    row('outside size', None, '%.1f x %.1f x %.1f mm' % (b.XLength, b.YLength, lid.BoundBox.ZMax), 'info', 'derived')

    fails = [r for r in ROWS if r[1] == 'FAIL']
    n_chk = len([r for r in ROWS if r[1] != 'INFO'])
    out = ['# Nosh enclosure check report', '',
           'Generated by `mech/check_enclosure.py` from `mech/Nosh-enclosure.FCStd`.',
           'Source tags: M measured by the user, B board file / STEP, D datasheet, C design choice,',
           'A assumed (confirm before printing).', '',
           '**%d checks, %d failed.** INFO rows are values, not checks. The plug and card keep-outs are' % (n_chk, len(fails)),
           'built from the same parameters as the notches, so those rows prove margin, not position;',
           'position is checked separately against the STEP (J3, J4) and the footprints (J2, J8, J9).',
           'The boxes standing in for J2, J6, J7, J8, J9, H5 and U1 use assumed heights.', '',
           '| Check | Result | Found | Limit | Inputs |', '|---|---|---|---|---|']
    out += ['| %s | %s | %s | %s | %s |' % r for r in ROWS]
    open(os.path.join(HERE, 'check_report.md'), 'w').write('\n'.join(out) + '\n')
    print('%d checks, %d failed' % (n_chk, len(fails)))


try:
    main()
except Exception:
    import traceback
    print('CHECK SCRIPT ERROR')
    print(traceback.format_exc())
    open(os.path.join(HERE, 'check_report.md'), 'w').write('# check script crashed\n\n```\n%s```\n' % traceback.format_exc())
