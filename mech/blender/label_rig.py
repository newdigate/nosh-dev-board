"""Camera-facing labels with leader lines.

A label is: a root empty Label_<key> (turns with the camera and scales with its distance,
so the text keeps its size on screen), a text and a rounded plate under it, and per target
a leader line and a dot. Fading is the alpha of each object's colour, keyed.
"""
import math

import bmesh
import bpy
from mathutils import Vector

import common as C
from common import mm

FADE = 12  # frames


def _mat(name, rgb):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    mix = nt.nodes.new('ShaderNodeMixShader')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    em = nt.nodes.new('ShaderNodeEmission')
    info = nt.nodes.new('ShaderNodeObjectInfo')
    em.inputs['Color'].default_value = (*rgb, 1.0)
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(info.outputs['Alpha'], mix.inputs['Fac'])
    nt.links.new(tr.outputs['BSDF'], mix.inputs[1])
    nt.links.new(em.outputs['Emission'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    m.surface_render_method = 'DITHERED'
    m.use_backface_culling = False
    m.diffuse_color = (*rgb, 1.0)
    return m


def materials():
    return (_mat('label_text', (1.0, 1.0, 1.0)), _mat('label_plate', (0.035, 0.045, 0.065)),
            _mat('label_line', (1.0, 1.0, 1.0)))


def target_point(dg, tgt):
    """World point (metres) for a target spec, evaluated in depsgraph dg."""
    name, frac, nudge = (tgt, (0.5, 0.5, 0.5), (0, 0, 0)) if isinstance(tgt, str) else (tuple(tgt) + ((0, 0, 0),))[:3]
    obj = bpy.data.objects[name]
    lo, hi = C.world_bbox(obj, dg)
    if lo.x > hi.x:   # nothing with a box: an empty
        p = obj.evaluated_get(dg).matrix_world.translation.copy()
    else:
        p = Vector([lo[i] + frac[i] * (hi[i] - lo[i]) for i in range(3)])
    return p + Vector([mm(v) for v in nudge])


def _rounded_rect(name, w, h, r, seg=6):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a), 0.0))
    me = bpy.data.meshes.new(name)
    me.from_pydata(pts, [], [tuple(range(len(pts)))])
    return me


def _unit_rod(name, radius):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=radius, radius2=radius, depth=1.0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__('mathutils').Matrix.Rotation(-math.pi / 2, 3, 'X'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0.5, 0))
    bm.to_mesh(me)
    bm.free()
    return me


def _sphere(name, radius):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    return me


def add_label(scene, camera, col, spec, dg, anchor, em_px=48.0, line_mm=0.22):
    """Build one label. anchor = world position (metres) of the label's middle."""
    m_text, m_plate, m_line = materials()
    key = spec['key']
    root = bpy.data.objects.new('Label_' + key, None)
    root.empty_display_size = 0.2
    root.location = anchor
    col.objects.link(root)
    cr = root.constraints.new('COPY_ROTATION')
    cr.target = camera
    k = em_px * camera.data.sensor_width / (camera.data.lens * scene.render.resolution_x)
    for fc in root.driver_add('scale'):
        d = fc.driver
        d.type = 'SCRIPTED'
        v = d.variables.new()
        v.name = 'd'
        v.type = 'LOC_DIFF'
        v.targets[0].id = root
        v.targets[1].id = camera
        d.expression = 'd*%.6f' % k

    cu = bpy.data.curves.new('Label_%s_Text' % key, 'FONT')
    cu.body = spec['text']
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.size = 1.0
    cu.materials.append(m_text)
    text = bpy.data.objects.new('Label_%s_Text' % key, cu)
    col.objects.link(text)
    text.parent = root
    text.location = (0, 0, 0.22)
    me = text.to_mesh()
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    text.to_mesh_clear()
    pad = 0.42
    w, h = max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad
    pm = _rounded_rect('Label_%s_Plate' % key, w, h, 0.32)
    pm.materials.append(m_plate)
    plate = bpy.data.objects.new('Label_%s_Plate' % key, pm)
    col.objects.link(plate)
    plate.parent = root
    plate.location = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, 0.16)

    objs = [text, plate]
    for i, tgt in enumerate(spec['targets']):
        p = target_point(dg, tgt)
        dm = _sphere('Label_%s_Dot_%d' % (key, i), mm(line_mm * 3.2))
        dm.materials.append(m_line)
        dot = bpy.data.objects.new('Label_%s_Dot_%d' % (key, i), dm)
        dot.location = p
        col.objects.link(dot)
        lm = _unit_rod('Label_%s_Leader_%d' % (key, i), mm(line_mm))
        lm.materials.append(m_line)
        rod = bpy.data.objects.new('Label_%s_Leader_%d' % (key, i), lm)
        rod.location = p
        col.objects.link(rod)
        # ride with the part, so a re-timed animation does not leave them behind
        host = bpy.data.objects[tgt if isinstance(tgt, str) else tgt[0]]
        inv = host.evaluated_get(dg).matrix_world.inverted()
        for o in (dot, rod):
            o.parent = host
            o.matrix_parent_inverse = inv
        st = rod.constraints.new('STRETCH_TO')
        st.target = root
        st.rest_length = 1.0
        st.volume = 'NO_VOLUME'
        objs += [dot, rod]

    keys = [(spec['cue'], 0.0), (spec['cue'] + FADE, 1.0)]
    if spec.get('out') is not None:
        keys += [(spec['out'], 1.0), (spec['out'] + FADE, 0.0)]
    for o in objs:
        o.visible_shadow = False
        for frame, a in keys:
            o.color = (1.0, 1.0, 1.0, a)
            o.keyframe_insert('color', index=3, frame=frame)
    return root
