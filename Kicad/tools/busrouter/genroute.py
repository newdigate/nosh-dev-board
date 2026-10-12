"""General router for the open connections left on the board (run with KiCad's bundled python3; uses libastar.dylib).
usage: genroute.py in.kicad_pcb out.kicad_pcb NETS|all|power|signal track_mm [rounds]
Every existing pad, track and via is fixed: hard for other nets, a source/target for its own net. For each net the
existing copper is grouped into connected islands (vias inside a filled plane zone of the net count as joined
through the plane); the router joins the islands, or drops a 0.45/0.3 via into the net's plane. New copper is
negotiated (PathFinder, as busroute.py). Tracks on F.Cu, SIG and B.Cu only. Through-hole pads keep 0.2 mm,
keep-out areas and the board edge are respected.
"""
import sys, os, math, re, time, array, collections, ctypes, random
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT, SEL, TRK = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
ROUNDS = int(sys.argv[5]) if len(sys.argv) > 5 else 60
BASE = sys.argv[6] if len(sys.argv) > 6 else None          # copper absent from this board is negotiable (e.g. an autorouter's)
def _key(t):
    if t.Type() == pcbnew.PCB_VIA_T: return ('v', t.GetNetname(), round(ToMM(t.GetPosition().x), 3), round(ToMM(t.GetPosition().y), 3))
    a = (round(ToMM(t.GetStart().x), 3), round(ToMM(t.GetStart().y), 3)); c = (round(ToMM(t.GetEnd().x), 3), round(ToMM(t.GetEnd().y), 3))
    return ('t', t.GetNetname(), t.GetLayer(), min(a, c), max(a, c))
BASE_KEYS = {_key(t) for t in pcbnew.LoadBoard(BASE).GetTracks()} if BASE else None
board = pcbnew.LoadBoard(IN)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
LAY = {'F': pcbnew.F_Cu, 'S': board.GetLayerID('SIG'), 'B': pcbnew.B_Cu}; LIDX = {'F': 0, 'S': 1, 'B': 2}; LNAME = 'FSB'
LAYER_OF = {v: LIDX[k] for k, v in LAY.items()}
CLR, FAN_CLR, HOLE_CLR, PTH_CLR = 0.127, 0.10, 0.20, 0.20
VIA_D, VIA_H = 0.45, 0.30
G = 0.05; SAFE = 0.003
bb = board.GetBoardEdgesBoundingBox(); X0, Y0, X1, Y1 = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
X0 = math.floor(X0 / G) * G; Y0 = math.floor(Y0 / G) * G
NX, NY = int(round((X1 - X0) / G)) + 1, int(round((Y1 - Y0) / G)) + 1; N = NX * NY
def gx(x): return int(round((x - X0) / G))
def gy(y): return int(round((y - Y0) / G))
def wx(i): return X0 + i * G
def wy(j): return Y0 + j * G
def idx(i, j): return j * NX + i
def _lo(v, o): return int(math.ceil((v - o) / G - 1e-9))
def _hi(v, o): return int(math.floor((v - o) / G + 1e-9))
def disc_cells(x, y, r):
    r = r + SAFE if r > 0.2 else r; out = []
    for j in range(max(0, _lo(y - r, Y0)), min(NY - 1, _hi(y + r, Y0)) + 1):
        dy = wy(j) - y
        if dy * dy > r * r: continue
        h = math.sqrt(r * r - dy * dy); a, b_ = _lo(x - h, X0), _hi(x + h, X0)
        if b_ >= a: out.append((j, max(0, a), min(NX - 1, b_)))
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
    """cells within `extra` of a SHAPE_POLY_SET outline (bounding-box rows, tested per cell centre)"""
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
TRK_R = TRK / 2 + CLR
static = [bytearray(N) for _ in range(3)]; via_static = bytearray(N)
cnt = [array.array('H', bytes(2 * N)) for _ in range(3)]; fixc = [array.array('H', bytes(2 * N)) for _ in range(3)]
hist = [array.array('H', bytes(2 * N)) for _ in range(3)]
via_soft = array.array('H', bytes(2 * N)); via_fix = array.array('H', bytes(2 * N))
item_fix = {}; via_own = {}; core = collections.defaultdict(list); item_obj = {}; SOFT = collections.defaultdict(lambda: ([], [])); SOFT_OBJ = []     # key -> [(layer, spans)], key -> via spans, net -> [(key, layer, spans)]
t0 = time.time()
# ---- board edge and keep-outs
edge = 0.3 + TRK / 2
for l in range(3):
    paint(static[l], rect_cells(X0 - 1, Y0 - 1, X1 + 1, Y0 + edge)); paint(static[l], rect_cells(X0 - 1, Y1 - edge, X1 + 1, Y1 + 1))
    paint(static[l], rect_cells(X0 - 1, Y0 - 1, X0 + edge, Y1 + 1)); paint(static[l], rect_cells(X1 - edge, Y0 - 1, X1 + 1, Y1 + 1))
paint(via_static, rect_cells(X0 - 1, Y0 - 1, X1 + 1, Y0 + 0.6)); paint(via_static, rect_cells(X0 - 1, Y1 - 0.6, X1 + 1, Y1 + 1))
paint(via_static, rect_cells(X0 - 1, Y0 - 1, X0 + 0.6, Y1 + 1)); paint(via_static, rect_cells(X1 - 0.6, Y0 - 1, X1 + 1, Y1 + 1))
for z in list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]:
    if not z.GetIsRuleArea(): continue
    o = z.Outline()
    if z.GetDoNotAllowTracks():
        for L, l in LAY.items():
            if z.IsOnLayer(l): paint(static[LIDX[L]], poly_cells(o, TRK / 2 + CLR))
    if z.GetDoNotAllowVias(): paint(via_static, poly_cells(o, VIA_D / 2 + CLR))
# ---- copper: everything is fixed (hard for other nets, own-exempt)
nets_by_name = board.GetNetInfo().NetsByName()
def pad_layers(p): return [l for L, l in LAY.items() if p.IsOnLayer(l)]
for f in board.GetFootprints():
    for p in f.Pads():
        net = p.GetNetname(); x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        pth = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH); hole = ToMM(p.GetDrillSize().x) if p.GetDrillSize().x else 0.0
        poly = p.GetEffectivePolygon(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu) if hasattr(p, 'GetEffectivePolygon') else None
        bx = p.GetBoundingBox(); px0, py0, px1, py1 = ToMM(bx.GetLeft()), ToMM(bx.GetTop()), ToMM(bx.GetRight()), ToMM(bx.GetBottom())
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
for t in board.GetTracks():
    net = t.GetNetname()
    if BASE_KEYS is not None and _key(t) not in BASE_KEYS:              # soft: loaded below as the net's current route
        SOFT_OBJ.append(t)
        if t.Type() == pcbnew.PCB_VIA_T: SOFT[net][1].append((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y), ToMM(t.GetWidth(pcbnew.F_Cu)), ToMM(t.GetDrill())))
        elif t.GetLayer() in LAYER_OF: SOFT[net][0].append((LAYER_OF[t.GetLayer()], ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y), ToMM(t.GetWidth())))
        continue
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y); vd, vh = ToMM(t.GetWidth(pcbnew.F_Cu)), ToMM(t.GetDrill())
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
        sp = capsule_cells(x0, y0, x1, y1, w / 2 + TRK_R); key = (net, 'trk', x0, y0, x1, y1); item_fix[key] = [(l, sp)]; bump(fixc[l], sp, 1); item_obj[key] = t
        vs = capsule_cells(x0, y0, x1, y1, w / 2 + CLR + VIA_D / 2); bump(via_fix, vs, 1); via_own[key] = vs
        core[net].append((key, [(l, capsule_cells(x0, y0, x1, y1, max(0.0, w / 2 - 0.01)))], ((x0 + x1) / 2, (y0 + y1) / 2), False))
print('grids built: %d x %d, %.1fs' % (NX, NY, time.time() - t0), flush=True)
# ---- planes: filled zones on GND1 / PWR / GND2 per net
PLANE_L = [board.GetLayerID(n) for n in ('GND1', 'PWR', 'GND2')]
planes = collections.defaultdict(list)
for z in board.Zones():
    if z.GetIsRuleArea() or not z.GetNetname(): continue
    for l in PLANE_L:
        if z.IsOnLayer(l): planes[z.GetNetname()].append(z.GetFilledPolysList(l))
def in_plane(net, x, y):
    return any(ps.Contains(VECTOR2I(FromMM(x), FromMM(y))) for ps in planes.get(net, ()))
# ---- islands per net
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
# ---- C core
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
OUTCAP = 600000
via_cells = {}; routed_cells = {}; added = collections.defaultdict(lambda: ([], []))
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
OWN_CACHE = {}
def route(net, sources, targets):
    srcs = array.array('i'); [srcs.extend(c) for c in sources]
    tg = array.array('i'); [tg.extend(c) for c in targets]
    own = own_spans(net)
    hx = sum(wx(i) for _, i, _ in targets) / len(targets); hy = sum(wy(j) for _, _, j in targets) / len(targets)
    out = array.array('i', bytes(4 * 3 * OUTCAP)); n = c_int(0); exp = c_int(0)
    as32 = lambda a: ctypes.cast(a.buffer_info()[0], P32)
    lib.route(byref(GR), byref(W), len(sources), as32(srcs), len(targets), as32(tg), len(own) // 5, as32(own) if len(own) else None,
              hx, hy, 6000000, as32(out), OUTCAP, byref(n), byref(exp))
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
GREEDY = os.environ.get('GREEDY') == '1'          # every new link becomes fixed at once: one pass, no conflicts possible
def commit(net, segs, vias):
    """segs: (l, x0, y0, x1, y1[, w]); vias: (x, y[, d, h])"""
    if GREEDY:
        for sg in segs:
            l, x0, y0, x1, y1 = sg[:5]; w = sg[5] if len(sg) > 5 else TRK
            k = (net, 'gtrk', x0, y0, x1, y1); sp = capsule_cells(x0, y0, x1, y1, w / 2 + TRK_R); item_fix[k] = [(l, sp)]; bump(fixc[l], sp, 1)
            vs = capsule_cells(x0, y0, x1, y1, w / 2 + CLR + VIA_D / 2); bump(via_fix, vs, 1); via_own[k] = vs
            core[net].append((k, [(l, capsule_cells(x0, y0, x1, y1, max(0.0, w / 2 - 0.01)))], ((x0 + x1) / 2, (y0 + y1) / 2), False))
        for v in vias:
            x, y = v[:2]; d, h = (v[2], v[3]) if len(v) > 2 else (VIA_D, VIA_H)
            k = (net, 'gvia', x, y); sp = disc_cells(x, y, max(d / 2 + CLR + TRK / 2, h / 2 + HOLE_CLR + TRK / 2)); item_fix[k] = [(l, sp) for l in range(3)]
            for l in range(3): bump(fixc[l], sp, 1)
            vs = disc_cells(x, y, max(d / 2 + CLR + VIA_D / 2, h / 2 + 0.254 + VIA_H / 2) + 0.02); bump(via_fix, vs, 1); via_own[k] = vs
            paint(via_static, disc_cells(x, y, h / 2 + 0.254 + VIA_H / 2))
            core[net].append((k, [(l, disc_cells(x, y, 0.2)) for l in range(3)], (x, y), True))
        added[net][0].extend(segs); added[net][1].extend(vias); return
    for sg in segs:
        l, x0, y0, x1, y1 = sg[:5]; w = sg[5] if len(sg) > 5 else TRK
        sp = capsule_cells(x0, y0, x1, y1, w / 2 + TRK_R); bump(cnt[l], sp, 1)
        vs = capsule_cells(x0, y0, x1, y1, w / 2 + CLR + VIA_D / 2); bump(via_soft, vs, 1)
        k = (net, 'rtrk', x0, y0, x1, y1); routed_cells[k] = [(l, sp)]; via_cells[k] = vs
    for v in vias:
        x, y = v[:2]; d, h = (v[2], v[3]) if len(v) > 2 else (VIA_D, VIA_H)
        sp = disc_cells(x, y, max(d / 2 + CLR + TRK / 2, h / 2 + HOLE_CLR + TRK / 2))
        for l in range(3): bump(cnt[l], sp, 1)
        vs = disc_cells(x, y, max(d / 2 + CLR + VIA_D / 2, h / 2 + 0.254 + VIA_H / 2) + 0.02); bump(via_soft, vs, 1)
        k = (net, 'rvia', x, y); routed_cells[k] = [(l, sp) for l in range(3)]; via_cells[k] = vs
    added[net][0].extend(segs); added[net][1].extend(vias)
def uncommit(net):
    for k in [k for k in routed_cells if k[0] == net]:
        for l, sp in routed_cells[k]: bump(cnt[l], sp, -1)
        bump(via_soft, via_cells[k], -1); del routed_cells[k]; del via_cells[k]
    added.pop(net, None)
def plane_via_targets(net, cells, radius=4.0):
    """cells where a via into the net's plane may go, near an island"""
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
PLANE_VIA_TARGET = set()
def route_net(net):
    """join the net's islands; returns (segs, vias, failed_islands) - partial success is kept"""
    comps = islands(net)
    if len(comps) <= 1: return [], [], []
    has_plane = net in planes
    base = [c for c in comps if c['plane']] if has_plane else []
    if not base: base = [max(comps, key=lambda c: len(c['cells']))]
    rest = [c for c in comps if c not in base and c['has_pad']]
    src = set().union(*[c['cells'] for c in base]); segs_all = []; vias_all = []; failed = []
    for c in sorted(rest, key=lambda c: len(c['cells'])):
        pv = plane_via_targets(net, c['cells']) if has_plane else set()
        pv = {c_ for c_ in pv if all(math.hypot(wx(c_[1]) - vx, wy(c_[2]) - vy) > 0.6 for vx, vy in vias_all)}   # not on a via this call just placed
        tg = pv if pv else src
        path, exp = route(net, list(c['cells']), list(tg))
        if path is None:
            cc = next(iter(c['cells'])); failed.append((wx(cc[1]), wy(cc[2]))); continue
        segs, vias = path_to_geometry(path); end = path[-1]
        if pv and end in pv and not any(math.hypot(vx - wx(end[1]), vy - wy(end[2])) < 0.1 for vx, vy in vias): vias.append((wx(end[1]), wy(end[2])))           # drop into the plane (unless the path already ended with a via there)
        segs_all += segs; vias_all += vias
        if not has_plane or not pv:
            src |= c['cells']
            for l, x0, y0, x1, y1 in segs: src.update((l, gx(x0 + (x1 - x0) * k / 20), gy(y0 + (y1 - y0) * k / 20)) for k in range(21))
    return segs_all, vias_all, failed
def net_conflicts(net):
    hits = []
    for k, cells in routed_cells.items():
        if k[0] != net: continue
        for l, sp in cells: bump(cnt[l], sp, -1)
    for sg in added.get(net, ([], []))[0]:
        if len(sg) > 5: continue                     # negotiable copper from the input already passed DRC; only new, on-grid segments are checked
        l, x0, y0, x1, y1 = sg[:5]
        L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / G))
        for s in range(n + 1):
            i, j = gx(x0 + (x1 - x0) * s / n), gy(y0 + (y1 - y0) * s / n); k = j * NX + i
            if cnt[l][k]: hits.append((l, k))
    for k, cells in routed_cells.items():
        if k[0] != net: continue
        for l, sp in cells: bump(cnt[l], sp, 1)
    return hits
# ---- which nets
POWER = re.compile(r'^(GND$|\+|VDD|NVCC|DCDC|SDRAM_3V3|WL_3V3|VSD|VLDO|USB\d_VBUS|USB\d_CON_VBUS|DC_IN|AUD_VDDA|CODEC_1V8|LCD_5V|LCD_IOVCC|CTP_3V3|ADC_VREFH)')
cands = [n for n in core if n and not n.startswith('unconnected')]
if SEL == 'power': nets = [n for n in cands if POWER.match(n)]
elif SEL == 'signal': nets = [n for n in cands if not POWER.match(n)]
elif SEL == 'all': nets = cands
else: nets = [n for n in SEL.split(',') if n in core]
# fragments of the selected nets that reach no pad and no plane are dead copper: remove them (they would block and
# show up as unconnected); the board objects are removed just before saving
for _net, (_segs, _vias) in SOFT.items(): commit(_net, _segs, _vias)
print('negotiable copper loaded: %d nets, %d segments, %d vias' % (len(SOFT), sum(len(a) for a, b_ in SOFT.values()), sum(len(b_) for a, b_ in SOFT.values())), flush=True)
DEAD = []
for n in nets:
    for c in islands(n):
        if c['has_pad'] or c['plane']: continue
        for key in c['members']:
            if key not in item_obj: continue
            for l, sp in item_fix.pop(key, []): bump(fixc[l], sp, -1)
            if key in via_own: bump(via_fix, via_own.pop(key), -1)
            DEAD.append(item_obj[key])
        core[n] = [it for it in core[n] if it[0] not in set(c['members'])]
print('dead fragments removed: %d items' % len(DEAD), flush=True)
open_nets = [n for n in nets if sum(1 for c in islands(n) if c['has_pad']) > 1 or (n in planes and any(c['has_pad'] and not c['plane'] for c in islands(n)))]
print('nets selected %d, with open connections %d' % (len(nets), len(open_nets)), flush=True)
todo = set(open_nets); best = None; conf = {}; fails = {}; FAILS_PREV = None; FULL = set(); RIP_R = 1.5
def nets_near(pts, r=RIP_R):
    near = set()
    for x, y in pts:
        j0, j1, i0, i1 = gy(y - r), gy(y + r), gx(x - r), gx(x + r)
        for k, cells in routed_cells.items():
            if k[0] in near: continue
            for l, sp in cells:
                if any(j0 <= j <= j1 and a <= i1 and b_ >= i0 for j, a, b_ in sp): near.add(k[0]); break
    return near
for rnd in range(1, ROUNDS + 1):
    t1 = time.time(); fails = {}; failpts = []
    order = sorted(todo); random.Random(rnd + int(os.environ.get('SEED', '0'))).shuffle(order)
    if os.environ.get('U1_FIRST') == '1':          # nets with an MCU ball first: their escapes are the scarce resource
        u1n = {p_.GetNetname() for f_ in board.GetFootprints() if f_.GetReference() == 'U1' for p_ in f_.Pads()} if rnd == 1 and 'U1N' not in globals() else globals().get('U1N')
        globals()['U1N'] = u1n; order.sort(key=lambda n: n not in u1n)
    for net in order:
        if net in FULL: uncommit(net)                       # full rip-up; otherwise only the missing links are added
        segs, vias, failed = route_net(net)
        commit(net, segs, vias)
        if failed: fails[net] = 'islands not reached: ' + ' '.join('(%.1f, %.1f)' % p_ for p_ in failed); failpts += failed
    conf = {}
    for net in list(added):
        h = net_conflicts(net)
        if h:
            conf[net] = len(h)
            for l, k in h: hist[l][k] = min(hist[l][k] + 1, 60000)
    print('round %2d: pres %.1f, worked on %d (full rip-up %d), failed %d, conflicting %d (%d cells) %.1fs' % (rnd, GR.pres, len(todo), len(FULL & todo), len(fails), len(conf), sum(conf.values()), time.time() - t1), flush=True)
    score = len(conf) * 1000 + 3000 * len(fails)
    if best is None or score < best[0]: best = (score, rnd, {n: (list(a), list(b_)) for n, (a, b_) in added.items()}, dict(fails), dict(conf))
    if not conf and not fails: break
    GR.pres = min(GR.pres * 1.6, 2000.0)
    near = nets_near(failpts) - set(fails)
    todo = set(conf) | set(fails) | near; FULL = set(conf) | set(fails) | near
    if near: print('   ripping up %d nets round the boxed-in islands' % len(near), flush=True)
score, rnd, keep, fails, conf = best
print('keeping round %d: %d nets failed, %d conflicting' % (rnd, len(fails), len(conf)))
for n, w in sorted(fails.items()): print('   failed %-16s %s' % (n, w))
# write every net's final copper; a net still conflicting keeps its original (negotiable) copper if it had any
n_items = 0
for t in SOFT_OBJ: board.Remove(t)
for net in set(keep) | set(SOFT):
    segs, vias = (SOFT[net] if net in conf else keep.get(net, ([], [])))
    if net in conf and net not in SOFT: continue
    ni = nets_by_name[net]
    for sg in segs:
        l, x0, y0, x1, y1 = sg[:5]; w = sg[5] if len(sg) > 5 else TRK
        if math.hypot(x1 - x0, y1 - y0) < 1e-6: continue
        t = pcbnew.PCB_TRACK(board); t.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); t.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
        t.SetWidth(FromMM(w)); t.SetLayer(LAY[LNAME[l]]); t.SetNet(ni); t.SetLocked(True); board.Add(t); n_items += 1
    for v in vias:
        x, y = v[:2]; d, h = (v[2], v[3]) if len(v) > 2 else (VIA_D, VIA_H)
        vv = pcbnew.PCB_VIA(board); vv.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); vv.SetViaType(pcbnew.VIATYPE_THROUGH)
        vv.SetWidth(FromMM(d)); vv.SetDrill(FromMM(h)); vv.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); vv.SetNet(ni); vv.SetLocked(True); board.Add(vv); n_items += 1
for t in DEAD: board.Remove(t)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
for z in board.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, board)
print('items written %d (still conflicting, kept as before: %s) -> %s' % (n_items, sorted(conf), OUT))
