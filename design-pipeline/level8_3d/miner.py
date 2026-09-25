"""The Level 8 characters: cute miner critters (3D, Blender), in three variants.

  gold   -- the targets: shiny gold fur and hat, glowing headlamp
  yellow -- look-alike decoy: matte butter-yellow fur, yellow plastic hat
  brown  -- decoy: brown fur, dark leather-brown hat

build(variant, location, scale) adds one character standing in a hole at `location` (the centre of
the hole opening on the ground plane, z = 0) and returns its objects. The body continues well
below the ground so it can rise out of the hole (the game clips it at the hole's front rim).
"""
import bpy, math
from mathutils import Vector

PALETTE = {
    # the targets: shining gold all over (fur with a metallic sheen, polished gold hat, lamp on)
    'gold':   dict(fur=(1.0, 0.56, 0.0), fur_metal=0.5, fur_rough=0.28, belly=(1.0, 0.86, 0.36),
                   hat=(1.0, 0.62, 0.04), hat_metal=1.0, hat_rough=0.14, glow=0.55, lamp=True),
    # look-alike decoy: pale lemon, matte, a plain yellow plastic hat, lamp off
    'yellow': dict(fur=(1.0, 0.93, 0.42), fur_metal=0.0, fur_rough=0.6, belly=(1.0, 0.98, 0.82),
                   hat=(1.0, 0.95, 0.30), hat_metal=0.0, hat_rough=0.32, glow=0.0, lamp=False),
    # decoy: brown fur, dark leather hat, lamp off
    'brown':  dict(fur=(0.42, 0.18, 0.06), fur_metal=0.0, fur_rough=0.6, belly=(0.95, 0.70, 0.48),
                   hat=(0.16, 0.08, 0.035), hat_metal=0.0, hat_rough=0.42, glow=0.0, lamp=False),
}


def mat(name, color, metal=0.0, rough=0.5, emit=0.0, emit_color=None, coat=0.0, sss=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    if sss:
        p.inputs['Subsurface Weight'].default_value = sss
        p.inputs['Subsurface Radius'].default_value = (0.3, 0.12, 0.08)
        p.inputs['Subsurface Scale'].default_value = 0.08
    if emit:
        p.inputs['Emission Color'].default_value = (*(emit_color or color), 1)
        p.inputs['Emission Strength'].default_value = emit
    return m


def smooth(obj, levels=2):
    for poly in obj.data.polygons:
        poly.use_smooth = True
    if levels:
        mod = obj.modifiers.new('sub', 'SUBSURF')
        mod.levels = levels
        mod.render_levels = levels
    return obj


def sphere(name, loc, scale, material, parent=None, segs=48):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=segs, ring_count=segs // 2, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    for poly in o.data.polygons:
        poly.use_smooth = True
    if parent:
        o.parent = parent
    return o


def build(variant, location=(0, 0, 0), scale=1.0, tag=''):
    P = PALETTE[variant]
    t = variant + tag
    fur = mat('fur_' + variant, P['fur'], P['fur_metal'], P['fur_rough'], emit=P['glow'], sss=0.0 if variant == 'gold' else 0.25,
              coat=0.3 if variant == 'gold' else 0.0)
    belly = mat('belly_' + variant, P['belly'], 0.3 if variant == 'gold' else 0.0, 0.45, emit=P['glow'] * 0.6, sss=0.2)
    hat = mat('hat_' + variant, P['hat'], P['hat_metal'], P['hat_rough'], emit=P['glow'] * 0.5, coat=0.6)
    white = mat('eye_white', (0.97, 0.97, 0.97), 0.0, 0.15, coat=1.0)
    black = mat('eye_black', (0.01, 0.008, 0.01), 0.0, 0.08, coat=1.0)
    shine = mat('eye_shine', (1, 1, 1), emit=6.0)
    nose = mat('nose', (0.25, 0.10, 0.08), 0.0, 0.25, coat=0.8)
    pink = mat('cheek', (1.0, 0.45, 0.45), 0.0, 0.6)
    tooth = mat('tooth', (1, 0.98, 0.94), 0.0, 0.3)
    lamp_body = mat('lamp_body', (0.15, 0.15, 0.17), 0.8, 0.3)
    lamp_glass = (mat('lamp_glass', (1.0, 0.95, 0.75), emit=14.0, emit_color=(1.0, 0.92, 0.65)) if P['lamp'] else
                  mat('lamp_off', (0.55, 0.6, 0.65), 0.2, 0.08, coat=1.0))
    dark = mat('mouth', (0.18, 0.04, 0.05), 0.0, 0.5)

    root = bpy.data.objects.new('miner_' + t, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = location
    root.scale = (scale, scale, scale)

    # body: a soft bean, continuing down into the hole
    body = sphere('body_' + t, (0, 0, 0.95), (0.78, 0.66, 1.05), fur, root)
    lower = sphere('lower_' + t, (0, 0, -0.2), (0.80, 0.68, 1.3), fur, root)
    bel = sphere('belly_' + t, (0, -0.30, 0.55), (0.52, 0.40, 0.62), belly, root)
    # ears (peeking out below the hat brim)
    for s in (-1, 1):
        sphere('ear_' + t, (0.62 * s, 0.05, 1.42), (0.2, 0.12, 0.2), fur, root)
        sphere('earin_' + t, (0.64 * s, -0.04, 1.42), (0.12, 0.05, 0.12), pink, root)
    # eyes: big and glossy
    for s in (-1, 1):
        sphere('eyew_' + t, (0.27 * s, -0.56, 1.18), (0.22, 0.14, 0.25), white, root)
        sphere('pupil_' + t, (0.26 * s, -0.685, 1.16), (0.15, 0.07, 0.18), black, root)
        sphere('shine1_' + t, (0.21 * s + 0.0, -0.745, 1.24), (0.05, 0.02, 0.055), shine, root)
        sphere('shine2_' + t, (0.30 * s, -0.74, 1.09), (0.022, 0.012, 0.025), shine, root)
        sphere('cheek_' + t, (0.48 * s, -0.47, 0.92), (0.14, 0.05, 0.09), pink, root)
    # little paws held up at the chest
    for s_ in (-1, 1):
        sphere('paw_' + t, (0.34 * s_, -0.56, 0.52), (0.17, 0.13, 0.13), fur, root)
        for k in (-1, 0, 1):
            sphere('toe_' + t, (0.34 * s_ + 0.07 * k, -0.67, 0.58), (0.045, 0.03, 0.04), belly, root)
    # muzzle, nose, smile, teeth
    sphere('muzzle_' + t, (0, -0.60, 0.90), (0.26, 0.16, 0.17), belly, root)
    sphere('nose_' + t, (0, -0.755, 0.98), (0.085, 0.06, 0.065), nose, root)
    sphere('noseshine_' + t, (-0.02, -0.81, 1.0), (0.022, 0.01, 0.015), shine, root)
    tongue = mat('tongue', (1.0, 0.36, 0.40), 0.0, 0.4)
    sphere('mouth_' + t, (0, -0.735, 0.80), (0.12, 0.05, 0.075), dark, root)
    sphere('tongue_' + t, (0, -0.765, 0.765), (0.07, 0.03, 0.035), tongue, root)
    for s in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0.03 * s, -0.775, 0.855))
        th = bpy.context.object
        th.name = 'tooth_' + t
        th.scale = (0.05, 0.02, 0.05)
        th.data.materials.append(tooth)
        bv = th.modifiers.new('bev', 'BEVEL'); bv.width = 0.012; bv.segments = 3
        th.parent = root
    # miner's hard hat: dome, brim, ridge, headlamp
    dome = sphere('hat_' + t, (0, 0, 1.52), (0.74, 0.68, 0.52), hat, root, segs=64)
    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, vertices=96, location=(0, -0.06, 1.47))
    brim = bpy.context.object
    brim.name = 'brim_' + t
    brim.scale = (0.86, 0.80, 0.05)
    brim.data.materials.append(hat)
    bv = brim.modifiers.new('bev', 'BEVEL'); bv.width = 0.035; bv.segments = 4
    for poly in brim.data.polygons:
        poly.use_smooth = True
    brim.parent = root
    sphere('ridge_' + t, (0, 0.0, 1.66), (0.13, 0.62, 0.46), hat, root)
    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, vertices=48, location=(0, -0.66, 1.66), rotation=(math.radians(90), 0, 0))
    lamp = bpy.context.object
    lamp.name = 'lamp_' + t
    lamp.scale = (0.16, 0.16, 0.12)
    lamp.data.materials.append(lamp_body)
    bv = lamp.modifiers.new('bev', 'BEVEL'); bv.width = 0.02; bv.segments = 3
    lamp.parent = root
    sphere('lens_' + t, (0, -0.725, 1.66), (0.12, 0.04, 0.12), lamp_glass, root)
    return root
