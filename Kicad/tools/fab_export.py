"""Export the JLCPCB fabrication and assembly files for Nosh into fab/.

Usage: python3 Kicad/tools/fab_export.py [--no-tht] [--board PATH] [--out DIR]
       (plain python3; needs kicad-cli, looked up in $KICAD_CLI, PATH or the macOS app bundle)

Writes
  fab/gerbers/            Gerber (Protel extensions, no X2, mask subtracted from silk) + Excellon drill (one file, PTH and NPTH together, Gerber X2 map)
  fab/Nosh-gerbers.zip    the gerbers/ directory zipped, ready for the JLCPCB quote page
  fab/Nosh-bom.csv        JLCPCB BOM: Comment, Designator, Footprint, LCSC Part #, MPN  - one row per order code, DNP and no-part footprints left out
  fab/Nosh-cpl.csv        JLCPCB CPL: Designator, Mid X, Mid Y, Layer, Rotation  - fitted parts only, KiCad rotations (check the polarised parts in JLCPCB's preview)
  fab/README.md           the order settings and the part / layer summary of this export

--no-tht leaves the through-hole parts (the barrel jack J4 and the UART header J11) out of the BOM and CPL for hand soldering.
The LCSC numbers come from Kicad/tools/data/lcsc_parts.csv (regenerate it with lcsc_table.py after schematic edits).
"""
import argparse, csv, collections, datetime, os, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
COPPER = ['F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu']
OTHER = ['F.Paste', 'B.Paste', 'F.SilkS', 'B.SilkS', 'F.Mask', 'B.Mask', 'Edge.Cuts']


def find_cli():
    for c in [os.environ.get('KICAD_CLI'), shutil.which('kicad-cli'), '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli']:
        if c and os.path.exists(c):
            return c
    sys.exit('kicad-cli not found: set KICAD_CLI')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit('failed: %s\n%s%s' % (' '.join(cmd), r.stdout, r.stderr))
    return r.stdout


def via_summary(board):
    """(n at 0.45/0.2, n at 0.45/0.3, n at 0.5/0.3) from the board file text; other sizes abort so the README stays truthful."""
    import re
    s = open(board).read()
    counts = {}
    for m in re.finditer(r'\n\t\(via\b', s):
        blk = s[m.start():s.find('\n\t(', m.start() + 3)]
        size = re.search(r'\(size ([\d.]+)\)', blk).group(1)
        drill = re.search(r'\(drill ([\d.]+)\)', blk)
        key = (float(size), float(drill.group(1)) if drill else None)
        counts[key] = counts.get(key, 0) + 1
    known = {(0.45, 0.2), (0.45, 0.3), (0.5, 0.3)}
    if set(counts) - known:
        sys.exit('unexpected via sizes, update the README text in fab_export.py: %s' % sorted(set(counts) - known))
    return counts.get((0.45, 0.2), 0), counts.get((0.45, 0.3), 0), counts.get((0.5, 0.3), 0)


def read_parts(path):
    """lcsc_parts.csv -> {ref: (lcsc, mpn)} for fitted refs only (DNP refs carry a '(DNP)' suffix)."""
    parts = {}
    for row in csv.DictReader(open(path)):
        for ref in row['Refs'].split():
            if '(DNP)' not in ref:
                parts[ref] = (row['LCSC'], row['MPN'])
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', default=os.path.join(REPO, 'Kicad', 'Nosh.kicad_pcb'))
    ap.add_argument('--out', default=os.path.join(REPO, 'fab'))
    ap.add_argument('--no-tht', action='store_true', help='leave through-hole parts out of the BOM and CPL')
    a = ap.parse_args()
    cli = find_cli()
    gdir = os.path.join(a.out, 'gerbers')
    if os.path.isdir(gdir):
        shutil.rmtree(gdir)
    os.makedirs(gdir)

    # Gerbers and drill, with the settings JLCPCB's KiCad guide asks for
    run([cli, 'pcb', 'export', 'gerbers', '--layers', ','.join(COPPER + OTHER), '--no-x2', '--no-netlist',
         '--subtract-soldermask', '--check-zones', '--precision', '6', '-o', gdir + '/', a.board])
    run([cli, 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-zeros-format', 'decimal', '--excellon-units', 'mm',
         '--generate-map', '--map-format', 'gerberx2', '-o', gdir + '/', a.board])
    zpath = os.path.join(a.out, 'Nosh-gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)

    # Placement: kicad-cli already drops DNP parts and the footprints marked "exclude from position files"
    pos = os.path.join(a.out, 'pos-kicad.csv')
    cmd = [cli, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '--exclude-dnp', '-o', pos, a.board]
    if a.no_tht:
        cmd.insert(-2, '--exclude-fp-th')
    run(cmd)
    rows = list(csv.DictReader(open(pos)))
    os.remove(pos)

    parts = read_parts(os.path.join(HERE, 'data', 'lcsc_parts.csv'))
    missing = [r['Ref'] for r in rows if r['Ref'] not in parts]
    if missing:
        sys.exit('fitted footprints without an LCSC number in lcsc_parts.csv: ' + ' '.join(missing))

    with open(os.path.join(a.out, 'Nosh-cpl.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in sorted(rows, key=lambda r: (r['Side'], r['Ref'])):
            w.writerow([r['Ref'], '%.4f' % float(r['PosX']), '%.4f' % float(r['PosY']), 'Top' if r['Side'] == 'top' else 'Bottom', '%.1f' % float(r['Rot'])])

    groups = collections.OrderedDict()
    for r in rows:
        lcsc, mpn = parts[r['Ref']]
        g = groups.setdefault(lcsc, dict(refs=[], vals=set(), fps=set(), mpn=mpn))
        g['refs'].append(r['Ref']); g['vals'].add(r['Val']); g['fps'].add(r['Package'])
    with open(os.path.join(a.out, 'Nosh-bom.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'MPN'])
        for lcsc, g in groups.items():
            w.writerow([' / '.join(sorted(g['vals'])), ','.join(sorted(g['refs'])), ' / '.join(sorted(g['fps'])), lcsc, g['mpn']])

    tht = sorted(r['Ref'] for r in rows if r['Ref'] in ('J4', 'J11'))
    top = sum(r['Side'] == 'top' for r in rows); bot = len(rows) - top
    try:
        commit = subprocess.run(['git', '-C', REPO, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = '?'
    with open(os.path.join(a.out, 'README.md'), 'w') as f:
        f.write('# Nosh fabrication outputs\n\n'
                'Generated by `python3 Kicad/tools/fab_export.py%s` on %s from %s (commit %s).\n\n'
                % (' --no-tht' if a.no_tht else '', datetime.date.today().isoformat(), os.path.relpath(a.board, REPO), commit))
        f.write('| File | Contents |\n|---|---|\n'
                '| `Nosh-gerbers.zip` | %d Gerber/drill files: 6 copper layers, paste, silk, mask, edge cuts, one Excellon drill file (PTH + NPTH, slots as routed ovals) and its map |\n'
                '| `Nosh-bom.csv` | %d order codes covering %d fitted parts |\n'
                '| `Nosh-cpl.csv` | %d placements, %d top / %d bottom%s |\n\n'
                % (len(os.listdir(gdir)), len(groups), len(rows), len(rows), top, bot,
                   '' if a.no_tht else '; through-hole parts included: ' + ', '.join(tht)))
        f.write('## JLCPCB order settings\n\n'
                '- 6 layers, 1.6 mm, FR4 TG155 (chosen over TG135 for the two lead-free reflow passes and hand rework), 1 oz outer / 0.5 oz inner copper (0.5 oz inner keeps the 0.09 mm inner spacing allowed), any colour.\n'
                '- Order options worth the free day each: Confirm Production File = Yes, Confirm Parts Placement = Yes (rotation preview); Depanel boards & edge rail = Yes (JLCPCB rails go on the long edges; J5 pads sit 0.3 mm from the north V-score).\n'
                '- Surface finish: ENIG, 1U" gold (0.025 um, the IPC-4552 minimum and JLCPCB\'s standard). The gold is sacrificial and dissolves into the joint,'
                ' so 2U" adds nothing to wetting and only moves the small 0402 / 0.4 mm QFN joints toward Au embrittlement; thicker gold is for wiping contacts, which this board has none of.'
                ' OSP is also offered on 6 layers but was rejected: two reflow passes (70 bottom-side parts), hand soldering of J4/J11, test points and rework all want a finish that survives handling.\n'
                '- Stackup: Specify Stackup = Yes, JLC06161H-3313 (3313 prepreg, 0.0994 mm outer dielectric, 0.5 oz inner, finished 1.54 mm +-10%%). JLCPCB impedance calculator, 2026-11-03, L1 over L2:'
                ' the USB pairs (0.13 mm / 0.11 mm gap) come out ~85 R (USB 2.0 wants 90 +-15%%) and the MIPI pairs (0.13 / 0.13) ~90 R (D-PHY 80-125 R), so no impedance-control order is needed.'
                ' The 7628 and 2116 stackups put 0.21-0.22 mm under the outer layers (our pairs would read ~115-120 R) and 1080 only 0.076 mm (~75 R); do not pick those.\n'
                '- Via covering: "Epoxy Filled & Capped" (the 6-layer default) - the board has via-in-pad under the decoupling capacitors.\n'
                '- Min track / spacing: the 0.09 / 0.09 mm tier (board minimum 0.13 mm track, 0.09 mm spacing).\n'
                '- Min via hole size / diameter: choose "0.2 mm / (0.3/0.35 mm)". The board has %d vias at 0.2 mm drill in a 0.45 mm pad (0.125 mm ring),'
                ' %d at 0.3 mm drill in 0.45 mm (0.075 mm ring) and %d at 0.3 mm in 0.5 mm; the 0.2 mm drills carry JLCPCB\'s small-via surcharge. Smallest component hole 0.6 mm.\n'
                '- Assembly: both sides, standard parts; order the stencil for both sides; add BGA X-ray inspection.\n'
                '- Consigned / pre-ordered parts: U1 MIMXRT1176DVMAA (C1020237, reserved in the parts library) and U9/U10 AS4C32M16SB-6TIN (C1351095, four pre-ordered).\n'
                '- Through-hole: J4 barrel jack and J11 UART header are the only THT parts; run with `--no-tht` to leave them off the BOM/CPL and hand-solder them.\n'
                '- Rotation: the CPL carries KiCad rotations. Check every polarised part (SOT-23 family, QFN, WSON, TSSOP, TSOP, SOT-223, SOD/SMA diodes, BGA) in the JLCPCB placement preview before paying.\n'
                % via_summary(a.board))
    print('fab/: %d gerber files, %d BOM rows, %d placements (%d top / %d bottom)%s' % (len(os.listdir(gdir)), len(groups), len(rows), top, bot, ', THT left out' if a.no_tht else ''))


if __name__ == '__main__':
    main()
