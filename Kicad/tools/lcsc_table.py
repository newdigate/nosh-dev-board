"""Regenerate tools/data/lcsc_parts.csv from the LCSC/MPN properties on every sheet.

Usage: python3 Kicad/tools/lcsc_table.py   (paths are relative to this file)
"""
import re, csv, collections, os
K = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
rows = []
for sh in ['power', 'core', 'gpio', 'usb', 'supply', 'sdram', 'm2', 'sdcard', 'lcd', 'audio']:
    S = open(K + sh + '.kicad_sch').read()
    for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "[^"]+"\)', S):
        e = re.compile(r'\n\t\(').search(S, m.start() + 3).start(); blk = S[m.start():e]
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        no_part = '(lib_id "Connector:TestPoint")' in blk or '(lib_id "Mechanical:' in blk or '(lib_id "Device:NetTie' in blk   # net ties are copper, not parts
        if ref.startswith('#') or (no_part and not re.search(r'\(property "LCSC" "C\d+"', blk)): continue   # power symbols; test points, holes, fiducials unless they carry an LCSC part (H5 nut)
        val = re.search(r'\(property "Value" "([^"]*)"', blk).group(1)
        fp = re.search(r'\(property "Footprint" "([^"]*)"', blk).group(1).split(':')[-1]
        l = re.search(r'\(property "LCSC" "([^"]*)"', blk); p = re.search(r'\(property "MPN" "([^"]*)"', blk)
        dnp = '(dnp yes)' in blk
        rows.append((ref, val, fp, l.group(1) if l else '', p.group(1) if p else '', dnp))
seen = set(); uniq = []
for r in rows:
    if r[0] in seen: continue      # multi-unit parts (U1) count once
    seen.add(r[0]); uniq.append(r)
groups = collections.OrderedDict()
for ref, val, fp, l, p, dnp in uniq:
    groups.setdefault((l, p), []).append((ref, val, fp, dnp))
with open(K + 'tools/data/lcsc_parts.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['LCSC', 'MPN', 'Value', 'Footprint', 'Qty', 'Refs'])
    for (l, p), items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0])):
        fitted = [i for i in items if not i[3]]
        w.writerow([l, p, items[0][1], items[0][2], len(fitted), ' '.join(i[0] + ('(DNP)' if i[3] else '') for i in items)])
print(len(uniq), 'components,', len(groups), 'unique LCSC lines; without LCSC:', [r[0] for r in uniq if not r[3]])
