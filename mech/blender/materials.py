"""Materials for the Nosh scenes. get(name) creates on first use."""
import bpy

# name -> (base colour rgb, metallic, roughness, emission strength)
SPEC = {
    'plastic_grey': ((0.33, 0.35, 0.38), 0.0, 0.62, 0.0),
    'pcb_black':    ((0.02, 0.025, 0.03), 0.0, 0.45, 0.0),
    'pcb_green':    ((0.02, 0.16, 0.07), 0.0, 0.45, 0.0),
    'glass':        ((0.012, 0.012, 0.015), 0.0, 0.06, 0.0),
    'panel_frame':  ((0.55, 0.56, 0.58), 0.9, 0.35, 0.0),
    'ic_black':     ((0.03, 0.03, 0.035), 0.0, 0.40, 0.0),
    'metal':        ((0.75, 0.76, 0.78), 1.0, 0.30, 0.0),
    'brass':        ((0.80, 0.62, 0.22), 1.0, 0.30, 0.0),
    'screw':        ((0.10, 0.10, 0.11), 1.0, 0.40, 0.0),
    'ribbon':       ((0.85, 0.55, 0.20), 0.0, 0.45, 0.0),
    'sd_card':      ((0.03, 0.03, 0.035), 0.0, 0.50, 0.0),
    'backdrop':     ((0.80, 0.81, 0.83), 0.0, 0.90, 0.0),
}


def get(name):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    if name == 'screen':
        return _screen()
    col, metal, rough, emis = SPEC[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1.0)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    m.diffuse_color = (*col, 1.0)
    return m


def _screen():
    """The lit area of the panel. Node 'Screen Image' takes a screenshot; with no image
    it shows a dark blue-grey glow so the active area reads against the bezel."""
    m = bpy.data.materials.new('screen')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    b.inputs['Roughness'].default_value = 0.06
    img = nt.nodes.new('ShaderNodeTexImage')
    img.name = img.label = 'Screen Image'
    img.location = (-600, 0)
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.name = 'Screen Mix'
    mix.location = (-300, 0)
    mix.inputs[0].default_value = 0.0            # 0 = idle colour, 1 = image
    mix.inputs[6].default_value = (0.02, 0.035, 0.06, 1.0)
    nt.links.new(img.outputs['Color'], mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = 1.0
    return m


def set_screen_image(path):
    m = get('screen')
    nt = m.node_tree
    nt.nodes['Screen Image'].image = bpy.data.images.load(path)
    nt.nodes['Screen Mix'].inputs[0].default_value = 1.0
