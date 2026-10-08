import json, glob, os
S = os.path.dirname(os.path.abspath(__file__)) + '/'
rows = []
for f in sorted(glob.glob(S + 'run_*.json')) + [S + 'baseline.json']:
    R = json.load(open(f)); rows.append((R['cost'], R['length'], R['crossings'], R['scenario'], R['seed'], R['sides'], os.path.basename(f)))
rows.sort()
print('%-10s %-5s %8s %6s %7s  %s' % ('scenario', 'seed', 'cost', 'len', 'cross', 'sides'))
for c, L, X, sc, sd, sides, fn in rows:
    print('%-10s %-5s %8.0f %6.0f %7d  %s' % (sc, sd, c, L, X, ' '.join(k + ':' + v for k, v in sides.items())))
