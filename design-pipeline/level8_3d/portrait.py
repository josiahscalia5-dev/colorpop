"""The gold miner's portrait for the instruction panel (transparent PNG), rendered by Blender."""
import bpy, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import miner
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 96; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Punchy'; sc.view_settings.exposure = 0.35
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = 400
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.2, 0.2, 0.3, 1)
r = miner.build('gold', (0, 0, 0), 1.0)
r.rotation_euler = (math.radians(-6), 0, math.radians(-8))
cam = bpy.data.cameras.new('c'); cam.type = 'ORTHO'; cam.ortho_scale = 2.35
co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co)
co.location = (0.02, -8, 1.22); co.rotation_euler = (math.radians(90), 0, 0); sc.camera = co
def light(loc, energy, color, size):
    l = bpy.data.lights.new('a', 'AREA'); l.energy = energy; l.color = color; l.size = size
    o = bpy.data.objects.new('a', l); sc.collection.objects.link(o); o.location = loc
    d = -o.location; o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
light((-3, -4, 4), 700, (1.0, 0.9, 0.8), 4)
light((4, -2, 2), 300, (1.0, 0.7, 0.4), 3)
light((0, 4, 3), 400, (0.6, 0.5, 1.0), 4)
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
