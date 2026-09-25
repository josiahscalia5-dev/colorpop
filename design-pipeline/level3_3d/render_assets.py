"""Render the new Level 3's game assets with Blender (run with Blender's Python, see README).

  python render_assets.py -- OUT_DIR [samples]

Writes, at 2x the art resolution (art frame 724 x 1570):
  bg_render.png     the scene without characters (empty holes), transparent sky
  char_<hole>.png   each character of the reference moment alone, cropped around it
                    (the rest of the scene lights it but is not seen), and char_<hole>.json with
                    the crop origin in 2x px
  rim_ids.png       every hole's rim stones in a flat colour of their own (front edges)
  geometry.json     each hole's opening ellipse in art px
Same scene, camera and lights as the approved mockup (scene.py); the rim bricks are named stone_* too.
"""
import bpy, os, sys, json, math
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene
from scene import ART_W, ART_H, R_HOLE, CAST

argv = sys.argv[sys.argv.index('--') + 1:]
OUT = argv[0]
SAMPLES = int(argv[1]) if len(argv) > 1 else 128
os.makedirs(OUT, exist_ok=True)


def art_px(sc, p):
    v = world_to_camera_view(sc, sc.camera, Vector(p))
    return v.x * ART_W, (1 - v.y) * ART_H


def setup():
    sc = scene.reset(1.0, SAMPLES)
    hw = scene.build(sc)
    return sc, hw


# ---------------------------------------------------------------- geometry + background
sc, hw = setup()
geo = {}
for k, p in hw.items():
    pts = [art_px(sc, (p.x + R_HOLE * math.cos(a), p.y + R_HOLE * math.sin(a), 0.0)) for a in [i * math.pi / 90 for i in range(180)]]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    geo[k] = {'opening': [round((min(xs) + max(xs)) / 2, 2), round((min(ys) + max(ys)) / 2, 2),
                          round((max(xs) - min(xs)) / 2, 2), round((max(ys) - min(ys)) / 2, 2)],
              'world': [p.x, p.y]}
json.dump(geo, open(os.path.join(OUT, 'geometry.json'), 'w'), indent=1)
if '--skip-bg' not in sys.argv and '--chars-only' not in sys.argv:
    sc.render.filepath = os.path.join(OUT, 'bg_render.png')
    bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------- rim stones in id colours
def rim_ids():
    sc, hw = setup()
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = 'BOX'
    sc.cycles.filter_width = 0.01
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0
    keys = list(hw)
    for o in sc.objects:
        if o.type not in ('MESH', 'CURVE'):
            continue
        hole_key = o.parent.name[5:] if o.parent and o.parent.name.startswith('hole_') else None
        if hole_key and o.name.startswith('stone_'):
            i = keys.index(hole_key) + 1
            m = bpy.data.materials.new('id%d' % i)
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            em = nt.nodes.new('ShaderNodeEmission')
            em.inputs['Color'].default_value = (i / 10.0, 0, 0, 1)
            outn = nt.nodes.new('ShaderNodeOutputMaterial')
            nt.links.new(em.outputs[0], outn.inputs[0])
            o.material_slots[0].material = m
        else:
            o.hide_render = True
    sc.render.image_settings.color_depth = '16'
    sc.render.filepath = os.path.join(OUT, 'rim_ids.png')
    bpy.ops.render.render(write_still=True)


if '--chars-only' not in sys.argv:
    rim_ids()

# ---------------------------------------------------------------- the characters, one at a time
sc, hw = setup()
E = 140                                   # art px added on each side: characters at the screen edges come out whole
sc.render.resolution_x = (ART_W + 2 * E) * 2   # vertical sensor fit: same scale and projection, wider view
cast = dict(scene.EXTRA) if '--extra' in sys.argv else dict(CAST)     # --extra: the pop-up-only looks
roots = scene.characters(sc, hw, cast)
chars = {k: [o for o in sc.objects if o == r or o.parent == r] for k, r in roots.items()}
everything = [o for o in sc.objects if o.type in ('MESH', 'CURVE')]
for k in roots:
    if len(sys.argv) > 1 and '--only' in sys.argv and k not in sys.argv[sys.argv.index('--only') + 1].split(','):
        continue
    mine = set(chars[k])
    for o in everything:
        o.visible_camera = o in mine
    # crop around the character: from above its hat to below the hole's front
    cx, cy, a, b = geo[k]['opening']
    x0, x1 = cx - 1.35 * a, cx + 1.35 * a
    y0, y1 = cy - 3.4 * b - 1.2 * a, cy + b + 70
    x0, y0 = max(-E, int(x0 + E) // 2 * 2 - E), max(0, int(y0) // 2 * 2)
    x1, y1 = min(ART_W + E, int(x1 + E + 2) // 2 * 2 - E), min(ART_H, int(y1 + 2) // 2 * 2)
    sc.render.use_border = True
    sc.render.use_crop_to_border = True
    sc.render.border_min_x, sc.render.border_max_x = (x0 + E) / (ART_W + 2 * E), (x1 + E) / (ART_W + 2 * E)
    sc.render.border_min_y, sc.render.border_max_y = 1 - y1 / ART_H, 1 - y0 / ART_H
    name = ('extra_%s' if '--extra' in sys.argv else 'char_%s') % k
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    json.dump({'hole': k, 'variant': cast[k], 'extra': '--extra' in sys.argv, 'x0': 2 * x0, 'y0': 2 * y0, 'x1': 2 * x1, 'y1': 2 * y1},
              open(os.path.join(OUT, name + '.json'), 'w'))
print('assets done')
