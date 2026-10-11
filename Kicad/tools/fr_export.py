"""Export the board for Freerouting (run with KiCad's bundled python3; the board file is not modified).
usage: fr_export.py board.kicad_pcb out.dsn
- the outer GND pours (GND_F, GND_B) are left out: Freerouting would treat them as copper areas on the signal layers
- through-hole padstacks ("[A]" in KiCad's naming) grow by 0.073 mm on every side, so Freerouting's 0.127 mm class
  clearance becomes JLCPCB's 0.2 mm pad-to-trace rule for through-hole pads
- every existing track and via exports as fixed if it is locked (lock everything that must stay before exporting)
"""
import sys, re, pcbnew
SRC, OUT = sys.argv[1], sys.argv[2]
GROW = 73                                            # um per side (DSN units are um)
b = pcbnew.LoadBoard(SRC)
for z in [z for z in b.Zones() if z.GetZoneName() in ('GND_F', 'GND_B')]: b.Remove(z)
assert pcbnew.ExportSpecctraDSN(b, OUT), 'export failed'
s = open(OUT).read()
assert '(resolution um 10)' in s, 'unexpected DSN units'
def grow(m):
    block = m.group(0)
    block = re.sub(r'\(circle (\S+) ([\d.]+)', lambda c: '(circle %s %g' % (c.group(1), float(c.group(2)) + 2 * GROW), block)
    block = re.sub(r'\(rect (\S+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)\)', lambda r: '(rect %s %g %g %g %g)' % (
        r.group(1), min(float(r.group(2)), float(r.group(4))) - GROW, min(float(r.group(3)), float(r.group(5))) - GROW,
        max(float(r.group(2)), float(r.group(4))) + GROW, max(float(r.group(3)), float(r.group(5))) + GROW), block)
    block = re.sub(r'\(path (\S+) ([\d.]+)', lambda p: '(path %s %g' % (p.group(1), float(p.group(2)) + 2 * GROW), block)
    block = re.sub(r'\(polygon (\S+) ([\d.]+)', lambda p: '(polygon %s %g' % (p.group(1), max(float(p.group(2)), 2 * GROW)), block)
    return block
s, n = re.subn(r'\(padstack "?[A-Za-z]*\[A\][^\n]*\n(?:      [^\n]*\n)*?    \)', grow, s)
open(OUT, 'w').write(s)
print('exported %s: %d through-hole padstacks grown by %.3f mm per side, %d fixed wires/vias' % (OUT, n, GROW / 1000, s.count('(type fix)')))
