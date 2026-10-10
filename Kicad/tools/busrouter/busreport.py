"""Per-net length / via report for the SDRAM bus on a board file. usage: busreport.py board.kicad_pcb"""
import sys, re, collections, pcbnew
from pcbnew import ToMM
b = pcbnew.LoadBoard(sys.argv[1])
L = collections.defaultdict(float); V = collections.Counter(); LAYS = collections.defaultdict(set)
for t in b.GetTracks():
    n = t.GetNetname()
    if not re.match(r'^(SEMC_|U9_CLK$|U10_CLK$)', n): continue
    if t.Type() == pcbnew.PCB_VIA_T: V[n] += 1
    else: L[n] += ToMM(t.GetLength()); LAYS[n].add(b.GetLayerName(t.GetLayer()))
clk9 = L['SEMC_CLK'] + L['U9_CLK']; clk10 = L['SEMC_CLK'] + L['U10_CLK']
print('clock branches (upper bound, shared trunk counted fully): U9 %.1f mm  U10 %.1f mm' % (clk9, clk10))
groups = [('data lo  (U9 W, bottom)', [f'SEMC_D{i}' for i in range(8)] + ['SEMC_DM0'], clk9),
          ('data D8-15 (U9 E, top)', [f'SEMC_D{i}' for i in range(8, 16)] + ['SEMC_DM1'], clk9),
          ('data D24-31 (U10 E)', [f'SEMC_D{i}' for i in range(24, 32)] + ['SEMC_DM3'], clk10),
          ('data D16-23 (U10 W)', [f'SEMC_D{i}' for i in range(16, 24)] + ['SEMC_DM2'], clk10),
          ('address/control (both)', [f'SEMC_A{i}' for i in range(13)] + ['SEMC_BA0', 'SEMC_BA1', 'SEMC_CS0', 'SEMC_RAS', 'SEMC_CAS', 'SEMC_WE', 'SEMC_CKE'], clk10)]
for name, nets, clk in groups:
    ls = [L[n] for n in nets]; vs = [V[n] for n in nets]
    print('%-26s len %5.1f..%5.1f (spread %4.1f)  vs clk %+5.1f..%+5.1f  vias %d..%d avg %.1f  layers %s' % (
        name, min(ls), max(ls), max(ls) - min(ls), min(ls) - clk, max(ls) - clk, min(vs), max(vs), sum(vs) / len(vs), sorted(set().union(*[LAYS[n] for n in nets]))))
print()
for n in sorted(L, key=lambda s: (re.sub(r'\d+', '', s), int(re.search(r'(\d+)$', s).group(1)) if re.search(r'\d$', s) else 0)):
    print('  %-10s %5.1f mm  %d vias  %s' % (n, L[n], V[n], ','.join(sorted(LAYS[n]))))
conn = b.GetConnectivity(); print('unconnected (ratsnest) items on the board:', conn.GetUnconnectedCount(True))
