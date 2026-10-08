"""Extract the macro placement model from Nosh.kicad_pcb into gp/model.json (no pcbnew needed afterwards)."""
import os, math, json, collections, pcbnew
from pcbnew import ToMM
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..') + '/'
import os
S = os.environ.get('GP', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work')) + '/'; os.makedirs(S, exist_ok=True)
b = pcbnew.LoadBoard(K + 'Nosh.kicad_pcb')
PLANES = {'GND', '+3V3', '+5V', 'SDRAM_3V3', 'WL_3V3', 'VDD_SOC_IN'}
MACRO = {'U1','U9','U10','J6','H5','U2','U3','U6','U7','U8','U11','U12','U15','L1','L5','L3','L4','U4','U5','Y1','Y2','SW1','SW2','SW3','SW4','J1','J2','J3','J4','J5','J8','J9','J10','J11'}
FIXED = {'J7','H1','H2','H3','H4','FID1','FID2','FID3','FID4','FID5','FID6'}
fps = {f.GetReference(): f for f in b.GetFootprints()}
def sig(n): return bool(n) and n not in PLANES and not n.startswith('unconnected')
# union-find over nets through 2-pin passives
parent = {}
def find(n):
    while parent.get(n, n) != n: n = parent[n]
    return n
def union(a, b_):
    ra, rb = find(a), find(b_)
    if ra != rb: parent[ra] = rb
merged = 0
for r, f in fps.items():
    if r in MACRO or r in FIXED: continue
    pads = [p.GetNetname() for p in f.Pads()]
    if len(pads) == 2 and sig(pads[0]) and sig(pads[1]): union(pads[0], pads[1]); merged += 1
parts = {}
for r in MACRO | FIXED:
    f = fps[r]; x, y = ToMM(f.GetPosition().x), ToMM(f.GetPosition().y); rot = f.GetOrientationDegrees(); back = f.GetLayer() == pcbnew.B_Cu
    th = math.radians(rot); c, s = math.cos(th), math.sin(th)
    def local(px, py):      # world -> local at rot 0 (KiCad: positive rot = CCW on screen with y down)
        dx, dy = px - x, py - y
        lx, ly = dx * c - dy * s, dx * s + dy * c     # inverse rotation
        return (round(lx, 3), round(ly, 3))
    pads = []
    for p in f.Pads():
        n = p.GetNetname()
        if not sig(n): continue
        pads.append((find(n), *local(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))))
    cy = f.GetCourtyard(pcbnew.B_CrtYd if back else pcbnew.F_CrtYd).BBox()
    if cy.GetWidth() == 0: cy = f.GetBoundingBox(False, False)
    c0 = (local(ToMM(cy.GetLeft()), ToMM(cy.GetTop())), local(ToMM(cy.GetRight()), ToMM(cy.GetBottom())))
    lx0, lx1 = sorted((c0[0][0], c0[1][0])); ly0, ly1 = sorted((c0[0][1], c0[1][1]))
    parts[r] = dict(x=x, y=y, rot=rot, back=back, pads=pads, box=[lx0, ly0, lx1, ly1], fixed=r in FIXED)
# verify the local transform reproduces world pads
def world(part, lx, ly):
    th = math.radians(part['rot']); c, s = math.cos(th), math.sin(th)
    return part['x'] + lx * c + ly * s, part['y'] - lx * s + ly * c
err = 0
for r, pt in parts.items():
    f = fps[r]
    for p in f.Pads():
        n = p.GetNetname()
        if not sig(n): continue
        pad = next(q for q in pt['pads'] if q[0] == find(n) and abs(world(pt, q[1], q[2])[0] - ToMM(p.GetPosition().x)) < 0.01 and abs(world(pt, q[1], q[2])[1] - ToMM(p.GetPosition().y)) < 0.01) if True else None
nets = collections.Counter(q[0] for pt in parts.values() for q in pt['pads'])
print('merged nets through passives:', merged, '| macro nets with >=2 pads:', sum(1 for n, k in nets.items() if k >= 2), '| pads', sum(nets.values()))
json.dump(dict(parts=parts, W=155.0, H=83.5), open(S + 'model.json', 'w'))
print('saved')
