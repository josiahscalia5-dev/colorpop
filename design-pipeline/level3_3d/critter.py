"""The Level 3 characters in 3D (Blender): the reference's round critters in knit caps.

  purple -- the targets: purple, darker patches round the eyes, lavender muzzle, purple cap with a
            lilac band and a lilac curl on top
  pink   -- decoy: pink, a red-pink cap with a knob
  red    -- decoy: red, tan muzzle, a red cap with a knob

build(variant, location, scale) adds one critter standing in a hole at `location` (the centre of the
hole opening on the ground plane, z = 0) and returns its root. The body continues well below the
ground so it can rise out of the hole (the game clips it at the hole's front rim).
"""
import bpy, math

PALETTE = {
    'purple': dict(fur=(0.20, 0.035, 0.62), cap=(0.10, 0.03, 0.50), band=(0.26, 0.10, 0.75), muzzle=(0.44, 0.24, 0.82),
                   mask=(0.055, 0.008, 0.20), top='curl', top_col=(0.22, 0.26, 0.92)),
    'pink':   dict(fur=(0.88, 0.07, 0.42), cap=(0.72, 0.02, 0.10), band=(0.85, 0.06, 0.18), muzzle=(1.0, 0.45, 0.68),
                   mask=None, top='knob', top_col=(0.72, 0.02, 0.10)),
    'red':    dict(fur=(0.72, 0.008, 0.01), cap=(0.55, 0.005, 0.008), band=(0.75, 0.02, 0.02), muzzle=(0.90, 0.46, 0.25),
                   mask=None, top='knob', top_col=(0.60, 0.006, 0.01)),
}


def mat(name, color, metal=0.0, rough=0.5, emit=0.0, emit_color=None, coat=0.0, sss=0.0, sheen=0.0):
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
    if sheen:
        p.inputs['Sheen Weight'].default_value = sheen
        p.inputs['Sheen Tint'].default_value = (1, 1, 1, 1)
    if sss:
        p.inputs['Subsurface Weight'].default_value = sss
        p.inputs['Subsurface Radius'].default_value = (0.3, 0.12, 0.08)
        p.inputs['Subsurface Scale'].default_value = 0.08
    if emit:
        p.inputs['Emission Color'].default_value = (*(emit_color or color), 1)
        p.inputs['Emission Strength'].default_value = emit
    return m


def knit_material(name, color):
    """The cap: soft knit (fine ribs across, a little fuzz)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = 0.55
    p.inputs['Sheen Weight'].default_value = 0.6
    p.inputs['Coat Weight'].default_value = 0.15
    tc = nt.nodes.new('ShaderNodeTexCoord')
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'; wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = 9.0
    wave.inputs['Distortion'].default_value = 0.6
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.18
    nt.links.new(tc.outputs['Object'], wave.inputs['Vector'])
    nt.links.new(wave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m


def sphere(name, loc, scale, material, parent=None, segs=48, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=segs, ring_count=segs // 2, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    for poly in o.data.polygons:
        poly.use_smooth = True
    if parent:
        o.parent = parent
    return o


def build(variant, location=(0, 0, 0), scale=1.0, tag='', ears=False, paw=False, short=False):
    """ears / paw / short: the instruction-panel portrait shows the purple whole (a rounded base instead
    of the body going down into a hole), its ears out and a paw up."""
    P = PALETTE[variant]
    t = variant + tag
    fur = mat('fur_' + variant, P['fur'], 0.0, 0.36, coat=0.3, sss=0.1)
    muzzle = mat('muzzle_' + variant, P['muzzle'], 0.0, 0.42, coat=0.2, sss=0.15)
    cap = mat('cap_' + variant, P['cap'], 0.0, 0.3, coat=0.5)          # glossy vinyl, like the reference
    band = mat('band_' + variant, P['band'], 0.0, 0.32, coat=0.5)
    top = mat('top_' + variant, P['top_col'], 0.0, 0.35, coat=0.4)
    white = mat('eye_white', (0.96, 0.96, 0.97), 0.0, 0.12, coat=1.0)
    black = mat('eye_black', (0.0, 0.0, 0.0), 0.0, 0.05, coat=1.0)
    shine = mat('eye_shine', (1, 1, 1), emit=6.0)
    nose = mat('nose_dark', (0.03, 0.012, 0.02), 0.0, 0.2, coat=0.9)
    mouth = mat('mouth_dark', (0.10, 0.02, 0.04), 0.0, 0.5)

    root = bpy.data.objects.new('critter_' + t, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = location
    root.scale = (scale, scale, scale)

    # body: a gumdrop -- round top, wider low down -- continuing into the hole
    sphere('body_' + t, (0, 0, 0.92), (0.88, 0.76, 0.98), fur, root)
    if short:
        sphere('lower_' + t, (0, 0, 0.50), (0.90, 0.80, 0.68), fur, root)
    else:
        sphere('lower_' + t, (0, 0, -0.1), (0.90, 0.80, 1.25), fur, root)
    # face: lavender / tan muzzle and chest, darker patches round the eyes (purple)
    if short:
        sphere('chest_' + t, (0, -0.56, 0.44), (0.46, 0.30, 0.36), muzzle, root)
    else:
        sphere('chest_' + t, (0, -0.44, 0.34), (0.50, 0.38, 0.42), muzzle, root)
    sphere('muzzle_' + t, (0, -0.65, 0.78), (0.25, 0.15, 0.16), muzzle, root)
    if P['mask']:
        mask = mat('mask_' + variant, P['mask'], 0.0, 0.4, coat=0.3)
        for s in (-1, 1):
            sphere('mask_' + t, (0.34 * s, -0.60, 1.04), (0.33, 0.13, 0.30), mask, root, rot=(0, 0.35 * s, 0))
    # eyes: big, glossy, looking out
    for s in (-1, 1):
        sphere('eyew_' + t, (0.33 * s, -0.66, 1.03), (0.28, 0.13, 0.30), white, root)
        sphere('pupil_' + t, (0.325 * s, -0.775, 1.01), (0.18, 0.065, 0.21), black, root)
        sphere('shine1_' + t, (0.27 * s, -0.865, 1.08), (0.058, 0.03, 0.062), shine, root)     # clean round glints,
        sphere('shine2_' + t, (0.37 * s, -0.86, 0.95), (0.026, 0.02, 0.028), shine, root)      # in front of the pupil
    # nose and a small smile
    sphere('nose_' + t, (0, -0.80, 0.84), (0.085, 0.055, 0.06), nose, root)
    sphere('noseshine_' + t, (-0.02, -0.85, 0.86), (0.022, 0.01, 0.014), shine, root)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.11, minor_radius=0.018, location=(0, -0.79, 0.74),
                                     rotation=(math.radians(90), 0, 0))
    sm = bpy.context.object
    sm.name = 'smile_' + t
    sm.data.materials.append(mouth)
    import bmesh
    bm = bmesh.new(); bm.from_mesh(sm.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > -0.02], context='VERTS')   # the lower half: a smile
    bm.to_mesh(sm.data); bm.free()
    for poly in sm.data.polygons:
        poly.use_smooth = True
    sm.parent = root
    if ears:
        pink = mat('earin_' + variant, (1.0, 0.45, 0.72), 0.0, 0.5)
        for s in (-1, 1):
            sphere('ear_' + t, (0.86 * s, 0.02, 1.16), (0.13, 0.22, 0.22), fur, root, rot=(0, 0, 0.5 * s))
            sphere('earin_' + t, (0.90 * s, -0.08, 1.16), (0.06, 0.13, 0.13), pink, root, rot=(0, 0, 0.5 * s))
    if paw:
        sphere('paw_' + t, (-0.80, -0.52, 0.72), (0.19, 0.15, 0.23), fur, root, rot=(0, -0.45, 0))
        for k in (-1, 0, 1):
            sphere('toe_' + t, (-0.86 + 0.07 * k, -0.64, 0.88 + 0.02 * abs(k)), (0.05, 0.035, 0.05), muzzle, root)
    # knit cap: dome, turned-up band, and the curl (purple) or knob on top
    sphere('cap_' + t, (0, 0.02, 1.34), (0.89, 0.79, 0.64), cap, root, segs=64)     # a round beanie
    bpy.ops.mesh.primitive_torus_add(major_radius=0.85, minor_radius=0.09, major_segments=96, minor_segments=24, location=(0, -0.01, 1.30))
    b = bpy.context.object
    b.name = 'band_' + t
    b.scale = (1.0, 0.92, 0.85)
    b.data.materials.append(band)
    for poly in b.data.polygons:
        poly.use_smooth = True
    b.parent = root
    if P['top'] == 'curl':
        # a soft lilac curl: a tapered tube rising from the crown and curling over to one side
        cd = bpy.data.curves.new('curl_' + t, 'CURVE'); cd.dimensions = '3D'
        sp = cd.splines.new('BEZIER'); sp.bezier_points.add(2)
        pts = [(0.0, 0.05, 1.96), (0.04, 0.05, 2.22), (-0.20, 0.05, 2.34)]
        for bp, co in zip(sp.bezier_points, pts):
            bp.co = co
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        tp = bpy.data.curves.new('curltaper_' + t, 'CURVE'); tp.dimensions = '2D'
        ts = tp.splines.new('BEZIER'); ts.bezier_points.add(1)
        ts.bezier_points[0].co = (0, 1.0, 0); ts.bezier_points[1].co = (1, 0.25, 0)
        for bp in ts.bezier_points:
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        taper = bpy.data.objects.new('curltaper_' + t, tp)
        bpy.context.scene.collection.objects.link(taper)
        taper.hide_render = True
        cd.bevel_depth = 0.14; cd.bevel_resolution = 6; cd.use_fill_caps = True
        cd.taper_object = taper
        co = bpy.data.objects.new('curl_' + t, cd)
        bpy.context.scene.collection.objects.link(co)
        co.data.materials.append(top)
        co.parent = root
        sphere('curltip_' + t, (-0.22, 0.05, 2.335), (0.045, 0.045, 0.045), top, root)
    else:
        sphere('knobstem_' + t, (0, 0.03, 2.0), (0.1, 0.1, 0.12), top, root)
        sphere('knob_' + t, (0, 0.03, 2.11), (0.15, 0.15, 0.13), top, root)
    return root
