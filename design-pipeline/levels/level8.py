"""Level 8 art: "HIT THE GOLD ONES!" (mining town at night, "SPEED INCREASED!").

Reference: reference/screens/level8.png (724 x 1570 art px). Output: app-assets/level8/ + level.json.
Same method as level6.py (see screen_art.py). The gold miners glow: each is a sprite (clipped at the
front rim) plus an additive light layer (halo, rays, the inside of its hole it lights up) that moves
with it. The yellow and the brown-hat miners are look-alike decoys. The blurred blue miner at the
bottom left is out of focus in front of the scene (no hole): it stays in the background. The
"SPEED INCREASED!" banner is a sprite, shown when the level speeds up.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from screen_art import *
from paths import ROOT, work

NAME = 'level8'
OUT = os.path.join(ROOT, 'app-assets', NAME)
I = load_ref(NAME)
H, W = I.shape[:2]
Y, X = grid(I.shape)
HSV = hsv(I)
h_, s_, v_ = HSV[..., 0], HSV[..., 1], HSV[..., 2]

# ---------------------------------------------------------------- geometry (measured)
HOLES = {
    'H1': {'outer': (160, 665, 125, 38), 'inner': (160, 661, 94, 25)},
    'H2': {'outer': (385, 648, 83, 24), 'inner': (385, 645, 62, 16)},
    'H3': {'outer': (525, 740, 115, 40), 'inner': (527, 731, 90, 26)},
    'H4': {'outer': (40, 775, 130, 45), 'inner': (40, 770, 97, 30)},       # at the left edge
    'H5': {'outer': (330, 810, 130, 40), 'inner': (330, 805, 97, 26)},
    'H6': {'outer': (130, 905, 160, 92), 'inner': (125, 893, 130, 52)},    # big, out of focus, left edge
    'H7': {'outer': (595, 880, 125, 65), 'inner': (605, 865, 92, 42)},     # empty
    'H8': {'outer': (437, 1130, 232, 100), 'inner': (440, 1105, 170, 60)},
}
# characters: GrabCut box, a sure-foreground ellipse, hole, role, glow (px of halo kept with it)
CHARS = {
    'gold_a': {'box': (75, 490, 290, 705), 'fg': (165, 605, 62, 60), 'hole': 'H1', 'role': 'target', 'halo': 34,
               'poly': [(165, 519), (200, 526), (221, 551), (231, 583), (237, 606), (233, 622), (248, 635), (262, 648),
                        (262, 668), (250, 690), (80, 690), (80, 650), (88, 630), (92, 618), (88, 604), (98, 572), (111, 547),
                        (130, 529)]},
    'gold_b': {'box': (325, 548, 450, 670), 'fg': (385, 610, 36, 32), 'hole': 'H2', 'role': 'target', 'halo': 16,
               'poly': [(383, 553), (398, 563), (416, 579), (426, 600), (429, 620), (428, 648), (426, 664), (341, 664),
                        (341, 645), (341, 620), (344, 600), (355, 579), (371, 563)]},
    'gold_c': {'box': (450, 598, 590, 770), 'fg': (515, 690, 38, 45), 'hole': 'H3', 'role': 'target', 'halo': 18,
               'poly': [(531, 609), (542, 625), (550, 642), (560, 665), (567, 686), (571, 707), (568, 745), (560, 760),
                        (470, 760), (465, 735), (465, 705), (468, 686), (478, 668), (492, 652), (512, 630)]},
    'gold_d': {'box': (230, 650, 445, 860), 'fg': (330, 755, 65, 60), 'hole': 'H5', 'role': 'target', 'halo': 34,
               'poly': [(330, 673), (366, 676), (388, 699), (401, 725), (408, 760), (430, 772), (436, 800), (425, 835),
                        (240, 835), (232, 800), (236, 772), (255, 760), (267, 722), (280, 697), (303, 678)]},
    'gold_e': {'box': (315, 830, 620, 1180), 'fg': (455, 1010, 95, 110), 'hole': 'H8', 'role': 'target', 'halo': 40,
               'poly': [(467, 848), (500, 851), (514, 865), (547, 905), (564, 955), (575, 990), (560, 1022), (562, 1096),
                        (566, 1140), (566, 1175), (330, 1175), (331, 1113), (338, 1063), (348, 1017), (340, 990), (338, 960),
                        (373, 909), (400, 872), (430, 855)]},
    'yellow': {'box': (0, 680, 180, 812), 'fg': (65, 745, 55, 38), 'hole': 'H4', 'role': 'distractor',
               'poly': [(0, 719), (20, 703), (45, 694), (68, 692), (90, 698), (104, 707), (118, 722), (130, 733),
                        (122, 748), (118, 770), (116, 795), (110, 814), (0, 814)]},
    'brown':  {'box': (0, 805, 270, 955), 'fg': (120, 895, 80, 35), 'hole': 'H6', 'role': 'distractor'},
}
# long rays / flares that belong to a gold miner's light
RAYS = {
    'gold_e': [[(180, 860), (330, 850), (362, 962), (300, 1012), (196, 992)],
               [(560, 1000), (706, 1008), (706, 1072), (600, 1072)],
               [(252, 1162), (302, 1162), (308, 1218), (258, 1218)],
               [(562, 1168), (618, 1168), (624, 1244), (572, 1244)],
               [(205, 1040), (275, 1030), (285, 1150), (215, 1160)],          # its light on the rim
               [(590, 1040), (672, 1060), (668, 1150), (600, 1160)]],
    'gold_d': [[(333, 838), (377, 838), (372, 906), (333, 906)]],
}
BANNER = {'box': (100, 1317, 615, 1442), 'r': 62}       # "SPEED INCREASED!" pill


def front_arc(hole, x):
    cx, cy, a, b = HOLES[hole]['inner']
    return cy + b * np.sqrt(np.clip(1 - ((x - cx) / a) ** 2, 0, 1))


def hull_of(m):
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = np.zeros(I.shape[:2], np.uint8)
    cv2.drawContours(out, [cv2.convexHull(max(cnts, key=len))], -1, 1, -1)
    return out.astype(bool)


def segment_char(k):
    c = CHARS[k]
    fa = front_arc(c['hole'], X)
    if 'poly' in c:       # glowing: outline traced on the reference, refined by GrabCut
        pm = poly_mask(I.shape, c['poly'])
        return grabcut(I, c['box'], fg=erode(pm, 7) & (Y < fa - 3), pr_fg=dilate(pm, 3), bg=(Y > fa + 8) | ~dilate(pm, 8))
    fg = ellipse_mask(I.shape, c['fg']) & (Y < fa - 3)
    box = rect_mask(I.shape, c['box'])
    return grabcut(I, c['box'], fg=fg, pr_fg=dilate(fg, 20) & box & (Y < fa + 6), bg=(Y > fa + 8) | ~box)


OPEN, EDGE = {}, {}       # fitted openings / front edges (build)


def visible(hk, pad=0.0):
    """Where a character standing in hole hk can be seen (the app's clip), edge lowered by pad."""
    e = dict(EDGE[hk]); e['y'] = [v + pad for v in e['y']]
    return ~hides_mask(I.shape, OPEN[hk], e)


def interior(hk):
    """The hole's opening above its front rim (dark inside, or whatever stands in it)."""
    if hk in OPEN:
        return ellipse_mask(I.shape, OPEN[hk]) & visible(hk, 1)
    cx, cy, a, b = HOLES[hk]['inner']
    return ellipse_mask(I.shape, (cx, cy, a, b)) & (Y < front_arc(hk, X) + 1)


def light_region(k, m):
    """A gold miner's light: halo around it, rays, and the inside of its hole it lights up."""
    fx = dilate(m, CHARS[k]['halo'])
    for p in RAYS.get(k, []):
        fx |= poly_mask(I.shape, p)
    return fx | interior(CHARS[k]['hole'])


def char_region(k, m):
    return dilate(hull_of(m), 6) & visible(CHARS[k]['hole'], 2)


def connected(mask):
    n, lab = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    return [lab == i for i in range(1, n)]


def banner_mask(grow=0):
    x0, y0, x1, y1 = BANNER['box']
    r = BANNER['r']
    m = np.zeros((H, W), np.uint8)
    cv2.rectangle(m, (x0 + r - grow, y0 - grow), (x1 - r + grow, y1 + grow), 1, -1)
    cv2.circle(m, (x0 + r, (y0 + y1) // 2), r + grow, 1, -1)
    cv2.circle(m, (x1 - r, (y0 + y1) // 2), r + grow, 1, -1)
    return m.astype(bool)


# ---------------------------------------------------------------- frame + live HUD parts
STATUS = [(40, 26, 130, 74), (530, 28, 700, 72)]
HOME_BAR = (240, 1538, 495, 1562)
CORNER_R = 44
PAUSE = {'cx': 77, 'cy': 137, 'r': 43}
DIGITS = {
    'timer':  {'box': (564, 120, 658, 152), 'align': 'left', 'text': '00:20'},
    'target': {'box': (562, 250, 630, 311), 'align': 'center', 'text': '15'},
    'score':  {'box': (375, 382, 483, 418), 'align': 'left', 'text': '2,480'},
}


def build():
    masks, edges, openings = {}, {}, {}
    for k, c in CHARS.items():
        masks[k] = segment_char(k) & (Y < front_arc(c['hole'], X) + 8)
        openings[c['hole']], edges[c['hole']] = fit_front(HOLES[c['hole']]['inner'], masks[k])
    for hk, hd in HOLES.items():
        if hk not in openings:
            openings[hk] = tuple(round(v, 1) for v in hd['inner'])
            edges[hk] = edge_columns(openings[hk], {}, 0)
    OPEN.update(openings); EDGE.update(edges)
    for k, c in CHARS.items():
        masks[k] &= visible(c['hole'], 1.5)

    frame = rounded_outside(I.shape, CORNER_R) | rect_mask(I.shape, HOME_BAR)
    for r in STATUS:
        frame |= rect_mask(I.shape, r)
    fx = {k: light_region(k, masks[k]) for k, c in CHARS.items() if 'halo' in c}
    digits = np.zeros((H, W), bool)
    for d in DIGITS.values():
        x0, y0, x1, y1 = d['box']
        digits |= rect_mask(I.shape, (x0 - 5, y0 - 5, x1 + 5, y1 + 8))
    pause = ellipse_mask(I.shape, (PAUSE['cx'], PAUSE['cy'], PAUSE['r'] + 3, PAUSE['r'] + 3))
    chars = np.zeros((H, W), bool)
    for k in CHARS:
        chars |= char_region(k, masks[k])
    for k in fx:
        chars |= fx[k]
    banner = banner_mask(14)
    dyn = chars | digits | pause | banner
    return dict(masks=masks, edges=edges, openings=openings, frame=frame, dyn=dyn, fx=fx, banner=banner,
                pause=pause, digits=digits)


def rebuild(P):
    frame, dyn = P['frame'], P['dyn']
    flat = P['digits'] | P['pause']
    B = I.copy()
    B = cv2.inpaint(np.clip(B, 0, 255).astype(np.uint8), frame.astype(np.uint8) * 255, 6, cv2.INPAINT_TELEA).astype(np.float64)
    for comp in connected(flat):
        B = merge_region(B, np.zeros_like(B), comp)
    dyn = dyn & ~flat
    bad = dyn | frame
    # hidden parts of the holes from clean donors at the same ring coordinates; the empty hole on
    # the right (H7) is the main donor: its right half, mirrored for the left
    order = ['H7', 'H6', 'H2', 'H3', 'H1', 'H5', 'H4', 'H8']
    guide = B.copy(); covered = np.zeros((H, W), bool)
    for hk in order:
        hd = {'inner': HOLES[hk]['inner'], 'outer': HOLES[hk]['outer']}
        donors = [dict(inner=HOLES['H7']['inner'], outer=HOLES['H7']['outer'], fold=True)]
        donors += [dict(inner=HOLES[d]['inner'], outer=HOLES[d]['outer'], mirror=mi) for d, mi in
                   ((hk, True), ('H7', False), ('H6', False), ('H6', True), ('H3', False), ('H5', False), ('H1', False), ('H8', False))
                   if not (d == hk and not mi)]
        g, cov = hole_guidance(B, hd, donors, bad & ~covered, bad | (X > W - 14))   # not the bezel
        guide[cov] = g[cov]; covered |= cov
    done = np.zeros((H, W), bool)
    for hk in HOLES:
        ins = interior(hk)
        r = bad & covered & ins
        if r.any():
            B = poisson_free(B, guide, r, ins & ~bad)
            done |= r
    rings = np.zeros((H, W), bool)
    for hk, hd in HOLES.items():
        rings |= ellipse_mask(I.shape, hd['outer'], 6)
    rest = bad & ~covered & ~frame
    near = np.zeros((H, W), bool)
    for k in P['fx']:
        near |= dilate(P['masks'][k], 50)
    sparks = dilate((v_ > 215) & (h_ >= 15) & (h_ <= 40) & (s_ < 215), 4) | dilate((s_ < 70) & (v_ > 190), 4)
    # thin light streaks and specks (they would repeat): brighter than their surroundings
    lum = I.mean(-1).astype(np.float32)
    tophat = lum - cv2.morphologyEx(lum, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    sparks |= dilate(tophat > 22, 4)
    sparks |= (X < 6) | (X > W - 14)          # the reference phone's bezel
    far = rest & (Y < 600)
    front = rest & (Y > 1250) & ~P['banner']
    ground = rest & ~far & ~front & ~P['banner']
    # behind the banner: the out-of-focus grass below it mirrored upwards, the dirt above it
    # mirrored downwards at its top edge
    bn = rest & P['banner']
    if bn.any():
        ys, xs = np.where(bn)
        top, bot = ys.min(), ys.max() + 1
        wgt = np.clip((ys - (top + 26)) / 40.0, 0, 1)[:, None]          # dirt fades into grass
        sb = 2 * bot - ys
        sb = np.where(sb > H - 34, 2 * (H - 34) - sb, sb)            # reflected again above the bottom bezel
        below = B[np.clip(sb, 0, H - 1), xs]
        above = B[np.clip(2 * top - ys, 0, H - 1), xs]
        g = below * wgt + above * (1 - wgt)
        guide[ys, xs] = g
    src_ground = ~bad & ~rings & ~near & ~sparks & (Y > 600) & (Y < 1260)
    src_far = ~bad & ~sparks & (Y > 440) & (Y < 640)
    src_front = ~bad & ~sparks & (Y > 1200) & (Y < H - 30) & ~banner_mask(12)
    for part, sr, blur in ((ground, src_ground, 1.1), (far, src_far, 2.6), (front, src_front, 2.2)):
        if part.any():
            filled = exemplar_fill(guide, part, sr, ps=13)
            soft = cv2.GaussianBlur(filled.astype(np.float32), (0, 0), blur).astype(np.float64)
            guide[part] = soft[part]
    guide[done] = B[done]
    B = merge_region(B, guide, ((bad & ~frame) | (covered & ~frame)) & ~done)
    # glow that leaked into the rebuilt parts: keep its fine texture only
    hb = hsv(B)
    leak = (bad & ~frame) & (hb[..., 2] > 235) & (hb[..., 1] < 150) & (Y > 470)
    leak = dilate(leak, 3) & (bad & ~frame) & ~done
    for comp in connected(leak):
        y0, y1, x0, x1 = bbox(comp, 3, I.shape)
        reg = B[y0:y1, x0:x1]
        hp = reg - cv2.GaussianBlur(reg.astype(np.float32), (0, 0), 2.0).astype(np.float64)
        B[y0:y1, x0:x1] = poisson_merge(reg, hp, comp[y0:y1, x0:x1])
    return B


# Level 8: significantly harder. 40 s, 28 gold miners, gold vs yellow / brown-hat look-alikes, eight
# holes, some quick pop-ups; at 00:20 "SPEED INCREASED!" (the reference moment): faster, shorter,
# one more up at a time.
RULES = {'duration': 40, 'goal': 28, 'target': 'gold', 'combo': False, 'points': 60,
         'mix': {'target': 0.5, 'distractor': 0.5}, 'hold': [0.9, 1.2], 'gap': [0.38, 0.62], 'up_max': [2, 3],
         'quick': 0.25,
         'speedup': {'at': 20.0, 'hold': 0.8, 'gap': 0.78, 'up': 1},
         'reference_state': {'elapsed': 20.0, 'targets_left': 15, 'score': 2480, 'combo': 0}}


def export(P, B):
    from levels.export import sprite_entry, calibrate_digits, write_level, clean_frame, sharp_sprite, sharp_entry
    import sr
    HIRES = sr.hires_canvas(NAME)[0]
    masks, edges, openings = P['masks'], P['edges'], P['openings']
    rel = NAME
    level = {'id': 8, 'art': {'w': W, 'h': H}, 'content': {'top': 92, 'bottom': 1450}}
    B = clean_frame(B, right=10)
    PAD = 24
    full = cv2.copyMakeBorder(B.astype(np.float32), 0, 0, PAD, PAD, cv2.BORDER_REFLECT_101)
    soft = cv2.GaussianBlur(full, (0, 0), 6)
    ramp = np.clip((np.abs(np.arange(W + 2 * PAD) - (W + 2 * PAD - 1) / 2) - (W / 2 - 1)) / PAD, 0, 1)[None, :, None]
    save_png(os.path.join(OUT, 'bg.png'), full * (1 - ramp) + soft * ramp)
    level['bg'] = {'file': rel + '/bg.png', 'pad_side': PAD, 'pad_top': 0, 'pad_bottom': 0}
    level['holes'] = {hk: {'opening': list(openings[hk]), 'edge': edges[hk]} for hk in sorted(HOLES)}
    level['chars'] = {}
    layers = []
    for k, c in CHARS.items():
        hk = c['hole']
        rgba2, xy, rgba = sharp_sprite(NAME, I, B, char_region(k, masks[k]), masks[k], edges[hk], ext=30, hires=HIRES)
        if xy[0] == 0 and masks[k][:, 0].any():
            # cut by the screen edge in the reference: a soft edge instead of a straight cut, for
            # when it pops up in a hole away from the edge
            rgba[:, :10, 3] *= np.linspace(0.15, 1, 10)[None, :]
            rgba2[:, :20, 3] *= np.linspace(0.15, 1, 20)[None, :]
        e = sharp_entry(OUT, 'char_' + k, rgba2, xy, rel)
        e.update({'hole': hk, 'color': k.split('_')[0], 'role': c['role']})
        level['chars'][k] = e
        vis = ~hides_mask(I.shape, openings[hk], edges[hk])
        layers.append((rgba, xy[0], xy[1], vis))
    with_chars = composite(B, layers)
    for k in P['fx']:
        g, xy = glow_layer(I, with_chars, P['fx'][k])
        save_png(os.path.join(OUT, 'glow_' + k + '.png'), g)
        level['chars'][k]['glow'] = {'file': f'{rel}/glow_{k}.png', 'x': xy[0], 'y': xy[1], 'w': int(g.shape[1]), 'h': int(g.shape[0])}
        full_g = np.zeros_like(I); full_g[xy[1]:xy[1] + g.shape[0], xy[0]:xy[0] + g.shape[1]] = g
        with_chars = np.minimum(with_chars + full_g, 255)
    rgba, xy = diff_matte(I, with_chars, P['banner'])
    level['banner'] = sprite_entry(OUT, 'banner', rgba, xy, rel)
    layers2 = [(rgba, xy[0], xy[1], None)]
    pm = ellipse_mask(I.shape, (PAUSE['cx'], PAUSE['cy'], PAUSE['r'] + 2, PAUSE['r'] + 2))
    rgba, xy = cut_sprite(I, pm, feather=0.8)
    level['pause'] = sprite_entry(OUT, 'pause', rgba, xy, rel)
    level['pause']['hit'] = dict(PAUSE)
    layers2.append((rgba, xy[0], xy[1], None))
    scene = composite(with_chars, layers2)
    print(' calibrating lettering')
    level['live_text'] = calibrate_digits(I, scene, DIGITS)
    level['rules'] = RULES
    write_level(NAME, level)
    for key, d in DIGITS.items():
        scene = draw_text(scene, d['text'], level['live_text'][key])
    save_png(work('l8_rebuilt_reference.png'), scene)
    d = np.abs(scene - I).mean(-1)
    d = d[92:1450, 4:W - 10]          # inside the reference phone's bezel
    print(' rebuilt reference vs reference: mean diff %.2f/255, %.2f%% px off by >40' % (d.mean(), (d > 40).mean() * 100))


if __name__ == '__main__' and '--preview' not in sys.argv:
    import time
    t0 = time.time()
    P = build()
    print('masks', {k: int(m.sum()) for k, m in P['masks'].items()}, 'dyn px', int(P['dyn'].sum()), '%.1fs' % (time.time() - t0))
    if '--reuse-bg' in sys.argv and os.path.exists(work('l8_bg.npy')):
        B = np.load(work('l8_bg.npy'))
    else:
        B = rebuild(P)
        np.save(work('l8_bg.npy'), B)
        save_png(work('l8_bg.png'), B)
    print('background %.1fs' % (time.time() - t0))
    export(P, B)
    print('done %.1fs' % (time.time() - t0))


if __name__ == '__main__' and '--preview' in sys.argv:
    P = build()
    out = I * 0.55
    out[P['dyn']] = out[P['dyn']] * 0.4 + np.array([255, 0, 255]) * 0.6
    for k, m in P['masks'].items():
        e = m & ~erode(m, 1)
        out[e] = (0, 255, 0)
    for hk, hd in HOLES.items():
        for e, c in ((P['openings'][hk], (0, 255, 255)), (hd['outer'], (255, 255, 0))):
            ring = ellipse_mask(I.shape, e) & ~ellipse_mask(I.shape, e, -1.2)
            out[ring] = c
        f = edge_fn(P['edges'][hk])
        for x in range(W):
            y = f(x)
            if y is not None and 0 <= int(y) < H:
                out[int(y), x] = (255, 80, 0)
    save_png(work('l8_preview.png'), out)
    print('preview written', {k: int(m.sum()) for k, m in P['masks'].items()})
