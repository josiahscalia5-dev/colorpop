"""The Level 3 scene rebuilt in 3D (Blender Cycles, CPU): the reference's farmyard, high resolution.

The same layout as the reference screen (reference/screens/level3.png), in the new levels' art frame
(724 x 1570 px, rendered at 2x): a camera fitted to the reference's seven holes (their places and
sizes), a warm dirt yard, holes ringed by rounded clay bricks, a grass strip with flowers, the wooden
fence (brown top rail, pale lower rail), sunlit trees and hills with a red barn on the right beyond
it, leafy plants and flowers along the bottom. The sky is painted in 2D (sky.py) -- the render is
transparent there.
"""
import bpy, bmesh, math, random, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import critter
from critter import mat

ART_W, ART_H = 724, 1570
CAM_H, PITCH, LENS = 10.0, 24.75, 41.3         # fitted to the reference's holes: places, sizes, their flat look
R_HOLE, RIM_W, RIM_H = 1.29, 0.42, 0.28
# hole centres (art px): the reference's, in the 724-wide frame
HOLE_ART = {'H1': (333, 687), 'H2': (150, 785), 'H3': (583, 782), 'H4': (369, 960), 'H5': (40, 1000),
            'H6': (690, 1000), 'H7': (228, 1243)}
FENCE_Y = 600                                   # art px of the fence's foot (reference)


def ray_to_ground(px, py):
    th = math.radians(90 - PITCH)
    sx = (px - ART_W / 2) / ART_H * 36
    sy = (ART_H / 2 - py) / ART_H * 36
    d = Vector((sx, sy * math.cos(th) + LENS * math.sin(th), sy * math.sin(th) - LENS * math.cos(th)))
    t = CAM_H / -d.z
    return Vector((d.x * t, d.y * t, 0.0))


YARD_END = ray_to_ground(ART_W / 2, FENCE_Y).y  # the fence line (world y)
_SHARED = {}


def reset(scale=1.0, samples=64):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _SHARED.clear()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.view_settings.view_transform = 'Khronos PBR Neutral'    # keeps the reference's vivid colours
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.render.resolution_x, sc.render.resolution_y = ART_W * 2, ART_H * 2
    sc.render.resolution_percentage = int(round(scale * 100))
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'
    cam = bpy.data.cameras.new('cam')
    cam.lens = LENS
    cam.sensor_fit = 'VERTICAL'
    cam.sensor_height = 36
    cam.clip_end = 400
    co = bpy.data.objects.new('cam', cam)
    sc.collection.objects.link(co)
    co.location = (0, 0, CAM_H)
    co.rotation_euler = (math.radians(90 - PITCH), 0, 0)
    sc.camera = co
    return sc


def light(sc, kind, loc, target, energy, color, size=2.0, radius=0.1, angle=None):
    l = bpy.data.lights.new(kind, kind)
    l.energy = energy
    l.color = color
    if kind == 'AREA':
        l.size = size
    elif kind == 'SUN':
        l.angle = angle if angle is not None else 0.05
    else:
        l.shadow_soft_size = radius
    o = bpy.data.objects.new(kind, l)
    sc.collection.objects.link(o)
    o.location = loc
    if target is not None:
        d = Vector(target) - Vector(loc)
        o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def obj_from(name, material=None, smooth=True, parent=None):
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    if smooth and o.type == 'MESH':
        for p in o.data.polygons:
            p.use_smooth = True
    if parent:
        o.parent = parent
    return o


def instance(name, me, loc, scale, rot, material, parent=None):
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.scale = scale
    o.rotation_euler = rot
    if material:
        if not me.materials:
            me.materials.append(material)
        o.material_slots[0].link = 'OBJECT'
        o.material_slots[0].material = material
    if parent:
        o.parent = parent
    return o


def shared_mesh(kind, i):
    """A few shared meshes (bricks, pebbles, leaves, petals...), instanced many times."""
    key = (kind, i)
    if key in _SHARED:
        return _SHARED[key]
    bm = bmesh.new()
    r = random.Random(100 + i)
    if kind == 'brick':
        # a rounded clay block: a superellipsoid (a box with soft, seamless round edges)
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=1.0)
        for v in bm.verts:
            v.co = type(v.co)([math.copysign(abs(c) ** 0.4, c) * 0.5 for c in v.co])
            v.co.z *= 1 + 0.04 * math.sin(3 * v.co.x + i)
    elif kind in ('pebble', 'bush'):
        bmesh.ops.create_icosphere(bm, subdivisions=2 if kind == 'pebble' else 3, radius=1.0)
        for v in bm.verts:
            n = v.co.normalized()
            v.co = v.co * (1 + (0.12 if kind == 'bush' else 0.06) * math.sin(4.1 * n.x + i) * math.cos(3.3 * n.y - i))
    elif kind == 'leaf':
        # a broad leaf: flat teardrop, curled a little
        verts = []
        for k in range(17):
            a = math.pi * k / 16
            verts.append((0.42 * math.sin(a) * (1 - 0.3 * (1 - math.sin(a))), 1.0 - (1 - math.cos(a)) * 0.5))
        top = [bm.verts.new((x, y, 0.08 * x * x)) for x, y in verts]
        bot = [bm.verts.new((-x, y, 0.08 * x * x)) for x, y in reversed(verts[1:-1])]
        bm.faces.new(top + bot)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
        for v in bm.verts:
            v.co.z += 0.18 * (v.co.y - 0.5) ** 2 - 0.12 * abs(v.co.x)
    elif kind == 'petal':
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    elif kind == 'crown':
        # a tree crown: a lumpy sphere
        bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
        for v in bm.verts:
            n = v.co.normalized()
            v.co = v.co * (1 + 0.09 * math.sin(5 * n.x + i) * math.cos(4 * n.z - i) + 0.05 * math.sin(11 * n.y + 2 * i))
    me = bpy.data.meshes.new('%s%d' % (kind, i))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    _SHARED[key] = me
    return me


# ---------------------------------------------------------------- materials
def noise_ramp_material(name, c0, c1, scale0=0.4, scale1=3.0, bump=0.3, rough=0.9, p0=0.3, p1=0.75):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Roughness'].default_value = rough
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = scale0; n1.inputs['Detail'].default_value = 3
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = scale1; n2.inputs['Detail'].default_value = 6
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'FLOAT'; mix.inputs[0].default_value = 0.35
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    rr = ramp.color_ramp
    rr.elements[0].position = p0; rr.elements[0].color = (*c0, 1)
    rr.elements[1].position = p1; rr.elements[1].color = (*c1, 1)
    for n in (n1, n2):
        nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    nt.links.new(n1.outputs['Fac'], mix.inputs[2])
    nt.links.new(n2.outputs['Fac'], mix.inputs[3])
    nt.links.new(mix.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    if bump:
        n3 = nt.nodes.new('ShaderNodeTexNoise'); n3.inputs['Scale'].default_value = 7; n3.inputs['Detail'].default_value = 8
        b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = bump
        nt.links.new(tc.outputs['Object'], n3.inputs['Vector'])
        nt.links.new(n3.outputs['Fac'], b.inputs['Height'])
        nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return m


def dirt_material():
    # the reference's warm orange-brown yard, lighter where it is dusty
    return noise_ramp_material('dirt', (0.36, 0.12, 0.035), (0.62, 0.26, 0.08), 0.25, 2.5, 0.25)


def grass_material():
    return noise_ramp_material('grass', (0.05, 0.22, 0.02), (0.20, 0.50, 0.05), 0.3, 4.0, 0.2, rough=0.75)


BRICK_TONES = [(0.30, 0.11, 0.04), (0.25, 0.09, 0.033), (0.35, 0.14, 0.05), (0.28, 0.10, 0.038)]


def brick_material(i):
    return mat('brick%d' % i, BRICK_TONES[i % len(BRICK_TONES)], 0.0, 0.55, coat=0.15)


# ---------------------------------------------------------------- the yard and its holes
def ground(sc, holes_world):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=220, y_subdivisions=160, size=1, location=(0, 0, 0))
    g = bpy.context.object
    g.name = 'ground'
    g.scale = (46, YARD_END + 8, 1)
    g.location = (0, (YARD_END - 8) / 2 + 4, 0)
    bpy.ops.object.transform_apply(location=True, scale=True)
    bm = bmesh.new()
    bm.from_mesh(g.data)
    kill = [f for f in bm.faces if any((Vector((f.calc_center_median().x, f.calc_center_median().y)) - Vector((x, y))).length < R_HOLE + 0.1
                                       for (x, y) in holes_world)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y > YARD_END], context='FACES')
    bm.to_mesh(g.data)
    bm.free()
    g.data.materials.append(dirt_material())
    return g


def hole(name, x, y, rnd):
    parent = bpy.data.objects.new('hole_' + name, None)
    bpy.context.scene.collection.objects.link(parent)
    wall = mat('pitwall', (0.06, 0.028, 0.015), 0, 0.95)
    bpy.ops.mesh.primitive_cylinder_add(radius=R_HOLE + 0.12, depth=3.4, vertices=128, location=(x, y, -1.7), end_fill_type='NOTHING')
    obj_from('pit_' + name, wall, parent=parent)
    bpy.ops.mesh.primitive_circle_add(radius=R_HOLE + 0.12, vertices=128, fill_type='NGON', location=(x, y, -1.2))
    obj_from('pitfloor_' + name, mat('pitfloor', (0.0, 0.0, 0.0), 0, 1.0), parent=parent)
    # a ring of rounded clay bricks, like a curb (named stone_* for the rim-id pass)
    n = 16
    rr = R_HOLE + RIM_W * 0.5
    for i in range(n):
        a = 2 * math.pi * i / n + rnd.uniform(-0.015, 0.015)
        cx, cy = x + rr * math.cos(a), y + rr * math.sin(a)
        length = 2 * math.pi * rr / n * 0.97
        hgt = RIM_H * rnd.uniform(0.92, 1.06)
        instance('stone_%s_%d' % (name, i), shared_mesh('brick', rnd.randrange(6)), (cx, cy, hgt * 0.42),
                 (RIM_W * rnd.uniform(0.95, 1.05), length * rnd.uniform(0.95, 1.02), hgt),
                 (rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), a), brick_material(rnd.randrange(4)), parent)
    return parent


def free_of_holes(holes_world, x, y, r):
    return all((Vector((x, y)) - Vector(h)).length > R_HOLE + RIM_W + r for h in holes_world)


FLOWERS = [((1.0, 0.80, 0.05), (0.95, 0.35, 0.02)), ((1.0, 1.0, 1.0), (1.0, 0.72, 0.05)), ((0.55, 0.25, 1.0), (1.0, 0.85, 0.2)),
           ((1.0, 0.40, 0.70), (1.0, 0.9, 0.3))]


def flower(x, y, z, s, k, rnd, n_petals=6):
    petal_col, heart_col = FLOWERS[k % len(FLOWERS)]
    pm = mat('petal%d' % k, petal_col, 0, 0.45, sss=0.2, coat=0.2)
    hm = mat('heart%d' % k, heart_col, 0, 0.5)
    rot0 = rnd.uniform(0, 6.28)
    for j in range(n_petals):
        a = rot0 + 2 * math.pi * j / n_petals
        instance('petal', shared_mesh('petal', 0), (x + 0.55 * s * math.cos(a), y + 0.55 * s * math.sin(a), z),
                 (0.5 * s, 0.24 * s, 0.07 * s), (0, 0, a), pm)
    instance('heart', shared_mesh('petal', 0), (x, y, z + 0.04 * s), (0.28 * s, 0.28 * s, 0.14 * s), (0, 0, 0), hm)


def tuft(x, y, s, rnd, material):
    for j in range(7):
        a = rnd.uniform(0, 6.28)
        instance('blade', shared_mesh('leaf', 0), (x, y, 0), (0.18 * s, 0.9 * s * rnd.uniform(0.7, 1.2), 0.18 * s),
                 (math.radians(rnd.uniform(60, 85)), 0, a), material)


def scatter(sc, holes_world, rnd):
    peb = [mat('pebble%d' % i, c, 0, 0.7) for i, c in enumerate(((0.42, 0.30, 0.22), (0.32, 0.22, 0.16), (0.55, 0.42, 0.32)))]
    placed = 0
    while placed < 70:
        p = ray_to_ground(rnd.uniform(-40, ART_W + 40), rnd.uniform(FENCE_Y + 20, ART_H + 60))
        if p.y > YARD_END - 1.2 or not free_of_holes(holes_world, p.x, p.y, 0.15):
            continue
        s = rnd.uniform(0.04, 0.1)
        instance('pebble', shared_mesh('pebble', rnd.randrange(3)), (p.x, p.y, s * 0.3), (s * rnd.uniform(0.9, 1.4), s * rnd.uniform(0.9, 1.4), s * 0.6),
                 (0, 0, rnd.uniform(0, 6.28)), peb[rnd.randrange(3)])
        placed += 1
    # grass: the strip along the fence, a patch on the right (reference), tufts here and there
    gm = mat('blade', (0.10, 0.40, 0.03), 0, 0.6, sss=0.2)
    strip = grass_material()
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, YARD_END - 0.55, 0.012))
    s_ = obj_from('grass_strip', strip); s_.scale = (60, 1.4, 1)
    for i in range(160):
        x = rnd.uniform(-16, 16)
        tuft(x, YARD_END - rnd.uniform(0.0, 1.2), rnd.uniform(0.35, 0.6), rnd, gm)
    for i in range(34):
        x = rnd.uniform(-15, 15)
        flower(x, YARD_END - rnd.uniform(0.1, 1.0), 0.32, rnd.uniform(0.16, 0.24), rnd.randrange(4), rnd)
    patch = ray_to_ground(655, 900)             # a tuft-covered green patch (loose tufts, no flat disc)
    for i in range(70):
        x, y = patch.x + rnd.uniform(-1.4, 1.4), patch.y + rnd.uniform(-0.9, 0.9)
        if free_of_holes(holes_world, x, y, 0.3):
            tuft(x, y, rnd.uniform(0.3, 0.5), rnd, gm)
    placed = 0
    while placed < 22:
        p = ray_to_ground(rnd.uniform(0, ART_W), rnd.uniform(FENCE_Y + 40, 1400))
        if p.y > YARD_END - 1.5 or not free_of_holes(holes_world, p.x, p.y, 0.4):
            continue
        tuft(p.x, p.y, rnd.uniform(0.22, 0.36), rnd, gm)
        placed += 1


# ---------------------------------------------------------------- beyond the fence
def beam(name, a, b, w, material, h=None):
    """A timber from point a to point b (w wide, h deep)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cube_add(size=1, location=(a + b) / 2)
    o = obj_from(name, material)
    o.scale = (w, h or w, d.length)
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    bv = o.modifiers.new('bev', 'BEVEL'); bv.width = min(w, h or w) * 0.2; bv.segments = 3
    return o


def fence(sc, rnd):
    wood = noise_ramp_material('fencewood', (0.24, 0.10, 0.035), (0.42, 0.20, 0.08), 1.5, 9.0, 0.35, rough=0.7)
    pale = noise_ramp_material('fencepale', (0.30, 0.26, 0.33), (0.46, 0.41, 0.50), 1.5, 9.0, 0.3, rough=0.7)
    y = YARD_END + 0.3
    xs = [-19 + 2.9 * i + rnd.uniform(-0.12, 0.12) for i in range(15)]
    for x in xs:
        hgt = 2.0 + rnd.uniform(-0.08, 0.08)
        p = beam('post', (x, y, 0), (x, y, hgt), 0.44, wood, 0.38)
        p.rotation_euler.z += rnd.uniform(-0.05, 0.05)
    beam('rail_top', (xs[0] - 1, y - 0.24, 1.58), (xs[-1] + 1, y - 0.24, 1.58), 0.40, wood, 0.18)
    beam('rail_low', (xs[0] - 1, y - 0.24, 0.82), (xs[-1] + 1, y - 0.24, 0.82), 0.34, pale, 0.18)


def backdrop(sc, rnd):
    """Meadow behind the fence, rolling hills, sunlit trees, a red barn on the right."""
    y0 = YARD_END + 0.4
    meadow = grass_material()
    DEPTH = 17.0                                # the meadow ends behind the far tree line: sky above it
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=30, size=1, location=(0, 0, 0))
    m = obj_from('meadow', meadow)
    m.scale = (90, DEPTH, 1)
    m.location = (0, y0 + DEPTH / 2, 0)
    bpy.ops.object.transform_apply(location=True, scale=True)
    for v in m.data.vertices:
        d = v.co.y - y0
        v.co.z = 0.06 * d
    for v in m.data.vertices:
        if v.co.y < y0 + 0.2:
            v.co.z = -0.02
    # trees: trunks and lumpy crowns, sunlit yellow-green, in two bands
    trunk = mat('trunk', (0.20, 0.10, 0.04), 0, 0.8)
    crowns = [noise_ramp_material('crown%d' % i, c0, c1, 1.2, 6.0, 0.6, rough=0.8)
              for i, (c0, c1) in enumerate((((0.04, 0.18, 0.02), (0.30, 0.52, 0.04)), ((0.08, 0.22, 0.02), (0.55, 0.55, 0.05)),
                                            ((0.03, 0.14, 0.03), (0.18, 0.42, 0.06))))]
    def ground_z(x, y):
        d = y - y0
        return 0.06 * d
    # a hedge of round bushes right behind the fence
    bush = [noise_ramp_material('bush%d' % i, c0, c1, 1.5, 8.0, 0.6, rough=0.8)
            for i, (c0, c1) in enumerate((((0.03, 0.16, 0.02), (0.22, 0.48, 0.04)), ((0.06, 0.2, 0.02), (0.42, 0.52, 0.05))))]
    for i in range(60):
        x = rnd.uniform(-26, 26)
        yy = y0 + rnd.uniform(0.8, 3.0)
        s_ = rnd.uniform(0.9, 1.6)
        instance('bush', shared_mesh('crown', rnd.randrange(5)), (x, yy, s_ * 0.55), (s_ * 1.3, s_, s_ * 0.9), (0, 0, rnd.uniform(0, 6.28)),
                 bush[rnd.randrange(2)])
    for band, (ya, yb, n, smin, smax) in enumerate(((y0 + 4, y0 + 10, 20, 1.1, 1.8), (y0 + 12, y0 + 16.5, 46, 1.5, 2.4))):
        for i in range(n):
            x = rnd.uniform(-24 - band * 6, 24 + band * 6)
            yy = rnd.uniform(ya, yb)
            if 9 < x < 21:
                continue                        # the barn stands there
            s = rnd.uniform(smin, smax)
            z = ground_z(x, yy)
            beam('trunk', (x, yy, z - 0.2), (x, yy, z + s * 0.9), 0.35 * s / 2, trunk)
            instance('crown', shared_mesh('crown', rnd.randrange(5)), (x, yy, z + s * 1.25), (s * 0.95, s * 0.85, s * 0.9),
                     (0, 0, rnd.uniform(0, 6.28)), crowns[rnd.randrange(3)])
            if rnd.random() < 0.6:
                instance('crown', shared_mesh('crown', rnd.randrange(5)), (x + s * 0.45, yy + 0.3, z + s * 0.95), (s * 0.6, s * 0.55, s * 0.55),
                         (0, 0, rnd.uniform(0, 6.28)), crowns[rnd.randrange(3)])
    # the red barn and its silo (right, behind the fence, as in the reference)
    red = noise_ramp_material('barnred', (0.35, 0.02, 0.015), (0.62, 0.05, 0.03), 2.0, 12.0, 0.2, rough=0.6)
    roofm = mat('barnroof', (0.20, 0.10, 0.08), 0, 0.6)
    white = mat('barnwhite', (0.9, 0.88, 0.84), 0, 0.5)
    bx, by = 15.0, y0 + 9
    bz = ground_z(bx, by)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, bz + 1.6))
    b = obj_from('barn', red); b.scale = (4.4, 3.4, 3.2)
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=3.4, depth=1.9, location=(bx, by, bz + 4.15), rotation=(0, 0, math.pi / 4))
    r = obj_from('barnroof', roofm, smooth=False); r.scale = (1.0, 0.8, 1.0)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by - 1.72, bz + 1.1))
    d = obj_from('barndoor', white); d.scale = (1.6, 0.06, 2.0)
    bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=5.6, vertices=48, location=(bx + 3.6, by + 0.8, bz + 2.8))
    obj_from('silo', red)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(bx + 3.6, by + 0.8, bz + 5.6))
    obj_from('silotop', white)


def foreground(sc, rnd):
    """Leafy plants and flowers along the bottom of the screen (reference)."""
    leafm = [mat('leaf%d' % i, c, 0, 0.45, sss=0.2, coat=0.2) for i, c in enumerate(((0.03, 0.18, 0.015), (0.06, 0.28, 0.02), (0.02, 0.13, 0.012)))]
    for (px, py, n) in ((20, ART_H + 40, 14), (160, ART_H + 70, 9), (520, ART_H + 70, 10), (700, ART_H + 30, 14), (360, ART_H + 110, 8)):
        base = ray_to_ground(px, py)
        for j in range(n):
            a = rnd.uniform(0, 6.28)
            s = rnd.uniform(0.55, 0.95)
            instance('leaf', shared_mesh('leaf', 0), (base.x + rnd.uniform(-0.5, 0.5), base.y + rnd.uniform(-0.4, 0.3), 0.05),
                     (s * 1.1, s * 1.5, s), (math.radians(rnd.uniform(35, 70)), 0, a), leafm[rnd.randrange(3)])
    for (px, py, k) in ((90, 1470, 0), (60, 1540, 0), (175, 1510, 1), (430, 1530, 2), (540, 1450, 0), (640, 1470, 1), (700, 1540, 3), (330, 1500, 1)):
        p = ray_to_ground(px, py)
        flower(p.x, p.y, 0.55 + rnd.uniform(0, 0.25), rnd.uniform(0.32, 0.42), k, rnd, n_petals=6 if k != 2 else 5)


def build(sc, seed=5):
    rnd = random.Random(seed)
    holes_world = {k: ray_to_ground(*v) for k, v in HOLE_ART.items()}
    hw = [(p.x, p.y) for p in holes_world.values()]
    ground(sc, hw)
    for k, p in holes_world.items():
        hole(k, p.x, p.y, rnd)
    scatter(sc, hw, rnd)
    fence(sc, rnd)
    backdrop(sc, rnd)
    foreground(sc, rnd)
    # a sunny afternoon: the sun high on the left (behind a little), blue sky light, warm bounce
    w = bpy.data.worlds.new('day'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.45, 0.62, 1.0, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.55
    light(sc, 'SUN', (-10, 30, 20), (2, 10, 0), 4.0, (1.0, 0.84, 0.60), angle=0.08)       # golden sun: upper left, behind
    light(sc, 'AREA', (-9, -4, 12), (0, 14, 0), 12000, (1.0, 0.90, 0.76), 12)           # soft warm key from the front left (faces)
    light(sc, 'AREA', (10, 0, 8), (0, 16, 0), 3000, (0.85, 0.9, 1.0), 10)              # cool fill from the right
    return holes_world


# the reference moment: two purples (targets), the pink and the red decoys, three empty holes
CAST = {'H1': 'pink', 'H2': 'purple', 'H3': 'red', 'H4': 'purple', 'H5': None, 'H6': None, 'H7': None}
CHAR_SCALE, CHAR_SINK, CHAR_TILT = 1.0, -0.62, -21.0


def characters(sc, holes_world, cast=CAST):
    roots = {}
    for k, variant in cast.items():
        if not variant:
            continue
        p = holes_world[k]
        r = critter.build(variant, (p.x, p.y, CHAR_SINK), CHAR_SCALE, tag='_' + k)
        r.scale = (CHAR_SCALE * 1.1, CHAR_SCALE * 1.05, CHAR_SCALE)       # chunky, like the reference
        cam = sc.camera.location
        yaw = math.atan2(cam.x - p.x, -(cam.y - p.y))
        r.rotation_euler = (math.radians(CHAR_TILT), 0, yaw)
        roots[k] = r
    return roots


if __name__ == '__main__':
    argv = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if not a.startswith('--')]
    samples = int(argv[0]) if argv else 16
    scale = float(argv[1]) if len(argv) > 1 else 0.5
    out = argv[2] if len(argv) > 2 else '/tmp/claude-0/-home-user-colorpop/b506899a-d85d-5b15-9527-e91d05eeee0f/scratchpad/l3r/layout.png'
    sc = reset(scale, samples)
    hw = build(sc)
    if '--chars' in sys.argv:
        characters(sc, hw)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
