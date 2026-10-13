"""Fixed exits for the codec's west pads (run with KiCad's bundled python3). usage: u15_exits.py in out
U15's pads 16-20 sit at 0.4 mm pitch with the I2C pull-ups R74/R75 0.5 mm in front of them, and every router ran
one exit along the pad row and sealed the rest. The exits are laid by hand instead:
  pad 16 SAI1_RXD0  west 0.8 mm then north, joined to the net's via at (97.6, 67.0) where its B.Cu route ends,
  pad 17 SAI1_TXD0  west to a via at (96.45, 68.1) and 5 mm west on SIG under the pull-ups,
  pad 18 LPI2C5_SDA west then straight to R74.2 (R74/R75 swap places so SDA's pull-up is the upper one),
  pad 19 LPI2C5_SCL west then straight to R75.2 (now the lower one),
  pad 20 CODEC_1V8  west 0.85 mm then south (free below).
CODEC_1V8's old exit (north along the pad row) and NVCC_SD1's pieces in the corridor are removed; the routers
continue from the stub ends."""
import sys, math, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
IN, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(IN); fps = {f.GetReference(): f for f in b.GetFootprints()}; nets = b.GetNetInfo().NetsByName()
for ref, (x, y, rot) in {'R74': (95.5, 67.25, -90), 'R75': (95.5, 69.75, 90)}.items():
    f = fps[ref]; f.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); f.SetOrientationDegrees(rot)
    print('  %s -> (%.2f,%.2f): %s' % (ref, x, y, [(p.GetNumber(), p.GetNetname(), round(ToMM(p.GetPosition().x), 2), round(ToMM(p.GetPosition().y), 2)) for p in f.Pads()]))
rm = []
for t in b.GetTracks():
    net = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T: x0 = x1 = ToMM(t.GetPosition().x); y0 = y1 = ToMM(t.GetPosition().y)
    else: x0, x1 = sorted((ToMM(t.GetStart().x), ToMM(t.GetEnd().x))); y0, y1 = sorted((ToMM(t.GetStart().y), ToMM(t.GetEnd().y)))
    if net == 'CODEC_1V8' and x0 < 97.6 and x1 > 96.9 and y1 > 66.5 and y0 < 69.6: rm.append(t)          # the old exit along the pad row
    if net == 'NVCC_SD1' and x1 > 93.4 and x0 < 97.7 and y1 > 66.0 and y0 < 71.0: rm.append(t)           # its via and pieces in the corridor
for t in rm: b.Remove(t)
print('  removed %d items (CODEC_1V8 exit, NVCC_SD1 corridor pieces)' % len(rm))
F, SIG = pcbnew.F_Cu, b.GetLayerID('SIG')
def trk(net, layer, a, c, w=0.1):
    t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1]))); t.SetEnd(VECTOR2I(FromMM(c[0]), FromMM(c[1]))); t.SetWidth(FromMM(w)); t.SetLayer(layer); t.SetNet(nets[net]); t.SetLocked(True); b.Add(t)
def via(net, x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetWidth(FromMM(0.45)); v.SetDrill(FromMM(0.3)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets[net]); v.SetLocked(True); b.Add(v)
PX = 97.76
trk('SAI1_RXD0', F, (PX, 67.70), (96.95, 67.70)); trk('SAI1_RXD0', F, (96.95, 67.70), (96.95, 66.30))
trk('SAI1_RXD0', F, (96.95, 67.00), (97.60, 67.00))                                                   # joins the net's via at (97.6, 67.0) where its B.Cu route ends
trk('SAI1_TXD0', F, (PX, 68.10), (96.45, 68.10)); via('SAI1_TXD0', 96.45, 68.10); trk('SAI1_TXD0', SIG, (96.45, 68.10), (96.45, 68.30)); trk('SAI1_TXD0', SIG, (96.45, 68.30), (91.50, 68.30))
trk('LPI2C5_SDA', F, (PX, 68.50), (96.20, 68.50)); trk('LPI2C5_SDA', F, (96.20, 68.50), (95.50, 67.76))
trk('LPI2C5_SCL', F, (PX, 68.90), (96.50, 68.90)); trk('LPI2C5_SCL', F, (96.50, 68.90), (95.50, 69.24))
trk('CODEC_1V8', F, (PX, 69.30), (96.90, 69.30)); trk('CODEC_1V8', F, (96.90, 69.30), (96.90, 70.20))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for z in b.Zones():
    if z.GetZoneName() in ('GND_F', 'GND_B'): z.UnFill(); z.SetIsFilled(False)
pcbnew.SaveBoard(OUT, b); print('  exits laid -> ' + OUT)
