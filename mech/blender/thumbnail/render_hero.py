"""Label-free, transparent still of the Exploded scene for the YouTube thumbnail.
Run: Blender --background ../nosh_presentation.blend --python render_hero.py -- [frame]
Does not save the .blend. Blender aborts on quit here; check that hero.png was written."""
import os
import sys
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
frame = int(argv[0]) if argv else 1290

sc = bpy.data.scenes['Exploded']
for name in ('Labels_Exploded', 'Labels_Closed'):
    c = bpy.data.collections.get(name)
    if c:
        c.hide_render = True
for o in bpy.data.collections['Studio'].all_objects:
    print('STUDIO', o.name, o.type)
    if o.type == 'MESH':
        o.hide_render = True
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.frame_set(frame)
sc.render.filepath = os.path.join(HERE, 'hero_%d.png' % frame)
# rendering a scene other than the window's takes the frame from the window's scene
if bpy.context.window is not None:
    bpy.context.window.scene = sc
    sc.frame_set(frame)
    bpy.ops.render.render(write_still=True)
else:
    with bpy.context.temp_override(scene=sc):
        bpy.ops.render.render(write_still=True)
print('HERO WRITTEN', sc.render.filepath)
