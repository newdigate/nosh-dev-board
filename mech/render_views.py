"""Render review views of Nosh-enclosure.FCStd to out/*.png, then quit.

  /Applications/FreeCAD.app/Contents/Resources/bin/freecad \
      /Users/nicholasnewdigate/Development/nosh-dev-board/mech/render_views.py

Model frame: x = east, +y = the user's north (audio jacks), z up (display).
"""
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
COL = {'Carrier': (0.10, 0.45, 0.20), 'Panel': (0.03, 0.03, 0.04), 'Standoffs': (0.80, 0.65, 0.20),
       'Tray': (0.90, 0.55, 0.15), 'Lid': (0.30, 0.50, 0.80)}


BOUNDS = [-3.0, -36.0, 0.0, 157.0, 85.0, 36.0]  # scene box: x0, y0, z0, x1, y1, z1


def look(view, d, up=V(0, 0, 1), aspect=1.6, bounds=None):
    """Set an orthographic camera explicitly (setCameraOrientation animates and lags)."""
    b = bounds or BOUNDS
    d = V(*d).normalize()
    right = d.cross(up).normalize()
    up2 = right.cross(d)
    back = d * -1
    m = App.Matrix(right.x, up2.x, back.x, 0, right.y, up2.y, back.y, 0, right.z, up2.z, back.z, 0, 0, 0, 0, 1)
    rot = App.Rotation(m)
    c = V((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)
    ru = [abs((V(x, y, z) - c).dot(right)) for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]
    uu = [abs((V(x, y, z) - c).dot(up2)) for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]
    height = 2.1 * max(max(uu), max(ru) / aspect)
    pos = c - d * 600
    view.setCamera('#Inventor V2.1 ascii\n\nOrthographicCamera {\n viewportMapping ADJUST_CAMERA\n'
                   ' position %f %f %f\n orientation %f %f %f %f\n nearDistance 1\n farDistance 1500\n'
                   ' aspectRatio 1\n focalDistance 600\n height %f\n}\n' % (
                       pos.x, pos.y, pos.z, rot.Axis.x, rot.Axis.y, rot.Axis.z, rot.Angle, height))


def shot(view, name, d, up=V(0, 0, 1), w=1800, h=1100, bounds=None):
    look(view, d, up, float(w) / h, bounds)
    Gui.updateGui()
    view.saveImage(os.path.join(OUT, name + '.png'), w, h, 'White')
    open(os.path.join(OUT, 'render.log'), 'a').write(name + '\n')


def main():
    doc = App.openDocument(os.path.join(HERE, 'Nosh-enclosure.FCStd'))
    view = Gui.activeDocument().activeView()
    view.setCameraType('Orthographic')
    try:
        view.setAxisCross(False)
    except Exception:
        pass
    aux = []
    # a document saved by freecadcmd has no view data: everything opens hidden
    for o in doc.Objects:
        if o.TypeId in ('App::Part', 'Part::Feature') and o.ViewObject:
            o.ViewObject.Visibility = True
    for o in doc.Objects:
        if o.TypeId != 'Part::Feature':
            continue
        v = o.ViewObject
        if o.Name in COL:
            v.ShapeColor = COL[o.Name]
        elif o.Name.startswith('Plug_'):
            v.ShapeColor = (0.95, 0.2, 0.2)
            v.Transparency = 55
            aux.append(o)
        elif o.Name == 'RibbonKeepout':
            v.ShapeColor = (0.92, 0.92, 0.92)
        elif o.Name.startswith('Box_'):
            v.ShapeColor = (0.6, 0.6, 0.65)
        elif 'PCB' in o.Label:
            v.ShapeColor = (0.05, 0.35, 0.15)

    def plugs(on):
        for o in aux:
            o.ViewObject.Visibility = on

    tray, lid = doc.getObject('Tray'), doc.getObject('Lid')
    plugs(False)
    shot(view, '01_closed_from_south_east', (-1, 1, -0.8))
    shot(view, '02_closed_from_north_west', (1, -1, -0.8))
    shot(view, '03_top', (0, 0, -1), up=V(0, 1, 0))
    shot(view, '04_side_south_sd_ribbon', (0, 1, 0), h=600, bounds=[-3.0, -3.0, 0.0, 157.0, 85.0, 36.0])
    shot(view, '05_side_north_audio', (0, -1, 0), h=600, bounds=[-3.0, -3.0, 0.0, 157.0, 85.0, 36.0])
    shot(view, '06_side_east_usb', (-1, 0, 0), h=800)
    shot(view, '07_side_west_power', (1, 0, 0), h=800)
    shot(view, '08_underside', (-1, 1, 1))
    plugs(True)
    shot(view, '09_with_plug_keepouts', (-1, 1, -0.8))
    plugs(False)
    # exploded
    lid.Placement.Base = V(0, 0, 30)
    tray.Placement.Base = V(0, 0, -25)
    doc.recompute()
    shot(view, '10_exploded', (-1, 1, -0.5), h=1500, bounds=[-3.0, -36.0, -25.0, 157.0, 85.0, 66.0])
    lid.Placement.Base = V(0, 0, 0)
    tray.Placement.Base = V(0, 0, 0)
    # shells alone
    for o in doc.Objects:
        if hasattr(o, 'ViewObject') and o.ViewObject and o.Name not in ('Tray',):
            o.ViewObject.Visibility = False
    tray.ViewObject.Visibility = True
    doc.recompute()
    shot(view, '11_tray_alone', (-1, 1, -1), bounds=[-3.0, -3.0, 0.0, 157.0, 85.0, 16.0])
    tray.ViewObject.Visibility = False
    lid.ViewObject.Visibility = True
    shot(view, '12_lid_alone_inside', (-1, 1, 1), bounds=[-3.0, -3.0, 13.0, 157.0, 85.0, 36.0])
    # leave the document in a sensible state for the user and keep the view data
    for o in doc.Objects:
        if o.TypeId in ('App::Part', 'Part::Feature') and o.ViewObject:
            o.ViewObject.Visibility = True
    plugs(False)
    look(view, (-1, 1, -0.8))
    doc.save()


try:
    main()
except Exception:
    traceback.print_exc()
    open(os.path.join(OUT, 'render_error.txt'), 'w').write(traceback.format_exc())
for d in list(App.listDocuments()):
    App.closeDocument(d)
Gui.getMainWindow().close()
os._exit(0)
