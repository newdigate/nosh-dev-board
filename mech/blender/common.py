"""Shared frame, parameters and helpers for the Nosh Blender scenes.

World frame = the mech/ model frame, in metres at real size:
X east, Y = board-south (the user's north: audio jacks), Z up, display on top, Z = 0 at the table.
"""
import json
import os
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
MECH = os.path.dirname(HERE)
if MECH not in sys.path:
    sys.path.insert(0, MECH)
import params  # noqa: E402

PARAMS = params.P
Z = params.levels(PARAMS)
BOARD = json.load(open(os.path.join(MECH, 'board.json')))
FOOTPRINTS = {f[0]: f for f in BOARD['footprints']}
BLEND = os.path.join(HERE, 'nosh_presentation.blend')
GLB = os.path.join(HERE, 'build', 'board.glb')
OUT = os.path.join(HERE, 'out')

# Stand-ins for parts with no body in the board export: ref -> (size x, size y, height) in mm,
# before the footprint rotation. Heights of J*/U1 come from params.BOXES.
STANDIN_SIZE = {
    'U2': (8.0, 6.0, 0.8),    # Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm
    'U15': (3.0, 3.0, 0.9),   # Package_DFN_QFN:QFN-20-1EP_3x3mm_P0.4mm_EP1.65x1.65mm
}


def mm(v):
    return v / 1000.0


def board_to_world(x, y, z_above=0.0, side='TOP'):
    """Board mm (origin NW, x east, y south) to world metres.

    z_above is the height above the face the part sits on. TOP parts hang below the
    board (the component face looks at the tray); BOT parts stand above it.
    """
    z = Z['comp'] - z_above if side == 'TOP' else Z['split'] + z_above
    return Vector((mm(x), mm(y), mm(z)))


def footprint_world(ref):
    f = FOOTPRINTS[ref]
    return board_to_world(f[1], f[2], 0.0, f[3])


def ref_object(ref):
    import bpy
    o = bpy.data.objects.get(ref)
    if o is None:
        raise KeyError('no object for reference %s' % ref)
    return o


def world_bbox(obj, depsgraph=None):
    """(min Vector, max Vector) in world metres over obj and its children."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    todo = [obj]
    while todo:
        o = todo.pop()
        todo.extend(c for c in o.children if not c.name.startswith('Label_'))
        if o.type not in ('MESH', 'CURVE', 'FONT') or o.name.startswith('Label_'):
            continue   # label dots and leaders ride on parts but are not part of them
        e = o.evaluated_get(depsgraph) if depsgraph is not None else o
        for c in e.bound_box:
            w = e.matrix_world @ Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return lo, hi
