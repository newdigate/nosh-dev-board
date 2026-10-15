"""Hand-route list: every open connection on the board (run with KiCad's bundled python3).
usage: handroute_list.py [board.kicad_pcb] [out_dir]        defaults: Kicad/Nosh.kicad_pcb, Kicad/handroute/
Runs kicad-cli DRC on a scratch copy (with the project's rules, zones refilled), traces each unconnected end to the
copper it belongs to, groups the U1 ball-grid connections by the side they must leave on, lists the rest by net, and
writes bga_handroute.md + bga_open.png (ball-grid close-up) + board_open.png (whole board, every open numbered)."""
import sys, os, json, math, re, shutil, subprocess, tempfile, collections, datetime
import pcbnew
from pcbnew import ToMM
from PIL import Image, ImageDraw, ImageFont
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
SRC = sys.argv[1] if len(sys.argv) > 1 else K + 'Nosh.kicad_pcb'
OUT = (sys.argv[2].rstrip('/') + '/') if len(sys.argv) > 2 else K + 'handroute/'
CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
ROWS = 'ABCDEFGHJKLMNPRTU'
POWER = re.compile(r'^(\+|GND$|NVCC_|VDD|ADC_VREFH|SDRAM_3V3|USB2_VBUS|DCDC_(IN|DIG|ANA|LP|LN)$)')
# ---- DRC on a scratch copy next to the project files
tmp = tempfile.mkdtemp(); shutil.copy(SRC, tmp + '/Nosh.kicad_pcb')
for ext in ('kicad_pro', 'kicad_dru'):
    if os.path.exists(K + 'Nosh.' + ext): shutil.copy(K + 'Nosh.' + ext, tmp + '/Nosh.' + ext)
# --refill-zones + --save-board: the board may be saved with unfilled pours (every plane pad would show as open),
# and the saved fills let the connectivity below see which copper reaches a plane
subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--refill-zones', '--save-board', '-o', tmp + '/drc.json', tmp + '/Nosh.kicad_pcb'], check=True, capture_output=True)
drc = json.load(open(tmp + '/drc.json'))
b = pcbnew.LoadBoard(tmp + '/Nosh.kicad_pcb'); b.BuildConnectivity(); conn = b.GetConnectivity()
def cluster(it):
    """pads, vias and layers of the copper piece an item belongs to"""
    seen = {it.m_Uuid.AsString(): it}; todo = [it]; plane = False
    while todo:
        x = todo.pop()
        for y in conn.GetConnectedItems(x):
            y = y.Cast()
            if y.Type() == pcbnew.PCB_ZONE_T: plane = True; continue
            k = y.m_Uuid.AsString()
            if k not in seen: seen[k] = y; todo.append(y)
    pads = sorted({'%s.%s' % (p.GetParentFootprint().GetReference(), p.GetNumber()) for p in seen.values() if p.Type() == pcbnew.PCB_PAD_T})
    vias = [(round(ToMM(v.GetPosition().x), 2), round(ToMM(v.GetPosition().y), 2)) for v in seen.values() if v.Type() == pcbnew.PCB_VIA_T]
    return dict(pads=pads, vias=vias, plane=plane)
def drclayer(desc):
    """layer as the DRC names it ('Pad 1 [X] of C39 on B.Cu' -> B.Cu; a via -> 'via'): a pad's own GetLayer() reports
    F.Cu for pads of bottom-side footprints"""
    m = re.search(r' on ([^,]+?)(?:, |$)', desc)
    return '?' if not m else 'via' if ' - ' in m.group(1) else m.group(1)
ends = []
for v in drc['unconnected_items']:
    e = []
    for i in v['items']:
        it = b.ResolveItem(pcbnew.KIID(i['uuid'])); it = it.Cast() if it else None
        zone = bool(it) and it.Type() == pcbnew.PCB_ZONE_T
        c = dict(pads=[], vias=[], plane=True) if zone else cluster(it) if it else dict(pads=[], vias=[], plane=False)
        c.update(desc=i['description'], x=i['pos']['x'], y=i['pos']['y'], zone=it.GetZoneName() if zone else None,
                 layer=drclayer(i['description'])); e.append(c)
    ends.append(e)
# ---- rows: one per connection with an end at the ball grid
u1 = next(f for f in b.GetFootprints() if f.GetReference() == 'U1'); cx, cy = ToMM(u1.GetPosition().x), ToMM(u1.GetPosition().y)
def ballpos(n): return (cx - 6.4 + (int(n[1:]) - 1) * 0.8, cy - 6.4 + ROWS.index(n[0]) * 0.8)
def inbga(e): return abs(e['x'] - cx) <= 7.2 and abs(e['y'] - cy) <= 7.2
def balls(e): return [p[3:] for p in e['pads'] if p.startswith('U1.')]
def padname(e):
    m = re.match(r'Pad (\S+) \[.*?\] of (\S+)', e['desc']); return '%s.%s' % (m.group(2), m.group(1)) if m else None
def nearball(x, y, net):
    """U1 ball on `net` whose dog-bone ends at (x, y), if any (a lattice via is equidistant from four balls)"""
    for p in u1.Pads():
        if p.GetNetname() == net and math.dist((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)), (x, y)) < 0.6: return p.GetNumber()
    return None
def endtext(e):
    """what an unconnected end is: the pour, the pad itself, or the pads its copper already reaches"""
    if e['zone']: return '%s pour (%s)' % (e['zone'], e['layer'])
    own = padname(e)
    if own and own.startswith('U1.'): return 'U1 ball ' + own[3:]
    if own: return own
    if e['pads']: return 'copper from ' + ', '.join(e['pads'][:4]) + (' …' if len(e['pads']) > 4 else '')
    return 'stub (%d via%s, no pad)' % (len(e['vias']), '' if len(e['vias']) == 1 else 's')
def plane_islands(net):
    """inner-layer pieces of a net's pours that are not the main piece, with the vias inside them: a zone-to-zone
    open is usually a via boxed in by other nets' vias, whose plane connection is a scrap cut off by the antipads"""
    out = []
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net]
    for z in b.Zones():
        if z.GetNetname() != net or z.GetIsRuleArea(): continue
        for L in z.GetLayerSet().Seq():
            if L in (b.GetLayerID('F.Cu'), b.GetLayerID('B.Cu')): continue
            ps = z.GetFilledPolysList(L)
            if ps.OutlineCount() < 2: continue
            big = max(range(ps.OutlineCount()), key=lambda i: abs(ps.Outline(i).Area()))
            for i in range(ps.OutlineCount()):
                if i == big: continue
                for v in vias:
                    if ps.Outline(i).PointInside(v.GetPosition()):
                        vx, vy = ToMM(v.GetPosition().x), ToMM(v.GetPosition().y)
                        out.append((b.GetLayerName(L), round(vx, 2), round(vy, 2)))
    return out
rows = []; others = []
for a, c in ends:
    if a['zone'] and c['zone']:
        net = re.search(r'\[(.*?)\]', a['desc']).group(1); isl = plane_islands(net); where = collections.OrderedDict()
        for L, vx, vy in isl: where.setdefault((vx, vy), []).append(L)
        note = '; '.join('via at (%.2f, %.2f)%s reaches only a scrap of %s: the vias around it cut it off from the plane' %
                         (vx, vy, ' (ball %s fan-out)' % nearball(vx, vy, net) if nearball(vx, vy, net) else '', ' and '.join(Ls)) for (vx, vy), Ls in where.items())
        others.append(dict(net=net, a=a, c=c, note=note)); continue
    if c['zone'] and not a['zone']: pass
    elif a['zone']: a, c = c, a
    if not (inbga(a) or inbga(c) and not c['zone']):
        others.append(dict(net=re.search(r'\[(.*?)\]', a['desc']).group(1), a=a, c=c)); continue
    if not inbga(a): a, c = c, a
    if inbga(c) and balls(c) and not balls(a): a, c = c, a
    net = re.search(r'\[(.*?)\]', a['desc']).group(1); ba = balls(a); bb = balls(c)
    if os.environ.get('DEBUG'): print('row', a['desc'], '|', c['desc'], padname(c))
    ball = min(ba, key=lambda k: math.dist(ballpos(k), (a['x'], a['y']))) if ba else None
    via = None
    if ball:
        bp = ballpos(ball); vs = [v for v in a['vias'] if math.dist(v, bp) < 0.8]
        via = min(vs, key=lambda v: math.dist(v, bp)) if vs else None
    if c['zone']: far = '%s pour: needs a via to the plane' % c['zone']
    elif padname(c) and not padname(c).startswith('U1.'): far = padname(c) + (' (on the plane)' if c['plane'] else '')
    elif bb:
        near = [k for k in bb if math.dist(ballpos(k), (c['x'], c['y'])) < 0.05]
        far = ('U1 ball ' + near[0]) if near else ('%s via at (%.2f, %.2f)' % ('plane' if c['plane'] else 'fan-out', c['x'], c['y']))
    else: far = endtext(c)
    dx, dy = c['x'] - cx, c['y'] - cy
    side = 'inside' if c['zone'] or inbga(c) else ('S' if abs(dy) >= abs(dx) and dy > 0 else 'N' if abs(dy) >= abs(dx) else 'E' if dx > 0 else 'W')
    if c['zone']: c = dict(c, x=a['x'], y=a['y'])          # a pour has no position: mark the ball only
    rows.append(dict(net=net, power=bool(POWER.match(net)), ball=ball, via=via, far=far, fx=c['x'], fy=c['y'], flayer=c['layer'], side=side,
                     length=round(math.dist((a['x'], a['y']), (c['x'], c['y'])), 1), ax=a['x'], ay=a['y']))
order = {'inside': 0, 'S': 1, 'E': 2, 'N': 3, 'W': 4}
rows.sort(key=lambda r: (order[r['side']], r['ball'] or 'Z'))
for i, r in enumerate(rows, 1): r['id'] = i
others.sort(key=lambda r: (r['net'], r['a']['x']))
for i, r in enumerate(others, len(rows) + 1):
    r.update(id=i, power=bool(POWER.match(r['net'])), length=None if r['a']['zone'] or r['c']['zone'] else round(math.dist((r['a']['x'], r['a']['y']), (r['c']['x'], r['c']['y'])), 1))
# ---- close-up render, numbered at the ball end
os.makedirs(OUT, exist_ok=True)
x0, y0, x1, y1, k = cx - 9, cy - 8.5, cx + 9, cy + 8.5, 60
F, B, SIG = b.GetLayerID('F.Cu'), b.GetLayerID('B.Cu'), b.GetLayerID('SIG')
COL = {F: (110, 40, 40), SIG: (35, 90, 35), B: (40, 60, 120)}
im = Image.new('RGB', (int((x1 - x0) * k), int((y1 - y0) * k)), (18, 18, 22)); d = ImageDraw.Draw(im)
P = lambda x, y: ((x - x0) * k, (y - y0) * k)
try: f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 16)
except Exception: f = ImageFont.load_default()
for fp in b.GetFootprints():
    for p in fp.Pads():
        x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        if not (x0 - 3 < x < x1 + 3 and y0 - 3 < y < y1 + 3): continue
        bb_ = p.GetBoundingBox(); a_ = P(ToMM(bb_.GetLeft()), ToMM(bb_.GetTop())); c_ = P(ToMM(bb_.GetRight()), ToMM(bb_.GetBottom()))
        if fp.GetReference() == 'U1': d.ellipse([a_, c_], fill=(130, 110, 60))
        else: d.rectangle([a_, c_], fill=(120, 100, 60) if p.IsOnLayer(F) else (60, 70, 100))
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetLayer() in COL:
        d.line([P(ToMM(t.GetStart().x), ToMM(t.GetStart().y)), P(ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))], fill=COL[t.GetLayer()], width=max(1, int(ToMM(t.GetWidth()) * k)))
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y); r = ToMM(t.GetWidth(F)) / 2
        d.ellipse([P(x - r, y - r), P(x + r, y + r)], fill=(85, 85, 85))
for i, rr in enumerate(ROWS): d.text(P(cx - 7.6, cy - 6.4 + i * 0.8 - 0.25), rr, fill=(200, 200, 200), font=f)
for j in range(17): d.text(P(cx - 6.4 + j * 0.8 - 0.2, cy - 7.4), str(j + 1), fill=(200, 200, 200), font=f)
for r in rows:
    ax, ay, fx, fy = r['ax'], r['ay'], r['fx'], r['fy']; col = (0, 230, 255) if r['power'] else (255, 220, 0)
    L = math.dist((ax, ay), (fx, fy)); u = ((fx - ax) / L, (fy - ay) / L) if L else (0, 0)
    d.line([P(ax, ay), P(fx, fy)], fill=tuple(v // 2 for v in col), width=1)
    d.line([P(ax, ay), P(ax + u[0] * 1.5, ay + u[1] * 1.5)], fill=col, width=5)
    txt = str(r['id']); bw = d.textbbox((0, 0), txt, font=f); px, py = P(ax, ay); tx, ty = px - bw[2] / 2, py - bw[3] / 2 - 1
    d.rectangle([tx - 2, ty - 1, tx + bw[2] + 2, ty + bw[3] + 3], fill=(0, 0, 0), outline=col); d.text((tx, ty), txt, fill=col, font=f)
im.save(OUT + 'bga_open.png')
# ---- whole-board render, every open connection numbered at the middle of its airline
bb_ = b.GetBoardEdgesBoundingBox(); X0, Y0, X1, Y1 = ToMM(bb_.GetLeft()) - 1, ToMM(bb_.GetTop()) - 1, ToMM(bb_.GetRight()) + 1, ToMM(bb_.GetBottom()) + 1
kb = 14; im = Image.new('RGB', (int((X1 - X0) * kb), int((Y1 - Y0) * kb)), (18, 18, 22)); d = ImageDraw.Draw(im)
Q = lambda x, y: ((x - X0) * kb, (y - Y0) * kb)
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetLayer() in COL:
        d.line([Q(ToMM(t.GetStart().x), ToMM(t.GetStart().y)), Q(ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))], fill=COL[t.GetLayer()], width=1)
for fp in b.GetFootprints():
    for p in fp.Pads():
        bx_ = p.GetBoundingBox(); d.rectangle([Q(ToMM(bx_.GetLeft()), ToMM(bx_.GetTop())), Q(ToMM(bx_.GetRight()), ToMM(bx_.GetBottom()))], fill=(120, 100, 60) if p.IsOnLayer(F) else (60, 70, 100))
for dw in b.GetDrawings():
    if dw.GetLayer() == b.GetLayerID('Edge.Cuts') and dw.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        d.line([Q(ToMM(dw.GetStart().x), ToMM(dw.GetStart().y)), Q(ToMM(dw.GetEnd().x), ToMM(dw.GetEnd().y))], fill=(200, 200, 60), width=2)
allc = [(r['id'], r['ax'], r['ay'], r['fx'], r['fy'], r['power']) for r in rows] + \
       [(r['id'], r['a']['x'], r['a']['y'], r['c']['x'], r['c']['y'], r['power']) for r in others if not (r['a']['zone'] or r['c']['zone'])]
for n, ax, ay, fx, fy, pw in allc:
    col = (0, 230, 255) if pw else (255, 220, 0); d.line([Q(ax, ay), Q(fx, fy)], fill=col, width=2)
    for x, y in ((ax, ay), (fx, fy)): d.ellipse([Q(x - 0.35, y - 0.35), Q(x + 0.35, y + 0.35)], outline=col, width=2)
    txt = str(n); bw = d.textbbox((0, 0), txt, font=f); px, py = Q((ax + fx) / 2, (ay + fy) / 2); tx, ty = px - bw[2] / 2, py - bw[3] / 2 - 1
    d.rectangle([tx - 2, ty - 1, tx + bw[2] + 2, ty + bw[3] + 3], fill=(0, 0, 0), outline=col); d.text((tx, ty), txt, fill=col, font=f)
im.save(OUT + 'board_open.png')
# ---- markdown
G = {'inside': 'Inside the grid: ball-to-ball links and balls not yet on their plane', 'S': 'Escaping south', 'E': 'Escaping east', 'N': 'Escaping north', 'W': 'Escaping west'}
o = ['# Open connections to hand-route', '',
     'Generated by `tools/handroute_list.py` on %s from a KiCad DRC of the board with its zones refilled: **%d open connections** in total, %d with one end at the U1 ball grid (%d power, %d signal) and %d elsewhere on the board.' % (datetime.date.today().isoformat(), len(drc['unconnected_items']), len(rows), sum(r['power'] for r in rows), sum(not r['power'] for r in rows), len(others)),
     '', 'Numbers 1–%d match the labels in `bga_open.png` (label = the ball end; yellow = signal, cyan = power; the short bar points toward the other end). Every number is also in `board_open.png`, labelled at the middle of its airline.' % len(rows),
     'Balls are 0.8 mm pitch, A1 at (%.1f, %.1f), rows A–U top to bottom, columns 1–17 left to right. Coordinates are mm from the board origin (top-left, y down).' % ballpos('A1'),
     '', '- **Fan-out via** is the dog-bone via already on that ball: start there. "none" means the ball has no fan-out yet (the outer two rings escape on F.Cu).',
     "- **Other end** is where KiCad's ratsnest line lands (a pad, or the end of copper already routed on that net) and the pads it is part of.",
     '- Inside the grid only 0.1 mm tracks fit between the fan-out vias; no tracks on GND1, PWR or GND2.', '']
for side in ('inside', 'S', 'E', 'N', 'W'):
    rs = [r for r in rows if r['side'] == side]
    if not rs: continue
    o += ['## %s (%d)' % (G[side], len(rs)), '', '| # | Net | Ball | Fan-out via | Other end | At (x, y), layer | Airline mm |', '|---|---|---|---|---|---|---|']
    for r in rs:
        o.append('| %d | %s | %s | %s | %s | (%.2f, %.2f) %s | %s |' % (r['id'], r['net'] + (' ⚡' if r['power'] else ''), r['ball'] or '–', '(%.2f, %.2f)' % tuple(r['via']) if r['via'] else 'none', r['far'], r['fx'], r['fy'], r['flayer'], '–' if r['side'] == 'inside' and 'pour' in r['far'] else '%.1f' % r['length']))
    o.append('')
if others:
    o += ['## Elsewhere on the board (%d)' % len(others), '', 'Neither end is at the ball grid. "Copper from" means the end is a track or via already joined to those pads.', '',
          '| # | Net | From | At (x, y), layer | To | At (x, y), layer | Airline mm |', '|---|---|---|---|---|---|---|']
    for r in others:
        a, c = r['a'], r['c']
        at = lambda e: '–' if e['zone'] else '(%.2f, %.2f) %s' % (e['x'], e['y'], e['layer'])
        o.append('| %d | %s | %s | %s | %s | %s | %s |' % (r['id'], r['net'] + (' ⚡' if r['power'] else ''), endtext(a), at(a), endtext(c), at(c), '–' if r['length'] is None else '%.1f' % r['length']))
    for r in others:
        if r.get('note'): o += ['', '%d: %s.' % (r['id'], r['note'][0].upper() + r['note'][1:])]
    o.append('')
o.append('⚡ = power net (route wider than 0.1 mm once outside the grid where there is room).')
open(OUT + 'bga_handroute.md', 'w').write('\n'.join(o) + '\n')
print('%d BGA connections (%s), %d elsewhere, %d open in total -> %sbga_handroute.md, bga_open.png, board_open.png' % (len(rows), dict(collections.Counter(r['side'] for r in rows)), len(others), len(drc['unconnected_items']), OUT))
