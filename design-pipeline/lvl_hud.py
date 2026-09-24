"""Level 1 HUD: cut the pause button into its own sprite and erase the three live numbers
(timer digits, green-targets-left counter, score value) from the background.

The numbers are redrawn by the game with Lilita One; LIVE_TEXT below is the calibration used by
the app (see TextStyle in the Android code) and by the preview at the end of this script, which
renders the reference values over the erased panels for a side-by-side check.

Input:  _work/lvl_bg_holes.npy (from lvl_holes.py), reference/lvl_crop.png
Output: _work/lvl_bg_hud.npy, app-assets/level/pause.png, _work/lvl_hud.json, preview _work/lvl_hud_check.png
"""
import json
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from common import circle_mask, cut_sprite, save_rgba, inpaint
from paths import work, ref, asset_dir, ROOT
import os

bg = np.load(work('lvl_bg_holes.npy')).astype(np.float64)
H, W = bg.shape[:2]
orig = np.asarray(Image.open(ref('lvl_crop.png')).convert('RGB'))
base = np.load(work('lvl_base.npy'))  # status bar cleaned, characters still there (HUD untouched)
OUT = asset_dir('level')


def membrane(img, mask):
    """Harmonic fill of `mask` from its boundary (the panels behind the digits are smooth)."""
    import scipy.sparse as sp, scipy.sparse.linalg as spla
    ys, xs = np.where(mask)
    idx = -np.ones(mask.shape, np.int64); idx[ys, xs] = np.arange(len(ys))
    n = len(ys); rows, cols, vals = [], [], []; b = np.zeros((n, 3)); diag = np.zeros(n)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ny, nx = ys + dy, xs + dx
        diag += 1
        inside = mask[ny, nx]
        rows.append(np.where(inside)[0]); cols.append(idx[ny, nx][inside]); vals.append(-np.ones(inside.sum()))
        b[~inside] += img[ny[~inside], nx[~inside]]
    A = sp.csr_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [np.arange(n)]),
                       np.concatenate(cols + [np.arange(n)]))), shape=(n, n))
    solve = spla.factorized(A.tocsc())
    out = img.copy()
    for c in range(3):
        out[ys, xs, c] = solve(b[:, c])
    return out


# ---------------------------------------------------------------- pause button sprite
PAUSE = dict(cx=65.0, cy=116.5, r=42.0)
alpha = circle_mask(orig.shape, PAUSE['cx'], PAUSE['cy'], PAUSE['r'], margin=2.5)
rgba, (px0, py0) = cut_sprite(base, alpha)
save_rgba(os.path.join(OUT, 'pause.png'), rgba)
hole = cv2.dilate((alpha > 0.01).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
bg = inpaint(np.clip(bg, 0, 255).astype(np.uint8), hole, 'fsr_best').astype(np.float64)

# ---------------------------------------------------------------- erase the live numbers
# white glyph boxes measured on the reference (crop px); the dark outline + drop shadow add ~4 px
TIMER = (498, 98, 584, 127)    # "00:28", left-aligned after the stopwatch icon
TARGET = (508, 210, 578, 271)  # "12", centred in the right-hand box of the objective panel
SCORE = (352, 335, 375, 370)   # "0" after the static "SCORE:"
for (x0, y0, x1, y1), pad in ((TIMER, 5), (TARGET, 6)):
    m = np.zeros((H, W), bool); m[y0 - pad:y1 + pad + 1, x0 - pad:x1 + pad] = True
    bg = membrane(bg, m)
x0, y0, x1, y1 = SCORE  # translucent panel over clouds: keep some texture
m = np.zeros((H, W), bool); m[y0 - 6:y1 + 7, x0 - 5:x1 + 6] = True
bg = inpaint(np.clip(bg, 0, 255).astype(np.uint8), m, 'fsr_best').astype(np.float64)

out = np.clip(bg, 0, 255).astype(np.uint8)
np.save(work('lvl_bg_hud.npy'), out)

# ---------------------------------------------------------------- live text calibration
# size: font px such that digits are as tall as in the reference (Lilita One digits = 0.72 em);
# scale_x: Lilita One is wider than the reference lettering; stroke: outline width (centred on
# the glyph edge); shadow: outline colour offset downwards.
DIGIT_EM = 0.72
LIVE_TEXT = {
    'timer':  dict(box=TIMER, align='left', size=round((TIMER[3] - TIMER[1]) / DIGIT_EM, 1), scale_x=0.83,
                   outline=3.0, shadow=2.0, initial='00:30'),
    'target': dict(box=TARGET, align='center', size=round((TARGET[3] - TARGET[1]) / DIGIT_EM, 1), scale_x=0.93,
                   outline=3.6, shadow=3.0, initial='12'),
    'score':  dict(box=SCORE, align='left', size=round((SCORE[3] - SCORE[1]) / DIGIT_EM, 1), scale_x=0.83,
                   outline=3.2, shadow=2.5, initial='0'),
}
# outline: dark edge outside the glyph (crop px; the reference keeps it ~3 px at every size);
# shadow: the same dark edge repeated this far below
STYLE = dict(fill_top=[255, 255, 255], fill_bottom=[226, 228, 236], outline=[6, 12, 28])
json.dump({'pause': dict(PAUSE, x=px0, y=py0, w=int(rgba.shape[1]), h=int(rgba.shape[0])),
           'live_text': LIVE_TEXT, 'text_style': STYLE}, open(work('lvl_hud.json'), 'w'), indent=1)


def draw_text(img, text, spec, sample=None):
    """Same drawing as the app: shadow (outline colour, offset down), outline, gradient fill."""
    S = 4  # supersample
    x0, y0, x1, y1 = spec['box']
    size = spec['size'] * S
    font = ImageFont.truetype(os.path.join(ROOT, 'design-pipeline', 'fonts', 'LilitaOne-Regular.ttf'), int(round(size)))
    stroke = max(1, int(round(spec['outline'] * S)))
    tw = font.getlength(text)
    layer_w, layer_h = int(tw + 8 * stroke), int(size * 1.6)
    def glyph_mask(extra):
        m = Image.new('L', (layer_w, layer_h), 0)
        ImageDraw.Draw(m).text((4 * stroke, 0), text, font=font, fill=255, stroke_width=extra, stroke_fill=255)
        return m
    fill = glyph_mask(0)
    outline = glyph_mask(stroke)
    # horizontal condensing like Paint.setTextScaleX
    new_w = int(layer_w * spec['scale_x'])
    fill = fill.resize((new_w, layer_h), Image.LANCZOS); outline = outline.resize((new_w, layer_h), Image.LANCZOS)
    fa = np.asarray(fill).astype(np.float32) / 255; oa = np.asarray(outline).astype(np.float32) / 255
    ys, xs = np.where(fa > 0.5)
    gy0, gy1, gx0, gx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    # place: glyph ink box -> reference box (left or centre), baseline by the ink top
    tx = x0 * S - gx0 if spec['align'] == 'left' else ((x0 + x1) / 2) * S - (gx0 + gx1) / 2
    ty = y0 * S - gy0
    dy = spec['shadow'] * S
    big = cv2.resize(img.astype(np.float32), (W * S, H * S), interpolation=cv2.INTER_CUBIC)
    def comp(a, color, ox, oy):
        M = np.float32([[1, 0, tx + ox], [0, 1, ty + oy]])
        aa = cv2.warpAffine(a, M, (W * S, H * S))[..., None]
        return aa, np.array(color, np.float32)
    for a, col, oy in ((oa, STYLE['outline'], dy), (oa, STYLE['outline'], 0)):
        aa, c = comp(a, col, 0, oy); big = big * (1 - aa) + c * aa
    aa, _ = comp(fa, [0, 0, 0], 0, 0)
    t = np.clip((np.arange(H * S)[:, None, None] - (ty + gy0)) / max(gy1 - gy0, 1), 0, 1)
    grad = np.array(STYLE['fill_top'], np.float32) * (1 - t) + np.array(STYLE['fill_bottom'], np.float32) * t
    big = big * (1 - aa) + grad * aa
    return cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA)


prev = out.astype(np.float32)
prev = draw_text(prev, '00:28', LIVE_TEXT['timer'])
prev = draw_text(prev, '12', LIVE_TEXT['target'])
prev = draw_text(prev, '0', LIVE_TEXT['score'])
prev = np.clip(prev, 0, 255).astype(np.uint8)
S = 3
tiles = []
for box in ((425, 75, 610, 150), (480, 190, 605, 300), (190, 320, 400, 385), (10, 60, 125, 175)):
    a = Image.fromarray(orig).crop(box); b = Image.fromarray(prev).crop(box); e = Image.fromarray(out).crop(box)
    w, h = a.size
    t = Image.new('RGB', (w * S * 3 + 12, h * S), (255, 0, 255))
    for i, im in enumerate((a, e, b)):
        t.paste(im.resize((w * S, h * S), Image.LANCZOS), (i * (w * S + 6), 0))
    tiles.append(t)
Wt = max(t.size[0] for t in tiles); Ht = sum(t.size[1] + 6 for t in tiles)
sheet = Image.new('RGB', (Wt, Ht), (255, 0, 255)); y = 0
for t in tiles:
    sheet.paste(t, (0, y)); y += t.size[1] + 6
sheet.save(work('lvl_hud_check.png'))
print(json.dumps(LIVE_TEXT))
