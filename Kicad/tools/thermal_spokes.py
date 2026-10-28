"""Give starved thermal reliefs a second spoke: a short track from the pad into the pour beside it (run with KiCad's
bundled python3).   usage: thermal_spokes.py [board.kicad_pcb]      DRY=1 reports without writing the board
KiCad counts a track that runs from the pad to a point inside the zone fill as a spoke (how C9 was fixed in 6cd3999).
For every pad that kicad-cli DRC reports as starved_thermal, candidate tracks leave the pad centre in 16 directions
(0.3 mm wide first, then 0.2): the end must sit inside the filled pour with a margin, the track must stay CLR from
other nets' tracks, vias and pads, and directions that already have a spoke are skipped. The shortest candidate per
pad is tried; DRC (zones refilled) then checks that the pad is no longer starved and nothing new appeared; a pad
whose track causes a new violation moves on to its next candidate."""
import sys, os, re, json, math, uuid, shutil, subprocess, tempfile, collections
import pcbnew
from pcbnew import ToMM, FromMM
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
SRC = sys.argv[1] if len(sys.argv) > 1 else K + 'Nosh.kicad_pcb'
DRY = bool(os.environ.get('DRY'))
CLR, MARGIN = 0.15, 0.1                     # mm: to other nets; end of the track inside the pour
text = open(SRC).read()
tmp = tempfile.mkdtemp()
for ext in ('kicad_pro', 'kicad_dru'):
    if os.path.exists(K + 'Nosh.' + ext): shutil.copy(K + 'Nosh.' + ext, tmp + '/Nosh.' + ext)
def drc(board_text, save=False):
    open(tmp + '/Nosh.kicad_pcb', 'w').write(board_text)
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--refill-zones', '--severity-all'] + (['--save-board'] if save else [])
                   + ['-o', tmp + '/drc.json', tmp + '/Nosh.kicad_pcb'], check=True, capture_output=True)
    d = json.load(open(tmp + '/drc.json'))
    if sum(1 for v in d['violations'] if v['type'] == 'clearance') > 300: sys.exit('the rules file did not load (hundreds of clearance errors): stopping')
    return d
WATCH = {'connection_width', 'hole_to_hole', 'track_dangling', 'via_dangling'}
key = lambda v: (v['type'], tuple(sorted(i['description'] for i in v['items'])))
relevant = lambda v: (v['severity'] == 'error' or v['type'] in WATCH) and v['type'] != 'starved_thermal'
PADRE = re.compile(r'Pad (\S+) \[([^\]]*)\] of (\S+) on (\S+)')
def starved(d):
    out = {}
    for v in d['violations']:
        if v['type'] != 'starved_thermal': continue
        for i in v['items']:
            m = PADRE.match(i['description'])
            if m: out[(m.group(3), m.group(1))] = dict(net=m.group(2), layer=m.group(4), zone=v['items'][0]['description'])
    return out
base = drc(text, save=True); base_keys = collections.Counter(key(v) for v in base['violations'] if relevant(v)); base_open = len(base['unconnected_items'])
todo = starved(base)
print('starved thermals: %s' % ', '.join('%s.%s' % k for k in sorted(todo)), flush=True)
b = pcbnew.LoadBoard(tmp + '/Nosh.kicad_pcb')                    # saved by DRC with the zones filled
def candidates(ref, num, info):
    fp = b.FindFootprintByReference(ref); pad = [p for p in fp.Pads() if p.GetNumber() == num][0]
    layer = b.GetLayerID(info['layer']); net = pad.GetNetname()
    fills = [z.GetFilledPolysList(layer) for z in b.Zones() if z.GetNetname() == net and z.IsOnLayer(layer) and not z.GetIsRuleArea()]
    infill = lambda x, y: any(f.Contains(pcbnew.VECTOR2I(FromMM(x), FromMM(y))) for f in fills)
    foreign = [t for t in b.GetTracks() if t.GetNetname() != net and (t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() == layer)]
    foreign += [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() != net and p.IsOnLayer(layer)]
    cx, cy = ToMM(pad.GetPosition().x), ToMM(pad.GetPosition().y)
    out = []
    for w in (0.3, 0.2):
        for k in range(16):
            a = k * math.pi / 8; ux, uy = math.cos(a), math.sin(a)
            r0 = 0.0                                                # leave the pad: first point no longer on it
            while pad.HitTest(pcbnew.VECTOR2I(FromMM(cx + ux * r0), FromMM(cy + uy * r0)), 0): r0 += 0.02
            if infill(cx + ux * (r0 + 0.12), cy + uy * (r0 + 0.12)): continue     # a spoke already leaves this way
            for L in [r0 + 0.2 + 0.05 * i for i in range(17)]:
                ex, ey = cx + ux * L, cy + uy * L; rr = w / 2 + MARGIN
                if not all(infill(ex + rr * math.cos(t * math.pi / 4), ey + rr * math.sin(t * math.pi / 4)) for t in range(8)) or not infill(ex, ey): continue
                pts = [(cx + ux * s, cy + uy * s) for s in [r0 + 0.05 * i for i in range(int((L - r0) / 0.05) + 1)] + [L]]
                acc = FromMM(w / 2 + CLR)
                if any(o.HitTest(pcbnew.VECTOR2I(FromMM(x), FromMM(y)), acc) for x, y in pts for o in foreign): continue
                out.append(dict(w=w, start=(cx, cy), end=(round(ex, 3), round(ey, 3)), L=L, layer=info['layer'], net=net, deg=k * 22.5))
                break
    return sorted(out, key=lambda c: (-c['w'], c['L']))
cands = {k: candidates(k[0], k[1], v) for k, v in todo.items()}
for k, c in sorted(cands.items()): print('  %s.%s: %d candidates%s' % (k[0], k[1], len(c), '' if c else '  (none: needs a hand fix)'))
def seg(c, u):
    return ('\n\t(segment\n\t\t(start %g %g)\n\t\t(end %g %g)\n\t\t(width %g)\n\t\t(layer "%s")\n\t\t(net "%s")\n\t\t(uuid "%s")\n\t)'
            % (c['start'][0], c['start'][1], c['end'][0], c['end'][1], c['w'], c['layer'], c['net'], u))
at = text.rindex('\n\t)', 0, text.index('\n\t(via')) + 3              # after the last segment, before the vias
def board_with(chosen):
    return text[:at] + ''.join(seg(c, u) for k, (c, u) in sorted(chosen.items())) + text[at:]
pick = {k: 0 for k, c in cands.items() if c}
for rnd in range(1, 9):
    chosen = {k: (cands[k][i], str(uuid.uuid4())) for k, i in pick.items()}
    d = drc(board_with(chosen)); left = starved(d); seen = collections.Counter(); bad = set()
    for v in d['violations']:
        if not relevant(v): continue
        kk = key(v); seen[kk] += 1
        if seen[kk] <= base_keys[kk]: continue
        ids = {i.get('uuid') for i in v['items']}; hit = [k for k, (c, u) in chosen.items() if u in ids]
        if not hit:                                                  # a pour neck etc.: blame the nearest new track
            p = [(i['pos']['x'], i['pos']['y']) for i in v['items'] if (i['pos']['x'], i['pos']['y']) != (0.5, 0.5)]
            hit = [min(chosen, key=lambda k: min(math.dist(q, chosen[k][0]['end']) for q in p))] if p else []
        bad.update(hit); print('  new %s at %s -> %s' % (v['type'], [i['description'][:40] for i in v['items']], hit))
    bad |= {k for k in chosen if k in left}                         # still starved: that track did not count
    opened = len(d['unconnected_items']) - base_open
    print('round %d: %d tracks, %d still starved, %d new violations%s' % (rnd, len(chosen), len(left), len(bad), '' if opened <= 0 else ', %d new open!' % opened), flush=True)
    if not bad and opened <= 0: break
    for k in bad:
        pick[k] += 1
        if pick[k] >= len(cands[k]): print('  %s.%s: out of candidates' % k); del pick[k]
else: sys.exit('did not settle')
for k, (c, u) in sorted(chosen.items()):
    print('  %s.%s %s: %.1f mm track %g mm wide, (%.2f, %.2f) -> (%.2f, %.2f), heading %g deg' % (k[0], k[1], c['net'], c['L'], c['w'], *c['start'], *c['end'], c['deg']))
print('starved thermals left:', ', '.join('%s.%s' % k for k in sorted(left)) or 'none')
if not DRY: open(SRC, 'w').write(board_with(chosen)); print('written:', SRC)
