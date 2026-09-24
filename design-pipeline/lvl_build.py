"""Level 1: clean base image + the six character sprites.

1. status bar ("9:41", icons) and bezel corners of the reference photo removed -> _work/lvl_base.npy
2. each character cut out with its reviewed GrabCut mask (_lvl_masks.npz); the body colour is
   extended EXT px below the front edge of the opening, so a character can rise above its
   reference pose (bounce) without showing a gap -- in-game everything below the front edge is
   hidden by the clip, so the extension is never seen at rest.

The front edge is the fitted one from lvl_geom (the stored inner ellipse is up to 8 px off).
Output: app-assets/level/characters/char_c1..c6.png + _meta.json, _work/lvl_base.npy
"""
import numpy as np, cv2, json, time
from PIL import Image
from common import fix_edges, status_and_corner_mask, inpaint, save_rgba
from paths import ref, work, asset_dir
from lvl_geom import load, openings

EXT = 34
OUT = asset_dir('level', 'characters')
a = fix_edges(np.asarray(Image.open(ref('lvl_crop.png')).convert('RGB')).copy())
H, W = a.shape[:2]
HOLES, CHARS, M = load()
t0 = time.time()
# ---------- 1. clean status bar + bezel corners ----------
clean = status_and_corner_mask(a, [(44, 18, 110, 54), (448, 14, 588, 52)])
base = inpaint(a, clean, 'fsr_best')
np.save(work('lvl_base.npy'), base)
FRONT, OPEN = openings(HOLES, CHARS, M, base.astype(np.float64))
# ---------- 2. character sprites ----------
meta = {'chars': {}, 'holes': HOLES}
for k, (hole, box, col) in CHARS.items():
    m = M[k].astype(np.float32)
    alpha = cv2.GaussianBlur(m, (0, 0), 0.6)
    alpha = np.where(m > 0, np.maximum(alpha, 0.5), alpha * 0.8)
    cx, cy, ea, eb = OPEN[hole]
    ys, xs = np.where(m > 0)
    x0, x1 = xs.min() - 2, xs.max() + 3
    y0, y1 = ys.min() - 2, int(np.ceil(cy + eb)) + EXT
    rgb = base[y0:min(y1, H), x0:x1].astype(np.float32)
    al = alpha[y0:min(y1, H), x0:x1]
    if rgb.shape[0] < y1 - y0:  # pad below image bottom
        padn = y1 - y0 - rgb.shape[0]
        rgb = np.concatenate([rgb, np.repeat(rgb[-1:], padn, 0)], 0)
        al = np.concatenate([al, np.zeros((padn, al.shape[1]), np.float32)], 0)
    mm = np.zeros_like(al)
    sub = m[y0:min(y1, H), x0:x1]; mm[:sub.shape[0]] = sub
    # extend body colour straight down from where the body meets the front edge
    for j in range(al.shape[1]):
        col_idx = np.where(mm[:, j] > 0)[0]
        xg = x0 + j
        if len(col_idx) == 0 or abs(xg - cx) > ea:
            continue
        yb = col_idx.max()
        arc = cy + eb * np.sqrt(max(0.0, 1 - ((xg - cx) / ea) ** 2)) - y0
        if abs(yb - arc) > 4:
            continue  # this column of the body does not reach the rim (ear, hand, side)
        src = rgb[max(0, yb - 4):yb - 1, j].mean(0)
        start = min(yb, int(arc)) - 1
        for yy in range(start, al.shape[0]):
            rgb[yy, j] = src * (1 - 0.35 * max(0, yy - start) / EXT)
            al[yy, j] = 1.0
    rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), (np.clip(al, 0, 1) * 255).astype(np.uint8)])
    save_rgba(f'{OUT}/char_{k}.png', rgba)
    meta['chars'][k] = dict(hole=hole, color=col, x=int(x0), y=int(y0), w=int(rgba.shape[1]), h=int(rgba.shape[0]))
meta['openings'] = OPEN
json.dump(meta, open(OUT + '/_meta.json', 'w'), indent=1)
print('done', round(time.time() - t0, 1))
