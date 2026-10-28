"""Delete dangling copper (tracks with an unconnected end, vias connected on one layer or none), verified by KiCad's
own DRC (plain python3 is enough; kicad-cli does the work).
usage: remove_dangling.py [board.kicad_pcb]      default board: Kicad/Nosh.kicad_pcb;  DRY=1 reports without writing
Every round runs kicad-cli DRC on a scratch copy (zones refilled, the project's rules) and deletes what it flags as
track_dangling / via_dangling; removing a stub can leave the segment or via behind it dangling, so it repeats until
nothing is flagged. A deletion that opens a connection (a via sitting on a dangling track's middle still joins it) is
put back and kept. The board is written only if the final DRC has no more opens and no error the original lacks."""
import sys, os, re, json, shutil, subprocess, tempfile, collections, math
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
SRC = sys.argv[1] if len(sys.argv) > 1 else K + 'Nosh.kicad_pcb'
DRY = bool(os.environ.get('DRY'))
text = open(SRC).read()
tmp = tempfile.mkdtemp()
for ext in ('kicad_pro', 'kicad_dru'):
    if os.path.exists(K + 'Nosh.' + ext): shutil.copy(K + 'Nosh.' + ext, tmp + '/Nosh.' + ext)
def drc(board_text):
    open(tmp + '/Nosh.kicad_pcb', 'w').write(board_text)
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--refill-zones', '--severity-all', '-o', tmp + '/drc.json', tmp + '/Nosh.kicad_pcb'], check=True, capture_output=True)
    d = json.load(open(tmp + '/drc.json'))
    if sum(1 for v in d['violations'] if v['type'] == 'clearance') > 300: sys.exit('the rules file did not load (hundreds of clearance errors): stopping')
    return d
def block(t, uid):
    """span of the top-level (segment / via / arc ...) block holding this uuid"""
    i = t.index('(uuid "%s")' % uid); s = t.rindex('\n\t(', 0, i); e = t.index('\n\t)', i) + 3
    return s, e
DANGLING = {'track_dangling', 'via_dangling'}
key = lambda v: (v['type'], tuple(sorted(i['description'] for i in v['items'])))
errors = lambda d: collections.Counter(key(v) for v in d['violations'] if v['severity'] == 'error')
base = drc(text); base_err = errors(base); base_open = len(base['unconnected_items'])
print('baseline: %d errors, %d open, %d dangling' % (sum(base_err.values()), base_open, sum(1 for v in base['violations'] if v['type'] in DANGLING)), flush=True)
removed = {}; keep = set(); last = {}; d = base
for rnd in range(1, 21):
    opens = d['unconnected_items']
    if len(opens) > base_open:                                   # the last round broke something: put back what was near it
        pts = [(i['pos']['x'], i['pos']['y']) for o in opens for i in o['items']]
        back = [u for u, r in last.items() if any(math.dist(p, r['pos']) < 3 for p in pts)] or list(last)
        for u in back:
            s = last[u]['at']; text = text[:s] + last[u]['src'] + text[s:]; keep.add(u); del removed[u]
        print('round %d: %d new open -> %d put back' % (rnd, len(opens) - base_open, len(back)), flush=True)
        last = {}; d = drc(text); continue
    flagged = {i['uuid']: (v['type'], i['description'], (i['pos']['x'], i['pos']['y'])) for v in d['violations'] if v['type'] in DANGLING
               for i in v['items'] if i.get('uuid') and i['uuid'] not in keep}
    if not flagged: break
    last = {}
    for u, (typ, desc, pos) in sorted(flagged.items(), key=lambda kv: -block(text, kv[0])[0]):   # back to front: earlier offsets stay valid
        s, e = block(text, u); last[u] = dict(src=text[s:e], at=s, pos=pos); removed[u] = (typ, desc, pos); text = text[:s] + text[e:]
    print('round %d: %d dangling items deleted' % (rnd, len(flagged)), flush=True)
    d = drc(text)
else: sys.exit('did not settle in 20 rounds')
new_err = errors(d) - base_err
print('result: %d items deleted, %d kept (their removal opened a connection); %d open (was %d); dangling left: %d' % (
    len(removed), len(keep), len(d['unconnected_items']), base_open, sum(1 for v in d['violations'] if v['type'] in DANGLING)))
for k, n in new_err.items(): print('  NEW error:', k)
by_net = collections.defaultdict(list)
for u, (typ, desc, pos) in removed.items():
    by_net[re.search(r'\[([^\]]*)\]', desc).group(1)].append('%s (%.2f, %.2f)%s' % ('via' if typ == 'via_dangling' else 'track', pos[0], pos[1],
                                                                              (' ' + desc.split(', ')[-1]) if 'length' in desc else ''))
for n in sorted(by_net): print('  %-18s %s' % (n, '; '.join(by_net[n])))
if new_err or len(d['unconnected_items']) > base_open: sys.exit('not written: the result has new errors or opens (scratch: %s)' % tmp)
if not DRY: open(SRC, 'w').write(text); print('written:', SRC)
