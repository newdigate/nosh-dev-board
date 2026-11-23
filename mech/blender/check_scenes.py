"""Checks for nosh_presentation.blend. Run:
  Blender --background nosh_presentation.blend --python check_scenes.py
Prints CHECK PASS/FAIL lines and CHECKS n/m. Read that last line: on this Mac Blender
aborts as it quits, so the exit code says nothing.
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as C  # noqa: E402

TASK1_REFS = ['U9', 'U10', 'U6', 'J1', 'J3', 'J4', 'J5', 'J11', 'SW1', 'SW2', 'SW3', 'SW4']


def near(a, b, tol):
    return abs(a - b) <= tol


def check_board_refs():
    missing = [r for r in TASK1_REFS if bpy.data.objects.get(r) is None]
    return 'board_refs', not missing, 'missing %s' % missing


def check_board_frame():
    bad = []
    for r in TASK1_REFS:
        o = bpy.data.objects.get(r)
        if o is None:
            bad.append((r, 'absent'))
            continue
        w = o.matrix_world.translation
        t = C.footprint_world(r)
        if abs(w.x - t.x) > 0.001 or abs(w.y - t.y) > 0.001:
            bad.append((r, round(w.x * 1000, 2), round(w.y * 1000, 2)))
    return 'board_frame', not bad, 'off %s' % bad


def check_board_extent():
    nosh = bpy.data.objects.get('Nosh')
    if nosh is None:
        return 'board_extent', False, 'no Nosh'
    best = None
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        lo, hi = C.world_bbox(o)
        if (near(lo.x, 0, 2e-4) and near(hi.x, C.mm(153.9), 2e-4) and near(lo.y, 0, 2e-4)
                and near(hi.y, C.mm(81.8), 2e-4) and near(hi.z, C.mm(C.Z['split']), 2e-4)):
            best = o.name
            break
    return 'board_extent', best is not None, 'board body %s' % best


CHECKS = [check_board_refs, check_board_frame, check_board_extent]


# ---------------------------------------------------------------- task 2: model
def bbox_mm(name):
    o = bpy.data.objects.get(name)
    if o is None:
        return None
    lo, hi = C.world_bbox(o)
    return [v * 1000 for v in lo], [v * 1000 for v in hi]


def expected_standins():
    """ref -> (lo, hi) in world mm, from board.json and params only."""
    exp = {}
    parts = C.BOARD['parts']
    boxes = dict(C.params.BOXES)
    for ref in ('U1', 'J2', 'J6', 'J7', 'J8', 'J9'):
        x0, y0, x1, y1 = parts[ref]['body']
        h = boxes[ref]
        if parts[ref]['side'] == 'TOP':
            exp[ref] = ((x0, y0, C.Z['comp'] - h), (x1, y1, C.Z['comp']))
        else:
            exp[ref] = ((x0, y0, C.Z['split']), (x1, y1, C.Z['split'] + h))
    for ref in ('U2', 'U15'):
        _, x, y, _side = C.FOOTPRINTS[ref]
        sx, sy, h = C.STANDIN_SIZE[ref]
        exp[ref] = ((x - sx / 2, y - sy / 2, C.Z['comp'] - h), (x + sx / 2, y + sy / 2, C.Z['comp']))
    return exp


def check_standins():
    bad = []
    for ref, (elo, ehi) in expected_standins().items():
        b = bbox_mm(ref)
        if b is None:
            bad.append((ref, 'absent'))
            continue
        if any(abs(b[0][i] - elo[i]) > 0.2 or abs(b[1][i] - ehi[i]) > 0.2 for i in range(3)):
            bad.append((ref, [round(v, 2) for v in b[0] + b[1]], elo, ehi))
    m = C.params.M2_CARD
    b = bbox_mm('M2_Card')
    if b is None or abs(b[0][0] - m['x0']) > 0.2 or abs(b[1][0] - m['x1']) > 0.2 or b[1][2] > C.Z['comp']:
        bad.append(('M2_Card', b))
    b = bbox_mm('SD_Card')
    if b is None or abs((b[0][0] + b[1][0]) / 2 - 100.0) > 0.5 or abs(b[0][1] + 1.075) > 0.2:
        bad.append(('SD_Card', b))
    return 'standins', not bad, '%s' % bad


def check_stack():
    Zl = C.Z
    want = {
        'RK055_Carrier': (Zl['car0'], Zl['car1']),
        'RK055_Glass': (Zl['car1'], Zl['glass']),
        'Tray': (0.0, Zl['tongue']),
        'Lid': (Zl['lid0'], Zl['face']),
    }
    bad = []
    for name, (z0, z1) in want.items():
        b = bbox_mm(name)
        if b is None or abs(b[0][2] - z0) > 0.2 or abs(b[1][2] - z1) > 0.2:
            bad.append((name, b and (round(b[0][2], 2), round(b[1][2], 2)), (z0, z1)))
    for i in range(1, 5):
        b = bbox_mm('RK055_Standoff_%d' % i)
        if b is None or abs(b[0][2] - Zl['split']) > 0.2 or abs(b[1][2] - Zl['car0']) > 0.2:
            bad.append(('standoff', i, b))
    for n in ['Screw_Tray_%d' % i for i in range(1, 5)] + ['Screw_Lid_%d' % i for i in range(1, 5)] + ['RK055_Ribbon']:
        if bpy.data.objects.get(n) is None:
            bad.append((n, 'absent'))
    return 'stack', not bad, '%s' % bad


def check_glass_pos():
    P = C.PARAMS
    b = bbox_mm('RK055_Glass')
    if b is None:
        return 'glass_pos', False, 'absent'
    want = (P['glass_x0'], P['glass_y0'], P['glass_x0'] + P['glass_w'], P['glass_y0'] + P['glass_h'])
    got = (b[0][0], b[0][1], b[1][0], b[1][1])
    ok = all(abs(g - w) <= 0.2 for g, w in zip(got, want))
    return 'glass_pos', ok, 'got %s want %s' % ([round(g, 2) for g in got], want)


def check_screen_pos():
    P = C.PARAMS
    o = bpy.data.objects.get('RK055_Screen')
    if o is None:
        return 'screen_pos', False, 'absent'
    b = bbox_mm('RK055_Screen')
    cx = P['glass_x0'] + P['glass_w'] / 2
    cy = P['glass_y0'] + P['glass_h'] / 2
    want = (cx - 60.48, cy - 34.02, cx + 60.48, cy + 34.02)
    got = (b[0][0], b[0][1], b[1][0], b[1][1])
    ok = all(abs(g - w) <= 0.2 for g, w in zip(got, want))
    # image top (v = 1) must be at +Y, image right (u = 1) at +X
    uv = o.data.uv_layers.active.data
    top_ok = True
    for poly in o.data.polygons:
        for li in poly.loop_indices:
            w = o.matrix_world @ o.data.vertices[o.data.loops[li].vertex_index].co
            u, v = uv[li].uv
            if (v > 0.5) != (w.y * 1000 > cy) or (u > 0.5) != (w.x * 1000 > cx):
                top_ok = False
    return 'screen_pos', ok and top_ok, 'got %s want %s uv_ok %s' % ([round(g, 2) for g in got], want, top_ok)


def check_collections():
    bad = []
    for sc in bpy.data.scenes:
        if len(sc.collection.objects):
            bad.append((sc.name, [o.name for o in sc.collection.objects][:5]))
    for n in ('Board', 'Display', 'Enclosure', 'Studio'):
        if bpy.data.collections.get(n) is None:
            bad.append(n)
    return 'collections', not bad, '%s' % bad


CHECKS += [check_standins, check_stack, check_glass_pos, check_screen_pos, check_collections]


# ---------------------------------------------------------------- tasks 3-5: shots and labels
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

import labels as L  # noqa: E402

SHOTS = [('Closed', 'SCENE1'), ('Exploded', 'SCENE2')]


def dg_at(scene, frame):
    scene.frame_set(frame)
    dg = scene.view_layers[0].depsgraph
    dg.update()
    return dg


def px(scene, dg, co):
    cam = scene.camera.evaluated_get(dg)
    v = world_to_camera_view(scene, cam, Vector(co))
    return v.x * scene.render.resolution_x, v.y * scene.render.resolution_y, v.z


def screen_rect(scene, dg, obj):
    """(x0, y0, x1, y1) in pixels of the object's bounding box."""
    eo = obj.evaluated_get(dg)
    pts = [px(scene, dg, eo.matrix_world @ Vector(c)) for c in eo.bound_box]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def alpha(dg, obj):
    return obj.evaluated_get(dg).color[3]


def each_label():
    for scene_name, table in SHOTS:
        scene = bpy.data.scenes.get(scene_name)
        for spec in getattr(L, table):
            yield scene, spec


def check_label_text():
    bad = []
    for scene, spec in each_label():
        t = bpy.data.objects.get('Label_%s_Text' % spec['key'])
        if scene is None or t is None or t.data.body != spec['text']:
            bad.append(spec['key'])
        elif t.name not in bpy.data.collections['Labels_' + scene.name].all_objects:
            bad.append((spec['key'], 'wrong collection'))
    return 'label_text', not bad, '%s' % bad


def check_label_targets():
    """Each dot sits where board.json says the part is, carried by the Nosh's motion."""
    bad = []
    closed = bpy.data.scenes.get('Closed')
    if closed is None:
        return 'label_targets', False, 'no scene Closed'
    base = bpy.data.objects['Nosh'].evaluated_get(dg_at(closed, 1)).matrix_world.copy()
    parts = C.BOARD['parts']
    for scene, spec in each_label():
        if scene is None:
            bad.append(spec['key'])
            continue
        dg = dg_at(scene, spec['hold'])
        move = bpy.data.objects['Nosh'].evaluated_get(dg).matrix_world @ base.inverted()
        for i, tgt in enumerate(spec['targets']):
            dot = bpy.data.objects.get('Label_%s_Dot_%d' % (spec['key'], i))
            if dot is None:
                bad.append((spec['key'], i, 'no dot'))
                continue
            ref = tgt if isinstance(tgt, str) else tgt[0]
            if bpy.data.objects.get(ref) is None:
                bad.append((spec['key'], ref, 'no target object'))
                continue
            if ref not in C.FOOTPRINTS:
                continue
            w = move.inverted() @ dot.evaluated_get(dg).matrix_world.translation   # back to the assembled pose
            x, y = w.x * 1000, w.y * 1000
            if ref in parts:
                x0, y0, x1, y1 = parts[ref]['body']
            else:
                fx, fy = C.FOOTPRINTS[ref][1:3]
                x0, y0, x1, y1 = fx - 1, fy - 1, fx + 1, fy + 1
            # a nudge may push the dot out to the case wall: allow 4 mm outside the body
            if not (x0 - 4 <= x <= x1 + 4 and y0 - 4 <= y <= y1 + 4):
                bad.append((spec['key'], ref, round(x, 1), round(y, 1)))
    return 'label_targets', not bad, '%s' % bad


def check_label_visible():
    bad = []
    for scene, spec in each_label():
        root = bpy.data.objects.get('Label_%s' % spec['key'])
        if scene is None or root is None:
            bad.append(spec['key'])
            continue
        dg = dg_at(scene, spec['hold'])
        W, H = scene.render.resolution_x, scene.render.resolution_y
        if alpha(dg, bpy.data.objects['Label_%s_Text' % spec['key']]) < 0.99:
            bad.append((spec['key'], 'alpha'))
        for i in range(len(spec['targets'])):
            x, y, z = px(scene, dg, bpy.data.objects['Label_%s_Dot_%d' % (spec['key'], i)].evaluated_get(dg).matrix_world.translation)
            if not (0 < x < W and 0 < y < H and z > 0):
                bad.append((spec['key'], 'dot off screen', round(x), round(y)))
        x0, y0, x1, y1 = screen_rect(scene, dg, bpy.data.objects['Label_%s_Plate' % spec['key']])
        if x0 < 10 or y0 < 10 or x1 > W - 10 or y1 > H - 10:
            bad.append((spec['key'], 'plate off screen', [round(v) for v in (x0, y0, x1, y1)]))
    return 'label_visible', not bad, '%s' % bad


def check_label_size():
    bad = []
    for scene, spec in each_label():
        t = bpy.data.objects.get('Label_%s_Text' % spec['key'])
        if scene is None or t is None:
            bad.append(spec['key'])
            continue
        dg = dg_at(scene, spec['hold'])
        x0, y0, x1, y1 = screen_rect(scene, dg, t)
        line_h = (y1 - y0) / (spec['text'].count('\n') + 1)
        if line_h < 28:
            bad.append((spec['key'], round(line_h, 1)))
    return 'label_size', not bad, 'px %s' % bad


def check_label_overlap():
    bad = []
    for scene_name, table in SHOTS:
        scene = bpy.data.scenes.get(scene_name)
        specs = getattr(L, table)
        if scene is None:
            bad.append(scene_name)
            continue
        for frame in sorted({s['hold'] for s in specs}):
            dg = dg_at(scene, frame)
            vis = [s for s in specs if bpy.data.objects.get('Label_%s_Plate' % s['key']) is not None
                   and alpha(dg, bpy.data.objects['Label_%s_Plate' % s['key']]) > 0.01]
            rects = {s['key']: screen_rect(scene, dg, bpy.data.objects['Label_%s_Plate' % s['key']]) for s in vis}
            keys = sorted(rects)
            for i, a in enumerate(keys):
                ra = rects[a]
                for b in keys[i + 1:]:
                    rb = rects[b]
                    if ra[0] < rb[2] and rb[0] < ra[2] and ra[1] < rb[3] and rb[1] < ra[3]:
                        bad.append((frame, a, b))
                # no plate may sit on a visible label's dot
                for s in vis:
                    for i2 in range(len(s['targets'])):
                        x, y, _ = px(scene, dg, bpy.data.objects['Label_%s_Dot_%d' % (s['key'], i2)].evaluated_get(dg).matrix_world.translation)
                        if ra[0] < x < ra[2] and ra[1] < y < ra[3]:
                            bad.append((frame, a, 'covers dot of', s['key']))
    return 'label_overlap', not bad, '%s' % bad


def check_shots():
    bad = []
    for name, f0, f1, cam in (('Closed', 1, 750, 'Cam_Closed'), ('Exploded', 1001, 1750, 'Cam_Exploded')):
        sc = bpy.data.scenes.get(name)
        if sc is None or sc.camera is None or sc.camera.name != cam or (sc.frame_start, sc.frame_end) != (f0, f1):
            bad.append(name)
        elif (sc.render.resolution_x, sc.render.resolution_y, sc.render.fps) != (1920, 1080, 30):
            bad.append((name, 'render settings'))
    return 'shots', not bad, '%s' % bad


def check_explode_pose():
    sc = bpy.data.scenes.get('Exploded')
    if sc is None:
        return 'explode_pose', False, 'no scene'
    bad = []

    def zr(name, dg):
        lo, hi = C.world_bbox(bpy.data.objects[name], dg)
        return lo.z * 1000, hi.z * 1000

    dg = dg_at(sc, 1001)
    for name, (z0, z1) in {'Tray': (0.0, C.Z['tongue']), 'Lid': (C.Z['lid0'], C.Z['face']),
                           'RK055_Carrier': (C.Z['car0'], C.Z['car1'])}.items():
        a, b = zr(name, dg)
        if abs(a - z0) > 0.2 or abs(b - z1) > 0.2:
            bad.append((1001, name, round(a, 2), round(b, 2)))
    dg = dg_at(sc, 1240)
    order = ['Tray', 'Nosh', 'RK055', 'Lid']
    spans = [zr(n, dg) for n in order]
    for (n0, s0), (n1, s1) in zip(zip(order, spans), zip(order[1:], spans[1:])):
        if s1[0] - s0[1] < 25.0:
            bad.append((1240, n0, n1, round(s1[0] - s0[1], 1)))
    lid_top = spans[3][1]
    for i in range(1, 5):
        a, b = zr('Screw_Lid_%d' % i, dg)
        if a < lid_top + 2.0:
            bad.append((1240, 'screw', i, round(a - lid_top, 1)))
    return 'explode_pose', not bad, '%s' % bad


CHECKS += [check_shots, check_label_text, check_label_targets, check_label_visible, check_label_size,
           check_label_overlap, check_explode_pose]


# What each target is, written here independently of labels.py (sources: board_table.md, README).
# A label pointing at a target must contain its word.
MEANING = {
    'J4': 'power', 'J8': 'line out', 'J9': 'line in', 'J3': 'usb-c', 'J2': 'micro-usb', 'J5': 'microsd',
    'U1': 'rt1176', 'U9': 'sdram', 'U10': 'sdram', 'U2': 'flash', 'U15': 'sgtl5000', 'U6': 'buck',
    'J1': 'swd', 'J11': 'uart', 'SW1': 'reset', 'SW2': 'on/off', 'SW3': 'wake', 'SW4': 'boot',
    'SD_Card': 'microsd', 'M2_Card': 'm.2', 'Ribbon_Apex': 'ribbon', 'RK055_Screen': 'display',
    'Lid': 'lid', 'Tray': 'tray', 'RK055_Carrier': 'rk055',
}
MEANING_EXEMPT = {'x_board': 'points at the board edge by J3 and names the whole board'}


def check_label_meaning():
    bad = []
    for _scene, spec in each_label():
        if spec['key'] in MEANING_EXEMPT:
            continue
        text = spec['text'].lower().replace('\n', ' ')
        for tgt in spec['targets']:
            ref = tgt if isinstance(tgt, str) else tgt[0]
            if ref not in MEANING:
                bad.append((spec['key'], ref, 'target has no entry in MEANING'))
            elif MEANING[ref] not in text:
                bad.append((spec['key'], ref, 'text lacks "%s"' % MEANING[ref]))
    return 'label_meaning', not bad, '%s' % bad


def check_label_unobstructed():
    """From the camera, nothing but label parts may sit more than 3 mm in front of a dot."""
    bad = []
    for scene, spec in each_label():
        if scene is None:
            bad.append(spec['key'])
            continue
        dg = dg_at(scene, spec['hold'])
        cam = scene.camera.evaluated_get(dg).matrix_world.translation.copy()
        for i in range(len(spec['targets'])):
            dot = bpy.data.objects.get('Label_%s_Dot_%d' % (spec['key'], i))
            if dot is None:
                bad.append((spec['key'], i, 'no dot'))
                continue
            p = dot.evaluated_get(dg).matrix_world.translation
            total = (p - cam).length
            d = (p - cam).normalized()
            origin, gone = cam.copy(), 0.0
            for _ in range(60):
                hit, loc, _n, _idx, obj, _m = scene.ray_cast(dg, origin, d, distance=total - gone)
                if not hit:
                    break
                gone += (loc - origin).length + 1e-5
                if not obj.name.startswith('Label_'):
                    if gone < total - 0.003:
                        bad.append((spec['key'], i, obj.name, round((total - gone) * 1000, 1)))
                    break
                origin = loc + d * 1e-5
    return 'label_unobstructed', not bad, '(label, target, blocker, mm in front) %s' % bad


def check_board_turned():
    """At the end of the exploded shot the component face looks up: U1 lies above the board body."""
    sc = bpy.data.scenes.get('Exploded')
    if sc is None:
        return 'board_turned', False, 'no scene'
    dg = dg_at(sc, 1740)
    up = bpy.data.objects['Nosh'].evaluated_get(dg).matrix_world.to_3x3() @ Vector((0, 0, 1))
    dg = dg_at(sc, 1290)
    down = bpy.data.objects['Nosh'].evaluated_get(dg).matrix_world.to_3x3() @ Vector((0, 0, 1))
    ok = up.z > 0.99 and down.z < -0.99
    return 'board_turned', ok, 'component-face normal z: %.2f at 1290, %.2f at 1740' % (down.z, up.z)


CHECKS += [check_label_meaning, check_label_unobstructed, check_board_turned]


def main():
    n = 0
    closed = bpy.data.scenes.get('Closed') or bpy.data.scenes[0]
    for fn in CHECKS:
        closed.frame_set(1)
        try:
            name, ok, detail = fn()
        except Exception as e:  # a crashed check is a failed check
            name, ok, detail = fn.__name__, False, 'exception %r' % e
        n += ok
        print('CHECK %s %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else ': ' + detail))
    print('CHECKS %d/%d' % (n, len(CHECKS)))
    if n != len(CHECKS):
        sys.exit(1)


if __name__ == '__main__':
    main()
