"""The new Level 8 scene: a gold-mine yard at night (3D, Blender Cycles, CPU).

Rendered at twice the Level 8 art resolution (art frame 724 x 1570 px). The camera looks down at
the playfield like the other levels (holes drawn as ellipses, far ones smaller), the mine (hill,
entrance, head-frame, rails, cart, lanterns) stands at the far edge of the yard, the night sky is
painted in 2D behind it (sky.py) -- the render is transparent there.
"""
import bpy, bmesh, math, random, os, sys
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import miner
from miner import mat

ART_W, ART_H = 724, 1570
CAM_H, PITCH, LENS = 10.0, 18.7, 73.4          # camera height, pitch below the horizon (deg), mm (sensor 36 vertical)
R_HOLE, RIM_W, RIM_H = 0.85, 0.36, 0.24
# hole centres (art px): 2 far, 3 middle (the outer ones cut by the screen edges), 2, 1 near
HOLE_ART = {'H1': (214, 700), 'H2': (510, 700), 'H3': (66, 852), 'H4': (362, 842), 'H5': (658, 852),
            'H6': (206, 1012), 'H7': (518, 1012), 'H8': (362, 1200)}
YARD_END = 40.0                                 # far edge of the flat yard (world y)


def ray_to_ground(px, py):
    th = math.radians(90 - PITCH)
    sx = (px - ART_W / 2) / ART_H * 36
    sy = (ART_H / 2 - py) / ART_H * 36
    d = Vector((sx, sy * math.cos(th) + LENS * math.sin(th), sy * math.sin(th) - LENS * math.cos(th)))
    t = CAM_H / -d.z
    return Vector((d.x * t, d.y * t, 0.0))


def reset(scale=1.0, samples=64):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.view_settings.exposure = 0.35
    sc.render.resolution_x, sc.render.resolution_y = ART_W * 2, ART_H * 2
    sc.render.resolution_percentage = int(round(scale * 100))
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'
    cam = bpy.data.cameras.new('cam')
    cam.lens = LENS
    cam.sensor_fit = 'VERTICAL'
    cam.sensor_height = 36
    co = bpy.data.objects.new('cam', cam)
    sc.collection.objects.link(co)
    co.location = (0, 0, CAM_H)
    co.rotation_euler = (math.radians(90 - PITCH), 0, 0)
    sc.camera = co
    return sc


def light(sc, kind, loc, target, energy, color, size=2.0, radius=0.1):
    l = bpy.data.lights.new(kind, kind)
    l.energy = energy
    l.color = color
    if kind == 'AREA':
        l.size = size
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


# ---------------------------------------------------------------- materials
def dirt_material():
    m = bpy.data.materials.new('dirt')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Roughness'].default_value = 0.9
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.35; n1.inputs['Detail'].default_value = 3
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 3.0; n2.inputs['Detail'].default_value = 6
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'FLOAT'; mix.inputs[0].default_value = 0.35
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    r = ramp.color_ramp
    r.elements[0].position = 0.3; r.elements[0].color = (0.24, 0.10, 0.045, 1)
    r.elements[1].position = 0.72; r.elements[1].color = (0.50, 0.25, 0.10, 1)
    for n in (n1, n2):
        nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    nt.links.new(n1.outputs['Fac'], mix.inputs[2])
    nt.links.new(n2.outputs['Fac'], mix.inputs[3])
    nt.links.new(mix.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    n3 = nt.nodes.new('ShaderNodeTexNoise'); n3.inputs['Scale'].default_value = 9; n3.inputs['Detail'].default_value = 8
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35
    nt.links.new(tc.outputs['Object'], n3.inputs['Vector'])
    nt.links.new(n3.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    return m


STONE_TONES = [(0.20, 0.15, 0.17), (0.16, 0.12, 0.15), (0.24, 0.17, 0.15), (0.13, 0.10, 0.13), (0.22, 0.16, 0.14), (0.18, 0.14, 0.17)]


def stone_material(i, rnd):
    return mat('stone%d' % i, STONE_TONES[i % len(STONE_TONES)], 0.0, 0.45, coat=0.35)


def gold_material():
    return mat('gold', (1.0, 0.66, 0.12), 1.0, 0.22, emit=0.25, emit_color=(1.0, 0.6, 0.1))


# ---------------------------------------------------------------- ground with holes
def ground(sc, holes_world):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=200, y_subdivisions=200, size=1, location=(0, 0, 0))
    g = bpy.context.object
    g.name = 'ground'
    g.scale = (44, YARD_END + 6, 1)
    g.location = (0, (YARD_END - 6) / 2 + 3, 0)
    bpy.ops.object.transform_apply(location=True, scale=True)
    bm = bmesh.new()
    bm.from_mesh(g.data)
    kill = [f for f in bm.faces if any((Vector((f.calc_center_median().x, f.calc_center_median().y)) - Vector((x, y))).length < R_HOLE + 0.08
                                       for (x, y) in holes_world)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    far = [f for f in bm.faces if f.calc_center_median().y > YARD_END]
    bmesh.ops.delete(bm, geom=far, context='FACES')
    bm.to_mesh(g.data)
    bm.free()
    g.data.materials.append(dirt_material())
    return g


_SHARED = {}


def shared_mesh(kind, i, rnd):
    """A few shared meshes (stones, pebbles, nuggets), instanced many times."""
    key = (kind, i)
    if key in _SHARED:
        return _SHARED[key]
    bm = bmesh.new()
    if kind == 'stone':
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        r = random.Random(100 + i)
        for v in bm.verts:
            n = v.co.normalized()
            v.co = v.co * (1 + 0.10 * math.sin(3.1 * n.x + i) * math.cos(2.7 * n.y - i) + r.uniform(-0.015, 0.015))
    elif kind == 'pebble':
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    else:   # nugget: a lumpy low-poly rock
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        r = random.Random(200 + i)
        for v in bm.verts:
            v.co *= r.uniform(0.75, 1.15)
    me = bpy.data.meshes.new('%s%d' % (kind, i))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = kind != 'nugget'
    _SHARED[key] = me
    return me


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


def hole(name, x, y, rnd):
    parent = bpy.data.objects.new('hole_' + name, None)
    bpy.context.scene.collection.objects.link(parent)
    # pit wall: an open tube, dark earth getting darker downwards
    wall = mat('pitwall', (0.07, 0.035, 0.02), 0, 0.95)
    bpy.ops.mesh.primitive_cylinder_add(radius=R_HOLE + 0.1, depth=3.0, vertices=96, location=(x, y, -1.5), end_fill_type='NOTHING')
    obj_from('pit_' + name, wall, parent=parent)
    bpy.ops.mesh.primitive_circle_add(radius=R_HOLE + 0.1, vertices=96, fill_type='NGON', location=(x, y, -0.9))
    obj_from('pitfloor_' + name, mat('pitfloor', (0.0, 0.0, 0.0), 0, 1.0), parent=parent)
    # rim: rounded stones, two rows, slightly irregular
    n = 20
    for row in range(2):
        rr = R_HOLE + RIM_W * (0.32 if row == 0 else 0.78)
        for i in range(n if row == 0 else n + 4):
            nn = n if row == 0 else n + 4
            a = 2 * math.pi * (i + (0.5 if row else 0)) / nn + rnd.uniform(-0.04, 0.04)
            cx, cy = x + rr * math.cos(a), y + rr * math.sin(a)
            size = 2 * math.pi * rr / nn * 0.62
            hgt = RIM_H * (1.0 if row == 0 else 0.72) * rnd.uniform(0.85, 1.12)
            instance('stone_%s_%d_%d' % (name, row, i), shared_mesh('stone', rnd.randrange(8), rnd), (cx, cy, hgt * 0.35),
                     (RIM_W * (0.36 if row == 0 else 0.3) * rnd.uniform(0.9, 1.1), size * rnd.uniform(0.9, 1.15), hgt),
                     (rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1), a), stone_material(rnd.randrange(6), rnd), parent)
    return parent


# ---------------------------------------------------------------- scatter: pebbles, nuggets
def scatter(sc, holes_world, rnd, n_pebbles=90, n_nuggets=22):
    peb = [mat('pebble%d' % i, (0.20 + 0.04 * i, 0.15 + 0.03 * i, 0.16 + 0.03 * i), 0, 0.7) for i in range(3)]
    gold = gold_material()
    def free(x, y, r):
        return all((Vector((x, y)) - Vector(h)).length > R_HOLE + RIM_W + r for h in holes_world)
    placed = 0
    while placed < n_pebbles:
        p = ray_to_ground(rnd.uniform(-60, ART_W + 60), rnd.uniform(560, ART_H + 80))
        if p.y > YARD_END - 0.5 or not free(p.x, p.y, 0.2):
            continue
        s = rnd.uniform(0.03, 0.08)
        instance('pebble', shared_mesh('pebble', 0, rnd), (p.x, p.y, s * 0.3), (s * rnd.uniform(0.8, 1.4), s * rnd.uniform(0.8, 1.4), s * 0.6),
                 (0, 0, rnd.uniform(0, 6.28)), peb[rnd.randrange(3)])
        placed += 1
    placed = 0
    while placed < n_nuggets:
        p = ray_to_ground(rnd.uniform(0, ART_W), rnd.uniform(600, ART_H))
        if p.y > YARD_END - 0.5 or not free(p.x, p.y, 0.25):
            continue
        s = rnd.uniform(0.07, 0.15)
        instance('nugget', shared_mesh('nugget', rnd.randrange(4), rnd), (p.x, p.y, s * 0.4), (s * rnd.uniform(0.9, 1.3), s * rnd.uniform(0.9, 1.3), s * 0.75),
                 (rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0, 6.28)), gold)
        placed += 1


# ---------------------------------------------------------------- the mine at the far edge
def beam(name, a, b, w, material):
    """A square timber from point a to point b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cube_add(size=1, location=(a + b) / 2)
    o = obj_from(name, material)
    o.scale = (w, w, d.length)
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    bv = o.modifiers.new('bev', 'BEVEL'); bv.width = w * 0.18; bv.segments = 2
    return o


def mine(sc, rnd):
    rock = mat('hillrock', (0.045, 0.04, 0.085), 0, 0.8)
    wood = mat('wood', (0.42, 0.21, 0.09), 0, 0.65)
    wood_dark = mat('wood_dark', (0.20, 0.09, 0.04), 0, 0.7)
    iron = mat('iron', (0.30, 0.31, 0.36), 0.85, 0.32)
    lamp = mat('lanternglass', (1.0, 0.8, 0.45), emit=25.0, emit_color=(1.0, 0.66, 0.26))
    black = mat('tunnel', (0.0, 0.0, 0.0), 0, 1)
    y0 = YARD_END + 0.3
    # low hill ridge behind the yard (its top at ~1/4 of the screen)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=160, y_subdivisions=24, size=1, location=(0, 0, 0))
    hill = obj_from('hill', rock)
    hill.scale = (80, 14, 1)
    hill.location = (0, y0 + 7, 0)
    bpy.ops.object.transform_apply(location=True, scale=True)
    for v in hill.data.vertices:
        x, y = v.co.x, v.co.y
        k = min(1.0, max(0.0, (y - y0 + 0.5) / 3.0))
        ridge = 0.62 + 0.18 * math.sin(x * 0.7 + 0.4) + 0.1 * math.sin(x * 1.9 + 2.0) + 0.04 * math.sin(x * 5.1)
        ridge += 1.35 * math.exp(-((x + 2.6) / 1.9) ** 2)          # the mine hill (left of centre)
        ridge += 0.3 * math.exp(-((x - 3.2) / 1.2) ** 2)
        v.co.z = k * ridge - 0.3 * (1 - k)
    # little pine silhouettes on the ridge
    pine = mat('pine', (0.02, 0.05, 0.06), 0, 0.8)
    for i in range(26):
        x = rnd.uniform(-7, 7)
        if abs(x + 2.5) < 1.3:
            continue
        yy = y0 + rnd.uniform(2.5, 6)
        ridge = 0.62 + 0.18 * math.sin(x * 0.7 + 0.4) + 0.1 * math.sin(x * 1.9 + 2.0) + 1.35 * math.exp(-((x + 2.6) / 1.9) ** 2) + 0.3 * math.exp(-((x - 3.2) / 1.2) ** 2)
        hgt = rnd.uniform(0.35, 0.7)
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=hgt * 0.32, depth=hgt, location=(x, yy, ridge + hgt / 2 - 0.1))
        obj_from('pine', pine)
    # mine entrance in the hill (left): tunnel, timber frame, sign
    ex, ey = -2.5, y0 + 0.35
    bpy.ops.mesh.primitive_cube_add(size=1, location=(ex, ey + 0.6, 0.8))
    t = obj_from('tunnel', black, smooth=False); t.scale = (1.3, 1.2, 1.2)
    beam('post', (ex - 0.75, ey, 0), (ex - 0.72, ey, 1.3), 0.2, wood)
    beam('post', (ex + 0.75, ey, 0), (ex + 0.72, ey, 1.3), 0.2, wood)
    beam('lintel', (ex - 0.98, ey - 0.02, 1.3), (ex + 0.98, ey - 0.02, 1.3), 0.22, wood)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(ex, ey - 0.1, 1.72))
    sign = obj_from('sign', wood_dark); sign.scale = (1.3, 0.1, 0.36)
    bv = sign.modifiers.new('bev', 'BEVEL'); bv.width = 0.04; bv.segments = 2
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.12, location=(ex + 0.72, ey - 0.3, 1.12))
    obj_from('tunnel_lamp', lamp)
    light(sc, 'POINT', (ex + 0.72, ey - 0.6, 1.1), None, 90, (1.0, 0.62, 0.28), radius=0.15)
    # rails from the tunnel into the yard, bending right
    def rail_xy(u):
        return ex - 2.2 * u * u, ey - 0.3 - u * 5.0
    for side in (-0.34, 0.34):
        cd = bpy.data.curves.new('rail', 'CURVE'); cd.dimensions = '3D'
        sp = cd.splines.new('POLY'); sp.points.add(39)
        for i, p in enumerate(sp.points):
            u = i / 39
            x, y = rail_xy(u)
            dx = -4.4 * u / 5.0
            nx, ny = 1 / math.sqrt(1 + dx * dx), dx / math.sqrt(1 + dx * dx)
            p.co = (x + side * nx, y + side * ny, 0.06, 1)
        cd.bevel_depth = 0.04
        ro = bpy.data.objects.new('rail', cd); sc.collection.objects.link(ro)
        ro.data.materials.append(iron)
    for i in range(14):
        u = i / 13
        x, y = rail_xy(u)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.025))
        tie = obj_from('tie', wood_dark); tie.scale = (1.0, 0.16, 0.05)
        tie.rotation_euler = (0, 0, math.atan(-4.4 * u / 5.0))
    # mine cart full of gold on the rails
    cu = 0.3
    cx, cy = rail_xy(cu)
    ang = math.atan(-4.4 * cu / 5.0)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, 0.55))
    cart = obj_from('cart', iron); cart.scale = (0.95, 1.25, 0.62); cart.rotation_euler = (0, 0, ang)
    bv = cart.modifiers.new('bev', 'BEVEL'); bv.width = 0.07; bv.segments = 3
    for i in range(26):
        s = rnd.uniform(0.12, 0.2)
        ox, oy = rnd.uniform(-0.38, 0.38), rnd.uniform(-0.5, 0.5)
        instance('cartgold', shared_mesh('nugget', rnd.randrange(4), rnd),
                 (cx + ox * math.cos(ang) - oy * math.sin(ang), cy + ox * math.sin(ang) + oy * math.cos(ang), 0.88 + rnd.uniform(0, 0.22)),
                 (s, s, s * 0.8), (rnd.random(), rnd.random(), rnd.random()), gold_material())
    # head-frame tower with its wheel (right)
    hx, hy = 3.1, y0 + 1.2
    top = 3.1
    for sx in (-1, 1):
        beam('leg', (hx + sx * 0.95, hy - 0.5, 0), (hx + sx * 0.35, hy - 0.5, top), 0.14, wood)
        beam('leg', (hx + sx * 0.95, hy + 0.5, 0), (hx + sx * 0.35, hy + 0.5, top), 0.14, wood)
    for z in (0.9, 1.9, 2.8):
        wdt = 0.95 - (0.6 * z / top)
        beam('brace', (hx - wdt - 0.1, hy - 0.52, z), (hx + wdt + 0.1, hy - 0.52, z), 0.1, wood)
    beam('x', (hx - 0.9, hy - 0.55, 0.2), (hx + 0.55, hy - 0.55, 1.8), 0.08, wood_dark)
    beam('x', (hx + 0.9, hy - 0.55, 0.2), (hx - 0.55, hy - 0.55, 1.8), 0.08, wood_dark)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.62, minor_radius=0.06, location=(hx, hy - 0.6, top + 0.35), rotation=(math.radians(90), 0, 0))
    obj_from('bigwheel', iron)
    for k in range(4):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(hx, hy - 0.6, top + 0.35))
        spk = obj_from('spoke', iron); spk.scale = (1.24, 0.04, 0.04); spk.rotation_euler = (0, math.pi * k / 4, 0)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.12, location=(hx, hy - 0.75, top - 0.1))
    obj_from('towerlamp', lamp)
    # lantern posts at the far edge of the yard, a string of bulbs between them
    posts = [(-0.6, YARD_END + 0.1), (1.5, YARD_END - 0.2), (-4.4, YARD_END - 0.6), (4.6, YARD_END - 0.8)]
    for lx, ly in posts:
        beam('lpost', (lx, ly, 0), (lx, ly, 1.0), 0.07, wood_dark)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.1, location=(lx, ly - 0.05, 1.08))
        obj_from('lantern', lamp)
        light(sc, 'POINT', (lx, ly - 0.4, 1.05), None, 70, (1.0, 0.62, 0.28), radius=0.15)
    chain = [posts[2], (ex - 0.98, ey - 0.02), (ex + 0.98, ey - 0.02), posts[0], posts[1], (hx - 0.5, hy - 0.6), posts[3]]
    for (ax, ay), (bx, by) in zip(chain[:-1], chain[1:]):
        if (ax, ay) == (ex - 0.98, ey - 0.02):
            continue
        za = 1.3 if abs(ay - (ey - 0.02)) < 1e-6 else (1.9 if abs(ax - (hx - 0.5)) < 1e-6 else 1.05)
        zb = 1.3 if abs(by - (ey - 0.02)) < 1e-6 else (1.9 if abs(bx - (hx - 0.5)) < 1e-6 else 1.05)
        n = max(4, int(math.hypot(bx - ax, by - ay) / 0.28))
        for i in range(1, n):
            u = i / n
            x, y = ax + (bx - ax) * u, ay + (by - ay) * u
            z = za + (zb - za) * u - 0.25 * math.sin(math.pi * u)
            instance('bulb', shared_mesh('pebble', 0, rnd), (x, y, z), (0.04, 0.04, 0.04), (0, 0, 0), lamp)
    # props around the yard: crates, a barrel, a pickaxe
    for (px_, py_, sz, rz) in ((-4.0, YARD_END - 3.2, 0.5, 0.3), (-3.55, YARD_END - 3.3, 0.36, -0.2), (4.3, YARD_END - 5.0, 0.46, 0.5)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(px_, py_, sz / 2))
        c = obj_from('crate', wood); c.scale = (sz, sz, sz); c.rotation_euler = (0, 0, rz)
        bv = c.modifiers.new('bev', 'BEVEL'); bv.width = 0.03; bv.segments = 2
    bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=0.62, location=(3.7, YARD_END - 4.3, 0.31))
    obj_from('barrel', wood)


def foreground(sc, rnd):
    """Dark rocks with glowing gold ore at the bottom corners (in front of the playfield)."""
    ore = mat('ore', (1.0, 0.62, 0.1), 1.0, 0.2, emit=2.5, emit_color=(1.0, 0.55, 0.1))
    rock = mat('fgrock', (0.07, 0.05, 0.08), 0, 0.5, coat=0.3)
    for side, px in ((-1, -60), (1, ART_W + 60)):
        base = ray_to_ground(px, ART_H + 10)
        for k in range(3):
            p = base + Vector((-side * rnd.uniform(0, 0.6), rnd.uniform(-0.1, 0.4), 0))
            s = rnd.uniform(0.28, 0.45)
            instance('fgrock', shared_mesh('stone', rnd.randrange(8), rnd), (p.x, p.y, s * 0.3), (s, s * 0.9, s * 0.8),
                     (rnd.random(), rnd.random(), rnd.random()), rock)
            for j in range(3):
                q = p + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.1), s * 0.6))
                g = rnd.uniform(0.06, 0.13)
                instance('orebit', shared_mesh('nugget', rnd.randrange(4), rnd), q, (g, g, g), (rnd.random(), rnd.random(), rnd.random()), ore)


def ore_clusters(sc, rnd):
    """A few glinting clusters of gold ore on the ground near the bottom corners."""
    ore = mat('ore', (1.0, 0.62, 0.1), 1.0, 0.2, emit=0.5, emit_color=(1.0, 0.55, 0.1))
    for px, py in ((60, 1480), (668, 1500), (40, 1180), (700, 1130)):
        base = ray_to_ground(px, py)
        for j in range(6):
            q = base + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.25, 0.25), 0.05))
            g = rnd.uniform(0.06, 0.12)
            instance('orebit', shared_mesh('nugget', rnd.randrange(4), rnd), q, (g, g, g * 0.8), (rnd.random(), rnd.random(), rnd.random()), ore)


def build(sc, seed=7):
    rnd = random.Random(seed)
    holes_world = {k: ray_to_ground(*v) for k, v in HOLE_ART.items()}
    ground(sc, [(p.x, p.y) for p in holes_world.values()])
    for k, p in holes_world.items():
        hole(k, p.x, p.y, rnd)
    scatter(sc, [(p.x, p.y) for p in holes_world.values()], rnd)
    mine(sc, rnd)
    ore_clusters(sc, rnd)
    # lighting: cool moonlight from the upper left, warm bounce from the front, a violet rim
    w = bpy.data.worlds.new('night'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.12, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
    light(sc, 'AREA', (-16, 6, 24), (0, 24, 0), 9000, (0.66, 0.74, 1.0), 16)       # moonlight
    light(sc, 'AREA', (9, -6, 11), (0, 16, 0), 7500, (1.0, 0.74, 0.46), 10)        # warm key (the lanterns' glow)
    light(sc, 'AREA', (-3, -9, 7), (0, 18, 1), 2600, (1.0, 0.9, 0.8), 8)           # soft front fill (faces)
    light(sc, 'AREA', (0, 70, 10), (0, 20, 0), 9000, (0.60, 0.42, 1.0), 26)         # violet rim from the sky
    return holes_world


# the reference moment: 5 gold miners (targets), the two look-alike decoys, one empty hole
CAST = {'H1': 'gold', 'H2': 'yellow', 'H3': 'brown', 'H4': 'gold', 'H5': 'gold', 'H6': None, 'H7': 'gold', 'H8': 'gold'}
CHAR_SCALE, CHAR_SINK, CHAR_TILT = 0.82, -0.5, -12.0


def characters(sc, holes_world, cast=CAST):
    roots = {}
    for k, variant in cast.items():
        if not variant:
            continue
        p = holes_world[k]
        r = miner.build(variant, (p.x, p.y, CHAR_SINK), CHAR_SCALE, tag='_' + k)
        # face the camera: turned towards it and leaning back a little
        cam = sc.camera.location
        yaw = math.atan2(cam.x - p.x, -(cam.y - p.y))
        r.rotation_euler = (math.radians(CHAR_TILT), 0, yaw)
        roots[k] = r
    return roots


if __name__ == '__main__':
    argv = [a for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if not a.startswith('--')]
    samples = int(argv[0]) if argv else 16
    scale = float(argv[1]) if len(argv) > 1 else 0.5
    out = argv[2] if len(argv) > 2 else '/tmp/claude-0/-home-user-colorpop/b506899a-d85d-5b15-9527-e91d05eeee0f/scratchpad/l8new/render/layout.png'
    sc = reset(scale, samples)
    hw = build(sc)
    if '--chars' in sys.argv:
        characters(sc, hw)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
