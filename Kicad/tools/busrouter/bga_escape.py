"""Escape router for U1 (run with KiCad's bundled python3; uses libastar.dylib). Run bga_strip.py first.
usage: bga_escape.py in.kicad_pcb out.kicad_pcb [dest.json]
For every ball that still needs a connection it builds the short exit from the ball field to a band just outside
the strip window (63,33 .. 81,51): rings 0 and 1 leave on F.Cu from the pad, inner rings leave from their fan-out
via on SIG or B.Cu. Each escape heads for the side its nearest destination lies on (dest.json from the survey, else
the geometric side), and tries the other sides if that fails. Balls of a net already on a plane (GND, PWR islands)
get a via into the plane instead. Everything existing is fixed; each escape is fixed as soon as it is placed.
The joins from the band to the rest of the board are left for genroute.py / hand routing."""
import sys, os, math, re, time, array, collections, ctypes, json
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]
DEST = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
R = (63.0, 33.0, 81.0, 51.0); BAND = 0.4                 # strip window; escapes end in a BAND-wide strip outside it
WX0, WY0, WX1, WY1 = R[0] - 4, R[1] - 4, R[2] + 4, R[3] + 4
BOARDWIDE = os.environ.get('WINDOW') == 'board'           # route each escape all the way to the net's own copper anywhere on the board
TRK = 0.1
LIMIT = int(os.environ.get('LIMIT', '3000000')); DEBUG = os.environ.get('DEBUG') == '1'
board = pcbnew.LoadBoard(IN)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
if BOARDWIDE:
    _bb = board.GetBoardEdgesBoundingBox(); WX0, WY0, WX1, WY1 = ToMM(_bb.GetLeft()) - 0.5, ToMM(_bb.GetTop()) - 0.5, ToMM(_bb.GetRight()) + 0.5, ToMM(_bb.GetBottom()) + 0.5
LAY = {'F': pcbnew.F_Cu, 'S': board.GetLayerID('SIG'), 'B': pcbnew.B_Cu}; LIDX = {'F': 0, 'S': 1, 'B': 2}; LNAME = 'FSB'
LAYER_OF = {v: LIDX[k] for k, v in LAY.items()}
CLR, FAN_CLR, HOLE_CLR, PTH_CLR = 0.127, 0.10, 0.20, 0.20
VIA_D, VIA_H = 0.45, 0.30
G = 0.05; SAFE = 0.003
X0, Y0 = WX0, WY0
NX, NY = int(round((WX1 - WX0) / G)) + 1, int(round((WY1 - WY0) / G)) + 1; N = NX * NY
def gx(x): return int(round((x - X0) / G))
def gy(y): return int(round((y - Y0) / G))
def wx(i): return X0 + i * G
def wy(j): return Y0 + j * G
def _lo(v, o): return int(math.ceil((v - o) / G - 1e-9))
def _hi(v, o): return int(math.floor((v - o) / G + 1e-9))
def disc_cells(x, y, r):
    r = r + SAFE if r > 0.2 else r; out = []
    for j in range(max(0, _lo(y - r, Y0)), min(NY - 1, _hi(y + r, Y0)) + 1):
        dy = wy(j) - y
        if dy * dy > r * r: continue
        h = math.sqrt(r * r - dy * dy); a, b_ = _lo(x - h, X0), _hi(x + h, X0)
        a, b_ = max(0, a), min(NX - 1, b_)
        if b_ >= a: out.append((j, a, b_))
    return out
def rect_cells(x0, y0, x1, y1):
    i0, i1, j0, j1 = max(0, _lo(x0, X0)), min(NX - 1, _hi(x1, X0)), max(0, _lo(y0, Y0)), min(NY - 1, _hi(y1, Y0))
    return [(j, i0, i1) for j in range(j0, j1 + 1)] if i1 >= i0 else []
def capsule_cells(x0, y0, x1, y1, r):
    L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / (G * 0.7))); seen = {}
    for k in range(n + 1):
        t = k / n
        for j, a, b_ in disc_cells(x0 + t * (x1 - x0), y0 + t * (y1 - y0), r):
            seen[j] = (min(seen[j][0], a), max(seen[j][1], b_)) if j in seen else (a, b_)
    return [(j, a, b_) for j, (a, b_) in seen.items()]
def poly_cells(poly, extra):
    bbx = poly.BBox(); out = []
    x0, y0, x1, y1 = ToMM(bbx.GetLeft()) - extra, ToMM(bbx.GetTop()) - extra, ToMM(bbx.GetRight()) + extra, ToMM(bbx.GetBottom()) + extra
    for j, a, b_ in rect_cells(x0, y0, x1, y1):
        run = None
        for i in range(a, b_ + 1):
            inside = poly.Collide(VECTOR2I(FromMM(wx(i)), FromMM(wy(j))), FromMM(extra))
            if inside and run is None: run = i
            if not inside and run is not None: out.append((j, run, i - 1)); run = None
        if run is not None: out.append((j, run, b_))
    return out
def bump(grid, spans, d):
    for j, a, b_ in spans:
        base = j * NX
        for i in range(a, b_ + 1): grid[base + i] += d
def paint(grid, spans):
    for j, a, b_ in spans:
        base = j * NX
        for i in range(a, b_ + 1): grid[base + i] = 1
def in_window(x0, y0, x1, y1): return x1 >= WX0 - 1 and x0 <= WX1 + 1 and y1 >= WY0 - 1 and y0 <= WY1 + 1
TRK_R = TRK / 2 + CLR
static = [bytearray(N) for _ in range(3)]; via_static = bytearray(N)
cnt = [array.array('H', bytes(2 * N)) for _ in range(3)]; fixc = [array.array('H', bytes(2 * N)) for _ in range(3)]
hist = [array.array('H', bytes(2 * N)) for _ in range(3)]
via_soft = array.array('H', bytes(2 * N)); via_fix = array.array('H', bytes(2 * N))
item_fix = {}; via_own = {}; core = collections.defaultdict(list); item_obj = {}
t0 = time.time()
for z in list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]:
    if not z.GetIsRuleArea(): continue
    o = z.Outline(); bb = o.BBox()
    if not in_window(ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())): continue
    if z.GetDoNotAllowTracks():
        for L, l in LAY.items():
            if z.IsOnLayer(l): paint(static[LIDX[L]], poly_cells(o, TRK / 2 + CLR))
    if z.GetDoNotAllowVias(): paint(via_static, poly_cells(o, VIA_D / 2 + CLR))
if BOARDWIDE:
    _e = 0.3 + TRK / 2; _bb = board.GetBoardEdgesBoundingBox(); _x0, _y0, _x1, _y1 = ToMM(_bb.GetLeft()), ToMM(_bb.GetTop()), ToMM(_bb.GetRight()), ToMM(_bb.GetBottom())
    for l in range(3):
        for rc in (rect_cells(_x0 - 1, _y0 - 1, _x1 + 1, _y0 + _e), rect_cells(_x0 - 1, _y1 - _e, _x1 + 1, _y1 + 1), rect_cells(_x0 - 1, _y0 - 1, _x0 + _e, _y1 + 1), rect_cells(_x1 - _e, _y0 - 1, _x1 + 1, _y1 + 1)): paint(static[l], rc)
    for rc in (rect_cells(_x0 - 1, _y0 - 1, _x1 + 1, _y0 + 0.6), rect_cells(_x0 - 1, _y1 - 0.6, _x1 + 1, _y1 + 1), rect_cells(_x0 - 1, _y0 - 1, _x0 + 0.6, _y1 + 1), rect_cells(_x1 - 0.6, _y0 - 1, _x1 + 1, _y1 + 1)): paint(via_static, rc)
nets_by_name = board.GetNetInfo().NetsByName()
FIELD = (65.2, 35.2, 78.8, 48.8)                                  # the ball field: no new vias in here
paint(via_static, rect_cells(*FIELD))
def pad_layers(p): return [l for L, l in LAY.items() if p.IsOnLayer(l)]
BALL = {}                                                  # ball number -> (pad, net, ring, x, y)
ROWS = 'ABCDEFGHJKLMNPRTU'
for f in board.GetFootprints():
    for p in f.Pads():
        net = p.GetNetname(); x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        bx = p.GetBoundingBox(); px0, py0, px1, py1 = ToMM(bx.GetLeft()), ToMM(bx.GetTop()), ToMM(bx.GetRight()), ToMM(bx.GetBottom())
        if not in_window(px0, py0, px1, py1): continue
        pth = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH); hole = ToMM(p.GetDrillSize().x) if p.GetDrillSize().x else 0.0
        extra = TRK / 2 + (PTH_CLR if pth else CLR)
        spans = disc_cells(x, y, (px1 - px0) / 2 + extra) if (p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE or (p.GetShape() == pcbnew.PAD_SHAPE_OVAL and abs((px1 - px0) - (py1 - py0)) < 0.01)) else rect_cells(px0 - extra, py0 - extra, px1 + extra, py1 + extra)
        key = ('pad', f.GetReference(), p.GetNumber())
        lays = [LAYER_OF[l] for l in pad_layers(p)] if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH else [0, 1, 2]
        cells = [(l, spans) for l in lays]
        if hole:
            hs = disc_cells(x, y, hole / 2 + 0.3 + TRK / 2); cells += [(l, hs) for l in range(3)]
        for l, sp in cells: bump(fixc[l], sp, 1)
        item_fix[(net,) + key] = cells
        paint(via_static, rect_cells(px0 - VIA_D / 2 - CLR, py0 - VIA_D / 2 - CLR, px1 + VIA_D / 2 + CLR, py1 + VIA_D / 2 + CLR))
        if hole: paint(via_static, disc_cells(x, y, hole / 2 + 0.45 + VIA_H / 2))
        if net:
            sx, sy = ToMM(p.GetSize().x), ToMM(p.GetSize().y); shp = p.GetShape()
            if shp == pcbnew.PAD_SHAPE_CIRCLE: csp = disc_cells(x, y, sx / 2 - 0.02)
            elif shp == pcbnew.PAD_SHAPE_OVAL and abs(sx - sy) > 0.01:
                a = math.radians(p.GetOrientationDegrees()); half = (max(sx, sy) - min(sx, sy)) / 2
                ux, uy = (math.cos(a), -math.sin(a)) if sx > sy else (math.sin(a), math.cos(a))
                csp = capsule_cells(x - ux * half, y - uy * half, x + ux * half, y + uy * half, min(sx, sy) / 2 - 0.02)
            elif shp == pcbnew.PAD_SHAPE_OVAL: csp = disc_cells(x, y, sx / 2 - 0.02)
            else: csp = rect_cells(px0 + 0.02, py0 + 0.02, px1 - 0.02, py1 - 0.02)
            core[net].append(((net,) + key, [(l, csp) for l in lays], (x, y), pth))
        if f.GetReference() == 'U1' and net and not net.startswith('unconnected'):
            n = p.GetNumber(); r, c = ROWS.index(n[0]), int(n[1:]) - 1
            BALL[n] = (p, net, min(r, c, 16 - r, 16 - c), x, y)
for t in board.GetTracks():
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y); vd, vh = ToMM(t.GetWidth(pcbnew.F_Cu)), ToMM(t.GetDrill())
        if not in_window(x - 1, y - 1, x + 1, y + 1): continue
        r = max(vd / 2 + (FAN_CLR if vh < 0.3 else CLR) + TRK / 2, vh / 2 + HOLE_CLR + TRK / 2); sp = disc_cells(x, y, r)
        key = (net, 'via', x, y); item_fix[key] = [(l, sp) for l in range(3)]; item_obj[key] = t
        for l in range(3): bump(fixc[l], sp, 1)
        vs = disc_cells(x, y, max(vd / 2 + CLR + VIA_D / 2, vh / 2 + 0.2 + VIA_H / 2)); bump(via_fix, vs, 1); via_own[key] = vs
        paint(via_static, disc_cells(x, y, vh / 2 + 0.254 + VIA_H / 2))
        core[net].append((key, [(l, disc_cells(x, y, min(0.2, vd / 2))) for l in range(3)], (x, y), True))
    else:
        l = LAYER_OF.get(t.GetLayer())
        if l is None: continue
        x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y); w = ToMM(t.GetWidth())
        if not in_window(min(x0, x1) - 1, min(y0, y1) - 1, max(x0, x1) + 1, max(y0, y1) + 1): continue
        sp = capsule_cells(x0, y0, x1, y1, w / 2 + TRK_R); key = (net, 'trk', x0, y0, x1, y1); item_fix[key] = [(l, sp)]; bump(fixc[l], sp, 1); item_obj[key] = t
        vs = capsule_cells(x0, y0, x1, y1, w / 2 + CLR + VIA_D / 2); bump(via_fix, vs, 1); via_own[key] = vs
        core[net].append((key, [(l, capsule_cells(x0, y0, x1, y1, max(0.0, w / 2 - 0.01)))], ((x0 + x1) / 2, (y0 + y1) / 2), False))
print('grids built: %d x %d, %.1fs; %d balls with nets' % (NX, NY, time.time() - t0, len(BALL)), flush=True)
PLANE_L = [board.GetLayerID(n) for n in ('GND1', 'PWR', 'GND2')]
planes = collections.defaultdict(list)
for z in board.Zones():
    if z.GetIsRuleArea() or not z.GetNetname(): continue
    for l in PLANE_L:
        if z.IsOnLayer(l): planes[z.GetNetname()].append(z.GetFilledPolysList(l))
def in_plane(net, x, y):
    return any(ps.Contains(VECTOR2I(FromMM(x), FromMM(y))) for ps in planes.get(net, ()))
def routed_items(net):
    out = []
    segs, vias = added.get(net, ([], []))
    for n_, sg in enumerate(segs):
        l, x0, y0, x1, y1 = sg[:5]; w = sg[5] if len(sg) > 5 else TRK
        out.append(((net, 'r', n_), [(l, capsule_cells(x0, y0, x1, y1, max(0.0, w / 2 - 0.01)))], ((x0 + x1) / 2, (y0 + y1) / 2), False))
    for n_, v in enumerate(vias):
        out.append(((net, 'rv', n_), [(l, disc_cells(v[0], v[1], 0.2)) for l in range(3)], (v[0], v[1]), True))
    return out
def islands(net):
    items = core.get(net, []) + routed_items(net); par = list(range(len(items))); owner = {}
    def find(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for n_, (key, cells, xy, through) in enumerate(items):
        for l, sp in cells:
            for j, a, b_ in sp:
                for i in range(a, b_ + 1):
                    c = (l, j * NX + i)
                    if c in owner: par[find(n_)] = find(owner[c])
                    else: owner[c] = n_
    plane_hub = None
    for n_, (key, cells, xy, through) in enumerate(items):
        if through and in_plane(net, *xy):
            if plane_hub is None: plane_hub = n_
            else: par[find(n_)] = find(plane_hub)
    groups = collections.defaultdict(list)
    for n_ in range(len(items)): groups[find(n_)].append(n_)
    out = []
    for g, members in groups.items():
        cells = set()
        for m in members:
            for l, sp in items[m][1]:
                for j, a, b_ in sp: cells.update((l, i, j) for i in range(a, b_ + 1))
        out.append({'members': [items[m][0] for m in members], 'cells': cells, 'plane': plane_hub is not None and find(plane_hub) == g,
                    'has_pad': any(items[m][0][1] == 'pad' for m in members)})
    return [c for c in out if c['cells']]
HERE = os.path.dirname(os.path.abspath(__file__))
lib = ctypes.CDLL(os.path.join(HERE, 'libastar.dylib'))
from ctypes import c_int, c_float, c_void_p, POINTER, byref
class GridS(ctypes.Structure):
    _fields_ = [('nx', c_int), ('ny', c_int), ('g', c_float), ('x0', c_float), ('y0', c_float),
                ('stat', c_void_p * 3), ('cnt', c_void_p * 3), ('hist', c_void_p * 3), ('fixc', c_void_p * 3), ('via_static', c_void_p), ('via_soft', c_void_p), ('via_fix', c_void_p),
                ('fac', c_void_p * 3), ('viacost', c_void_p), ('pres', c_float), ('histw', c_float), ('turn', c_float), ('esc_i0', c_int), ('esc_i1', c_int)]
class WorkS(ctypes.Structure):
    _fields_ = [('dist', c_void_p), ('prev', c_void_p), ('dir', c_void_p), ('own_cnt', c_void_p), ('own_vsoft', c_void_p), ('own_vfix', c_void_p), ('own_fix', c_void_p), ('tmask', c_void_p)]
P32 = POINTER(ctypes.c_int32)
lib.route.argtypes = [POINTER(GridS), POINTER(WorkS), c_int, P32, c_int, P32, c_int, P32, c_float, c_float, c_int, P32, c_int, POINTER(c_int), POINTER(c_int)]
_keep = []
def addr(buf):
    if isinstance(buf, bytearray):
        c = (ctypes.c_char * len(buf)).from_buffer(buf); _keep.append(c); return ctypes.addressof(c)
    return buf.buffer_info()[0]
FAC = [array.array('f', [1.0] * NX), array.array('f', [1.15] * NX), array.array('f', [1.0] * NX)]
VIACOST = array.array('f', [0.8] * NX)
GR = GridS(); GR.nx, GR.ny, GR.g, GR.x0, GR.y0 = NX, NY, G, X0, Y0
for l in range(3):
    GR.stat[l] = addr(static[l]); GR.cnt[l] = addr(cnt[l]); GR.hist[l] = addr(hist[l]); GR.fixc[l] = addr(fixc[l]); GR.fac[l] = addr(FAC[l])
GR.via_static = addr(via_static); GR.via_soft = addr(via_soft); GR.via_fix = addr(via_fix); GR.viacost = addr(VIACOST)
GR.pres, GR.histw, GR.turn, GR.esc_i0, GR.esc_i1 = 0.3, 0.3, 0.03, -10, -10
N3 = 3 * N
WB = [array.array('d', bytes(8 * N3)), array.array('i', bytes(4 * N3)), bytearray(N3), array.array('H', bytes(2 * N3)),
      array.array('H', bytes(2 * N)), array.array('H', bytes(2 * N)), array.array('H', bytes(2 * N3)), bytearray(N3)]
W = WorkS(*[addr(b_) for b_ in WB])
OUTCAP = 200000
added = {}                                  # ball -> (net, segs, vias)   negotiated routes
routed_cells = {}; via_cells = {}           # (net, ball, kind, n) -> spans
def own_spans(net):
    out = array.array('i')
    for key, cells in item_fix.items():
        if key[0] != net: continue
        for l, sp in cells:
            for j, a, b_ in sp: out.extend((3, l, j, a, b_))
        for j, a, b_ in via_own.get(key, []): out.extend((2, 0, j, a, b_))
    for key, cells in routed_cells.items():
        if key[0] != net: continue
        for l, sp in cells:
            for j, a, b_ in sp: out.extend((0, l, j, a, b_))
        for j, a, b_ in via_cells.get(key, []): out.extend((1, 0, j, a, b_))
    return out
def route(net, sources, targets, limit):
    srcs = array.array('i'); [srcs.extend(c) for c in sources]
    tg = array.array('i'); [tg.extend(c) for c in targets]
    own = own_spans(net)
    hx = sum(wx(i) for _, i, _ in targets) / len(targets); hy = sum(wy(j) for _, _, j in targets) / len(targets)
    out = array.array('i', bytes(4 * 3 * OUTCAP)); n = c_int(0); exp = c_int(0)
    as32 = lambda a: ctypes.cast(a.buffer_info()[0], P32)
    lib.route(byref(GR), byref(W), len(sources), as32(srcs), len(targets), as32(tg), len(own) // 5, as32(own) if len(own) else None,
              hx, hy, limit, as32(out), OUTCAP, byref(n), byref(exp))
    if n.value < 0: return None, exp.value
    return [(out[3 * p], out[3 * p + 1], out[3 * p + 2]) for p in range(n.value)], exp.value
def path_to_geometry(path):
    segs = []; vias = []; run = [path[0]]
    def flush(run):
        if len(run) < 2: return
        pts = [run[0]]
        for a, b_, c in zip(run, run[1:], run[2:]):
            if (b_[1] - a[1], b_[2] - a[2]) != (c[1] - b_[1], c[2] - b_[2]): pts.append(b_)
        pts.append(run[-1])
        for a, b_ in zip(pts, pts[1:]): segs.append((a[0], wx(a[1]), wy(a[2]), wx(b_[1]), wy(b_[2])))
    for a, b_ in zip(path, path[1:]):
        if a[0] != b_[0]: flush(run); vias.append((wx(a[1]), wy(a[2]))); run = [b_]
        else: run.append(b_)
    flush(run); return segs, vias
def fix(net, segs, vias):
    """make copper hard (used for the plane vias, placed first and never ripped up)"""
    for sg in segs:
        l, x0, y0, x1, y1 = sg[:5]
        k = (net, 'gtrk', l, x0, y0, x1, y1); sp = capsule_cells(x0, y0, x1, y1, TRK / 2 + TRK_R); item_fix[k] = [(l, sp)]; bump(fixc[l], sp, 1)
        vs = capsule_cells(x0, y0, x1, y1, TRK / 2 + CLR + VIA_D / 2); bump(via_fix, vs, 1); via_own[k] = vs
        core[net].append((k, [(l, capsule_cells(x0, y0, x1, y1, TRK / 2 - 0.01))], ((x0 + x1) / 2, (y0 + y1) / 2), False))
    for x, y in vias:
        k = (net, 'gvia', x, y); sp = disc_cells(x, y, max(VIA_D / 2 + CLR + TRK / 2, VIA_H / 2 + HOLE_CLR + TRK / 2)); item_fix[k] = [(l, sp) for l in range(3)]
        for l in range(3): bump(fixc[l], sp, 1)
        vs = disc_cells(x, y, max(VIA_D / 2 + CLR + VIA_D / 2, VIA_H / 2 + 0.254 + VIA_H / 2) + 0.02); bump(via_fix, vs, 1); via_own[k] = vs
        paint(via_static, disc_cells(x, y, VIA_H / 2 + 0.254 + VIA_H / 2))
        core[net].append((k, [(l, disc_cells(x, y, 0.2)) for l in range(3)], (x, y), True))
def commit(ball, net, segs, vias):
    for n_, sg in enumerate(segs):
        l, x0, y0, x1, y1 = sg[:5]
        sp = capsule_cells(x0, y0, x1, y1, TRK / 2 + TRK_R); bump(cnt[l], sp, 1)
        vs = capsule_cells(x0, y0, x1, y1, TRK / 2 + CLR + VIA_D / 2); bump(via_soft, vs, 1)
        k = (net, ball, 'rtrk', n_); routed_cells[k] = [(l, sp)]; via_cells[k] = vs
    for n_, (x, y) in enumerate(vias):
        sp = disc_cells(x, y, max(VIA_D / 2 + CLR + TRK / 2, VIA_H / 2 + HOLE_CLR + TRK / 2))
        for l in range(3): bump(cnt[l], sp, 1)
        vs = disc_cells(x, y, max(VIA_D / 2 + CLR + VIA_D / 2, VIA_H / 2 + 0.254 + VIA_H / 2) + 0.02); bump(via_soft, vs, 1)
        k = (net, ball, 'rvia', n_); routed_cells[k] = [(l, sp) for l in range(3)]; via_cells[k] = vs
    added[ball] = (net, segs, vias)
def uncommit(ball):
    for k in [k for k in routed_cells if k[1] == ball]:
        for l, sp in routed_cells[k]: bump(cnt[l], sp, -1)
        bump(via_soft, via_cells[k], -1); del routed_cells[k]; del via_cells[k]
    added.pop(ball, None)
def conflicts(ball):
    """cells of this ball's route that other nets' routes also claim"""
    net = added[ball][0]; hits = []
    for k, cells in routed_cells.items():
        if k[0] != net: continue
        for l, sp in cells: bump(cnt[l], sp, -1)
        bump(via_soft, via_cells[k], -1)
    for l, x0, y0, x1, y1 in added[ball][1]:
        L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / G))
        for s in range(n + 1):
            i, j = gx(x0 + (x1 - x0) * s / n), gy(y0 + (y1 - y0) * s / n); k = j * NX + i
            if cnt[l][k]: hits.append((l, k))
    for x, y in added[ball][2]:
        k = gy(y) * NX + gx(x)
        if any(cnt[l][k] for l in range(3)) or via_soft[k] or via_fix[k]: hits.append((0, k))   # via too close to another net's track or via
    for k, cells in routed_cells.items():
        if k[0] != net: continue
        for l, sp in cells: bump(cnt[l], sp, 1)
        bump(via_soft, via_cells[k], 1)
    return hits
def plane_via_targets(net, cells, radius):
    xs = [wx(i) for _, i, _ in cells]; ys = [wy(j) for _, _, j in cells]
    out = set()
    for j, a, b_ in rect_cells(min(xs) - radius, min(ys) - radius, max(xs) + radius, max(ys) + radius):
        for i in range(a, b_ + 1):
            k = j * NX + i
            if via_static[k] or via_fix[k] or via_soft[k]: continue
            if any(static[l][k] or fixc[l][k] for l in range(3)): continue
            if not in_plane(net, wx(i), wy(j)): continue
            out.update((l, i, j) for l in range(3))
    return out
# ---- escape plan
BANDC = {'E': rect_cells(R[2], R[1], R[2] + BAND, R[3]), 'W': rect_cells(R[0] - BAND, R[1], R[0], R[3]),
         'S': rect_cells(R[0], R[3], R[2], R[3] + BAND), 'N': rect_cells(R[0], R[1] - BAND, R[2], R[1])}
def band_cells(sides):
    if BOARDWIDE: return []
    return [(l, i, j) for s in sides for l in range(3) for j, a, b_ in BANDC[s] for i in range(a, b_ + 1)]
def geo_side(x, y):
    dx, dy = x - 72, y - 42
    return ('E' if dx > 0 else 'W') if abs(dx) > abs(dy) else ('S' if dy > 0 else 'N')
def item_cells(key):
    for k, cells, xy, through in core[key[0]]:
        if k == key: return cells
    return []
def cells_of(spans_by_layer): return [(l, i, j) for l, sp in spans_by_layer for j, a, b_ in sp for i in range(a, b_ + 1)]
def fanout_via(name):
    p, net, ring, x, y = BALL[name]
    for key in item_fix:
        if key[0] == net and key[1] == 'via' and abs(abs(key[2] - x) - 0.4) < 0.02 and abs(abs(key[3] - y) - 0.4) < 0.02: return key
    return None
todo = []; done = {}
for name, (p, net, ring, x, y) in BALL.items():
    if net.startswith('SEMC'): continue
    comps = islands(net)
    mine = next((c for c in comps if (net, 'pad', 'U1', name) in c['members']), None)
    if mine is None: continue
    if mine['plane']: done[name] = 'on plane'; continue
    if DEST and name in DEST and DEST[name].get('dest') is None: done[name] = 'no other pad'; continue
    if any(k[1] == 'pad' and k[2] != 'U1' for k in mine['members']): done[name] = 'already routed'; continue
    if any(not (R[0] + 0.1 < wx(i) < R[2] - 0.1 and R[1] + 0.1 < wy(j) < R[3] - 0.1) for l, i, j in mine['cells']): done[name] = 'already routed'; continue   # reaches the band
    if any(k[1] in ('trk', 'via') and not (FIELD[0] - 0.3 <= k[-2] <= FIELD[2] + 0.3 and FIELD[1] - 0.3 <= k[-1] <= FIELD[3] + 0.3) for k in mine['members']): done[name] = 'already routed'; continue   # joined copper outside the field
    todo.append(name)
if os.environ.get('ONLY'): todo = [n for n in todo if n in os.environ['ONLY'].split(',')]
print('balls: %d to escape, %d done (%s)' % (len(todo), len(done), dict(collections.Counter(done.values()))), flush=True)
results = {}; t1 = time.time()
SRC = {}; PREF = {}
def outside_field(x, y): return not (FIELD[0] - 0.3 <= x <= FIELD[2] + 0.3 and FIELD[1] - 0.3 <= y <= FIELD[3] + 0.3)
OUTSIDE = collections.defaultdict(list)                   # net -> cells of its fixed copper outside the field, inside the window
for net_ in {BALL[n][1] for n in todo}:
    for key, cells, xy, through in core[net_]:
        if key[1] in ('pad', 'trk', 'via'): OUTSIDE[net_] += [c for c in cells_of(cells) if outside_field(wx(c[1]), wy(c[2]))]
for name in todo:
    p, net, ring, x, y = BALL[name]
    via = fanout_via(name) if ring >= 2 else None
    SRC[name] = cells_of([(l, sp) for l, sp in item_cells(via) if l in (1, 2)]) if via else cells_of(item_cells((net, 'pad', 'U1', name)))
    PREF[name] = DEST.get(name, {}).get('side') or geo_side(x, y)
# 1. balls of a net with a plane: a via into the plane (fixed at once; local, no competition)
for name in list(todo):
    p, net, ring, x, y = BALL[name]
    if net not in planes: continue
    pv = {c for c in plane_via_targets(net, SRC[name], 1.6) if not (FIELD[0] <= wx(c[1]) <= FIELD[2] and FIELD[1] <= wy(c[2]) <= FIELD[3])}
    own = set()
    for key, cells, xy, through in core[net]:
        if key[1] in ('gtrk', 'gvia'): own.update(cells_of(cells))
    path, exp = route(net, SRC[name], list(pv | own), LIMIT) if (pv or own) else (None, 0)
    if path is None: results[name] = ('FAILED', 'plane'); print('  %-4s %-16s ring %d: no via site into the plane' % (name, net, ring), flush=True)
    else:
        segs, vias = path_to_geometry(path); end = path[-1]
        if end in pv and not any(math.hypot(vx - wx(end[1]), vy - wy(end[2])) < 0.1 for vx, vy in vias): vias.append((wx(end[1]), wy(end[2])))
        fix(net, segs, vias); results[name] = ('plane', '%d seg %d via' % (len(segs), len(vias)))
    todo.remove(name)
print('plane vias placed: %d (%.0fs)' % (sum(1 for r in results.values() if r[0] == 'plane'), time.time() - t1), flush=True)
# 2. the escapes, negotiated: every ball re-routes each round through the current congestion, conflicts raise the
#    history cost of the contested cells, the pressure rises until every escape is alone in its channel
ROUNDS = int(os.environ.get('ROUNDS', '60')); WIDEN = int(os.environ.get('WIDEN', '12'))
SEED = int(os.environ.get('SEED', '0'))
OPP = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
def widen(name):
    have = sides_of[name]; pr = PREF[name]
    more = [s_ for s_ in 'NESW' if s_ not in have and s_ != OPP[pr]] or [s_ for s_ in 'NESW' if s_ not in have]
    if more: sides_of[name] = have + [more[0]]
work = set(todo); best = None; trouble = collections.Counter()
MODE = os.environ.get('MODE', 'band')                     # band: destination side + nearest side from the start; pref: destination side only
sides_of = {n: ([PREF[n]] if MODE == 'pref' else list(dict.fromkeys([PREF[n], geo_side(BALL[n][3], BALL[n][4])]))) for n in todo}
import random
for rnd in range(1, ROUNDS + 1):
    t2 = time.time(); fails = {}
    NETB = collections.defaultdict(list)
    for n_ in todo: NETB[BALL[n_][1]].append(n_)
    work = {n_ for n_ in work for n_ in NETB[BALL[n_][1]]}  # a net's balls travel together
    groups = sorted({BALL[n_][1] for n_ in work}); random.Random(rnd + SEED).shuffle(groups)
    groups.sort(key=lambda g: -max(BALL[n_][2] for n_ in NETB[g]))          # inner rings first within the round
    order = [n_ for g in groups for n_ in sorted(NETB[g], key=lambda n_: -BALL[n_][2])]
    for n_ in order: uncommit(n_)
    for name in order:
        p, net, ring, x, y = BALL[name]
        own = set()
        for k, cells in routed_cells.items():
            if k[0] == net: own.update(cells_of(cells))
        if MODE == 'pref': tg = band_cells(sides_of[name]) + [c for c in OUTSIDE.get(net, []) if geo_side(wx(c[1]), wy(c[2])) in sides_of[name]] + list(own)   # the band on the allowed sides, or the net's own copper there
        else: tg = band_cells(sides_of[name]) + OUTSIDE.get(net, []) + list(own)                                                                              # the band, or the net's own copper anywhere in the window
        path, exp = route(net, SRC[name], tg, LIMIT)
        if path is None:
            fails[name] = sides_of[name]; trouble[name] += 2
            if trouble[name] >= WIDEN: widen(name); trouble[name] = WIDEN // 2
            continue
        segs, vias = path_to_geometry(path); commit(name, net, segs, vias)
    conf = {}
    for name in list(added):
        h = conflicts(name)
        if h:
            conf[name] = len(h); trouble[name] += 1
            if trouble[name] >= WIDEN: widen(name); trouble[name] = WIDEN // 2
            for l, k in h: hist[l][k] = min(hist[l][k] + 1, 60000)
    print('round %2d: pres %.1f, worked on %d, failed %d, conflicting %d (%d cells) %.1fs' % (rnd, GR.pres, len(work), len(fails), len(conf), sum(conf.values()), time.time() - t2), flush=True)
    score = len(conf) * 1000 + 3000 * len(fails)
    if best is None or score < best[0]: best = (score, rnd, {n: (v[0], list(v[1]), list(v[2])) for n, v in added.items()}, dict(fails), dict(conf))
    if not conf and not fails: break
    GR.pres = min(GR.pres * 1.6, 2000.0)
    work = set(conf) | set(fails)
score, rnd, keep, fails, conf = best
print('keeping round %d: %d escapes placed, %d failed, %d still conflicting (dropped)' % (rnd, len(keep) - len(conf), len(fails), len(conf)))
for n in sorted(fails): print('   failed %-4s %-16s ring %d wanted %s' % (n, BALL[n][1], BALL[n][2], fails[n]))
for n, (net, segs, vias) in keep.items():
    if n in conf: results[n] = ('FAILED', 'conflict'); continue
    L = sum(math.hypot(s[3] - s[1], s[4] - s[2]) for s in segs); end = segs[-1][3:5] if segs else (0, 0)
    results[n] = (geo_side(*end), '%s %.1f mm %s' % (geo_side(*end), L, ''.join(LNAME[l] for l in sorted({s[0] for s in segs}))))
for n in fails: results[n] = ('FAILED', 'boxed in')
print('escapes: %d placed, %d failed (%.0fs)' % (sum(1 for r in results.values() if r[0] not in ('FAILED', 'plane')), sum(1 for r in results.values() if r[0] == 'FAILED'), time.time() - t1), flush=True)
json.dump({'results': results, 'done': done}, open(OUT + '.json', 'w'), indent=1)
WRITE = [(net, segs, vias) for n, (net, segs, vias) in keep.items() if n not in conf]
for net in {k[0] for k in item_fix if k[1] in ('gtrk', 'gvia')}:
    WRITE.append((net, [k[2:] for k in item_fix if k[0] == net and k[1] == 'gtrk'], [k[2:] for k in item_fix if k[0] == net and k[1] == 'gvia']))
# ---- write
DEAD = []
for n in set(k[0] for k in item_obj):
    for c in islands(n):
        if c['has_pad'] or c['plane']: continue
        if any(wx(i) < WX0 + 1 or wx(i) > WX1 - 1 or wy(j) < WY0 + 1 or wy(j) > WY1 - 1 for l, i, j in c['cells']): continue   # may continue outside the window
        for key in c['members']:
            if key in item_obj: DEAD.append(item_obj[key])
n_items = 0
for net, segs, vias in WRITE:
    ni = nets_by_name[net]
    for sg in segs:
        l, x0, y0, x1, y1 = sg[:5]
        if math.hypot(x1 - x0, y1 - y0) < 1e-6: continue
        t = pcbnew.PCB_TRACK(board); t.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); t.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
        t.SetWidth(FromMM(TRK)); t.SetLayer(LAY[LNAME[l]]); t.SetNet(ni); t.SetLocked(True); board.Add(t); n_items += 1
    for v in vias:
        if any(k[1] in ('via', 'gvia') and k[0] == net and abs(k[2] - v[0]) < 0.1 and abs(k[3] - v[1]) < 0.1 for k in item_fix if k[1] in ('via', 'gvia')): continue
        vv = pcbnew.PCB_VIA(board); vv.SetPosition(VECTOR2I(FromMM(v[0]), FromMM(v[1]))); vv.SetViaType(pcbnew.VIATYPE_THROUGH)
        vv.SetWidth(FromMM(VIA_D)); vv.SetDrill(FromMM(VIA_H)); vv.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); vv.SetNet(ni); vv.SetLocked(True); board.Add(vv); n_items += 1
for t in DEAD: board.Remove(t)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
for z in board.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, board)
print('items written %d, dead fragments removed %d -> %s' % (n_items, len(DEAD), OUT))
