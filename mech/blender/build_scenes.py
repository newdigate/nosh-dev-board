"""Build nosh_presentation.blend from scratch. Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_scenes.py -- [--model] [--stills [names]]
--model rebuilds build/model.blend (the geometry) first; it is also built when missing.
--stills renders the preview frames to out/ (optionally only the named ones, e.g. closed_0195).
Needs build/board.glb (export_board.sh). Reads ../params.py, ../board.json, ../out/*.stl.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as C  # noqa: E402
from common import mm  # noqa: E402
import materials as M  # noqa: E402
import label_rig as R  # noqa: E402
import labels as L  # noqa: E402


def collection(name, scene=None):
    scene = scene or bpy.context.scene
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        scene.collection.children.link(col)
    return col


def move_to(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def empty(name, col, location=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = 0.005
    o.location = location
    col.objects.link(o)
    if parent is not None:
        o.parent = parent
    return o


def build_board():
    """Import the GLB under an empty 'Nosh' so that world = the mech/ model frame."""
    scene = bpy.context.scene
    scene.name = 'Closed'
    col = collection('Board')
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=C.GLB)
    new = [o for o in bpy.data.objects if o not in before]
    nosh = empty('Nosh', col, (0, 0, mm(C.Z['split'])))
    nosh.rotation_euler = (math.pi, 0, 0)
    for o in new:
        move_to(o, col)
        if o.parent is None:
            o.parent = nosh
    bpy.context.view_layer.update()
    return nosh


# ---------------------------------------------------------------- mesh helpers
def box_obj(name, lo, hi, mat, col, parent=None):
    """Axis-aligned box from world mm corners."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = [mm((a + b) / 2) for a, b in zip(lo, hi)]
    o.scale = [mm(abs(b - a)) for a, b in zip(lo, hi)]
    me.materials.append(M.get(mat))
    col.objects.link(o)
    if parent is not None:
        attach(o, parent)
    return o


def attach(o, parent):
    """Parent keeping the world transform."""
    bpy.context.view_layer.update()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()


def cyl_obj(name, x, y, z0, z1, d, mat, col, parent=None, d_top=None, segments=32):
    """Vertical cylinder or cone frustum from world mm. Origin at the z0 end."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=mm(d / 2),
                          radius2=mm((d if d_top is None else d_top) / 2), depth=mm(abs(z1 - z0)))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, mm(abs(z1 - z0)) / 2))
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = (mm(x), mm(y), mm(z0))
    if z1 < z0:
        o.rotation_euler = (math.pi, 0, 0)
    me.materials.append(M.get(mat))
    col.objects.link(o)
    if parent is not None:
        attach(o, parent)
    return o


def join(name, objs):
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    objs[0].name = name
    objs[0].data.name = name
    return objs[0]


# ---------------------------------------------------------------- model
def named_part(ref, lo, hi, mat, col, nosh):
    """A stand-in body. If the board export already has an empty of that name, hang the body on it."""
    host = bpy.data.objects.get(ref)
    o = box_obj(ref if host is None else ref + '_Body', lo, hi, mat, col)
    attach(o, host if host is not None else nosh)
    return o


def build_standins(nosh):
    col = collection('Board')
    parts = C.BOARD['parts']
    zc, zs = C.Z['comp'], C.Z['split']
    mats = {'U1': 'ic_black', 'J2': 'metal', 'J6': 'ic_black', 'J7': 'ic_black', 'J8': 'ic_black', 'J9': 'ic_black'}
    for ref, mat in mats.items():
        x0, y0, x1, y1 = parts[ref]['body']
        h = C.params.BOXES[ref]
        if parts[ref]['side'] == 'TOP':
            named_part(ref, (x0, y0, zc - h), (x1, y1, zc), mat, col, nosh)
        else:
            named_part(ref, (x0, y0, zs), (x1, y1, zs + h), mat, col, nosh)
    for ref in ('U2', 'U15'):
        _, x, y, _side = C.FOOTPRINTS[ref]
        sx, sy, h = C.STANDIN_SIZE[ref]
        named_part(ref, (x - sx / 2, y - sy / 2, zc - h), (x + sx / 2, y + sy / 2, zc), 'ic_black', col, nosh)
    # audio jacks: a metal ring at the mouth so they read as 3.5 mm sockets
    for ref in ('J8', 'J9'):
        x0, y0, x1, y1 = parts[ref]['body']
        h = C.params.BOXES[ref]
        ring = cyl_obj(ref + '_Mouth', (x0 + x1) / 2, y1 - 0.45, 0, 0.6, 5.0, 'metal', col)
        ring.rotation_euler = (-math.pi / 2, 0, 0)   # axis along +Y, out of the board edge
        ring.location.z = mm(zc - h / 2)
        attach(ring, bpy.data.objects[ref])
    # M.2 radio card on its nut, and a microSD card in J5
    m = C.params.M2_CARD
    zt = zc - m['z_off']
    card = box_obj('M2_Card', (m['x0'], m['y0'], zt - 0.8), (m['x1'], m['y1'], zt), 'pcb_green', col)
    attach(card, nosh)
    can = box_obj('M2_Card_Shield', (m['x0'] + 2, m['y0'] + 4, zt - m['t']), (m['x1'] - 2, m['y1'] - 8, zt - 0.8), 'metal', col)
    attach(can, card)
    sd = C.params.SD
    x = C.FOOTPRINTS['J5'][1]
    z1 = zc - sd['card_d']
    sdc = box_obj('SD_Card', (x - sd['card_w'] / 2, -sd['locked_out'], z1 - sd['card_t']),
                  (x + sd['card_w'] / 2, -sd['locked_out'] + 15.0, z1), 'sd_card', col)
    attach(sdc, nosh)


def build_display():
    col = collection('Display')
    P, Zl = C.PARAMS, C.Z
    rk = empty('RK055', col, (0, 0, mm(Zl['car0'])))
    box_obj('RK055_Carrier', (0, 0, Zl['car0']), (P['board_w'], P['board_h'], Zl['car1']), 'pcb_black', col, rk)
    gx0, gy0 = P['glass_x0'], P['glass_y0']
    gx1, gy1 = gx0 + P['glass_w'], gy0 + P['glass_h']
    frame = box_obj('RK055_Glass', (gx0, gy0, Zl['car1']), (gx1, gy1, Zl['glass']), 'panel_frame', col, rk)
    # the cover glass is the top 0.7 mm of the module
    top = box_obj('RK055_Glass_Top', (gx0, gy0, Zl['glass'] - 0.7), (gx1, gy1, Zl['glass'] + 0.005), 'glass', col)
    attach(top, frame)
    # active area, datasheet 120.96 x 68.04, centred in the glass (assumed). Image top at +Y.
    cx, cy = (gx0 + gx1) / 2, (gy0 + gy1) / 2
    w, h, z = 120.96 / 2, 68.04 / 2, Zl['glass'] + 0.02
    me = bpy.data.meshes.new('RK055_Screen')
    me.from_pydata([(mm(cx - w), mm(cy - h), mm(z)), (mm(cx + w), mm(cy - h), mm(z)),
                    (mm(cx + w), mm(cy + h), mm(z)), (mm(cx - w), mm(cy + h), mm(z))], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for li, co in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = co
    me.materials.append(M.get('screen'))
    scr = bpy.data.objects.new('RK055_Screen', me)
    col.objects.link(scr)
    attach(scr, rk)
    for i, (x, y) in enumerate(C.BOARD['holes'].values(), 1):
        cyl_obj('RK055_Standoff_%d' % i, x, y, Zl['split'], Zl['car0'], P['standoff_d'], 'brass', col, rk, segments=6)
    build_ribbon(col, rk)
    return rk


def build_ribbon(col, rk):
    """Flat cable: from under the carrier out past the case on the board y = 0 side,
    round a loop and back in to J7 on the Nosh."""
    P, Zl = C.PARAMS, C.Z
    z_hi = Zl['car0'] - 0.4
    z_lo = Zl['split'] + 1.2
    r = (z_hi - z_lo) / 2
    y_out = -(P['clear'] + P['wall']) - 35.0 + r   # loop centre; the apex is 35 mm outside the case
    path = [(8.0, z_hi), (y_out, z_hi)]
    n = 24
    for k in range(1, n):
        a = math.pi * k / n
        path.append((y_out - r * math.sin(a), (z_hi + z_lo) / 2 + r * math.cos(a)))
    path += [(y_out, z_lo), (3.5, z_lo)]
    x0, x1 = P['ribbon_x'] - P['ribbon_w'] / 2, P['ribbon_x'] + P['ribbon_w'] / 2
    verts, faces = [], []
    for y, z in path:
        verts += [(mm(x0), mm(y), mm(z)), (mm(x1), mm(y), mm(z))]
    for k in range(len(path) - 1):
        faces.append((2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2))
    me = bpy.data.meshes.new('RK055_Ribbon')
    me.from_pydata(verts, [], faces)
    for f in me.polygons:
        f.use_smooth = True
    me.materials.append(M.get('ribbon'))
    o = bpy.data.objects.new('RK055_Ribbon', me)
    col.objects.link(o)
    sol = o.modifiers.new('Thickness', 'SOLIDIFY')
    sol.thickness = mm(0.25)
    attach(o, rk)
    apex = empty('Ribbon_Apex', col, (mm(P['ribbon_x']), mm(y_out - r), mm((z_hi + z_lo) / 2)))
    attach(apex, o)


def import_stl(name, filename, col):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=os.path.join(C.MECH, 'out', filename), global_scale=0.001)
    o = [x for x in bpy.data.objects if x not in before][0]
    o.name = name
    o.data.name = name
    move_to(o, col)
    o.data.materials.append(M.get('plastic_grey'))
    with bpy.context.temp_override(active_object=o, selected_editable_objects=[o], selected_objects=[o], object=o):
        bpy.ops.object.shade_auto_smooth(angle=math.radians(30))
    return o


def build_enclosure():
    col = collection('Enclosure')
    P, Zl = C.PARAMS, C.Z
    import_stl('Tray', 'tray.stl', col)
    lid = import_stl('Lid', 'lid.stl', col)
    # lid.stl is in print orientation: build_enclosure.py turned it 180 deg about X at z = face
    lid.rotation_euler = (math.pi, 0, 0)
    lid.location = (0, 0, mm(Zl['face']))
    head = 1.65  # DIN 7991 M3 head height
    for i, (x, y) in enumerate(C.BOARD['holes'].values(), 1):
        a = cyl_obj('Screw_Tray_%d' % i, x, y, 0.0, head, P['csk_d'] - 0.4, 'screw', col, d_top=3.0)
        b = cyl_obj('Screw_Tray_%d_Shaft' % i, x, y, head, P['tray_screw'], 3.0, 'screw', col)
        attach(b, a)
        a = cyl_obj('Screw_Lid_%d' % i, x, y, Zl['face'], Zl['face'] - head, P['csk_d'] - 0.4, 'screw', col, d_top=3.0)
        b = cyl_obj('Screw_Lid_%d_Shaft' % i, x, y, Zl['face'] - head, Zl['face'] - P['lid_screw'], 3.0, 'screw', col)
        attach(b, a)


def case_centre():
    P = C.PARAMS
    return (mm(P['board_w'] / 2), mm(P['board_h'] / 2), mm(C.Z['face'] / 2))


def build_studio():
    col = collection('Studio')
    cx, cy, _ = case_centre()
    me = bpy.data.meshes.new('Floor')
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=6.0)
    bm.to_mesh(me)
    bm.free()
    floor = bpy.data.objects.new('Floor', me)
    floor.location = (cx, cy, 0)
    me.materials.append(M.get('backdrop'))
    col.objects.link(floor)
    world = bpy.data.worlds.new('Studio')
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.80, 0.81, 0.83, 1.0)
    bg.inputs['Strength'].default_value = 0.45
    for sc in bpy.data.scenes:
        sc.world = world
    lights = [('Key', (-0.30, -0.35, 0.50), 1.6, 0.35), ('Fill', (0.45, -0.25, 0.30), 0.5, 0.50),
              ('Rim', (0.10, 0.50, 0.40), 0.9, 0.40)]
    target = empty('Light_Target', col, case_centre())
    for name, off, power, size in lights:
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = power
        ld.size = size
        lo = bpy.data.objects.new('Light_' + name, ld)
        lo.location = (cx + off[0], cy + off[1], off[2])
        col.objects.link(lo)
        tc = lo.constraints.new('TRACK_TO')
        tc.target = target
        tc.track_axis = 'TRACK_NEGATIVE_Z'
        tc.up_axis = 'UP_Y'


def setup_render(scene):
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.fps = 30
    scene.render.image_settings.file_format = 'PNG'
    scene.eevee.taa_render_samples = 32
    scene.eevee.use_raytracing = True
    scene.eevee.use_shadows = True
    scene.view_settings.view_transform = 'Standard'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'MILLIMETERS'


def add_camera(name, col, scene, lens=50.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.005
    cd.clip_end = 50.0
    cam = bpy.data.objects.new(name, cd)
    col.objects.link(cam)
    scene.camera = cam
    return cam


def orbit_pose(cam, azimuth_deg, elevation_deg, distance, target=None):
    """Place the camera on a sphere round the case centre. Azimuth 0 = looking from the
    board y = 0 side (microSD, the user's south) toward +Y; 90 = from the east (USB)."""
    t = Vector(target or case_centre())
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    pos = t + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * distance
    cam.location = pos
    cam.rotation_euler = (t - pos).to_track_quat('-Z', 'Y').to_euler()


def render_still(scene, path, frame=None, scale=50):
    if frame is not None:
        scene.frame_set(frame)
    scene.render.resolution_percentage = scale
    scene.render.filepath = path
    # rendering a scene other than the window's takes the frame from the window's scene,
    # so make this one current first
    if bpy.context.window is not None:
        bpy.context.window.scene = scene
        scene.frame_set(scene.frame_current)
        bpy.ops.render.render(write_still=True)
    else:
        with bpy.context.temp_override(scene=scene):
            bpy.ops.render.render(write_still=True)
    scene.render.resolution_percentage = 100


# ---------------------------------------------------------------- shots
MODEL = os.path.join(C.HERE, 'build', 'model.blend')
TOP_COLLECTIONS = ('Board', 'Display', 'Enclosure', 'Studio')


def build_model():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    nosh = build_board()
    build_standins(nosh)
    build_display()
    build_enclosure()
    build_studio()
    # the board turns about its middle in the exploded shot
    P = C.PARAMS
    pivot = empty('Nosh_Pivot', collection('Board'),
                  (mm(P['board_w'] / 2), mm(P['board_h'] / 2), mm(C.Z['split'] - P['pcb_t'] / 2)))
    attach(nosh, pivot)
    setup_render(scene)
    bpy.ops.wm.save_as_mainfile(filepath=MODEL)
    print('BUILD model saved', MODEL)


def key(obj, path, frame, value, index=-1):
    setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame, index=index)


def camera_rig(name, scene, keys, lens=50.0):
    """Orbit rig. keys = [(frame, azimuth deg, elevation deg, distance m, target mm)].
    Azimuth 0 looks from the microSD side toward the audio jacks; 90 from the USB side."""
    col = bpy.data.collections.new('Shot_' + name)
    scene.collection.children.link(col)
    rig = empty('Rig_' + name, col)
    rig.rotation_mode = 'XYZ'
    tilt = empty('Tilt_' + name, col, parent=rig)
    cam = add_camera('Cam_' + name, col, scene, lens)
    cam.parent = tilt
    cam.rotation_euler = (math.pi / 2, 0, 0)
    for frame, az, el, dist, tgt in keys:
        key(rig, 'location', frame, [mm(v) for v in tgt])
        key(rig, 'rotation_euler', frame, (0, 0, math.radians(az)))
        key(tilt, 'rotation_euler', frame, (-math.radians(el), 0, 0))
        key(cam, 'location', frame, (0, -dist, 0))
    return cam


def rise(obj, keys):
    """keys = [(frame, dz mm)] relative to where the object is now."""
    z0 = obj.location.z
    for frame, dz in keys:
        obj.location.z = z0 + mm(dz)
        obj.keyframe_insert('location', frame=frame)
    obj.location.z = z0


def dg_at(scene, frame):
    scene.frame_set(frame)
    dg = scene.view_layers[0].depsgraph
    dg.update()
    return dg


def add_labels(scene, table, em_px, line_mm):
    col = bpy.data.collections.new('Labels_' + scene.name)
    scene.collection.children.link(col)
    nosh = bpy.data.objects['Nosh']
    for spec in table:
        dg = dg_at(scene, spec['hold'])
        pts = [R.target_point(dg, t) for t in spec['targets']]
        if 'anchor_board' in spec:
            xb, yb = spec['anchor_board']
            # Nosh local frame = the GLB frame: x east, y = -south, z out of the component face (at 1.6 mm)
            anchor = nosh.evaluated_get(dg).matrix_world @ Vector((mm(xb), -mm(yb), mm(C.PARAMS['pcb_t'] + 12.0)))
        else:
            mid = sum(pts, Vector()) / len(pts)
            anchor = mid + Vector([mm(v) for v in spec['offset']])
        R.add_label(scene, scene.camera, col, spec, dg, anchor, em_px=spec.get('em', em_px), line_mm=line_mm)


CASE = None


def build_shots():
    global CASE
    bpy.ops.wm.open_mainfile(filepath=MODEL)
    P = C.PARAMS
    CASE = (P['board_w'] / 2, P['board_h'] / 2, C.Z['face'] / 2)
    closed = bpy.data.scenes['Closed']
    closed.frame_start, closed.frame_end = 1, 750

    # ---- shot 1: closed case, round the four edges
    est = (20, 35, 0.42, CASE)
    edge = lambda az: (az, 15, 0.34, CASE)   # noqa: E731
    keys1 = [(1, *est), (90, *est),
             (150, *edge(-90)), (240, *edge(-90)),      # west: power
             (300, *edge(-180)), (390, *edge(-180)),    # north: audio
             (450, *edge(-270)), (540, *edge(-270)),    # east: USB
             (600, *edge(-360)), (690, *edge(-360)),    # south: microSD, ribbon
             (750, -340, 35, 0.42, CASE)]
    camera_rig('Closed', closed, keys1)
    add_labels(closed, L.SCENE1, 48.0, 0.22)

    # ---- shot 2: explode, frames 1001-1750 (t = frame - 1000)
    ex = bpy.data.scenes.new('Exploded')
    for n in TOP_COLLECTIONS:
        ex.collection.children.link(bpy.data.collections[n])
    ex.world = closed.world
    setup_render(ex)
    ex.frame_start, ex.frame_end = 1001, 1750
    T = 1000
    ob = bpy.data.objects
    for i in range(1, 5):
        rise(ob['Screw_Lid_%d' % i], [(T + 1, 0), (T + 50, 22), (T + 110, 182)])
    rise(ob['Lid'], [(T + 30, 0), (T + 110, 160)])
    rise(ob['RK055'], [(T + 60, 0), (T + 150, 110)])
    piv = ob['Nosh_Pivot']
    z0, y0 = piv.location.z, piv.location.y
    out_y, out_z = -150.0, 35.0
    for frame, y, z, rx in [(T + 100, y0, z0, 0.0), (T + 190, y0, z0 + mm(55), 0.0), (T + 330, y0, z0 + mm(55), 0.0),
                            (T + 420, y0 + mm(out_y), mm(out_z), math.pi)]:
        piv.location = (piv.location.x, y, z)
        piv.rotation_euler = (rx, 0, 0)
        piv.keyframe_insert('location', frame=frame)
        piv.keyframe_insert('rotation_euler', frame=frame)
    piv.location = (piv.location.x, y0, z0)
    piv.rotation_euler = (0, 0, 0)
    stack = (25, 12, 0.80, (CASE[0], CASE[1], 100.0))
    over = (0, 62, 0.44, (CASE[0], P['board_h'] / 2 + out_y, out_z))
    keys2 = [(T + 1, *est), (T + 20, *est), (T + 200, *stack), (T + 330, *stack), (T + 420, *over), (T + 750, *over)]
    camera_rig('Exploded', ex, keys2)
    add_labels(ex, L.SCENE2, 42.0, 0.30)

    closed.frame_set(1)
    ex.frame_set(1001)
    bpy.ops.wm.save_as_mainfile(filepath=C.BLEND)
    print('BUILD saved', C.BLEND)
    return closed, ex


def stills(closed, ex, only=None):
    shots = [(closed, 'closed', sorted({s['hold'] for s in L.SCENE1})),
             (ex, 'exploded', [1001 + 80, 1001 + 160] + sorted({s['hold'] for s in L.SCENE2}) + [1380, 1560])]
    for scene, tag, frames in shots:
        for f in frames:
            if only and '%s_%04d' % (tag, f) not in only:
                continue
            render_still(scene, os.path.join(C.OUT, '%s_%04d.png' % (tag, f)), frame=f)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if '--model' in args or not os.path.exists(MODEL):
        build_model()
    closed, ex = build_shots()
    if '--stills' in args:
        stills(closed, ex, [a for a in args if not a.startswith('--')])


if __name__ == '__main__':
    main()
