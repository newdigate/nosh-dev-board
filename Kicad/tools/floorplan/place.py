"""Macro placement by simulated annealing on gp/model.json.
Cost = sum over nets of MST length (power nets weighted 0.5) + XW * number of crossing airwires.
usage: place.py <scenario> <seed> <iters> <out-prefix>      scenario: free | sdramN|E|S|W | m2W | m2W_sdramS ...
"""
import json, math, random, sys, time
import os
S = os.environ.get('GP', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work')) + '/'; os.makedirs(S, exist_ok=True)
M = json.load(open(S + 'model.json')); P = M['parts']; W, H = M['W'], M['H']
scenario, seed, ITERS, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
for _r in ('J4', 'U6', 'L5', 'U7', 'U8'): P[_r]['pads'].append(['__SUPPLY', 0.0, 0.0])     # supply chain clusters even though its rails are planes
PEN = 3000.0                                # cost per part violating the scenario
random.seed(seed)
XW = 3.0                                   # mm-equivalent cost of one crossing
EDGE_CONN = ['J2', 'J3', 'J4', 'J5', 'J8', 'J9']
MARGIN = {'U1': 4.0, 'U9': 1.5, 'U10': 1.5, 'J6': 1.0}
def margin(r): return MARGIN.get(r, 1.5 if r[0] in 'UY' else 0.5 if r[0] in 'JS' else 1.0)
POWER = ('+1V8', 'NVCC', 'VDD', 'VLDO', 'VSD', 'DC_IN', 'USB1_VBUS', 'USB2_VBUS', 'USB1_CON_VBUS', 'USB2_CON_VBUS', 'LCD_5V', 'CODEC', 'CTP_3V3', 'AUD_VDDA', 'BUCK', 'PWR_LED', 'USER_LED', 'M2_LED', 'SD_PWR', 'OTG2_VBUS')
def nweight(n): return 0.5 if n.startswith(POWER) else 1.0
EDGES = {0: (1, 0), 1: (0, -1), 2: (-1, 0), 3: (0, 1)}        # E, N, W, S (CCW order on screen)
# ---- geometry
def world(st, lx, ly):
    th = math.radians(st[2]); c, s = math.cos(th), math.sin(th)
    return st[0] + lx * c + ly * s, st[1] - lx * s + ly * c
def box(r, st, m=0.0):
    x0, y0, x1, y1 = P[r]['box']
    pts = [world(st, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return (min(p[0] for p in pts) - m, min(p[1] for p in pts) - m, max(p[0] for p in pts) + m, max(p[1] for p in pts) + m)
def pads(r, st): return [(n, *world(st, lx, ly)) for n, lx, ly in P[r]['pads']]
def card(st):   # M.2 card region in world coords (local: lx in [-11,11], ly in [0,32] at rot 0 of J6, per the EVKB placement at rot 180 with H5 30 mm north)
    pts = [world(st, x, y) for x, y in ((-11.5, 0.0), (11.5, 0.0), (11.5, 32.5), (-11.5, 32.5))]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
def overlap(a, b): return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
# edge connectors: outward edge, rotation at that edge, depth from the edge to the part origin
EC = {}
for r in EDGE_CONN:
    st0 = (P[r]['x'], P[r]['y'], P[r]['rot']); bx = box(r, st0)
    d = {0: W - bx[2], 1: bx[1], 2: bx[0], 3: H - bx[3]}; e0 = min(d, key=d.get)
    depth = {0: W - st0[0], 1: st0[1], 2: st0[0], 3: H - st0[1]}[e0]
    EC[r] = (e0, st0[2], depth)
def edge_state(r, e, t):
    e0, r0, depth = EC[r]; rot = (r0 + 90 * (e - e0)) % 360
    x, y = {0: (W - depth, t), 1: (t, depth), 2: (depth, t), 3: (t, H - depth)}[e]
    return (x, y, rot)
def edge_of(r, st):
    bx = box(r, st); d = {0: W - bx[2], 1: bx[1], 2: bx[0], 3: H - bx[3]}; return min(d, key=d.get)
# ---- state
state = {r: (P[r]['x'], P[r]['y'], P[r]['rot']) for r in P}
import os
if os.environ.get('START'): state.update({k: tuple(v) for k, v in json.load(open(os.environ['START']))['state'].items()}); print('start state from', os.environ['START'])
MOV = [r for r in P if not P[r]['fixed'] and r != 'H5' and r not in os.environ.get('LOCK', '').split(',')]
FIXBOX = [box(r, state[r]) for r in P if P[r]['fixed']]
KEEP = [(x - 3.0, y - 3.0, x + 3.0, y + 3.0) for x, y in ((3.8735, 5.2975), (151.1265, 5.2975), (151.1265, 78.2025), (3.8735, 78.2025))] + FIXBOX
def h5_state(j6): return (*world(j6, 0.0, 30.0), j6[2])
def u1_side(r, st):      # which side of U1 a part is on: N/E/S/W by dominant direction
    dx, dy = st[0] - state['U1'][0], st[1] - state['U1'][1]
    return ('E' if dx > 0 else 'W') if abs(dx) >= abs(dy) else ('S' if dy > 0 else 'N')
def scenario_ok(r, st):
    for tok in scenario.split('_'):
        if tok.startswith('sdram') and r in ('U9', 'U10') and u1_side(r, st) != tok[5]: return False
        if tok.startswith('m2') and r == 'J6' and u1_side(r, st) != tok[2]: return False
    return True
def valid(r, st, others):
    bx = box(r, st, margin(r)); raw = box(r, st)
    if r in EDGE_CONN:
        e = edge_of(r, st)
        lim = (-0.3 if e == 2 else 0.5, -0.3 if e == 1 else 0.5, W + 0.3 if e == 0 else W - 0.5, H + 0.3 if e == 3 else H - 0.5)
    else:
        em = 12.0 if r == 'U1' else 0.5
        lim = (em, em, W - em, H - em)
    if raw[0] < lim[0] or raw[1] < lim[1] or raw[2] > lim[2] or raw[3] > lim[3]: return False
    for k in KEEP:
        if overlap(raw, k): return False
    regions = [bx]
    if r == 'J6':
        cd = card(st)
        if cd[0] < 0.5 or cd[1] < 0.5 or cd[2] > W - 0.5 or cd[3] > H - 0.5: return False
        for k in KEEP:
            if overlap(cd, k): return False
        regions.append(cd)
    for o, so in others.items():
        if o == r or o == 'H5': continue
        ob = box(o, so, margin(o))
        for rg in regions:
            if overlap(rg, ob): return False
        if o == 'J6' and overlap(raw, card(so)): return False
    return True
def rand_state(r):
    if r in EDGE_CONN:
        e = random.choice(list(EDGES)); L_ = H if e in (0, 2) else W; return edge_state(r, e, random.uniform(10, L_ - 10))
    return (random.uniform(5, W - 5), random.uniform(5, H - 5), random.choice((0, 90, 180, 270)))
def relocate(o, changed, tries=1500):
    """Find a valid spot for o given state+changed (grid cells in random order). Adds it to changed; returns success."""
    others = dict(state); others.update(changed)
    if o in EDGE_CONN:
        cands = [edge_state(o, e, t) for e in EDGES for t in range(8, int((H if e in (0, 2) else W) - 8), 2)]
    else:
        cands = [(x, y, rot) for x in range(4, int(W) - 4, 3) for y in range(4, int(H) - 4, 3) for rot in (0, 90, 180, 270)]
    random.shuffle(cands)
    for st in cands[:tries]:
        if valid(o, st, others): changed[o] = st; return True
    return False
def evict_place(r, st, changed):
    """Put r at st; every movable part it collides with is relocated to a free spot. Fills `changed`; returns success."""
    changed[r] = st
    if r == 'J6': changed['H5'] = h5_state(st)
    fixed_only = {k: v for k, v in state.items() if k not in MOV}
    if not valid(r, st, fixed_only): return False
    bx = box(r, st, margin(r)); regs = [bx] + ([card(st)] if r == 'J6' else [])
    for o in MOV:
        if o in changed or o == 'H5' or o == 'U1': continue
        ob = box(o, state[o], margin(o))
        hit = any(overlap(rg, ob) for rg in regs) or (o == 'J6' and overlap(box(r, st), card(state[o])))
        if hit and not relocate(o, changed): return False
    others = dict(state); others.update(changed)
    return all(valid(k, v, others) for k, v in changed.items() if k != 'H5')
def viol_all(sts): return sum(0 if scenario_ok(r, sts[r]) else 1 for r in ('U9', 'U10', 'J6'))
# ---- cost
def mst(pts):
    n = len(pts)
    if n < 2: return 0.0, []
    inn = [False] * n; d = [1e9] * n; par = [-1] * n; d[0] = 0; L = 0.0; edges = []
    for _ in range(n):
        u = min((i for i in range(n) if not inn[i]), key=lambda i: d[i]); inn[u] = True
        if par[u] >= 0: L += d[u]; edges.append((pts[par[u]][0], pts[par[u]][1], pts[u][0], pts[u][1]))
        ux, uy = pts[u]
        for v in range(n):
            if not inn[v]:
                dv = math.hypot(pts[v][0] - ux, pts[v][1] - uy)
                if dv < d[v]: d[v] = dv; par[v] = u
    return L, edges
def seg_cross(a, b):
    ax0, ay0, ax1, ay1 = a[:4]; bx0, by0, bx1, by1 = b[:4]
    if max(ax0, ax1) < min(bx0, bx1) or min(ax0, ax1) > max(bx0, bx1) or max(ay0, ay1) < min(by0, by1) or min(ay0, ay1) > max(by0, by1): return False
    d1 = (bx1 - bx0) * (ay0 - by0) - (by1 - by0) * (ax0 - bx0); d2 = (bx1 - bx0) * (ay1 - by0) - (by1 - by0) * (ax1 - bx0)
    d3 = (ax1 - ax0) * (by0 - ay0) - (ay1 - ay0) * (bx0 - ax0); d4 = (ax1 - ax0) * (by1 - ay0) - (ay1 - ay0) * (bx1 - ax0)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0
def cross_count(A, B):
    return sum(1 for a in A for b in B if seg_cross(a, b))
def cross_within(A):
    return sum(1 for i in range(len(A)) for j in range(i + 1, len(A)) if A[i][4] != A[j][4] and seg_cross(A[i], A[j]))
# net -> pads over all parts
part_nets = {r: sorted({n for n, _, _ in P[r]['pads']}) for r in P}
net_parts = {}
for r in P:
    for n in part_nets[r]: net_parts.setdefault(n, []).append(r)
NETS = [n for n, rs in net_parts.items() if sum(1 for r in rs for q in P[r]['pads'] if q[0] == n) >= 2]
net_parts = {n: net_parts[n] for n in NETS}
padcache = {}
def part_pads(r): 
    if r not in padcache: padcache[r] = pads(r, state[r])
    return padcache[r]
def net_eval(n):
    pts = [(x, y) for r in net_parts[n] for nn, x, y in part_pads(r) if nn == n]
    L, e = mst(pts); return L * nweight(n), [(*s, n) for s in e]
netL = {}; netE = {}
for n in NETS: netL[n], netE[n] = net_eval(n)
def all_edges(exclude=()):
    return [e for n in NETS if n not in exclude for e in netE[n]]
Ltot = sum(netL.values()); Xtot = cross_within(all_edges()); Vtot = viol_all(state)
def cost(): return Ltot + XW * Xtot + PEN * Vtot
print('scenario', scenario, 'seed', seed, '| start: length %.0f mm, crossings %d, cost %.0f' % (Ltot, Xtot, cost()), '| nets', len(NETS), 'edges', len(all_edges()))
best = (cost(), dict(state))
def try_move(changed):
    """changed: {r: new_state}. Returns delta cost and applies if accepted by the caller via commit()."""
    nets = set(); 
    for r in changed: nets.update(part_nets[r])
    nets = [n for n in nets if n in netL]
    oldE = [e for n in nets for e in netE[n]]; U = all_edges(exclude=set(nets))
    old_part = cross_count(oldE, U) + cross_within(oldE); oldL = sum(netL[n] for n in nets)
    saved = {r: state[r] for r in changed}
    for r, st in changed.items(): state[r] = st; padcache.pop(r, None)
    newL = {}; newE = {}
    for n in nets: newL[n], newE[n] = net_eval(n)
    NE = [e for n in nets for e in newE[n]]
    new_part = cross_count(NE, U) + cross_within(NE)
    dL = sum(newL.values()) - oldL; dX = new_part - old_part; dV = viol_all(state) - Vtot
    return dL + XW * dX + PEN * dV, dL, dX, dV, saved, newL, newE
def revert(saved):
    for r, st in saved.items(): state[r] = st; padcache.pop(r, None)
def commit(nets_new):
    pass
if scenario != 'free':
    toks = scenario.split('_'); plan = {}
    for tok in toks:
        if tok.startswith('sdram'):
            side_ = tok[5]; rot = {'W': 0, 'S': 90, 'E': 180, 'N': 270}[side_]
            u1 = (state['U1'][0], 50.0 if side_ == 'N' else state['U1'][1], rot); plan['U1'] = u1
            plan['U9'] = (*world(u1, -21.0, -13.0), rot); plan['U10'] = (*world(u1, -21.0, 13.0), rot)
    for tok in toks:
        if tok.startswith('m2'):
            u1 = plan.get('U1', state['U1'])
            plan['J6'] = {'W': (17.0, 45.0, 180), 'N': (u1[0] + 12.0, 20.5, 90), 'E': (125.0, 40.0, 180), 'S': (u1[0] + 5.0, 66.0, 270)}[tok[2]]
    for r in ('U1', 'U9', 'U10', 'J6'):
        if r not in plan: continue
        ch = {}; ok = evict_place(r, plan[r], ch)
        if ok:
            d, dL, dX, dV, saved, newL, newE = try_move(ch); Ltot += dL; Xtot += dX; Vtot += dV; netL.update(newL); netE.update(newE)
        print('scenario init', r, 'placed' if ok else 'FAILED', 'relocated', sorted(k for k in ch if k != r), flush=True)
Vtot = viol_all(state); print('after init: violations', Vtot, 'cost %.0f' % cost(), flush=True)
best = (cost(), dict(state))
T0, T1 = float(os.environ.get('T0', 25.0)), 0.05; t_start = time.time(); acc = 0
for it in range(ITERS):
    T = T0 * (T1 / T0) ** (it / ITERS)
    r = 'U1' if random.random() < 0.03 else random.choice(MOV)
    st = state[r]; kind = random.random(); changed = {}
    if r in EDGE_CONN:
        e = edge_of(r, st); t = st[1] if e in (0, 2) else st[0]
        if kind < 0.55: t += random.gauss(0, 2 + 10 * T / T0); changed[r] = edge_state(r, e, t)
        elif kind < 0.8: e2 = random.choice([k for k in EDGES if k != e]); L_ = H if e2 in (0, 2) else W; changed[r] = edge_state(r, e2, random.uniform(10, L_ - 10))
        else:
            o = random.choice([k for k in EDGE_CONN if k != r]); eo = edge_of(o, state[o]); to = state[o][1] if eo in (0, 2) else state[o][0]
            changed[r] = edge_state(r, eo, to); changed[o] = edge_state(o, e, t)
    elif r in ('U9', 'U10') and kind < 0.3:          # move both SDRAM chips together
        o = 'U10' if r == 'U9' else 'U9'; so = state[o]
        if kind < 0.15:
            dx, dy = random.gauss(0, 1 + 12 * T / T0), random.gauss(0, 1 + 12 * T / T0)
            changed[r] = (st[0] + dx, st[1] + dy, st[2]); changed[o] = (so[0] + dx, so[1] + dy, so[2])
        else:                                           # rotate the pair about its common centre
            mx, my = (st[0] + so[0]) / 2, (st[1] + so[1]) / 2; a = random.choice((90, 180, 270)); th_ = math.radians(a); c_, s_ = math.cos(th_), math.sin(th_)
            def rotp(q): return (mx + (q[0] - mx) * c_ + (q[1] - my) * s_, my - (q[0] - mx) * s_ + (q[1] - my) * c_, (q[2] + a) % 360)
            changed[r] = rotp(st); changed[o] = rotp(so)
    else:
        if kind < 0.5: changed[r] = (st[0] + random.gauss(0, 1 + 12 * T / T0), st[1] + random.gauss(0, 1 + 12 * T / T0), st[2])
        elif kind < 0.7: changed[r] = (st[0], st[1], (st[2] + random.choice((90, 180, 270))) % 360)
        elif kind < 0.85:
            o = random.choice([k for k in MOV if k != r and k not in EDGE_CONN and k != 'U1'])
            if r == 'U1': continue
            changed[r] = (state[o][0], state[o][1], st[2]); changed[o] = (st[0], st[1], state[o][2])
        else: changed[r] = (random.uniform(5, W - 5), random.uniform(5, H - 5), random.choice((0, 90, 180, 270)))
    if r in ('U9', 'U10', 'J6', 'J5', 'J10', 'U2', 'U11', 'U12') and random.random() < 0.25 * T / T0:
        changed = {}
        if not evict_place(r, rand_state(r), changed): continue
    if 'J6' in changed: changed['H5'] = h5_state(changed['J6'])
    others = dict(state); others.update(changed)
    if not all(valid(k, v, others) for k, v in changed.items() if k != 'H5'): continue
    d, dL, dX, dV, saved, newL, newE = try_move(changed)
    if d <= 0 or random.random() < math.exp(-d / T):
        Ltot += dL; Xtot += dX; Vtot += dV; netL.update(newL); netE.update(newE); acc += 1
        c = cost()
        if c < best[0]: best = (c, dict(state))
    else: revert(saved)
    if it % 5000 == 0: print('it %6d T %.2f  length %.0f crossings %d cost %.0f  best %.0f  (%.0fs)' % (it, T, Ltot, Xtot, cost(), best[0], time.time() - t_start), flush=True)
# final: restore best, recompute exactly
state.update(best[1]); padcache.clear()
for n in NETS: netL[n], netE[n] = net_eval(n)
Ltot = sum(netL.values()); Xtot = cross_within(all_edges()); Vtot = viol_all(state)
print('FINAL %s seed %d: length %.0f mm, crossings %d, violations %d, cost %.0f, accepted %d' % (scenario, seed, Ltot, Xtot, Vtot, cost(), acc))
sides = {r: u1_side(r, state[r]) for r in ('U9', 'U10', 'J6', 'U2', 'U15', 'J5', 'J3', 'J2', 'J4', 'J8', 'J9', 'J10', 'J1')}
json.dump(dict(scenario=scenario, seed=seed, length=Ltot, crossings=Xtot, violations=Vtot, cost=cost(), state=state, sides=sides, edges=all_edges()), open(OUT + '.json', 'w'))
print('sides', sides)
