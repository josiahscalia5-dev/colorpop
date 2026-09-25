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
