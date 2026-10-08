"""Render a placement json (from place.py) as a PNG: boxes, labels, airwires, M.2 card."""
import json, math, sys
from PIL import Image, ImageDraw, ImageFont
import os
S = os.environ.get('GP', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work')) + '/'; os.makedirs(S, exist_ok=True)
M = json.load(open(S + 'model.json')); P = M['parts']; W, H = M['W'], M['H']
R = json.load(open(sys.argv[1])); st = R['state']; SC = 8
img = Image.new('RGB', (int(W * SC) + 20, int(H * SC) + 60), 'white'); d = ImageDraw.Draw(img)
try: font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 13); small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 10)
except Exception: font = small = ImageFont.load_default()
def X(x): return 10 + x * SC
def Y(y): return 10 + y * SC
def world(s, lx, ly):
    th = math.radians(s[2]); c, sn = math.sin(th) * 0 + math.cos(th), math.sin(th)
    return s[0] + lx * c + ly * sn, s[1] - lx * sn + ly * c
d.rectangle((X(0), Y(0), X(W), Y(H)), outline='black', width=2)
for x, y in ((3.8735, 5.2975), (151.1265, 5.2975), (151.1265, 78.2025), (3.8735, 78.2025)):
    d.ellipse((X(x - 1.75), Y(y - 1.75), X(x + 1.75), Y(y + 1.75)), outline='gray')
for e in R['edges']:
    n = e[4]; col = (200, 60, 60) if n.startswith('SEMC') else (60, 60, 200) if n.startswith(('MIPI', 'USB')) else (120, 120, 120)
    d.line((X(e[0]), Y(e[1]), X(e[2]), Y(e[3])), fill=col, width=1)
for r, s in st.items():
    x0, y0, x1, y1 = P[r]['box']
    pts = [world(s, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    poly = [(X(px), Y(py)) for px, py in pts]
    fill = (255, 230, 200) if r == 'U1' else (220, 240, 220) if r in ('U9', 'U10') else (230, 230, 250) if r.startswith('J') else (245, 245, 245)
    if r == 'J6':
        cp = [world(s, x, y) for x, y in ((-11, 0), (11, 0), (11, 32), (-11, 32))]
        d.polygon([(X(px), Y(py)) for px, py in cp], outline=(150, 150, 220), fill=(240, 240, 255))
    d.polygon(poly, outline='black' if not P[r]['fixed'] else 'gray', fill=fill)
    cx, cy = sum(p[0] for p in poly) / 4, sum(p[1] for p in poly) / 4
    d.text((cx - 4 * len(r), cy - 6), r, fill='black', font=font if (x1 - x0) > 5 else small)
d.text((12, Y(H) + 8), '%s seed %s: rats-nest %.0f mm, crossings %d, cost %.0f' % (R['scenario'], R['seed'], R['length'], R['crossings'], R['cost']), fill='black', font=font)
d.text((12, Y(H) + 28), 'red = SEMC, blue = MIPI/USB, grey = other; lines are MST airwires between macro parts (passives collapsed)', fill='gray', font=small)
img.save(sys.argv[2]); print('saved', sys.argv[2])
