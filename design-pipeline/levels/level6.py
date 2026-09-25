"""Level 6 art: "HIT THE STARS!" (farm at dusk, "AVOID THE BOMBS!").

Reference: reference/screens/level6.png (712 x 1486 art px). Output: app-assets/level6/ + level.json.
Same method as level3.py (see screen_art.py). Stars rise out of the holes like the characters: each
is a sprite (star + the creature holding it, clipped at the front rim) plus an additive light layer
(halo, rays, beam) that moves with it. The "AVOID THE BOMBS!" bar is a permanent reminder: it stays
in the background.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from screen_art import *
from paths import ROOT, work

NAME = 'level6'
OUT = os.path.join(ROOT, 'app-assets', NAME)
I = load_ref(NAME)
H, W = I.shape[:2]
Y, X = grid(I.shape)
HSV = hsv(I)
h_, s_, v_ = HSV[..., 0], HSV[..., 1], HSV[..., 2]

# ---------------------------------------------------------------- geometry (measured)
def inner_from_outer(o):
    cx, cy, a, b = o
    return (cx, cy - 0.11 * b, 0.75 * a, 0.66 * b)


HOLES = {
    'hA': {'outer': (143, 625, 103, 35), 'inner': (146, 615, 80, 21)},
    'hB': {'outer': (374, 663, 114, 41)},
    'hC': {'outer': (50, 740, 85, 55), 'inner': (45, 726, 56, 31)},      # empty, cut by the left edge
    'hD': {'outer': (546, 845, 154, 65), 'inner': (552, 830, 120, 38)},
    'hE': {'outer': (208, 965, 192, 85), 'inner': (212, 947, 150, 54)},
    'hF': {'outer': (515, 1195, 193, 100), 'inner': (522, 1175, 148, 66)},
}
for k, hd in HOLES.items():
    hd.setdefault('inner', inner_from_outer(hd['outer']))

# stars: outline polygon (tips and valleys of the white rim), the hole they rise from
STARS = {
    'star_purple': {'hole': 'hA', 'poly': [(143, 489), (124, 525), (77, 537), (107.5, 575), (101, 613), (142.5, 600),
                                           (184, 615), (179, 574), (211, 538), (167, 527.5)]},
    'star_orange': {'hole': 'hD', 'poly': [(560, 644), (530, 696), (456, 710), (500, 768), (496, 832), (558, 802),
                                           (622, 834), (620, 768), (668, 712), (600, 700)]},
    'star_gold':   {'hole': 'hE', 'poly': [(207.5, 741), (172.5, 802.5), (95, 820), (142.5, 880), (143, 958), (206, 930),
                                           (281, 958), (270, 880), (321, 822.5), (247.5, 803.75)]},
}
HALO = {'star_purple': 30, 'star_orange': 36, 'star_gold': 30}     # px of glow kept with a star beyond its rim
# light beams / long rays belonging to a star (drawn with it)
BEAMS = {
    'star_orange': [[(552, 518), (590, 518), (592, 660), (548, 660)],
                    [(495, 598), (515, 592), (545, 665), (522, 672)],
                    [(598, 605), (618, 605), (600, 668), (580, 662)]],
    'star_gold':   [[(226, 628), (256, 628), (236, 752), (200, 752)],
                    [(198, 610), (218, 610), (218, 745), (198, 745)]],
    'star_purple': [[(132, 452), (156, 452), (156, 492), (132, 492)]],
}
# characters: box, hole, role
CHARS = {
    'red':    {'box': (300, 530, 460, 690), 'hole': 'hB', 'role': 'distractor',
               # outline traced on the reference (its colour mask's hull took in the ground beside it)
               'poly': [(352, 561), (362, 550), (371, 543), (382, 545), (388, 557), (396, 560), (412, 568), (425, 580),
                        (433, 595), (437, 610), (437, 628), (440, 645), (440, 662), (430, 672), (410, 677), (380, 680),
                        (345, 678), (325, 672), (316, 660), (316, 640), (322, 625), (326, 605), (330, 585), (340, 570)]},
    'masked': {'box': (400, 1000, 660, 1250), 'hole': 'hF', 'role': 'bomb',
               # its face/cheeks are orange-red like the rim: outline measured, refined by GrabCut
               'poly': [(515, 1012), (535, 1022), (575, 1035), (605, 1060), (622, 1095), (632, 1110), (640, 1150),
                        (650, 1180), (652, 1225), (645, 1250), (410, 1250), (408, 1200), (415, 1160), (428, 1120),
                        (432, 1098), (450, 1070), (475, 1040), (500, 1025)]},
}


def red_mask():
    return ((h_ <= 7) | (h_ >= 170)) & (s_ > 110) & (v_ > 90)


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
    box = c['box']
    fa = front_arc(c['hole'], X)
    if 'poly' in c:
        pm = poly_mask(I.shape, c['poly'])
        bgs = (Y > fa + 8) | ~dilate(pm, 10)
        return grabcut(I, box, fg=erode(pm, 8) & (Y < fa - 4), pr_fg=dilate(pm, 3), bg=bgs)
    cm = red_mask() & rect_mask(I.shape, box)
    cm = cv2.morphologyEx(cm.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cm.astype(np.uint8), 8)
    cm = lab == (1 + np.argmax(st[1:, 4]))
    hull = hull_of(cm)
    ys, xs = np.where(hull)
    fa = front_arc(c['hole'], X)
    inner = HOLES[c['hole']]['inner']
    below = (X >= xs.min()) & (X <= xs.max()) & (Y >= ys.min()) & (Y < fa - 1) & (np.abs(X - inner[0]) < inner[2])
    pr = dilate(hull, 3) | (below & dilate(hull, 25))
    bgs = (Y > fa + 8) | ~dilate(pr, 6)
    return grabcut(I, box, fg=erode(cm, 3), pr_fg=pr, bg=bgs & ~erode(cm, 3))


def segment_star(k):
    """The star (inside its rim polygon, a little grown) and the creature under it in the opening:
    everything in the opening that is not the dark interior, below the star, above the front rim."""
    st = STARS[k]
    poly = dilate(poly_mask(I.shape, st['poly']), 3)
    cx, cy, a, b = HOLES[st['hole']]['inner']
    ys, xs = np.where(poly)
    opening = ellipse_mask(I.shape, (cx, cy, a, b)) & (Y < front_arc(st['hole'], X) + 1)
    tips = [p[0] for p in st['poly'][4:7:2]]           # the two lower tips
    rim = (h_ >= 5) & (h_ <= 22) & (s_ > 90) & (v_ < 215)     # the hole's brown back rim
    mg = 10 if k == 'star_purple' else 25              # the purple star's creature is hidden behind it
    blob = opening & (v_ > 70) & ~rim & (X > min(tips) - mg) & (X < max(tips) + mg) & (Y > cy - b)
    blob = cv2.morphologyEx(blob.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    m = poly | blob
    n, lab, stt, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    m = lab == (1 + np.argmax(stt[1:, 4]))
    return m & (Y < front_arc(st['hole'], X) + 1.5)


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


def star_effects(k):
    """A star's light: halo, beams / rays, and the inside of its hole it lights up."""
    fx = dilate(poly_mask(I.shape, STARS[k]['poly']), HALO[k])
    for p in BEAMS.get(k, []):
        fx |= poly_mask(I.shape, p)
    return fx | interior(STARS[k]['hole'])


def char_region(k, m):
    hull = hull_of(m)
    ys, xs = np.where(m)
    knob = rect_mask(I.shape, (xs.min() + 0.3 * (xs.max() - xs.min()), ys.min() - 16, xs.max() - 0.3 * (xs.max() - xs.min()), ys.min() + 4))
    r = dilate(hull | knob, 6)
    r |= dilate(r, 10) & red_mask()          # red edge pixels just outside (they are rim once it is empty)
    return r & visible(CHARS[k]['hole'], 2)


def connected(mask):
    n, lab = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    return [lab == i for i in range(1, n)]


# ---------------------------------------------------------------- frame + live HUD parts
STATUS = [(45, 28, 130, 72), (520, 30, 690, 70)]
HOME_BAR = (240, 1462, 480, 1484)
CORNER_R = 44
PAUSE = {'cx': 77, 'cy': 137, 'r': 43}
DIGITS = {
    'timer':  {'box': (563, 120, 651, 151), 'align': 'left', 'text': '00:15'},
    'target': {'box': (563, 255, 637, 320), 'align': 'center', 'text': '10'},
    'score':  {'box': (318, 396, 422, 433), 'align': 'left', 'text': '1,250'},
}
COMBO_BOX = (445, 385, 690, 532)
COMBO_NUMBER = {'box': (517, 395, 601, 457), 'align': 'center', 'text': '5x'}   # ink of the live number


def combo_number_region(combo):
    """The live number's part of the badge: its yellow fill grown by its outline (where its outline
    runs into the word's, the word keeps it)."""
    x0, y0, x1, y1 = COMBO_NUMBER['box']
    fill = rect_mask(I.shape, (x0 - 8, y0 - 8, x1 + 8, y1 + 2)) & (h_ >= 12) & (h_ <= 38) & (s_ > 90) & (v_ > 150)
    return dilate(fill, 9) & combo & (Y < y1 + 3)


def build():
    masks, edges, openings = {}, {}, {}
    for k in CHARS:
        masks[k] = segment_char(k)
    for k in STARS:
        masks[k] = segment_star(k)
    hole_of = {k: CHARS[k]['hole'] for k in CHARS}
    hole_of.update({k: STARS[k]['hole'] for k in STARS})
    for k, hk in hole_of.items():
        masks[k] &= Y < front_arc(hk, X) + (8 if k in CHARS else 1.5)
        openings[hk], edges[hk] = fit_front(HOLES[hk]['inner'], masks[k])
    for hk, hd in HOLES.items():
        if hk not in openings:
            openings[hk] = tuple(round(v, 1) for v in hd['inner'])
            edges[hk] = edge_columns(openings[hk], {}, 0)
    OPEN.update(openings); EDGE.update(edges)
    for k, hk in hole_of.items():
        masks[k] &= visible(hk, 1.5)

    frame = rounded_outside(I.shape, CORNER_R) | rect_mask(I.shape, HOME_BAR)
    for r in STATUS:
        frame |= rect_mask(I.shape, r)
    fx = {k: star_effects(k) for k in STARS}
    combo = rect_mask(I.shape, COMBO_BOX) & ((HSV[..., 1] > 120) & (HSV[..., 0] >= 12) & (HSV[..., 0] <= 35) | (HSV[..., 2] < 90))
    combo = dilate(cv2.morphologyEx(combo.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)).astype(bool), 3) & rect_mask(I.shape, COMBO_BOX)
    digits = np.zeros((H, W), bool)
    for d in DIGITS.values():
        x0, y0, x1, y1 = d['box']
        digits |= rect_mask(I.shape, (x0 - 5, y0 - 5, x1 + 5, y1 + 8))
    pause = ellipse_mask(I.shape, (PAUSE['cx'], PAUSE['cy'], PAUSE['r'] + 3, PAUSE['r'] + 3))
    chars = np.zeros((H, W), bool)
    for k in CHARS:
        chars |= char_region(k, masks[k])
    for k in STARS:
        chars |= dilate(masks[k], 4) | fx[k]
    dyn = chars | combo | digits | pause
    return dict(masks=masks, edges=edges, openings=openings, frame=frame, dyn=dyn, fx=fx, combo=combo,
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
    # hidden parts of the holes from clean donors at the same ring coordinates; the empty hole at
    # the left (hC) is the main donor (its back rim and dark inside are clean)
    order = ['hC', 'hB', 'hA', 'hF', 'hD', 'hE']
    guide = B.copy(); covered = np.zeros((H, W), bool)
    for hk in order:
        hd = {'inner': HOLES[hk]['inner'], 'outer': HOLES[hk]['outer']}
        donors = [dict(inner=HOLES[d]['inner'], outer=HOLES[d]['outer'], mirror=mi) for d, mi in
                  ((hk, True), ('hC', False), ('hC', True), ('hB', False), ('hF', False), ('hA', False), ('hD', False), ('hE', False))
                  if not (d == hk and not mi)]
        # the empty hole's right half, mirrored for the left, is the one clean full hole
        donors.insert(0 if hk != 'hC' else 1, dict(inner=HOLES['hC']['inner'], outer=HOLES['hC']['outer'], fold=True))
        g, cov = hole_guidance(B, hd, donors, bad & ~covered, bad)
        guide[cov] = g[cov]; covered |= cov
    # hole insides: the donor's dark inside, matched only to the clean inside around it (the bright
    # front rim must not brighten it)
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
    near_stars = np.zeros((H, W), bool)
    for k in STARS:
        near_stars |= dilate(poly_mask(I.shape, STARS[k]['poly']), 50)
    # no sparks, pink/purple streaks or red shards as sources (they would repeat)
    sparks = dilate((v_ > 215) & (h_ >= 15) & (h_ <= 40) & (s_ < 215), 4) | dilate((h_ >= 125) & (h_ <= 178) & (s_ > 60), 4) \
        | dilate(((h_ <= 7) | (h_ >= 170)) & (s_ > 110) & (v_ > 90), 5) | dilate((s_ < 70) & (v_ > 190), 4)
    src = ~bad & ~rings & ~near_stars & ~sparks & (Y > 440) & (Y < 1290)
    cb = rect_mask(I.shape, COMBO_BOX)
    src_sky = ~bad & ~sparks & (Y > 330) & (Y < 560) & ~rect_mask(I.shape, (140, 380, 440, 452))
    for part, sr, blur in ((rest & ~cb, src, 1.1), (rest & cb, src_sky, 2.6)):    # the far town is out of focus
        if part.any():
            filled = exemplar_fill(guide, part, sr, ps=13)
            soft = cv2.GaussianBlur(filled.astype(np.float32), (0, 0), blur).astype(np.float64)
            guide[part] = soft[part]
    guide[done] = B[done]
    B = merge_region(B, guide, ((bad & ~frame) | (covered & ~frame)) & ~done)
    # star colours / glow that leaked into the rebuilt parts: keep their fine texture only
    hb = hsv(B)
    leak = (bad & ~frame) & (((hb[..., 0] >= 125) & (hb[..., 0] <= 178) & (hb[..., 1] > 35)) |
                             ((hb[..., 2] > 235) & (hb[..., 1] < 140))) & (Y > 470)
    leak = dilate(leak, 3) & (bad & ~frame) & ~done
    for comp in connected(leak):
        y0, y1, x0, x1 = bbox(comp, 3, I.shape)
        reg = B[y0:y1, x0:x1]
        hp = reg - cv2.GaussianBlur(reg.astype(np.float32), (0, 0), 2.0).astype(np.float64)
        B[y0:y1, x0:x1] = poisson_merge(reg, hp, comp[y0:y1, x0:x1])
    return B


RULES = {'duration': 30, 'goal': 15, 'target': 'star', 'combo': True, 'points': 50, 'bomb_penalty': 3.0,
         'mix': {'target': 0.5, 'distractor': 0.3, 'bomb': 0.2}, 'hold': [1.0, 1.4], 'gap': [0.4, 0.7], 'up_max': [2, 3],
         'reference_state': {'elapsed': 15.0, 'targets_left': 10, 'score': 1250, 'combo': 5}}


def export(P, B):
    from levels.export import sprite_entry, calibrate_digits, write_level, sharp_sprite, sharp_entry
    import sr
    HIRES = sr.hires_canvas(NAME)[0]
    masks, edges, openings = P['masks'], P['edges'], P['openings']
    rel = NAME
    level = {'id': 6, 'art': {'w': W, 'h': H}, 'content': {'top': 92, 'bottom': 1432}}
    from levels.export import clean_frame
    B = clean_frame(B)
    PAD = 24
    full = cv2.copyMakeBorder(B.astype(np.float32), 0, 0, PAD, PAD, cv2.BORDER_REFLECT_101)
    soft = cv2.GaussianBlur(full, (0, 0), 6)
    ramp = np.clip((np.abs(np.arange(W + 2 * PAD) - (W + 2 * PAD - 1) / 2) - (W / 2 - 1)) / PAD, 0, 1)[None, :, None]
    save_png(os.path.join(OUT, 'bg.png'), full * (1 - ramp) + soft * ramp)
    level['bg'] = {'file': rel + '/bg.png', 'pad_side': PAD, 'pad_top': 0, 'pad_bottom': 0}
    level['holes'] = {hk: {'opening': list(openings[hk]), 'edge': edges[hk]} for hk in sorted(HOLES)}
    level['chars'] = {}
    layers = []
    for k, c in list(CHARS.items()) + list(STARS.items()):
        hk = c['hole']
        if k in STARS:
            region = dilate(masks[k], 6) & visible(hk, 2)
            colour, role = 'star', 'target'
        else:
            region = char_region(k, masks[k])
            colour, role = 'red', c['role']
        rgba2, xy, rgba = sharp_sprite(NAME, I, B, region, masks[k], edges[hk], ext=30, hires=HIRES)
        e = sharp_entry(OUT, 'char_' + k, rgba2, xy, rel)
        e.update({'hole': hk, 'color': colour, 'role': role})
        level['chars'][k] = e
        vis = ~hides_mask(I.shape, openings[hk], edges[hk])
        layers.append((rgba, xy[0], xy[1], vis))
    with_chars = composite(B, layers)
    # each star's light (halo, rays, beam): additive, moves with its star
    for k in STARS:
        region = P['fx'][k]
        g, xy = glow_layer(I, with_chars, region)
        save_png(os.path.join(OUT, 'glow_' + k + '.png'), g)
        level['chars'][k]['glow'] = {'file': f'{rel}/glow_{k}.png', 'x': xy[0], 'y': xy[1], 'w': int(g.shape[1]), 'h': int(g.shape[0])}
        full_g = np.zeros_like(I); full_g[xy[1]:xy[1] + g.shape[0], xy[0]:xy[0] + g.shape[1]] = g
        with_chars = np.minimum(with_chars + full_g, 255)
    word = P['combo'] & ~combo_number_region(P['combo'])
    rgba, xy = diff_matte(I, B, word)
    level['combo'] = {'word': sprite_entry(OUT, 'combo_word', rgba, xy, rel)}
    layers2 = [(rgba, xy[0], xy[1], None)]
    pm = ellipse_mask(I.shape, (PAUSE['cx'], PAUSE['cy'], PAUSE['r'] + 2, PAUSE['r'] + 2))
    rgba, xy = cut_sprite(I, pm, feather=0.8)
    level['pause'] = sprite_entry(OUT, 'pause', rgba, xy, rel)
    level['pause']['hit'] = dict(PAUSE)
    layers2.append((rgba, xy[0], xy[1], None))
    scene = composite(with_chars, layers2)
    print(' calibrating lettering')
    level['live_text'] = calibrate_digits(I, scene, DIGITS)
    from levels.export import calibrate_combo
    e0, e, best = calibrate_combo(I, scene, COMBO_NUMBER)
    print('   combo   %-6s error %.1f -> %.1f  %s' % (COMBO_NUMBER['text'], e0, e, {k: best[k] for k in ('size', 'scale_x', 'outline', 'shadow', 'rotate')}))
    best.pop('text', None)
    level['combo']['number'] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in best.items()}
    level['rules'] = RULES
    write_level(NAME, level)
    for key, d in DIGITS.items():
        scene = draw_text(scene, d['text'], level['live_text'][key])
    scene = draw_text(scene, COMBO_NUMBER['text'], level['combo']['number'])
    save_png(work('l6_rebuilt_reference.png'), scene)
    d = np.abs(scene - I).mean(-1)
    d = d[92:1432, 4:W - 8]          # inside the reference phone's bezel
    print(' rebuilt reference vs reference: mean diff %.2f/255, %.2f%% px off by >40' % (d.mean(), (d > 40).mean() * 100))


if __name__ == '__main__' and '--preview' not in sys.argv:
    import time
    t0 = time.time()
    P = build()
    print('masks', {k: int(m.sum()) for k, m in P['masks'].items()}, 'dyn px', int(P['dyn'].sum()), '%.1fs' % (time.time() - t0))
    if '--reuse-bg' in sys.argv and os.path.exists(work('l6_bg.npy')):
        B = np.load(work('l6_bg.npy'))
    else:
        B = rebuild(P)
        np.save(work('l6_bg.npy'), B)
        save_png(work('l6_bg.png'), B)
    print('background %.1fs' % (time.time() - t0))
    export(P, B)
    print('done %.1fs' % (time.time() - t0))


if __name__ == '__main__' and '--preview' in sys.argv:
    P = build()
    out = I * 0.55
    col = {'frame': (60, 60, 255), 'dyn': (255, 0, 255)}
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
            if y is not None:
                out[int(y), x] = (255, 80, 0)
    save_png(work('l6_preview.png'), out)
    print('preview written', {k: int(m.sum()) for k, m in P['masks'].items()})
