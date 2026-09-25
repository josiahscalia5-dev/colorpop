"""Level 3 art: "HIT THE PURPLE ONES!" (farm).

Reference: reference/screens/level3.png (702 x 1486 art px). Output: app-assets/level3/ + level.json.
See screen_art.py for the method. Everything here is measured on the reference; coordinates are
art px.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from screen_art import *
from paths import ROOT, work

NAME = 'level3'
OUT = os.path.join(ROOT, 'app-assets', NAME)
I = load_ref(NAME)
H, W = I.shape[:2]
Y, X = grid(I.shape)
HSV = hsv(I)
h_, s_, v_ = HSV[..., 0], HSV[..., 1], HSV[..., 2]

# ---------------------------------------------------------------- geometry (measured)
# outer = outside of the brick rim; inner = the opening. Empty holes: opening = dark interior fit.
def inner_from_outer(o):
    cx, cy, a, b = o
    return (cx, cy - 0.11 * b, 0.75 * a, 0.66 * b)

HOLES = {
    'h1': {'outer': (323, 690, 108, 36)},
    'h2': {'outer': (145, 795, 133, 53)},
    'h3': {'outer': (565, 790, 125, 52)},
    'h4': {'outer': (360, 977, 155, 105), 'inner': (358, 960, 113, 75)},
    'h5': {'outer': (60, 1005, 110, 78), 'inner': (57, 991, 75, 53)},
    'h6': {'outer': (650, 1003, 110, 78), 'inner': (660, 989, 72, 51)},
    'h7': {'outer': (217, 1256, 195, 116), 'inner': (221, 1243, 146, 77)},
}
for k, hd in HOLES.items():
    hd.setdefault('inner', inner_from_outer(hd['outer']))

# characters: box, colour, hole, role
CHARS = {
    'pink':    {'box': (268, 596, 412, 716), 'colour': 'pink', 'hole': 'h1', 'role': 'distractor'},
    'purple':  {'box': (52, 658, 232, 832), 'colour': 'purple', 'hole': 'h2', 'role': 'target'},
    'red':     {'box': (478, 658, 652, 830), 'colour': 'red', 'hole': 'h3', 'role': 'distractor'},
    'purple2': {'box': (262, 840, 432, 1045), 'colour': 'purple', 'hole': 'h4', 'role': 'target', 'intro_only': True},
}


def colour_mask(c):
    if c == 'purple':
        return (h_ >= 122) & (h_ <= 152) & (s_ > 60) & (v_ > 55)
    if c == 'pink':
        return (h_ >= 145) & (h_ <= 176) & (s_ > 60) & (v_ > 80)
    if c == 'red':
        return ((h_ <= 7) | (h_ >= 170)) & (s_ > 110) & (v_ > 90)
    raise ValueError(c)


def front_arc(hole, x):
    cx, cy, a, b = HOLES[hole]['inner']
    return cy + b * np.sqrt(np.clip(1 - ((x - cx) / a) ** 2, 0, 1))


def segment_char(k):
    c = CHARS[k]
    box = c['box']
    cm = colour_mask(c['colour']) & rect_mask(I.shape, box)
    cm = cv2.morphologyEx(cm.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cm.astype(np.uint8), 8)
    cm = lab == (1 + np.argmax(st[1:, 4]))
    cnts, _ = cv2.findContours(cm.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    hull = np.zeros(I.shape[:2], np.uint8)
    cv2.drawContours(hull, [cv2.convexHull(max(cnts, key=len))], -1, 1, -1)
    hull = hull.astype(bool)
    # the body reaches down to the front rim of its hole: everything between the hull and the
    # front arc (inside the opening's width) is probably the character too
    ys, xs = np.where(hull)
    fa = front_arc(c['hole'], X)
    inner = HOLES[c['hole']]['inner']
    below = (X >= xs.min()) & (X <= xs.max()) & (Y >= ys.min()) & (Y < fa - 1) & (np.abs(X - inner[0]) < inner[2])
    pr = dilate(hull, 3) | (below & dilate(hull, 25))
    bgs = (Y > fa + 2) | ~dilate(pr, 6)
    m = grabcut(I, box, fg=erode(cm, 3), pr_fg=pr, bg=bgs & ~erode(cm, 3))
    return m


def char_region(k, m):
    """What to remove for a character: its hull (hat brims, antenna knobs, glossy tops, glow edge)
    grown 6 px, above its hole's front rim. Its sprite is a difference matte over this region."""
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    hull = np.zeros(I.shape[:2], np.uint8)
    cv2.drawContours(hull, [cv2.convexHull(max(cnts, key=len))], -1, 1, -1)
    ys, xs = np.where(m)
    knob = rect_mask(I.shape, (xs.min() + 0.3 * (xs.max() - xs.min()), ys.min() - 16, xs.max() - 0.3 * (xs.max() - xs.min()), ys.min() + 4))
    r = dilate(hull.astype(bool) | knob, 6)
    return r & (Y < front_arc(CHARS[k]['hole'], X) + 2)


def is_dirt():
    return (h_ >= 4) & (h_ <= 22) & (s_ > 90) & (v_ > 120)


def connected(mask):
    n, lab = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    return [lab == i for i in range(1, n)]


# ---------------------------------------------------------------- frame + live HUD parts
STATUS = [(45, 28, 130, 72), (515, 30, 690, 70)]          # fake "9:41" and signal/wifi/battery
HOME_BAR = (240, 1462, 470, 1484)                          # iOS home indicator
CORNER_R = 44
PAUSE = {'cx': 77, 'cy': 137, 'r': 42}
DIGITS = {  # live numbers: white glyph box, alignment, the text shown in the reference
    'timer':  {'box': (560, 119, 649, 151), 'align': 'left', 'text': '00:18'},
    'target': {'box': (577, 254, 617, 320), 'align': 'center', 'text': '8'},
    'score':  {'box': (270, 396, 345, 433), 'align': 'left', 'text': '320'},
}
COMBO_BOX = (424, 366, 662, 506)       # "3x COMBO!" badge

# ---------------------------------------------------------------- effects (hint: hand + swipe trail + gem)
HINT_POLY = [(88, 1150), (250, 1060), (380, 960), (440, 880), (520, 850), (590, 900), (590, 1000),
             (570, 1030), (655, 1140), (655, 1268), (560, 1268), (430, 1175), (300, 1150), (160, 1215), (88, 1222)]
WISP_POLY = [(255, 838), (380, 838), (384, 915), (318, 915), (255, 905)]
BURST_POLY = [(300, 712), (330, 660), (385, 585), (455, 585), (470, 640), (515, 700), (520, 790), (480, 850),
              (420, 870), (340, 860), (296, 800)]
BEHIND_POLY = [(372, 818), (490, 818), (492, 890), (372, 890)]     # debris / sparks behind the centre purple
SPECKS = [(128, 1068, 168, 1110), (205, 1040, 240, 1062)]


def effect_pixels(region):
    fx = (v_ > 225) | ((s_ < 95) & (v_ > 150)) | ((h_ >= 85) & (h_ <= 178) & (s_ > 45) & (v_ > 70))
    fx &= region
    fx = cv2.morphologyEx(fx.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    return dilate(fx, 3) & dilate(region, 3)


def build():
    masks = {k: segment_char(k) for k in CHARS}
    edges, openings = {}, {}
    for k, c in CHARS.items():
        hk = c['hole']
        masks[k] &= Y < front_arc(hk, X) + 1.5
        openings[hk], edges[hk] = fit_front(HOLES[hk]['inner'], masks[k])
    for hk, hd in HOLES.items():
        if hk not in openings:
            openings[hk] = tuple(round(v, 1) for v in hd['inner'])
            edges[hk] = edge_columns(openings[hk], {}, 0)

    frame = rounded_outside(I.shape, CORNER_R) | rect_mask(I.shape, HOME_BAR)
    for r in STATUS:
        frame |= rect_mask(I.shape, r)
    hint = poly_mask(I.shape, HINT_POLY)
    fx_hint = hint | effect_pixels(dilate(hint, 12))
    fx_other = poly_mask(I.shape, WISP_POLY) | poly_mask(I.shape, BURST_POLY) | poly_mask(I.shape, BEHIND_POLY)
    for r in SPECKS:
        fx_other |= effect_pixels(rect_mask(I.shape, r))
    hsvm = HSV
    combo = rect_mask(I.shape, COMBO_BOX) & ((hsvm[..., 1] > 120) & (hsvm[..., 0] >= 12) & (hsvm[..., 0] <= 35) | (hsvm[..., 2] < 90))
    combo = dilate(cv2.morphologyEx(combo.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)).astype(bool), 3) & rect_mask(I.shape, COMBO_BOX)
    digits = np.zeros((H, W), bool)
    for d in DIGITS.values():
        x0, y0, x1, y1 = d['box']
        digits |= rect_mask(I.shape, (x0 - 5, y0 - 5, x1 + 5, y1 + 6))
    pause = ellipse_mask(I.shape, (PAUSE['cx'], PAUSE['cy'], PAUSE['r'] + 3, PAUSE['r'] + 3))
    chars = np.zeros((H, W), bool)
    for k, m in masks.items():
        chars |= char_region(k, m)
    dyn = chars | fx_hint | fx_other | combo | digits | pause
    return masks, edges, openings, frame, dyn, fx_hint, fx_other, combo, pause, digits


def rebuild(masks, frame, dyn, flat):
    B = I.copy()
    # 1. the frame (status bar, corners, home bar): smooth fill from around it
    B = cv2.inpaint(np.clip(B, 0, 255).astype(np.uint8), frame.astype(np.uint8) * 255, 6, cv2.INPAINT_TELEA).astype(np.float64)
    # live digits on flat dark panels and the pause button (sky): smooth membrane from around;
    # the score digits sit on a translucent panel over trees: patch fill from the panel itself
    for comp in connected(flat):
        B = merge_region(B, np.zeros_like(B), comp)
    dyn = dyn & ~flat
    bad = dyn | frame
    # 2. hidden parts of the holes, from clean donor holes at the same ring coordinates
    order = ['h7', 'h5', 'h6', 'h2', 'h3', 'h1', 'h4']
    guide = B.copy(); covered = np.zeros((H, W), bool)
    for hk in order:
        hd = {'inner': HOLES[hk]['inner'], 'outer': HOLES[hk]['outer']}
        donors = [dict(inner=HOLES[d]['inner'], outer=HOLES[d]['outer'], mirror=mi) for d, mi in
                  ((hk, True), ('h7', False), ('h7', True), ('h5', False), ('h6', False), ('h2', False), ('h3', False))
                  if not (d == hk and not mi) and not (d == hk and hk != 'h7')]   # only the big front hole mirrors itself
        g, cov = hole_guidance(B, hd, donors, bad & ~covered, bad)
        guide[cov] = g[cov]; covered |= cov
    # 3. everything else hidden: patch fill from nearby clean pixels (not from the rims)
    rings = np.zeros((H, W), bool)
    for hk, hd in HOLES.items():
        rings |= ellipse_mask(I.shape, hd['outer'], 6)
    rest = bad & ~covered & ~frame
    grass = (X > 540) & (Y > 1235 - (X - 560) * 0.4)
    dirt_src = ~bad & ~rings & ~grass & (Y > 600) & is_dirt()
    upper = rest & (Y <= 600)
    for part, src in ((rest & ~grass & ~upper, dirt_src), (rest & grass, ~bad & ~rings & (Y > 1150)), (upper, ~bad & ~rings & (Y <= 640))):
        if part.any():
            filled = exemplar_fill(guide, part, src, ps=13)
            # soften the patch seams (the reference dirt is soft anyway)
            soft = cv2.GaussianBlur(filled.astype(np.float32), (0, 0), 1.1).astype(np.float64)
            guide[part] = soft[part]
    # 4. one Poisson merge over everything rebuilt (removes seams and lighting steps)
    B = merge_region(B, guide, (bad & ~frame) | (covered & ~frame))
    # colour of a character / effect that leaked into the rebuilt dirt (pink, purple): re-solve those
    # pixels keeping only their fine texture, the tone from the clean surroundings
    hb = hsv(B)
    leak = (bad & ~frame) & (hb[..., 0] >= 125) & (hb[..., 0] <= 178) & (hb[..., 1] > 35) & (Y > 560)
    leak = dilate(leak, 3) & (bad & ~frame)
    for comp in connected(leak):
        y0, y1, x0, x1 = bbox(comp, 3, I.shape)
        reg = B[y0:y1, x0:x1]
        hp = reg - cv2.GaussianBlur(reg.astype(np.float32), (0, 0), 2.0).astype(np.float64)
        B[y0:y1, x0:x1] = poisson_merge(reg, hp, comp[y0:y1, x0:x1])
    return B


COMBO_NUMBER = {'box': (500, 382, 571, 431), 'align': 'center', 'text': '3x'}   # ink of the live number


def combo_number_region(combo):
    """The live number's part of the badge: its yellow fill grown by its outline."""
    x0, y0, x1, y1 = COMBO_NUMBER['box']
    fill = rect_mask(I.shape, (x0 - 6, y0 - 6, x1 + 6, y1 + 2)) & (h_ >= 12) & (h_ <= 38) & (s_ > 90) & (v_ > 150)
    return dilate(fill, 9) & combo & (Y < y1 + 3)
RULES = {'duration': 30, 'goal': 12, 'target': 'purple', 'combo': True, 'swipe': True, 'bombs': 0.0,
         'mix': {'target': 0.55, 'distractor': 0.45}, 'hold': [1.1, 1.5], 'gap': [0.45, 0.75], 'up_max': [2, 3],
         'reference_state': {'elapsed': 12.0, 'targets_left': 8, 'score': 320, 'combo': 3}}


def export(masks, edges, openings, B, parts):
    import json
    from levels.export import sprite_entry, calibrate_digits, write_level
    rel = NAME
    level = {'id': 3, 'art': {'w': W, 'h': H}, 'content': {'top': 92, 'bottom': 1380}}
    from levels.export import clean_frame
    B = clean_frame(B)
    # background, with 24 px of blurred reflection each side (only seen on wide screens)
    PAD = 24
    full = cv2.copyMakeBorder(B.astype(np.float32), 0, 0, PAD, PAD, cv2.BORDER_REFLECT_101)
    soft = cv2.GaussianBlur(full, (0, 0), 6)
    ramp = np.clip((np.abs(np.arange(W + 2 * PAD) - (W + 2 * PAD - 1) / 2) - (W / 2 - 1)) / PAD, 0, 1)[None, :, None]
    save_png(os.path.join(OUT, 'bg.png'), full * (1 - ramp) + soft * ramp)
    level['bg'] = {'file': rel + '/bg.png', 'pad_side': PAD, 'pad_top': 0, 'pad_bottom': 0}
    level['holes'] = {hk: {'opening': list(openings[hk]), 'edge': edges[hk]} for hk in sorted(HOLES)}
    # characters: difference matte over their removal region, solid on the body
    level['chars'] = {}
    layers = []
    for k, c in CHARS.items():
        hk = c['hole']
        region = char_region(k, masks[k])
        rgba, xy = matte_sprite(I, B, region, masks[k], edges[hk], ext=30)
        e = sprite_entry(OUT, 'char_' + k, rgba, xy, rel)
        e.update({'hole': hk, 'color': c['colour'], 'role': c['role']})
        if c.get('intro_only'):
            e['intro_only'] = True
        level['chars'][k] = e
        vis = ~hides_mask(I.shape, openings[hk], edges[hk])
        layers.append((rgba, xy[0], xy[1], vis))
    with_chars = composite(B, layers)
    # effects over the characters: the swipe hint (hand, trail, gem, sparks) and the hit burst
    hint_region = dilate(parts['fx_hint'] | poly_mask(I.shape, WISP_POLY) | poly_mask(I.shape, BEHIND_POLY), 2)
    rgba, xy = diff_matte(I, with_chars, hint_region)
    level['hint'] = sprite_entry(OUT, 'hint', rgba, xy, rel)
    layers.append((rgba, xy[0], xy[1], None))
    rgba, xy = diff_matte(I, with_chars, dilate(poly_mask(I.shape, BURST_POLY), 2))
    level['burst'] = sprite_entry(OUT, 'burst', rgba, xy, rel)
    level['burst']['anchor'] = [410, 760]          # centre of the flash
    layers.append((rgba, xy[0], xy[1], None))
    # combo badge: the word as art, the number live
    word = parts['combo'] & ~combo_number_region(parts['combo'])
    rgba, xy = diff_matte(I, B, word)
    level['combo'] = {'word': sprite_entry(OUT, 'combo_word', rgba, xy, rel)}
    layers.append((rgba, xy[0], xy[1], None))
    # pause button
    pm = ellipse_mask(I.shape, (PAUSE['cx'], PAUSE['cy'], PAUSE['r'] + 2, PAUSE['r'] + 2))
    rgba, xy = cut_sprite(I, pm, feather=0.8)
    level['pause'] = sprite_entry(OUT, 'pause', rgba, xy, rel)
    level['pause']['hit'] = dict(PAUSE)
    layers.append((rgba, xy[0], xy[1], None))
    scene = composite(B, layers)
    # live numbers
    print(' calibrating lettering')
    level['live_text'] = calibrate_digits(I, scene, DIGITS)
    for k in level['live_text']:
        level['live_text'][k].pop('text', None)
    from levels.export import calibrate_combo
    e0, e, best = calibrate_combo(I, scene, COMBO_NUMBER)
    print('   combo    3x     error %.1f -> %.1f  %s' % (e0, e, {k: best[k] for k in ('size', 'scale_x', 'outline', 'shadow', 'rotate')}))
    best.pop('text', None)
    level['combo']['number'] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in best.items()}
    level['rules'] = RULES
    write_level(NAME, level)
    # the reference moment rebuilt from the parts (checked by compare_screens.py)
    for key, t in (('timer', '00:18'), ('target', '8'), ('score', '320')):
        scene = draw_text(scene, t, level['live_text'][key])
    scene = draw_text(scene, '3x', level['combo']['number'])
    save_png(work('l3_rebuilt_reference.png'), scene)
    d = np.abs(scene - I).mean(-1)
    d = d[92:1380, 4:W - 8]          # inside the reference phone's bezel
    print(' rebuilt reference vs reference: mean diff %.2f/255, %.2f%% px off by >40' % (d.mean(), (d > 40).mean() * 100))


if __name__ == '__main__':
    import time
    t0 = time.time()
    masks, edges, openings, frame, dyn, fx_hint, fx_other, combo, pause, digits = build()
    print('masks', {k: int(m.sum()) for k, m in masks.items()}, 'dyn px', int(dyn.sum()), '%.1fs' % (time.time() - t0))
    if '--reuse-bg' in sys.argv and os.path.exists(work('l3_bg.npy')):
        B = np.load(work('l3_bg.npy'))
    else:
        B = rebuild(masks, frame, dyn, digits | pause)
        np.save(work('l3_bg.npy'), B)
        save_png(work('l3_bg.png'), B)
    print('background %.1fs' % (time.time() - t0))
    export(masks, edges, openings, B, {'fx_hint': fx_hint, 'fx_other': fx_other, 'combo': combo})
    print('done %.1fs' % (time.time() - t0))
