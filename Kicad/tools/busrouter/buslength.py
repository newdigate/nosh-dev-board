"""Per-pin flight lengths of the SDRAM bus: shortest copper path from the MCU ball to each chip pin.
usage: buslength.py board.kicad_pcb [via_mm]        via_mm: length counted per via passed (default 0.8)
Tracks are split wherever another item's end lands on them; vias join all layers; pads join what lies on them.
Clock: SEMC_CLK from J3 to R41/R42 pad 1, plus U9_CLK / U10_CLK from pad 2 to pin 38 (+1 mm for the resistor).
Reports each pin against the clock length at the same chip.
"""
import sys, re, math, heapq, collections, pcbnew
from pcbnew import ToMM
b = pcbnew.LoadBoard(sys.argv[1]); VIA_MM = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
SD = re.compile(r'^(SEMC_|U9_CLK$|U10_CLK$)')
Q = lambda v: round(ToMM(v) * 1000)                    # micrometre keys
items = collections.defaultdict(lambda: {'trk': [], 'via': [], 'pad': []})
for t in b.GetTracks():
    n = t.GetNetname()
    if not SD.match(n): continue
    if t.Type() == pcbnew.PCB_VIA_T: items[n]['via'].append((Q(t.GetPosition().x), Q(t.GetPosition().y), round(ToMM(t.GetWidth(pcbnew.F_Cu)) * 500)))
    else: items[n]['trk'].append((t.GetLayer(), Q(t.GetStart().x), Q(t.GetStart().y), Q(t.GetEnd().x), Q(t.GetEnd().y), round(ToMM(t.GetWidth()) * 500)))
for f in b.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if SD.match(n): items[n]['pad'].append((f.GetReference(), p.GetNumber(), p, {l for l in (pcbnew.F_Cu, pcbnew.B_Cu, b.GetLayerID('SIG')) if p.IsOnLayer(l)}))

def lengths(net, start_pad):
    it = items[net]; adj = collections.defaultdict(list)
    def edge(a, c, w): adj[a].append((c, w)); adj[c].append((a, w))
    pts = collections.defaultdict(set)                  # layer -> endpoints
    for l, x0, y0, x1, y1, hw in it['trk']: pts[l].add((x0, y0)); pts[l].add((x1, y1))
    for x, y, r in it['via']:
        for l in pts: pts[l].add((x, y))
    for l, x0, y0, x1, y1, hw in it['trk']:               # split each track at points lying on it
        dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy; on = [(0.0, (x0, y0)), (1.0, (x1, y1))]
        for (px, py) in pts[l]:
            if L2 == 0: continue
            t = ((px - x0) * dx + (py - y0) * dy) / L2
            if 0 < t < 1 and abs((px - x0) * dy - (py - y0) * dx) / math.sqrt(L2) <= hw: on.append((t, (px, py)))
        on.sort()
        for (ta, pa), (tb, pb) in zip(on, on[1:]): edge((l, pa), (l, pb), math.hypot(pb[0] - pa[0], pb[1] - pa[1]) / 1000)
    for x, y, r in it['via']:                            # via: a hub joined to every layer node within its pad
        hub = ('via', x, y)
        for l in pts:
            for (px, py) in pts[l]:
                if math.hypot(px - x, py - y) <= r: edge(hub, (l, (px, py)), VIA_MM / 2)
    for ref, num, p, lays in it['pad']:                  # pad: a hub joined to every node on it
        hub = ('pad', ref, num)
        for l in lays:
            for (px, py) in pts.get(l, ()):
                if p.HitTest(pcbnew.VECTOR2I(px * 1000, py * 1000)):
                    c = p.GetPosition(); edge(hub, (l, (px, py)), math.hypot(px - Q(c.x), py - Q(c.y)) / 1000)
        for x, y, r in it['via']:
            if any(p.IsOnLayer(l) for l in lays) and p.HitTest(pcbnew.VECTOR2I(x * 1000, y * 1000)): edge(hub, ('via', x, y), 0.0)
    src = ('pad',) + start_pad; dist = {src: 0.0}; pq = [(0.0, 0, src)]; tie = 0
    while pq:
        d, _, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18): continue
        for v, w in adj[u]:
            if d + w < dist.get(v, 1e18): dist[v] = d + w; tie += 1; heapq.heappush(pq, (d + w, tie, v))
    return {(k[1], k[2]): v for k, v in dist.items() if k[0] == 'pad'}

u1_ball = {}
for n, it in items.items():
    for ref, num, p, lays in it['pad']:
        if ref == 'U1': u1_ball[n] = (ref, num)
clk = {}
dc = lengths('SEMC_CLK', u1_ball['SEMC_CLK'])
for chip, r, net in (('U9', 'R41', 'U9_CLK'), ('U10', 'R42', 'U10_CLK')):
    a = dc.get((r, '1')); bb = lengths(net, (r, '2')).get((chip, '38'))
    clk[chip] = None if a is None or bb is None else a + 1.0 + bb
print('clock to pin 38: U9 %s mm, U10 %s mm' % tuple('%.1f' % clk[c] if clk[c] else 'OPEN' for c in ('U9', 'U10')))
rows = []
for n in sorted(items, key=lambda s: (re.sub(r'\d+', '', s), int(re.search(r'(\d+)$', s).group(1)) if re.search(r'\d$', s) else 0)):
    if n in ('SEMC_CLK', 'U9_CLK', 'U10_CLK', 'SEMC_DQS') or n not in u1_ball: continue
    d = lengths(n, u1_ball[n])
    for ref, num, p, lays in items[n]['pad']:
        if ref not in ('U9', 'U10'): continue
        L = d.get((ref, num)); rows.append((n, ref, num, L, None if L is None or clk[ref] is None else L - clk[ref]))
for n, ref, num, L, dlt in rows:
    print('  %-10s %-3s pin %-2s %s' % (n, ref, num, 'OPEN' if L is None else '%5.1f mm  vs clock %+6.1f' % (L, dlt)))
ok = [r for r in rows if r[3] is not None]
if ok:
    for chip in ('U9', 'U10'):
        ds = [r[4] for r in ok if r[1] == chip and r[4] is not None]
        if ds: print('%s: %d pins, vs clock %+.1f .. %+.1f mm, longest pin %.1f mm' % (chip, len(ds), min(ds), max(ds), max(r[3] for r in ok if r[1] == chip)))
print('open pins:', [(r[0], r[1], r[2]) for r in rows if r[3] is None])
# ---- summary for scripts: per chip, the signal span and the clock length that would centre it
import json
summary = {'clock': clk, 'pins': [(r[0], r[1], r[2], r[3]) for r in rows], 'chips': {}}
for chip in ('U9', 'U10'):
    ls = [r[3] for r in rows if r[1] == chip and r[3] is not None]
    if ls: summary['chips'][chip] = {'min': min(ls), 'max': max(ls), 'half_span': (max(ls) - min(ls)) / 2, 'centre': (max(ls) + min(ls)) / 2}
summary['score'] = max(c['half_span'] for c in summary['chips'].values()) if summary['chips'] else 1e9
print('SPAN U9 %.1f..%.1f  U10 %.1f..%.1f  worst half-span %.1f mm' % (summary['chips']['U9']['min'], summary['chips']['U9']['max'], summary['chips']['U10']['min'], summary['chips']['U10']['max'], summary['score']))
if len(sys.argv) > 3: json.dump(summary, open(sys.argv[3], 'w'))
