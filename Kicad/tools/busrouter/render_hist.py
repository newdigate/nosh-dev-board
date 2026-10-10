"""Heat map of where the bus router's nets kept overlapping (the history costs it dumps next to its output).
usage: render_hist.py <board.kicad_pcb> <out.png>      reads <board.kicad_pcb>.hist; region and grid must match busroute.py
"""
import sys, array
from PIL import Image, ImageDraw
X0, Y0, X1, Y1, G = 26.0, 14.0, 72.6, 60.0, 0.05
NX, NY = int(round((X1 - X0) / G)) + 1, int(round((Y1 - Y0) / G)) + 1
raw = open(sys.argv[1] + '.hist', 'rb').read()
layers = [array.array('H') for _ in range(3)]
for l in range(3): layers[l].frombytes(raw[l * 2 * NX * NY:(l + 1) * 2 * NX * NY])
tot = [layers[0][k] + layers[1][k] + layers[2][k] for k in range(NX * NY)]
mx = max(tot) or 1
img = Image.new('RGB', (NX, NY), 'white'); px = img.load()
for k, v in enumerate(tot):
    if not v: continue
    t = min(1.0, (v / mx) ** 0.5); c = [(0, 0, 255), (0, 200, 255), (255, 200, 0), (255, 0, 0)][min(3, int(t * 3.999))]
    # per-layer tint: which layer dominates
    l = max(range(3), key=lambda q: layers[q][k])
    px[k % NX, k // NX] = c if l != 0 else tuple(min(255, int(a * 0.8 + 50)) for a in c)
img = img.resize((NX, NY))
d = ImageDraw.Draw(img)
for x in range(30, 73, 5): d.line([((x - X0) / G, 0), ((x - X0) / G, 8)], fill='black'); d.text(((x - X0) / G + 2, 10), str(x), fill='black')
for y in range(15, 61, 5): d.line([(0, (y - Y0) / G), (8, (y - Y0) / G)], fill='black'); d.text((10, (y - Y0) / G - 5), str(y), fill='black')
img.save(sys.argv[2]); print('saved', sys.argv[2], 'max history', mx)
