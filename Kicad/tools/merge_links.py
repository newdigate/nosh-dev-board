"""Take out 0R links and join their nets (run with KiCad's bundled python3).
usage: merge_links.py [kicad_dir]        default: the Kicad/ folder this script lives under;  DRY=1 prints the board plan only
Each link (ref, surviving net, absorbed net) is removed from the schematic together with the two global labels on its
pins, and every label of the absorbed net on every sheet is renamed to the surviving net. On the board the absorbed
net's pads, tracks, vias and zones take the surviving net, the footprint goes, and the copper that landed on its two
pads is joined: a stub from each attached track end or via to its pad centre, then a pad-centre-to-pad-centre track
(0.5 mm for 0603 rail links, 0.4 mm for 0402 rail links, 0.2 mm for signals) unless other copper lies in the way
(listed as SKIPPED). A skipped rail link is left to the plane: both sides already have vias into it (R33, R35, R70 here,
checked by DRC). A skipped signal link needs a JUMP: two vias and a track on another layer, hand-placed below.
PWR_FLAGs that sat on an absorbed net are deleted with their label: the merged nets are driven by the 3.3 V / 1.8 V
regulators and the RT1176's VDDA_1P0 LDO output, so a flag there is a power-output conflict.
Idempotent: links already gone are skipped."""
import sys, os, re, math
K = (sys.argv[1].rstrip('/') + '/') if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
DRY = bool(os.environ.get('DRY'))
LINKS = [  # ref, surviving net, absorbed net, kind
    ('R31', '+3V3', 'VDD_LPSR_IN', 'rail'), ('R32', '+3V3', 'DCDC_IN', 'rail'), ('R33', '+3V3', 'NVCC_GPIO', 'rail'),
    ('R34', '+3V3', 'NVCC_EMC1', 'rail'), ('R35', '+3V3', 'NVCC_EMC2', 'rail'), ('R36', '+3V3', 'NVCC_LPSR', 'rail'),
    ('R37', '+3V3', 'NVCC_DISP2', 'rail'), ('R38', '+1V8', 'NVCC_SD1', 'rail'), ('R39', '+3V3', 'NVCC_DISP1', 'rail'),
    ('R4', 'VDDA_1P0', 'VDD_MIPI_1P0', 'rail'),
    ('R64', 'BACKLIGHT_CTL', 'BACKLIGHT_CTL_C', 'signal'), ('R72', 'LCM_PWR_EN', 'LCM_PWR_EN_C', 'signal'),
    ('R76', 'CTP_RST_B', 'CTP_RST_B_C', 'signal'), ('R77', 'CTP_INT', 'CTP_INT_C', 'signal'),
    ('R17', 'USB_OTG2_ID', 'USB2_CON_ID', 'signal'), ('R45', 'WL_RST_B', 'M2_WDIS1_N', 'signal'), ('R48', 'BT_RST_B', 'M2_WDIS2_N', 'signal'),
    ('R69', '+1V8', 'LCD_IOVCC_1V8', 'rail'), ('R70', '+3V3', 'CTP_3V3', 'rail'), ('R71', '+5V', 'LCD_5V', 'rail'), ('R79', '+1V8', 'CODEC_1V8', 'rail')]
REN = {absorbed: keep for _, keep, absorbed, _ in LINKS}
REFS = {r for r, *_ in LINKS}
# blocked signal joins: via a, via b, track a-b on `layer`, plus F.Cu stubs from the vias to the copper that was on the pads
JUMPS = {'R48': dict(layer='SIG', a=(60.25, 60.74), b=(60.4, 61.85),     # SWDIO (F.Cu) and WAKEUP (B.Cu) cross the old pad gap
                     stubs=[((60.25, 60.74), (60.55, 60.55)), ((60.4, 61.85), (60.55, 61.75))])}
# vias a trimmed lead ends on that stay anyway: R70's +3V3 via shapes the B.Cu ground pour round J7 pad 33; without it
# the pour reaches that pad with one thermal spoke instead of two (starved_thermal). It is left as a +3V3 plane via.
KEEP_VIAS = {(77.21, 6.88)}
NOTES = [  # sheet, old text, new text
    ('supply', '(text "+3V3 rails"', '(text "+3V3: VDD_LPSR_IN, DCDC_IN and NVCC_GPIO / EMC1 / EMC2 / LPSR / DISP1 / DISP2 are the +3V3 net (no links)"'),
    ('supply', '(text "+1V8 rails"', '(text "+1V8: NVCC_SD1 is the +1V8 net; ADC_VREFH through R40"'),
    ('supply', 'RAIL ASSIGNMENT  (0R links in place of the EVKB jumpers)', 'RAIL ASSIGNMENT  (bank rails tied straight to +3V3 / +1V8; the EVKB uses jumpers)'),
    ('gpio', 'Rails are left as per-bank nets (NVCC_GPIO, NVCC_EMC1 ...) to be assigned to 1.8V/3.3V on the power-distribution sheet.',
             'Bank rails are tied straight to +3V3 (NVCC_SD1 to +1V8): the per-bank NVCC nets are merged into the rails.'),
    ('core', 'VDD_MIPI_1P0 is fed from the internal VDDA_1P0 LDO output via R4 (0R).', 'VDD_MIPI_1P0 is fed directly from the internal VDDA_1P0 LDO output (one net, VDDA_1P0).'),
    ('audio', 'VDDD = external 1.8 V (CODEC_1V8 via R79)', 'VDDD = external 1.8 V (+1V8)'),
    ('lcd', 'R67/R64/R72/R76/R77 are the EVKB 0R isolation links.', 'R67 (DNP) is the EVKB TE isolation link; the EVKB 0R links on the other control lines are replaced by direct connections.'),
    ('lcd', 'RAIL LINKS  (EVKB R1827/R1826/R846)', 'RAILS  (EVKB links R1827/R1826/R846 omitted: +1V8 / +3V3 / +5V go straight to the panel and touch controller)'),
]
# ---------------- schematic
for f in sorted(os.listdir(K)):
    if not f.endswith('.kicad_sch'): continue
    S0 = S = open(K + f).read()
    for m in list(re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "Device:R"\)\n\t\t\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\n.*?\n\t\)(?=\n)', S, re.S)):
        ref = re.search(r'\(property "Reference" "([^"]+)"', m.group(0)).group(1)
        if ref not in REFS: continue
        x, y, r = float(m.group(1)), float(m.group(2)), float(m.group(3))
        a = math.radians(r); ends = [(round(x - ly * math.sin(a), 2), round(y - ly * math.cos(a), 2)) for ly in (3.81, -3.81)]
        S = S.replace(m.group(0), '')
        for lm in list(re.finditer(r'\n\t\(global_label "([^"]+)"\n\t\t\(shape [a-z_]+\)\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)\n.*?\n\t\)(?=\n)', S, re.S)):
            if (round(float(lm.group(2)), 2), round(float(lm.group(3)), 2)) in ends: S = S.replace(lm.group(0), '')
        print('schematic %s: %s removed with its pin labels' % (f, ref))
    # PWR_FLAGs sitting on a label of an absorbed net (pin on the label's anchor, no wires): flag and label go
    for fm in list(re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "power:PWR_FLAG"\)\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)\n.*?\n\t\)(?=\n)', S, re.S)):
        at = (round(float(fm.group(1)), 2), round(float(fm.group(2)), 2))
        for lm in re.finditer(r'\n\t\(global_label "([^"]+)"\n\t\t\(shape [a-z_]+\)\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)\n.*?\n\t\)(?=\n)', S, re.S):
            if lm.group(1) in REN and (round(float(lm.group(2)), 2), round(float(lm.group(3)), 2)) == at:
                ref = re.search(r'\(property "Reference" "([^"]+)"', fm.group(0)).group(1)
                S = S.replace(fm.group(0), '').replace(lm.group(0), ''); print('schematic %s: %s on %s removed with its label' % (f, ref, lm.group(1))); break
    S = re.sub(r'\n\t\((global_label|label|hierarchical_label) "([^"]+)"', lambda m: '\n\t(%s "%s"' % (m.group(1), REN.get(m.group(2), m.group(2))), S)
    for sh, old, new in NOTES:
        if f == sh + '.kicad_sch' and old in S: S = S.replace(old, new)
    if S != S0: open(K + f, 'w').write(S); print('schematic %s: written' % f)
# ---------------- board
import pcbnew
from pcbnew import ToMM, FromMM
pcb = K + 'Nosh.kicad_pcb'; b = pcbnew.LoadBoard(pcb)
fps = {f.GetReference(): f for f in b.GetFootprints() if f.GetReference() in REFS}
if not fps: print('board: no links left'); sys.exit()
P = lambda v: (ToMM(v.x), ToMM(v.y))
def segdist(p, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L)); return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
def segseg(a, c, d, e):
    cr = lambda o, p, q: (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if cr(a, c, d) * cr(a, c, e) < 0 and cr(d, e, a) * cr(d, e, c) < 0: return 0.0      # the segments cross
    return min(segdist(a, d, e), segdist(c, d, e), segdist(d, a, c), segdist(e, a, c))
plan = []   # (layer, start, end, width, net)
jumps = []; trim = []      # trim: short leads into the pads of a link left to the plane, once the pad is gone
tracks = list(b.GetTracks())
for ref, keep, absorbed, kind in LINKS:
    f = fps.get(ref)
    if not f: continue
    L = f.GetLayer(); pads = sorted(f.Pads(), key=lambda p: p.GetNumber()); nets = {p.GetNetname() for p in pads}
    side = []
    for p in pads:
        c = P(p.GetPosition()); stubs = []
        for it in tracks:              # copper of the pad's net whose end (or via) overlaps the pad
            if it.GetNetname() != p.GetNetname(): continue
            if it.Type() == pcbnew.PCB_VIA_T:
                if p.HitTest(it.GetPosition(), int(it.GetWidth(L) / 2)):
                    v = P(it.GetPosition()); stubs.append((v, 0.2) if math.dist(v, c) > 0.01 else None)
            elif it.GetLayer() == L:
                ends = [e for e in (it.GetStart(), it.GetEnd()) if p.HitTest(e, int(it.GetWidth() / 2))]
                for e in ends:
                    e = P(e); stubs.append((e, ToMM(it.GetWidth())) if math.dist(e, c) > 0.01 else None)
                if not ends:                # a track crossing the pad: stub from the centre to its nearest point
                    s0, s1 = P(it.GetStart()), P(it.GetEnd()); n = max(2, int(math.dist(s0, s1) / 0.05))
                    on = [(s0[0] + (s1[0] - s0[0]) * k / n, s0[1] + (s1[1] - s0[1]) * k / n) for k in range(n + 1)]
                    if any(p.HitTest(pcbnew.VECTOR2I(FromMM(q[0]), FromMM(q[1])), int(it.GetWidth() / 2)) for q in on):
                        q = min(on, key=lambda q: math.dist(q, c)); stubs.append((q, ToMM(it.GetWidth())) if math.dist(q, c) > 0.01 else None)
        side.append((c, stubs))
    w = 0.2 if kind == 'signal' else (0.5 if ToMM(pads[0].GetSize().x) >= 0.75 else 0.4)
    (c1, s1), (c2, s2) = side
    # anything of another net near the bridge line on this layer (vias on every layer)
    block = []
    for t in tracks:
        if t.GetNetname() in nets: continue
        if t.Type() == pcbnew.PCB_VIA_T: d = segdist(P(t.GetPosition()), c1, c2) - ToMM(t.GetWidth(L)) / 2
        elif t.GetLayer() == L: d = segseg(P(t.GetStart()), P(t.GetEnd()), c1, c2) - ToMM(t.GetWidth()) / 2
        else: continue
        if d < w / 2 + 0.13: block.append('%s %s (%.2f mm off the line)' % ('via' if t.Type() == pcbnew.PCB_VIA_T else 'track', t.GetNetname(), d))
    if not s1 or not s2: print('%-4s %s -> %s: one pad has no copper (%d / %d items), no bridge needed' % (ref, absorbed, keep, len(s1), len(s2)))
    elif block:
        print('%-4s %s -> %s: SKIPPED bridge, in the way: %s' % (ref, absorbed, keep, '; '.join(block)))
        if ref in JUMPS: jumps.append((JUMPS[ref], keep)); print('      jump on %s instead' % JUMPS[ref]['layer'])
        else:                       # the pads' leads are now dead ends: follow each back to its first junction
            for p in pads:
                for t in tracks:
                    if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != L or t.GetNetname() != p.GetNetname() or t in trim: continue
                    ends = [e for e in (t.GetStart(), t.GetEnd()) if p.HitTest(e, int(t.GetWidth() / 2))]
                    if len(ends) != 1: continue
                    chain = [t]; q = t.GetEnd() if ends[0] == t.GetStart() else t.GetStart()
                    while True:
                        nxt = [o for o in tracks if o.Type() != pcbnew.PCB_VIA_T and o not in chain and o.GetNetname() == t.GetNetname()
                               and o.GetLayer() == L and (o.GetStart() == q or o.GetEnd() == q)]
                        vias = [o for o in tracks if o.Type() == pcbnew.PCB_VIA_T and o.GetNetname() == t.GetNetname() and o.HitTest(q, 0)]
                        others = [o for o in tracks if o.Type() != pcbnew.PCB_VIA_T and o not in chain and o.GetNetname() == t.GetNetname()
                                  and o.HitTest(q, 0) and o not in nxt]
                        pads_q = [x for g in b.GetFootprints() for x in g.Pads() if g.GetReference() not in REFS and x.HitTest(q) and x.GetNetname() == t.GetNetname()]
                        if len(nxt) == 1 and not vias and not others and not pads_q:
                            chain.append(nxt[0]); q = nxt[0].GetEnd() if nxt[0].GetStart() == q else nxt[0].GetStart(); continue
                        if len(vias) == 1 and not nxt and not others and not pads_q:
                            v = vias[0]; vp = v.GetPosition()
                            used = [o for o in tracks if o.Type() != pcbnew.PCB_VIA_T and o not in chain and o.GetNetname() == t.GetNetname()
                                    and (o.HitTest(vp, int(v.GetWidth(L) / 2)) or v.HitTest(o.GetStart(), 0) or v.HitTest(o.GetEnd(), 0))]
                            if not used and tuple(round(c, 2) for c in P(vp)) not in KEEP_VIAS: chain.append(v)   # it only took this pad to the plane
                        break
                    trim.extend(chain)
                    print('      trim %d item(s) from (%.2f, %.2f): %.2f mm of track%s' % (len(chain), *P(ends[0]), sum(ToMM(c.GetLength()) for c in chain if c.Type() != pcbnew.PCB_VIA_T), ' + its via' if chain[-1].Type() == pcbnew.PCB_VIA_T else ''))
    else:
        for c, st in side:
            for s_ in st:
                if s_: plan.append((L, s_[0], c, s_[1], keep))
        plan.append((L, c1, c2, w, keep)); print('%-4s %s -> %s: bridge %.1f mm; items on the pads %d + %d' % (ref, absorbed, keep, w, len(s1), len(s2)))
if DRY: sys.exit()
for it in list(b.GetTracks()) + list(b.Zones()) + [p for f in b.GetFootprints() for p in f.Pads()]:
    if it.GetNetname() in REN: it.SetNet(b.FindNet(REN[it.GetNetname()]))
for L, s, e, w, net in plan:
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FromMM(s[0]), FromMM(s[1]))); t.SetEnd(pcbnew.VECTOR2I(FromMM(e[0]), FromMM(e[1])))
    t.SetWidth(FromMM(w)); t.SetLayer(L); t.SetNet(b.FindNet(net)); b.Add(t)
V = lambda q: pcbnew.VECTOR2I(FromMM(q[0]), FromMM(q[1]))
for j, net in jumps:
    for q in (j['a'], j['b']):
        v = pcbnew.PCB_VIA(b); v.SetPosition(V(q)); v.SetWidth(FromMM(0.45)); v.SetDrill(FromMM(0.3)); v.SetNet(b.FindNet(net)); b.Add(v)
    for L, (s_, e) in [(b.GetLayerID(j['layer']), (j['a'], j['b']))] + [(b.GetLayerID('F.Cu'), st) for st in j['stubs']]:
        t = pcbnew.PCB_TRACK(b); t.SetStart(V(s_)); t.SetEnd(V(e)); t.SetWidth(FromMM(0.1)); t.SetLayer(L); t.SetNet(b.FindNet(net)); b.Add(t)
for t in trim: b.Remove(t)
for f in fps.values(): b.Remove(f)            # last: no iteration after Remove (pcbnew's SWIG objects go stale)
b.Save(pcb); print('board: %d links removed, %d tracks added, %d jumps, nets renamed: %s' % (len(fps), len(plan), len(jumps), ', '.join('%s>%s' % kv for kv in REN.items())))
