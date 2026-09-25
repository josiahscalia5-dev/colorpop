"""Write a new level's art and level.json from its measurements (used by levels/level*.py).

All coordinates in level.json are art px of the level's reference (reference/screens/<name>.png).
Sprites at their home positions over bg.png reproduce the reference (see screen_art.py).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from screen_art import *
from paths import ROOT

WHITE = {'fill_top': [255, 255, 255], 'fill_bottom': [236, 238, 244], 'outline_color': [6, 12, 28]}


def clean_frame(B, left=4, right=8, top=6, bottom=0, radius=72, home_rows=26):
    """The reference phones' bezel (a few px on each side), rounded screen corners and home
    indicator, filled from the picture inside: the app shows the scene edge to edge (and mirrors it
    beyond the bottom). The bottom `home_rows` (home indicator, bezel) mirror the rows above them."""
    H, W = B.shape[:2]
    B = B.copy()
    k = np.arange(home_rows)
    B[H - home_rows + k] = B[H - home_rows - 1 - k]
    m = np.zeros((H, W), np.uint8)
    x0, y0, x1, y1 = left, top, W - 1 - right, H - 1 - bottom
    cv2.rectangle(m, (x0 + radius, y0), (x1 - radius, y1), 1, -1)
    cv2.rectangle(m, (x0, y0 + radius), (x1, y1 - radius), 1, -1)
    for cx, cy in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius), (x0 + radius, y1 - radius), (x1 - radius, y1 - radius)):
        cv2.circle(m, (cx, cy), radius, 1, -1)
    frame = (m == 0).astype(np.uint8) * 255
    return cv2.inpaint(np.clip(B, 0, 255).astype(np.uint8), frame, 12, cv2.INPAINT_TELEA).astype(np.float64)


def sprite_entry(out_dir, name, rgba, xy, rel):
    save_rgba(os.path.join(out_dir, name + '.png'), rgba)
    return {'file': f'{rel}/{name}.png', 'x': int(xy[0]), 'y': int(xy[1]), 'w': int(rgba.shape[1]), 'h': int(rgba.shape[0])}


def calibrate_digits(I, base, digits, style_grid=True):
    """White HUD numbers: size from the digit height, then outline/shadow/size/condensing."""
    out = {}
    for key, d in digits.items():
        x0, y0, x1, y1 = d['box']
        spec = dict(WHITE, box=list(d['box']), align=d['align'], size=round((y1 - y0) / 0.72, 1), scale_x=0.85,
                    outline=3.0, shadow=1.5)
        grid_ = {'outline': [2.0, 3.0, 4.0], 'shadow': [0.0, 1.5, 3.0],
                 'size': [lambda s, f=f: round(s['size'] * f, 1) for f in (0.97, 1.0, 1.03, 1.06)],
                 'scale_x': [0.78, 0.84, 0.9, 0.96]}
        e0 = calibrate_text(I, base, d['text'], spec, {})[0]
        e, best = calibrate_text(I, base, d['text'], spec, grid_)
        best = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in best.items()}
        out[key] = best
        print('   %-7s %-6s error %.1f -> %.1f  %s' % (key, d['text'], e0, e, {k: best[k] for k in ('size', 'scale_x', 'outline', 'shadow')}))
    return out


def write_level(name, level):
    out_dir = os.path.join(ROOT, 'app-assets', name)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(level, open(os.path.join(out_dir, 'level.json'), 'w'), indent=1)


COMBO_STYLE = {'fill_top': [255, 244, 120], 'fill_bottom': [246, 150, 20], 'outline_color': [48, 18, 6]}


def calibrate_combo(I, scene, number):
    """The yellow "Nx" of a combo badge: size from the ink height, then outline/shadow/tilt/condensing."""
    x0, y0, x1, y1 = number['box']
    num = dict(COMBO_STYLE, **number)
    num.update(size=round((y1 - y0) / 0.72, 1), scale_x=0.95, outline=5.0, shadow=2.0, rotate=0.0)
    e0 = calibrate_text(I, scene, number['text'], num, {})[0]
    e, best = calibrate_text(I, scene, number['text'], num,
                             {'outline': [4.0, 5.5, 7.0], 'shadow': [0.0, 3.0], 'rotate': [-8.0, -5.0, -2.0, 0.0],
                              'scale_x': [0.9, 1.0, 1.1],
                              'size': [lambda s, f=f: round(s['size'] * f, 1) for f in (0.94, 1.0, 1.06)]})
    return e0, e, best


def sharp_sprite(name, I, B, region, core, edge, ext=30, hires=None, deblur_px=1.0):
    """A character sprite at twice the art resolution, as sharp as the Level 1 characters: the body
    from the super-resolved enlargement (sr.py), the alpha tight around the character (its outline
    plus a 3 px soft edge: no background carried along when it pops up elsewhere), the colour below
    the rim continued as before. Returns (rgba at 2x, (x, y) in art px, rgba at 1x for checks)."""
    import sr
    region = region & dilate(core, 3)
    rgba1, (x0, y0), extm = matte_sprite(I, B, region, core, edge, ext=ext, ext_mask=True)
    h1, w1 = rgba1.shape[:2]
    if hires is None:
        hires = sr.hires_canvas(name)[0]
    Hh, Wh = hires.shape[:2]
    # the picture part of the sprite (rows inside the screen), super-resolved with a margin
    bx0, by0 = 2 * x0, 2 * y0
    bx1, by1 = min(Wh, 2 * (x0 + w1)), min(Hh, 2 * (y0 + h1))
    m = 24
    sharp, (sx0, sy0, sx1, sy1), _ = sr.sharp_region(hires, (max(0, bx0 - m), max(0, by0 - m), min(Wh, bx1 + m), min(Hh, by1 + m)),
                                                     deblur_px=deblur_px, keep=10.0 if deblur_px >= 2 else 6.0)
    pic = np.zeros((2 * h1, 2 * w1, 3), np.float32)
    ys, xs = slice(by0 - sy0, by1 - sy0), slice(bx0 - sx0, bx1 - sx0)
    pic[:by1 - by0, :bx1 - bx0] = sharp[ys, xs]
    up = cv2.resize(rgba1.astype(np.float32), (2 * w1, 2 * h1), interpolation=cv2.INTER_CUBIC)
    a2 = np.clip(up[..., 3] / 255.0, 0, 1)
    solid = cv2.resize((rgba1[..., 3] > 250).astype(np.float32), (2 * w1, 2 * h1), interpolation=cv2.INTER_LINEAR)
    e2 = cv2.resize(extm.astype(np.float32), (2 * w1, 2 * h1), interpolation=cv2.INTER_LINEAR) > 0.01
    # the reconstructed picture everywhere it exists (also on the soft edge: the matte's own
    # extrapolated colours there make a dark fringe); the continued colour below the rim
    w = (~e2).astype(np.float32)[..., None]
    w[by1 - by0:] = 0
    rgb = pic * w + np.clip(up[..., :3], 0, 255) * (1 - w)
    # a crisp silhouette: the soft edge of the upscaled alpha steepened
    a2 = np.clip((a2 - 0.12) / 0.76, 0, 1)
    rgba2 = np.dstack([np.clip(rgb, 0, 255), a2 * 255])
    return rgba2, (x0, y0), rgba1


def sharp_entry(out_dir, name, rgba2, xy, rel):
    """sprite_entry for a 2x sprite: w/h in art px, "scale": bitmap px per art px."""
    save_rgba(os.path.join(out_dir, name + '.png'), rgba2)
    return {'file': f'{rel}/{name}.png', 'x': int(xy[0]), 'y': int(xy[1]), 'w': round(rgba2.shape[1] / 2, 1),
            'h': round(rgba2.shape[0] / 2, 1), 'scale': 2}
