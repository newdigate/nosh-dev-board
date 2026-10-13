"""Clear the routed copper out of a band next to the BGA (run with KiCad's bundled python3) so the escape ends there
can be continued and the north-south highways re-routed. usage: band_strip.py in out x0 y0 x1 y1 base.kicad_pcb
Inside the window every track and via that is NOT in the base board (the pre-greedy board: escapes, stitching,
plane vias) is removed, SEMC copper and BGA fan-outs stay; pieces of routes that crossed the window are left
outside it (the router joins them again); with WHOLE=1 the crossing nets lose all their routed copper instead and are
routed afresh. Prints the nets touched."""
import sys, os, math, collections, pcbnew
from pcbnew import ToMM
IN, OUT = sys.argv[1], sys.argv[2]; X0, Y0, X1, Y1 = map(float, sys.argv[3:7]); BASE = sys.argv[7]
def key(t):
    if t.Type() == pcbnew.PCB_VIA_T: return ('v', t.GetNetname(), round(ToMM(t.GetPosition().x), 3), round(ToMM(t.GetPosition().y), 3))
    a = (round(ToMM(t.GetStart().x), 3), round(ToMM(t.GetStart().y), 3)); c = (round(ToMM(t.GetEnd().x), 3), round(ToMM(t.GetEnd().y), 3))
    return ('t', t.GetNetname(), t.GetLayer(), min(a, c), max(a, c))
base = {key(t) for t in pcbnew.LoadBoard(BASE).GetTracks()}
b = pcbnew.LoadBoard(IN); balls = collections.defaultdict(list)
for f in b.GetFootprints():
    if f.GetReference() == 'U1':
        for p in f.Pads(): balls[p.GetNetname()].append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)))
def fanout(t):
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
        return any(abs(abs(x - bx) - 0.4) < 0.02 and abs(abs(y - by) - 0.4) < 0.02 for bx, by in balls.get(net, ()))
    a, c = (ToMM(t.GetStart().x), ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
    return math.hypot(a[0] - c[0], a[1] - c[1]) < 0.6 and any(math.hypot(q[0] - bx, q[1] - by) < 0.02 for q in (a, c) for bx, by in balls.get(net, ()))
def inside(t):
    if t.Type() == pcbnew.PCB_VIA_T: x0 = x1 = ToMM(t.GetPosition().x); y0 = y1 = ToMM(t.GetPosition().y)
    else: x0, x1 = sorted((ToMM(t.GetStart().x), ToMM(t.GetEnd().x))); y0, y1 = sorted((ToMM(t.GetStart().y), ToMM(t.GetEnd().y)))
    return x1 > X0 and x0 < X1 and y1 > Y0 and y0 < Y1
rm = [t for t in b.GetTracks() if inside(t) and key(t) not in base and not t.GetNetname().startswith('SEMC') and not fanout(t)]
import re
POWER = re.compile(r'^(GND$|\+|VDD|NVCC|DCDC|SDRAM_3V3|WL_3V3|VSD|VLDO|USB\d_VBUS|USB\d_CON_VBUS|DC_IN|AUD_VDDA|CODEC_1V8|LCD_5V|LCD_IOVCC|CTP_3V3|ADC_VREFH)')
if os.environ.get('WHOLE') == '1':                     # signal nets that cross the window lose all their routed copper (routed afresh); power nets only the pieces inside
    nets_in = {t.GetNetname() for t in rm if not POWER.match(t.GetNetname())}
    rm = [t for t in rm if POWER.match(t.GetNetname())] + [t for t in b.GetTracks() if t.GetNetname() in nets_in and key(t) not in base and not fanout(t)]
nets = collections.Counter(t.GetNetname() for t in rm)
for t in rm: b.Remove(t)
pcbnew.SaveBoard(OUT, b)
print('removed %d items of %d nets from %.1f..%.1f x %.1f..%.1f -> %s' % (len(rm), len(nets), X0, X1, Y0, Y1, OUT))
print('nets: ' + ','.join(sorted(nets)))
