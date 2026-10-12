"""SDRAM bus router, EVKB-style stack (run with KiCad's bundled python3; C search core in libastar.dylib, built from astar.c).
Reads a board on which sdram_prebuild.py has built the fixed chip-side geometry, connects each SDRAM net's MCU side
to its prebuilt target with negotiated (PathFinder-style) grid A*, writes OUT.  usage: busroute.py in.kicad_pcb out.kicad_pcb [nets|all] [max_rounds] [threads] [seed]
Run several seeds side by side (busroute_multi.sh) and keep the best: the negotiation itself stays sequential.
Per-zone layer rules: FIELD (inside the BGA, x >= 64.6) any layer; APPROACH (51.6..64.6) and CHIP (x < 51.6) per class.
"""
import sys, math, heapq, re, time, collections, array
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

IN, OUT = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(IN)
LAY = {'F': pcbnew.F_Cu, 'S': board.GetLayerID('SIG'), 'B': pcbnew.B_Cu}; LIDX = {'F': 0, 'S': 1, 'B': 2}; LNAME = 'FSB'
TRK, CLR, VIA_D, VIA_H = 0.10, 0.127, 0.45, 0.20
HOLE_CLR, FAN_CLR = 0.20, 0.10
G = 0.05
X0, Y0, X1, Y1 = 26.0, 14.0, 72.6, 60.0
NX, NY = int(round((X1 - X0) / G)) + 1, int(round((Y1 - Y0) / G)) + 1
def gx(x): return int(round((x - X0) / G))
def gy(y): return int(round((y - Y0) / G))
def wx(i): return X0 + i * G
def wy(j): return Y0 + j * G
def idx(i, j): return j * NX + i

# ------------------------------------------------------------------ classes and zone rules
CLASS = {}
for n in [f'SEMC_A{i}' for i in range(13)] + ['SEMC_BA0', 'SEMC_BA1', 'SEMC_CS0', 'SEMC_RAS', 'SEMC_CAS', 'SEMC_WE', 'SEMC_CKE']: CLASS[n] = 'addr'
for n in [f'SEMC_D{i}' for i in range(0, 8)] + ['SEMC_DM0'] + [f'SEMC_D{i}' for i in range(24, 32)] + ['SEMC_DM3']: CLASS[n] = 'dout'
for n in [f'SEMC_D{i}' for i in range(8, 24)] + ['SEMC_DM1', 'SEMC_DM2']: CLASS[n] = 'dch'
ADDR_A = {'SEMC_WE', 'SEMC_CAS', 'SEMC_RAS', 'SEMC_CS0', 'SEMC_BA0', 'SEMC_BA1', 'SEMC_A10', 'SEMC_A0', 'SEMC_A1', 'SEMC_A2', 'SEMC_A3'}
CLASS['SEMC_DQS'] = 'dqs'                       # ball J2 to C145 (read-strobe loopback load), short
CLASS['SEMC_CLK'] = 'clk'; CLASS['U9_CLK'] = 'clkb'; CLASS['U10_CLK'] = 'clkb'
FIELD_X, CHIP_X = 64.6, 51.6
RULES = {   # class: (approach factors F,S,B), (chip-zone factors F,S,B); None = layer not allowed there
    'addr': ((2.0, 1.0, None), (None, 1.0, None)),
    'dout': ((2.0, None, 1.0), (None, None, 1.0)),
    'dch':  ((1.0, 2.5, 2.5), (1.0, None, None)),
    'clk':  ((1.0, 1.5, None), (1.0, 1.5, None)),
    'clkb': ((1.0, 1.0, None), (1.0, 1.0, None)),
    'dqs':  ((1.0, 2.0, 1.0), (None, None, None)),
}
FIELD_FAC = (1.0, 1.0, 1.0)
VIA_COST = {'field': 0.6, 'approach': 0.6, 'chip': 4.0}
TURN = 0.03
ESC_X0, ESC_X1 = 64.4, 65.3
def zone_of(i): x = wx(i); return 'field' if x >= FIELD_X else ('approach' if x >= CHIP_X else 'chip')

# ------------------------------------------------------------------ geometry -> grids
static = [bytearray(NX * NY) for _ in range(3)]      # non-SDRAM copper, per routing layer (with track clearance)
cnt = [array.array('H', bytes(2 * NX * NY)) for _ in range(3)]   # SDRAM-net items, counted so a net can unblock its own
via_static = bytearray(NX * NY)
via_fix = array.array('H', bytes(2 * NX * NY)); via_own = {}
fixc = [array.array('H', bytes(2 * NX * NY)) for _ in range(3)]; item_fix = {}      # fixed SDRAM-net copper: hard for other nets      # SDRAM-net board items: via exclusion, counted per item                     # cells where a via may NOT be placed (any layer reason)
routed = [bytearray(NX * NY) for _ in range(3)]
item_cells = {}                                     # (net, key) -> list of (layer, cells) for unblocking

SAFE = 0.003                                   # every keep-out radius / rectangle grows by this; cells count as blocked only if their centre is inside
def _lo(v, o): return int(math.ceil((v - o) / G - 1e-9))
def _hi(v, o): return int(math.floor((v - o) / G + 1e-9))
def disc_cells(x, y, r):
    r = r + SAFE if r > 0.2 else r; out = []
    for j in range(max(0, _lo(y - r, Y0)), min(NY - 1, _hi(y + r, Y0)) + 1):
        dy = wy(j) - y
        if dy * dy > r * r: continue
        half = math.sqrt(r * r - dy * dy); a_, b_ = _lo(x - half, X0), _hi(x + half, X0)
        if b_ >= a_: out.append((j, max(0, a_), min(NX - 1, b_)))
    return out
def rect_cells(x0, y0, x1, y1):
    i0, i1, j0, j1 = max(0, _lo(x0, X0)), min(NX - 1, _hi(x1, X0)), max(0, _lo(y0, Y0)), min(NY - 1, _hi(y1, Y0))
    return [(j, i0, i1) for j in range(j0, j1 + 1)] if i1 >= i0 else []
def capsule_cells(x0, y0, x1, y1, r):
    # sample along the segment
    L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / (G * 0.7))); seen = {}
    for k in range(n + 1):
        t = k / n; x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        for j, a, b_ in disc_cells(x, y, r):
            if j in seen: seen[j] = (min(seen[j][0], a), max(seen[j][1], b_))   # conservative fill between
            else: seen[j] = (a, b_)
    return [(j, a, b_) for j, (a, b_) in seen.items()]
def seg_cells(x0, y0, x1, y1):
    i0, j0, i1, j1 = gx(x0), gy(y0), gx(x1), gy(y1); n = max(abs(i1 - i0), abs(j1 - j0))
    if n == 0: return [(i0, j0)]
    return [(i0 + round(k * (i1 - i0) / n), j0 + round(k * (j1 - j0) / n)) for k in range(n + 1)]
def paint(grid, spans, val=1):
    for j, a, b_ in spans:
        base = j * NX
        for i in range(a, b_ + 1): grid[base + i] = val
def bump(grid, spans, d):
    for j, a, b_ in spans:
        base = j * NX
        for i in range(a, b_ + 1): grid[base + i] += d

def in_region(x, y, m=1.0): return X0 - m <= x <= X1 + m and Y0 - m <= y <= Y1 + m
SD = re.compile(r'^(SEMC_|U9_CLK$|U10_CLK$)')
TRK_R = TRK / 2 + CLR                               # clearance radius added to copper for a 0.1 track centreline
VIA_R = VIA_D / 2 + CLR                             # for via placement next to pads
VIA_TR = VIA_D / 2 + FAN_CLR                        # via next to a track (hole < 0.3 rule)
layers_of_pad = lambda p: ['F', 'S', 'B'] if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else (['B'] if p.GetParentFootprint().GetLayer() == pcbnew.B_Cu else ['F'])

def pad_spans(p, extra):
    x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y); sx, sy = ToMM(p.GetSize().x), ToMM(p.GetSize().y)
    rot = p.GetOrientationDegrees() % 180
    if abs(rot - 90) < 1: sx, sy = sy, sx
    if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE or (sx == sy and p.GetShape() != pcbnew.PAD_SHAPE_RECT):
        return disc_cells(x, y, max(sx, sy) / 2 + extra)
    if rot % 90 > 1: sx = sy = max(sx, sy)           # rotated oddly: bounding square
    return rect_cells(x - sx / 2 - extra, y - sy / 2 - extra, x + sx / 2 + extra, y + sy / 2 + extra)

t0 = time.time(); n_items = 0
for f in board.GetFootprints():
    for p in f.Pads():
        x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        if not in_region(x, y): continue
        net = p.GetNetname(); hole = ToMM(p.GetDrillSize().x) if p.GetDrillSize().x else 0.0
        spans = pad_spans(p, TRK_R)
        vspans = pad_spans(p, VIA_R)
        if hole: vspans += disc_cells(x, y, hole / 2 + 0.45 + VIA_H / 2)   # via hole to PTH hole 0.45
        if SD.match(net):
            key = (net, 'pad', f.GetReference(), p.GetNumber()); cells = []
            for L in layers_of_pad(p): bump(cnt[LIDX[L]], spans, 1); bump(fixc[LIDX[L]], spans, 1); cells.append((LIDX[L], spans))
            item_cells[key] = cells; item_fix[key] = cells
            paint(via_static, vspans)                # even own-net pads block vias (no via-in-pad)
        else:
            for L in layers_of_pad(p): paint(static[LIDX[L]], spans)
            if hole:                                 # track to PTH hole: 0.28 outer / 0.3 inner
                for L in 'FSB': paint(static[LIDX[L]], disc_cells(x, y, hole / 2 + 0.3 + TRK / 2))
            paint(via_static, vspans)
        n_items += 1
for t in board.GetTracks():
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        if not in_region(x, y): continue
        vd, vh = ToMM(t.GetWidth(pcbnew.F_Cu)), ToMM(t.GetDrill())
        pad_r = vd / 2 + (FAN_CLR if vh < 0.3 else CLR) + TRK / 2; hole_r = vh / 2 + HOLE_CLR + TRK / 2
        spans = disc_cells(x, y, max(pad_r, hole_r))
        vspans = disc_cells(x, y, max(vd / 2 + CLR + VIA_D / 2, vh / 2 + 0.2 + VIA_H / 2))
        if SD.match(net):
            key = (net, 'via', x, y); item_cells[key] = [(l, spans) for l in range(3)]; item_fix[key] = item_cells[key]
            for l in range(3): bump(cnt[l], spans, 1); bump(fixc[l], spans, 1)
            paint(via_static, disc_cells(x, y, vh / 2 + 0.254 + VIA_H / 2))   # same-net hole spacing still applies
            bump(via_fix, vspans, 1); via_own[key] = vspans
        else:
            for l in range(3): paint(static[l], spans)
            paint(via_static, vspans)
    else:
        x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
        if not (in_region(x0, y0) or in_region(x1, y1)): continue
        lid = t.GetLayer()
        L = next((k for k, v in LAY.items() if v == lid), None)
        if L is None: continue
        w = ToMM(t.GetWidth()); spans = capsule_cells(x0, y0, x1, y1, w / 2 + TRK_R); vspans = capsule_cells(x0, y0, x1, y1, w / 2 + VIA_TR)
        if SD.match(net):
            key = (net, 'trk', x0, y0, x1, y1); item_cells[key] = [(LIDX[L], spans)]; bump(cnt[LIDX[L]], spans, 1); bump(fixc[LIDX[L]], spans, 1); item_fix[key] = item_cells[key]
            bump(via_fix, vspans, 1); via_own[key] = vspans
        else:
            paint(static[LIDX[L]], spans); paint(via_static, vspans)
    n_items += 1
# board edge / region edge: keep tracks 0.5 mm inside the region (the region is interior anyway)
print('grids built (via_fix items %d):' % len(via_own), end=' '); print('grids built: %d items, %.1fs, region %dx%d' % (n_items, time.time() - t0, NX, NY), flush=True)
for l in range(3):
    if l == 0:     # top: two extra exit lanes just north of row A, west of x 68.6 (the MIPI pairs leave at x 71+)
        paint(static[l], rect_cells(64.5, Y0, X1, 34.15)); paint(static[l], rect_cells(68.6, 34.15, X1, 34.9))
    else: paint(static[l], rect_cells(64.5, Y0, X1, 34.9))
    if l == 2:     # bottom: leave a window south of the ball field so SEMC_DQS can reach C145 (10 pF load at x 67.5, y 49.75)
        paint(static[l], rect_cells(68.2, 49.3, X1, Y1)); paint(static[l], rect_cells(64.5, 50.6, 68.2, Y1))
    else: paint(static[l], rect_cells(64.5, 49.3, X1, Y1))
paint(via_static, rect_cells(64.4, 29.0, 65.75, 55.0))          # the escape band west of BGA column 1: nothing lands in front of the balls
for _r in ((65.6, 35.6, 66.4, 48.4), (77.6, 35.6, 78.4, 48.4), (65.6, 35.6, 78.4, 36.4), (65.6, 47.6, 78.4, 48.4)):
    paint(via_static, rect_cells(*_r))                             # the outer ring of lattice cells: the ring-1 balls' top-layer exits, no vias there
ZONE = [zone_of(i) for i in range(NX)]
FACS = {}
for cls, (appr, chip) in RULES.items():
    FACS[cls] = [[(FIELD_FAC[l] if ZONE[i] == 'field' else (appr[l] if ZONE[i] == 'approach' else chip[l])) for i in range(NX)] for l in range(3)]

# ------------------------------------------------------------------ net sources / targets
nets_by_name = board.GetNetInfo().NetsByName()
def net_items(net):
    """pads and existing copper of the net inside the region -> list of (kind, layer, x, y, extra)"""
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == net and in_region(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)):
                out.append(('pad', layers_of_pad(p), p))
    for t in board.GetTracks():
        if t.GetNetname() == net: out.append(('via' if t.Type() == pcbnew.PCB_VIA_T else 'trk', None, t))
    return out
def cluster_cells(net, exclude_pads=()):
    """cells (layer, i, j) on the net's connected copper that is already present: pads not in exclude, vias, tracks"""
    cells = set()
    for kind, Ls, obj in net_items(net):
        if kind == 'pad':
            if (obj.GetParentFootprint().GetReference(), obj.GetNumber()) in exclude_pads: continue
            x, y = ToMM(obj.GetPosition().x), ToMM(obj.GetPosition().y)
            for L in Ls:
                for j, a, b_ in pad_spans(obj, -0.05):
                    for i in range(a, b_ + 1): cells.add((LIDX[L], i, j))
        elif kind == 'via':
            x, y = ToMM(obj.GetPosition().x), ToMM(obj.GetPosition().y)
            for l in range(3):
                for j, a, b_ in disc_cells(x, y, 0.12):
                    for i in range(a, b_ + 1): cells.add((l, i, j))
        else:
            L = next((k for k, v in LAY.items() if v == obj.GetLayer()), None)
            if L is None: continue
            for i, j in seg_cells(ToMM(obj.GetStart().x), ToMM(obj.GetStart().y), ToMM(obj.GetEnd().x), ToMM(obj.GetEnd().y)): cells.add((LIDX[L], i, j))
    segs, vias = added.get(net, ([], []))
    for l, x0, y0, x1, y1 in segs:
        for i, j in seg_cells(x0, y0, x1, y1): cells.add((l, i, j))
    for x, y, la, lb in vias:
        for l in range(3):
            for j, a, b_ in disc_cells(x, y, 0.12):
                for i in range(a, b_ + 1): cells.add((l, i, j))
    return cells
def pad_cells(ref, num):
    f = next(f for f in board.GetFootprints() if f.GetReference() == ref); p = next(p for p in f.Pads() if p.GetNumber() == num)
    cells = set()
    for L in layers_of_pad(p):
        for j, a, b_ in pad_spans(p, -0.08):
            for i in range(a, b_ + 1): cells.add((LIDX[L], i, j))
    return cells


# ------------------------------------------------------------------ C core (ctypes releases the GIL: nets of a round are searched in parallel)
import ctypes, os, concurrent.futures, queue, json
from ctypes import c_int, c_float, c_void_p, POINTER, byref
HERE = os.path.dirname(os.path.abspath(__file__))
lib = ctypes.CDLL(os.path.join(HERE, 'libastar.dylib'))
class GridS(ctypes.Structure):
    _fields_ = [('nx', c_int), ('ny', c_int), ('g', c_float), ('x0', c_float), ('y0', c_float),
                ('stat', c_void_p * 3), ('cnt', c_void_p * 3), ('hist', c_void_p * 3), ('fixc', c_void_p * 3), ('via_static', c_void_p), ('via_soft', c_void_p), ('via_fix', c_void_p),
                ('fac', c_void_p * 3), ('viacost', c_void_p), ('pres', c_float), ('histw', c_float), ('turn', c_float), ('esc_i0', c_int), ('esc_i1', c_int)]
class WorkS(ctypes.Structure):
    _fields_ = [('dist', c_void_p), ('prev', c_void_p), ('dir', c_void_p), ('own_cnt', c_void_p), ('own_vsoft', c_void_p), ('own_vfix', c_void_p), ('own_fix', c_void_p), ('tmask', c_void_p)]
P32 = POINTER(ctypes.c_int32)
lib.route.argtypes = [POINTER(GridS), POINTER(WorkS), c_int, P32, c_int, P32, c_int, P32, c_float, c_float, c_int, P32, c_int, POINTER(c_int), POINTER(c_int)]
lib.route.restype = c_int
N3 = 3 * NX * NY
_keep = []
def addr(buf):
    if isinstance(buf, (bytearray,)):
        c = (ctypes.c_char * len(buf)).from_buffer(buf); _keep.append(c); return ctypes.addressof(c)
    return buf.buffer_info()[0]
via_soft = array.array('H', bytes(2 * NX * NY)); via_cells = {}
hist = [array.array('H', bytes(2 * NX * NY)) for _ in range(3)]
PRES = [0.3]; HIST = 0.3; PRES_MAX = 2000.0
VIACOST = array.array('f', [VIA_COST[ZONE[i]] for i in range(NX)])
GRIDS = {}
for cls in RULES:
    g = GridS(); g.nx, g.ny, g.g, g.x0, g.y0 = NX, NY, G, X0, Y0
    for l in range(3):
        g.stat[l] = addr(static[l]); g.cnt[l] = addr(cnt[l]); g.hist[l] = addr(hist[l]); g.fixc[l] = addr(fixc[l])
        fa = array.array('f', [(-1.0 if v is None else v) for v in FACS[cls][l]]); _keep.append(fa); g.fac[l] = addr(fa)
    g.via_static = addr(via_static); g.via_soft = addr(via_soft); g.via_fix = addr(via_fix); g.viacost = addr(VIACOST)
    g.pres, g.histw, g.turn = PRES[0], HIST, TURN
    g.esc_i0, g.esc_i1 = int(math.ceil((ESC_X0 - X0) / G - 1e-9)), int(math.floor((ESC_X1 - X0) / G + 1e-9))
    GRIDS[cls] = g
NTHREADS = int(sys.argv[5]) if len(sys.argv) > 5 else 1        # 1 = sequential negotiation (converges); >1 = parallel rounds
import random
SEED = int(sys.argv[6]) if len(sys.argv) > 6 else 0; RNG = random.Random(SEED)
WORK = queue.Queue()
for _ in range(NTHREADS):
    bufs = [array.array('d', bytes(8 * N3)), array.array('i', bytes(4 * N3)), bytearray(N3), array.array('H', bytes(2 * N3)),
            array.array('H', bytes(2 * NX * NY)), array.array('H', bytes(2 * NX * NY)), array.array('H', bytes(2 * N3)), bytearray(N3)]
    w = WorkS(*[addr(b) for b in bufs]); _keep.append(bufs); WORK.put(w)
OUTCAP = 400000
def own_spans(own_keys):
    out = array.array('i')
    for key in own_keys:
        for l, spans in item_cells.get(key, []):
            for j, a, b_ in spans: out.extend((0, l, j, a, b_))
        for j, a, b_ in via_cells.get(key, []): out.extend((1, 0, j, a, b_))
        for j, a, b_ in via_own.get(key, []): out.extend((2, 0, j, a, b_))
        for l, spans in item_fix.get(key, []):
            for j, a, b_ in spans: out.extend((3, l, j, a, b_))
    return out
def route(net, sources, targets, cls, own_keys):
    srcs = array.array('i'); [srcs.extend(c) for c in sources]
    tg = array.array('i'); [tg.extend(c) for c in targets]
    own = own_spans(own_keys)
    hx = sum(wx(i) for _, i, _ in targets) / len(targets); hy = sum(wy(j) for _, _, j in targets) / len(targets)
    out = array.array('i', bytes(4 * 3 * OUTCAP)); n = c_int(0); exp = c_int(0)
    as32 = lambda a: ctypes.cast(a.buffer_info()[0], P32)
    w = WORK.get()
    try:
        lib.route(byref(GRIDS[cls]), byref(w), len(sources), as32(srcs), len(targets), as32(tg), len(own) // 5, as32(own) if len(own) else None,
                  hx, hy, 4000000, as32(out), OUTCAP, byref(n), byref(exp))
    finally: WORK.put(w)
    if n.value < 0: return None, exp.value
    return [(out[3 * p], out[3 * p + 1], out[3 * p + 2]) for p in range(n.value)], exp.value

def path_to_geometry(path):
    """-> segments [(layer, x0,y0,x1,y1)], vias [(x,y)]"""
    segs = []; vias = []; run = [path[0]]
    def flush(run):
        if len(run) < 2: return
        # compress collinear
        pts = [run[0]]
        for a, b_, c in zip(run, run[1:], run[2:]):
            if (b_[1] - a[1], b_[2] - a[2]) != (c[1] - b_[1], c[2] - b_[2]): pts.append(b_)
        pts.append(run[-1])
        for a, b_ in zip(pts, pts[1:]): segs.append((a[0], wx(a[1]), wy(a[2]), wx(b_[1]), wy(b_[2])))
    for a, b_ in zip(path, path[1:]):
        if a[0] != b_[0]:
            flush(run); vias.append((wx(a[1]), wy(a[2]), a[0], b_[0])); run = [b_]
        else: run.append(b_)
    flush(run); return segs, vias

added = collections.defaultdict(lambda: ([], []))      # net -> (segs, vias) routed so far (not yet on the board)
def commit(net, segs, vias):
    for l, x0, y0, x1, y1 in segs:
        sp = capsule_cells(x0, y0, x1, y1, TRK / 2 + TRK_R); bump(cnt[l], sp, 1)
        vs = capsule_cells(x0, y0, x1, y1, TRK / 2 + VIA_TR); bump(via_soft, vs, 1)
        item_cells[(net, 'trk', x0, y0, x1, y1)] = [(l, sp)]; via_cells[(net, 'trk', x0, y0, x1, y1)] = vs
    for x, y, la, lb in vias:
        r = max(VIA_D / 2 + FAN_CLR + TRK / 2, VIA_H / 2 + HOLE_CLR + TRK / 2); sp = disc_cells(x, y, r)
        for l in range(3): bump(cnt[l], sp, 1)
        vs = disc_cells(x, y, max(VIA_D / 2 + CLR + VIA_D / 2, VIA_H + 0.254) + 0.02); bump(via_soft, vs, 1)
        item_cells[(net, 'via', x, y)] = [(l, sp) for l in range(3)]; via_cells[(net, 'via', x, y)] = vs
    added[net][0].extend(segs); added[net][1].extend(vias)
def uncommit(net):
    """rip a net's routed geometry out of the grids"""
    for key in [k for k in item_cells if k[0] == net and k[1] in ('trk', 'via') and k in via_cells]:
        for l, sp in item_cells[key]: bump(cnt[l], sp, -1)
        bump(via_soft, via_cells[key], -1); del item_cells[key]; del via_cells[key]
    added.pop(net, None); done.pop(net, None)
def write_board():
    n_t = 0
    for net, (segs, vias) in added.items():
        n = nets_by_name[net]
        for l, x0, y0, x1, y1 in segs:
            t = pcbnew.PCB_TRACK(board); t.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); t.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
            t.SetWidth(FromMM(TRK)); t.SetLayer(LAY[LNAME[l]]); t.SetNet(n); board.Add(t); n_t += 1
        for x, y, la, lb in vias:
            v = pcbnew.PCB_VIA(board); v.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(FromMM(VIA_D)); v.SetDrill(FromMM(VIA_H)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(n); board.Add(v); n_t += 1
    return n_t
def seg_len(segs): return sum(math.hypot(x1 - x0, y1 - y0) for _, x0, y0, x1, y1 in segs)

def chip_pads(net):
    out = []
    for f in board.GetFootprints():
        if f.GetReference() in ('U9', 'U10', 'R41', 'R42', 'C145'):
            for p in f.Pads():
                if p.GetNetname() == net: out.append((f.GetReference(), p.GetNumber(), ToMM(p.GetPosition().x)))
    return out
_pre = {}
def prebuilt_cells(net):
    if net not in _pre:
        cells = set()
        for t in board.GetTracks():
            if t.GetNetname() != net: continue
            if t.Type() == pcbnew.PCB_VIA_T:
                x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
                if x >= 60: continue
                for l in range(3):
                    for j, a, b_ in disc_cells(x, y, 0.12):
                        for i in range(a, b_ + 1): cells.add((l, i, j))
            else:
                x0, y0, x1, y1 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
                if max(x0, x1) >= 60: continue
                L = next((k for k, v in LAY.items() if v == t.GetLayer()), None)
                if L is None: continue
                for i, j in seg_cells(x0, y0, x1, y1): cells.add((LIDX[L], i, j))
        _pre[net] = cells
    return _pre[net]
WAYPOINTS = json.loads(os.environ.get('BUS_WAYPOINTS', '{}')) if 'json' in globals() else {}
def waypoint_cells(net):
    x, y, h = WAYPOINTS[net]; fac = FACS[CLASS[net]]; out = set()
    for j, a, b_ in rect_cells(x - h, y - h, x + h, y + h):
        for i in range(a, b_ + 1):
            for l in range(3):
                if fac[l][i] is not None and not static[l][idx(i, j)]: out.add((l, i, j))
    return out
def targets_for(net):
    if net in WAYPOINTS: return [waypoint_cells(net)] + _targets_for(net)
    return _targets_for(net)
def _targets_for(net):
    cls = CLASS[net]
    if cls == 'addr':     # its bottom link, in the half of the channel that balances the two chip pins
        # group A (pins 16-26: outer row on U9, channel side on U10) joins near U9 (north half); group B (29-37) near U10
        lo, hi = (31.9, 36.6) if net in ADDR_A else (37.2, 41.9)
        return [{c for c in prebuilt_cells(net) if c[0] == 2 and lo <= wy(c[2]) <= hi}]
    if cls == 'dout':     # its outer via
        return [{c for c in prebuilt_cells(net) if c[0] == 2}]
    if cls == 'dch':
        return [set().union(*[pad_cells(r, n_) for r, n_, _ in chip_pads(net) if r in ('U9', 'U10')])]
    if cls == 'clk':
        return [pad_cells('R41', '1'), pad_cells('R42', '1')]
    if cls == 'dqs':
        return [pad_cells('C145', '1')]
    ref = 'R41' if net == 'U9_CLK' else 'R42'; chip = 'U9' if net == 'U9_CLK' else 'U10'
    return [pad_cells(chip, '38')]

# ------------------------------------------------------------------ per-net sources / targets (precomputed: no pcbnew calls inside threads)
done = {}
u1 = next(f for f in board.GetFootprints() if f.GetReference() == 'U1')
def ball_col(n):
    cols = [int(p.GetNumber()[1:]) for p in u1.Pads() if p.GetNetname() == n]; return max(cols) if cols else 0
ORDER = {'addr': 0, 'dout': 1, 'dch': 2, 'clk': 3, 'clkb': 4, 'dqs': 5}
all_nets = sorted(CLASS, key=lambda n: (ORDER[CLASS[n]], ball_col(n)))
if len(sys.argv) > 3 and sys.argv[3] not in ('', 'all'): all_nets = [n for n in all_nets if n in sys.argv[3].split(',')]
MAX_ROUNDS = int(sys.argv[4]) if len(sys.argv) > 4 else 40
TARGETS = {n: targets_for(n) for n in all_nets}
BASE_SRC = {n: cluster_cells(n, exclude_pads=[(r, n_) for r, n_, _ in chip_pads(n)]) - prebuilt_cells(n) for n in all_nets}
CLKB_SRC = {n: pad_cells('R41' if n == 'U9_CLK' else 'R42', '2') for n in all_nets if CLASS[n] == 'clkb'}
OWN = {n: [k for k in item_cells if k[0] == n] for n in all_nets}            # board items only (routed copper is ripped before a re-route)
def job(net):
    cls = CLASS[net]; segs_all = []; vias_all = []; local = set(); wp_block = []; wp_end = None
    for leg, tg in enumerate(TARGETS[net]):
        if not tg: return net, False, segs_all, vias_all, 'no target cells (leg %d)' % leg
        srcs = CLKB_SRC[net] if (cls == 'clkb' and not segs_all) else ({wp_end} if (net in WAYPOINTS and leg > 0) else (BASE_SRC[net] | local))
        if not srcs: return net, False, segs_all, vias_all, 'no source cells (leg %d)' % leg
        path, exp = route(net, list(srcs), list(tg), cls, OWN[net] + ROUTED_KEYS.get(net, []))   # its own previous route is discounted, everyone else's stays
        if path is None: return net, False, segs_all, vias_all, 'leg %d (%d expanded)' % (leg, exp)
        segs, vias = path_to_geometry(path); segs_all += segs; vias_all += vias
        if net in WAYPOINTS and leg == 0:          # the way back must not run along the way out: leg 0 is a hard obstacle for leg 1
            wp_end = path[-1]; ex, ey = wx(wp_end[1]), wy(wp_end[2]); wp_block = []
            for l, x0, y0, x1, y1 in segs:
                sp = [(j, a, b_) for j, a, b_ in capsule_cells(x0, y0, x1, y1, TRK / 2 + TRK_R)]
                keep = []
                for j, a, b_ in sp:          # leave a 0.6 mm opening round the waypoint so leg 1 can leave it
                    for i in range(a, b_ + 1):
                        if math.hypot(wx(i) - ex, wy(j) - ey) > 0.6: keep.append((j, i, i))
                bump(fixc[l], keep, 1); wp_block.append((l, keep))
        for l, x0, y0, x1, y1 in segs: local.update((l, i, j) for i, j in seg_cells(x0, y0, x1, y1))
        for x, y, la, lb in vias:
            for l in range(3):
                for j, a, b_ in disc_cells(x, y, 0.12): local.update((l, i, j) for i in range(a, b_ + 1))
    for l, keep in (wp_block if net in WAYPOINTS else []): bump(fixc[l], keep, -1)
    return net, True, segs_all, vias_all, ''
def net_conflicts(net):
    """cells where the net's own centreline / vias sit inside another net's clearance -> list of (l, k)"""
    own = [k for k in item_cells if k[0] == net]
    for key in own:
        for l, spans in item_cells.get(key, []): bump(cnt[l], spans, -1)
        if key in via_cells: bump(via_soft, via_cells[key], -1)
    hits = []
    segs, vias = added.get(net, ([], []))
    for l, x0, y0, x1, y1 in segs:
        for i, j in seg_cells(x0, y0, x1, y1):
            k = idx(i, j)
            if cnt[l][k] or static[l][k]: hits.append((l, k))
    for x, y, la, lb in vias:
        k = idx(gx(x), gy(y))
        if via_soft[k] or via_static[k]: hits.append((la, k))
        for l in range(3):
            if cnt[l][k]: hits.append((l, k))
    for key in own:
        for l, spans in item_cells.get(key, []): bump(cnt[l], spans, 1)
        if key in via_cells: bump(via_soft, via_cells[key], 1)
    return hits

todo = set(all_nets); T_START = time.time(); conf = {}; fails = {}; best_state = None; ROUTED_KEYS = {}; STALL = 0; LAST_BAD = 10**9
pool = concurrent.futures.ThreadPoolExecutor(max_workers=NTHREADS)
for rnd in range(1, MAX_ROUNDS + 1):
    t1 = time.time(); fails = {}
    for g in GRIDS.values(): g.pres = PRES[0]
    order = [n for n in all_nets if n in todo]
    if rnd > 1: RNG.shuffle(order)
    if NTHREADS > 1:                                                           # parallel round: everyone against the previous picture
        ROUTED_KEYS = {n: [k for k in via_cells if k[0] == n] for n in todo}
        results = list(pool.map(job, order))
        for net, ok, segs, vias, why in results:
            uncommit(net)
            if ok: commit(net, segs, vias)
            else: fails[net] = why
    else:                                                                      # sequential round: each reroute sees the ones before it
        for net in order:
            ROUTED_KEYS = {net: [k for k in via_cells if k[0] == net]}
            net_, ok, segs, vias, why = job(net)
            uncommit(net)
            if ok: commit(net, segs, vias)
            else: fails[net] = why
    conf = {}; hot = set()
    for net in all_nets:
        if net in fails: continue
        hits = net_conflicts(net)
        if hits:
            conf[net] = len(hits); hot.update(hits)
            for l, k in hits: hist[l][k] = min(hist[l][k] + 1, 60000)
    print('round %2d: pres %.2f routed %d of %d, failed %d, conflicting nets %d, conflict cells %d (%.1fs)' % (rnd, PRES[0], len(todo) - len(fails), len(todo), len(fails), len(conf), sum(conf.values()), time.time() - t1), flush=True)
    if fails: print('   failed:', ', '.join('%s@%s' % kv for kv in fails.items()), flush=True)
    score = len(conf) * 1000 + sum(conf.values()) + 5000 * len(fails)
    if best_state is None or score < best_state[0]:
        best_state = (score, rnd, {n: (list(sg), list(vi)) for n, (sg, vi) in added.items()}, set(conf) | set(fails))
    if not conf and not fails: break
    PRES[0] = min(PRES[0] * 1.6, PRES_MAX)
    todo = set(conf) | set(fails)
    STALL = STALL + 1 if (len(conf) + len(fails)) >= LAST_BAD else 0; LAST_BAD = min(LAST_BAD, len(conf) + len(fails)) if STALL else len(conf) + len(fails)
    if hot and len(todo) <= 8 and rnd >= 15:      # stuck on a few conflicts: also rip up every routed net near the contested cells
        near = set()
        rows = collections.defaultdict(list)
        for l, k in hot:
            for dj in range(-12, 13): rows[(l, k // NX + dj)].append(k % NX)
        for key, cells in item_cells.items():
            if key not in via_cells or key[0] in todo: continue
            for l, spans in cells:
                if any((l, j) in rows and any(a - 12 <= i <= b_ + 12 for i in rows[(l, j)]) for j, a, b_ in spans): near.add(key[0]); break
        todo |= near
        if near: print('   ripping up %d neighbours too: %s' % (len(near), ', '.join(sorted(near))), flush=True)
    if time.time() - T_START > 7200: print('time budget reached'); break
pool.shutdown()
with open(OUT + '.hist', 'wb') if OUT != '/dev/null' else open(os.devnull, 'wb') as fh:
    for l in range(3): fh.write(hist[l].tobytes())
print('history map: %d x %d x 3 uint16 -> %s.hist' % (NX, NY, OUT))
if best_state and (conf or fails):
    print('keeping the best round: %d (%d nets still conflicting or open: %s)' % (best_state[1], len(best_state[3]), sorted(best_state[3])))
    added.clear()
    for n, (sg, vi) in best_state[2].items(): added[n][0].extend(sg); added[n][1].extend(vi)
for net in all_nets:
    sg, vi = added.get(net, ([], [])); print('  %-10s %5.1f mm  %d vias' % (net, seg_len(sg), len(vi)))
if OUT != '/dev/null':
    print('board items written:', write_board())
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for z in board.Zones():
        if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
    pcbnew.SaveBoard(OUT, board); print('saved', OUT)
