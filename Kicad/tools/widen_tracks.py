"""Widen a group of tracks wherever they fit, verified by KiCad's own DRC (run with KiCad's bundled python3).
usage: widen_tracks.py NET_REGEX FROM_MM TO_MM [board.kicad_pcb]      default board: Kicad/Nosh.kicad_pcb
       DRY=1 reports without writing the board; ONLY=file limits it to the track UUIDs listed in that file.
Every segment whose net matches NET_REGEX (full match) and whose width is FROM_MM is set to TO_MM on a scratch copy;
kicad-cli DRC (zones refilled, the project's rules) then runs repeatedly. A widened segment involved in a DRC error
or a new connection_width / hole_to_hole warning that the original board does not have goes back to FROM_MM (of
two widened segments in one violation, only one goes back per round); a new error without a widened segment in it
(a starved thermal relief or a narrow pour neck where the wider track squeezes the zone) sends back the widened
segments within 1 mm of it. Repeats until the scratch board has no new violations, then writes the board.
Example: widen_tracks.py 'SEMC_.*' 0.1 0.13"""
import sys, os, re, json, math, shutil, subprocess, tempfile, collections
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
pat, w0, w1 = re.compile(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
SRC = sys.argv[4] if len(sys.argv) > 4 else K + 'Nosh.kicad_pcb'
DRY = bool(os.environ.get('DRY'))
ONLY = set(open(os.environ['ONLY']).read().split()) if os.environ.get('ONLY') else None
text = open(SRC).read()
SEG = re.compile(r'\n\t\(segment\n\t\t\(start ([-\d.]+) ([-\d.]+)\)\n\t\t\(end ([-\d.]+) ([-\d.]+)\)\n\t\t\(width ([\d.]+)\)\n\t\t\(layer "([^"]+)"\)\n\t\t\(net "([^"]*)"\)\n\t\t\(uuid "([^"]+)"\)\n\t\)')
segs = {}
for m in SEG.finditer(text):
    x0, y0, x1, y1, w, layer, net, uid = m.groups()
    if pat.fullmatch(net) and abs(float(w) - w0) < 1e-6 and (ONLY is None or uid in ONLY):
        segs[uid] = dict(a=(float(x0), float(y0)), b=(float(x1), float(y1)), layer=layer, net=net, len=math.dist((float(x0), float(y0)), (float(x1), float(y1))))
print('%d segments of %s at %.3f mm (%.0f mm of track)' % (len(segs), sys.argv[1], w0, sum(s['len'] for s in segs.values())), flush=True)
def board_with(wide):
    def sub(m):
        if m.group(8) not in wide: return m.group(0)
        return m.group(0).replace('(width %s)' % m.group(5), '(width %g)' % w1, 1)
    return SEG.sub(sub, text)
tmp = tempfile.mkdtemp()
for ext in ('kicad_pro', 'kicad_dru'):
    if os.path.exists(K + 'Nosh.' + ext): shutil.copy(K + 'Nosh.' + ext, tmp + '/Nosh.' + ext)
def drc(board_text, guard=False):
    open(tmp + '/Nosh.kicad_pcb', 'w').write(board_text)
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--refill-zones', '--severity-all', '-o', tmp + '/drc.json', tmp + '/Nosh.kicad_pcb'], check=True, capture_output=True)
    d = json.load(open(tmp + '/drc.json'))
    if guard and sum(1 for v in d['violations'] if v['type'] == 'clearance') > 300: sys.exit('the rules file did not load (hundreds of clearance errors): stopping')
    return d
WATCH = {'connection_width', 'hole_to_hole'}
key = lambda v: (v['type'], tuple(sorted(i['description'] for i in v['items'])))
relevant = lambda v: v['severity'] == 'error' or v['type'] in WATCH
base = drc(text, guard=True); base_keys = collections.Counter(key(v) for v in base['violations'] if relevant(v)); base_open = len(base['unconnected_items'])
print('baseline: %d errors, %d open' % (sum(1 for v in base['violations'] if v['severity'] == 'error'), base_open), flush=True)
wide = set(segs)
for rnd in range(1, 11):
    d = drc(board_with(wide)); seen = collections.Counter(); back = set()
    for v in d['violations']:
        if not relevant(v): continue
        k = key(v); seen[k] += 1
        if seen[k] <= base_keys[k]: continue                       # the original board has this one too
        ids = [i.get('uuid') for i in v['items'] if i.get('uuid') in wide]
        if ids: back.add(sorted(ids, key=lambda u: segs[u]['len'])[0])   # the shorter one goes back
        else:
            for i in v['items']:
                p = (i['pos']['x'], i['pos']['y'])
                if p == (0.5, 0.5): continue                         # zones report the board origin
                for u in wide:
                    s = segs[u]; ax, ay = s['a']; bx, by = s['b']; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
                    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
                    if math.dist(p, (ax + t * dx, ay + t * dy)) < 1.0: back.add(u)
    opened = len(d['unconnected_items']) - base_open
    print('round %d: %d widened, %d new violations -> %d back to %.3f mm%s' % (rnd, len(wide), sum(max(0, seen[k] - base_keys[k]) for k in seen), len(back), w0,
          '' if opened <= 0 else '  (%d new opens!)' % opened), flush=True)
    if not back and opened <= 0:
        for v in d['violations']:                                   # new ones that no widened segment can explain:
            k = key(v)                                              # usually the same spot reported as another pair
            if relevant(v) and seen[k] > base_keys[k]: print('  left as is (not near a widened segment):', v['type'], [i['description'][:50] for i in v['items']])
        break
    if not back: sys.exit('new open connections without a widened segment to blame: stopping')
    wide -= back
else: sys.exit('did not settle in 10 rounds')
kept = set(segs) - wide
lay = lambda S: dict(collections.Counter(segs[u]['layer'] for u in S))
print('result: %d segments widened to %.3f mm (%.0f mm, %s); %d stay at %.3f mm (%.0f mm, %s)' % (
    len(wide), w1, sum(segs[u]['len'] for u in wide), lay(wide), len(kept), w0, sum(segs[u]['len'] for u in kept), lay(kept)))
json.dump(dict(widened=sorted(wide), kept=sorted(kept)), open(tmp + '/result.json', 'w')); print('scratch:', tmp)
if not DRY: open(SRC, 'w').write(board_with(wide)); print('written:', SRC)
