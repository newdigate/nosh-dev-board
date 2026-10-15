"""Replace the 0R link R6 (DCDC_DIG -> VDD_SOC_IN) with a net tie NT1 (run with KiCad's bundled python3).
usage: r6_nettie.py [kicad_dir]          default: the Kicad/ folder this script lives under
Idempotent: each step is skipped when already done, so it can be re-run if KiCad saves an older copy over a file.
  1. Nosh.pretty/NetTie-2_SMD_0805: an 0805 land pattern (pads 1.025 x 1.4 mm, 1.825 mm pitch, copper only) joined by
     an F.Cu bridge, net_tie_pad_groups "1, 2", excluded from BOM and placement files. Same pads as R6, so the
     routing that lands on R6 lands on NT1 unchanged. The bridge is 0.55 mm wide and runs along the local +y half of
     the pad gap (y -0.05..0.5): the routing has a +1V8 via in the other half, at local (0, -0.45) = board (73.5, 62.7),
     which a centred bridge would short; this leaves 0.175 mm to its copper and 0.25 mm to its hole.
  2. power.kicad_sch: R6 (Device:R, 0R, C17477) -> NT1 (Device:NetTie_2, rotated so pin 1 faces the DCDC_DIG label),
     same symbol UUID and instance path; two 1.27 mm wire stubs reach the existing labels; the EVKB note updated.
  3. Nosh.kicad_pcb: the R6 footprint swapped for NT1 at the same place, side and rotation, same path, pad nets kept."""
import sys, os, re, uuid
K = (sys.argv[1].rstrip('/') + '/') if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + '/'
FP = 'NetTie-2_SMD_0805'
U = lambda: str(uuid.uuid4())
# ---- 1. footprint
fpf = K + 'Nosh.pretty/' + FP + '.kicad_mod'
if not os.path.exists(fpf):
    font = '(effects\n\t\t\t(font\n\t\t\t\t(size %s %s)\n\t\t\t\t(thickness %s)\n\t\t\t)\n\t\t)'
    def prop(name, val, at, layer, hide):
        return ('\t(property "%s" "%s"\n\t\t(at %s)\n%s\t\t(layer "%s")\n%s\t\t(uuid "%s")\n\t\t%s\n\t)\n'
                % (name, val, at, '' if name in ('Reference', 'Value') else '\t\t(unlocked yes)\n', layer, '\t\t(hide yes)\n' if hide else '', U(),
                   font % (('1', '1', '0.15') if name in ('Reference', 'Value') else ('1.27', '1.27', '0.15'))))
    def rect(x0, y0, x1, y1, w, layer, fill):
        return ('\t(fp_rect\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n\t\t\t(width %s)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill %s)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n\t)\n'
                % (x0, y0, x1, y1, w, 'yes' if fill else 'no', layer, U()))
    def pad(n, x):
        return ('\t(pad "%s" smd roundrect\n\t\t(at %s 0)\n\t\t(size 1.025 1.4)\n\t\t(layers "F.Cu")\n\t\t(roundrect_rratio 0.243902)\n\t\t(uuid "%s")\n\t)\n' % (n, x, U()))
    s = ('(footprint "%s"\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n\t(layer "F.Cu")\n'
         '\t(descr "Net tie, 2 pin, on an 0805 (2012 Metric) land pattern: a drop-in for an 0805 0R link. The 0.55 mm copper bridge runs along one side of the pad gap (local y -0.05 to 0.5) so a via can sit in the other half")\n'
         '\t(tags "net tie 0805")\n' % FP)
    s += prop('Reference', 'REF**', '-2.525 0 0', 'F.SilkS', False) + prop('Value', FP, '0 1.65 0', 'F.Fab', True)
    s += prop('Datasheet', '', '0 0 0', 'F.Fab', True) + prop('Description', '', '0 0 0', 'F.Fab', True)
    s += '\t(attr smd exclude_from_pos_files exclude_from_bom)\n\t(net_tie_pad_groups "1, 2")\n\t(duplicate_pad_numbers_are_jumpers no)\n'
    s += ('\t(fp_poly\n\t\t(pts\n\t\t\t(xy -0.5 -0.05) (xy 0.5 -0.05) (xy 0.5 0.5) (xy -0.5 0.5)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type solid)\n\t\t)\n'
          '\t\t(fill yes)\n\t\t(layer "F.Cu")\n\t\t(uuid "%s")\n\t)\n' % U())
    s += rect(-1.68, -0.95, 1.68, 0.95, 0.05, 'F.CrtYd', False) + rect(-1, -0.625, 1, 0.625, 0.1, 'F.Fab', False)
    s += ('\t(fp_text user "${REFERENCE}"\n\t\t(at 0 0 0)\n\t\t(layer "F.Fab")\n\t\t(uuid "%s")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.5 0.5)\n\t\t\t\t(thickness 0.08)\n\t\t\t)\n\t\t)\n\t)\n' % U())
    s += pad('1', -0.9125) + pad('2', 0.9125) + '\t(embedded_fonts no)\n)\n'
    open(fpf, 'w').write(s); print('footprint written:', fpf)
else: print('footprint already there')
# ---- 2. schematic
sch = K + 'power.kicad_sch'; S = open(sch).read()
blocks = [m for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "Device:R"\)\n.*?\n\t\)(?=\n)', S, re.S) if '(property "Reference" "R6"' in m.group(0)]
if blocks:
    blk = blocks[0].group(0)
    at = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)', blk); x, y = float(at.group(1)), float(at.group(2))
    get = lambda pat: re.search(pat, blk).group(1)
    sym_uuid = get(r'\n\t\t\(uuid "([^"]+)"\)'); p1 = get(r'\(pin "1"\n\t\t\t\(uuid "([^"]+)"'); p2 = get(r'\(pin "2"\n\t\t\t\(uuid "([^"]+)"')
    inst = get(r'\(path "([^"]+)"')
    # field angles are stored relative to the symbol: 90 on a symbol turned 270 reads horizontally, as R6's did
    ref_at = re.sub(r' [-\d.]+$', ' 90', get(r'\(property "Reference" "R6"\n\t\t\t\(at ([^)]+)\)'))
    val_at = re.sub(r' [-\d.]+$', ' 90', get(r'\(property "Value" "0R"\n\t\t\t\(at ([^)]+)\)'))
    def field(name, val, at_, hide, justify=False):
        return ('\t\t(property "%s" "%s"\n\t\t\t(at %s)\n%s\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n%s\t\t\t)\n\t\t)\n'
                % (name, val, at_, '\t\t\t(hide yes)\n' if hide else '', '\t\t\t\t(justify left)\n' if justify else ''))
    nb = ('\n\t(symbol\n\t\t(lib_id "Device:NetTie_2")\n\t\t(at %g %g 270)\n\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom no)\n'
          '\t\t(on_board yes)\n\t\t(in_pos_files no)\n\t\t(dnp no)\n\t\t(uuid "%s")\n' % (x, y, sym_uuid))
    nb += field('Reference', 'NT1', ref_at, False, True) + field('Value', 'NetTie_2', val_at, False, True)
    nb += field('Footprint', 'Nosh:' + FP, '%g %g 0' % (x, y), True) + field('Datasheet', '', '%g %g 0' % (x, y), True)
    nb += field('Description', 'Net tie DCDC_DIG -> VDD_SOC_IN (EVKB: R1853 0R + J14)', '%g %g 0' % (x, y), True)
    nb += ('\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n\t\t(pin "2"\n\t\t\t(uuid "%s")\n\t\t)\n\t\t(instances\n\t\t\t(project "Nosh"\n\t\t\t\t(path "%s"\n'
           '\t\t\t\t\t(reference "NT1")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)' % (p1, p2, inst))
    S = S.replace(blk, nb)
    # Device:R pins end 3.81 mm from the centre, NetTie_2 pins 2.54 mm: stubs from the new pin ends to the old ones (the labels)
    wire = lambda ya, yb: '\n\t(wire\n\t\t(pts\n\t\t\t(xy %g %g) (xy %g %g)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)' % (x, ya, x, yb, U())
    i = S.index('\n\t(wire\n'); S = S[:i] + wire(round(y - 3.81, 2), round(y - 2.54, 2)) + wire(round(y + 2.54, 2), round(y + 3.81, 2)) + S[i:]
    S = S.replace('0R links per EVKB: R6 (R1853) DCDC_DIG -> VDD_SOC_IN;', 'Links per EVKB: net tie NT1 (R1853 0R + J14) DCDC_DIG -> VDD_SOC_IN;')
    print('schematic: R6 -> NT1')
else: print('schematic: no Device:R R6 (already converted?)')
if '(symbol "Device:NetTie_2"' not in S:
    D = open('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Device.kicad_sym').read()
    i = D.index('\n\t(symbol "NetTie_2"'); j = D.index('\n\t(symbol "', i + 10)
    lib = '\n'.join('\t' + l if l else l for l in D[i + 1:j].split('\n')).replace('\t\t(symbol "NetTie_2"', '\t\t(symbol "Device:NetTie_2"', 1)
    k = S.index('\t\t(symbol "Device:R"\n'); S = S[:k] + lib + '\n' + S[k:]
    print('schematic: Device:NetTie_2 added to lib_symbols')
open(sch, 'w').write(S)
# ---- 3. board
import pcbnew
pcb = K + 'Nosh.kicad_pcb'; b = pcbnew.LoadBoard(pcb)
old = [f for f in b.GetFootprints() if f.GetReference() == 'R6']
if old:
    old = old[0]; assert not old.IsFlipped(), 'R6 expected on the top side'
    pos, ori, path = old.GetPosition(), old.GetOrientation(), old.GetPath()
    rpos, rang, rvis = old.Reference().GetPosition(), old.Reference().GetTextAngle(), old.Reference().IsVisible()
    nets = {p.GetNumber(): p.GetNetname() for p in old.Pads()}
    new = pcbnew.FootprintLoad(K + 'Nosh.pretty', FP); new.SetFPID(pcbnew.LIB_ID('Nosh', FP))
    new.SetPosition(pos); new.SetOrientation(ori); new.SetPath(path)
    new.SetReference('NT1'); new.SetValue('NetTie_2'); new.SetField('Description', 'Net tie DCDC_DIG -> VDD_SOC_IN (EVKB: R1853 0R + J14)')   # as on the symbol (schematic parity)
    new.Reference().SetPosition(rpos); new.Reference().SetTextAngle(rang); new.Reference().SetVisible(rvis)
    for p in new.Pads(): p.SetNet(b.FindNet(nets[p.GetNumber()]))
    b.Add(new); b.Remove(old); b.Save(pcb)          # no iteration after Remove (pcbnew's SWIG objects go stale)
    print('board: R6 -> NT1 at (%.3f, %.3f), %s' % (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), nets))
else: print('board: no R6 footprint (already converted?)')
