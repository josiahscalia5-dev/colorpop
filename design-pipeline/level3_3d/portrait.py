"""The purple critter's portrait for the instruction panel (transparent PNG, 3D, Blender): like the
reference's icon -- ears out, a paw up, looking at you.

  python portrait.py -- OUT.png
"""
import bpy, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import critter
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 128; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Khronos PBR Neutral'; sc.view_settings.exposure = 0.0
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = 560
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.45, 0.55, 0.9, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
r = critter.build('purple', (0, 0, 0), 1.0, ears=True, paw=True, short=True)
r.scale = (1.08, 1.04, 1.0)
r.rotation_euler = (math.radians(-6), 0, math.radians(-10))
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.ortho_scale = 3.05
co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co)
co.location = (-0.04, -8, 1.12); co.rotation_euler = (math.radians(90), 0, 0); sc.camera = co


def light(loc, energy, color, size):
    l = bpy.data.lights.new('a', 'AREA'); l.energy = energy; l.color = color; l.size = size
    o = bpy.data.objects.new('a', l); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (-o.location).to_track_quat('-Z', 'Y').to_euler()


light((-3, -4, 4), 900, (1.0, 0.92, 0.8), 4)
light((4, -2, 2), 320, (0.8, 0.85, 1.0), 3)
light((0, 4, 3), 600, (1.0, 0.8, 0.55), 4)
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
