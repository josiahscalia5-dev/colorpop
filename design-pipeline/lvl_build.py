import numpy as np, cv2, json, time, os
from PIL import Image
from common import *
from paths import ref, work, data, asset_dir
OUT = asset_dir('level', 'characters')
a = fix_edges(np.asarray(Image.open(ref('lvl_crop.png')).convert('RGB')).copy())
H, W = a.shape[:2]
G = json.load(open(data('_lvl_geom.json')))
HOLES, CHARS = G['HOLES'], G['CHARS']
M = dict(np.load(data('_lvl_masks.npz')))
t0 = time.time()
# ---------- 1. clean status bar + bezel corners ----------
clean = status_and_corner_mask(a, [(44, 18, 110, 54), (448, 14, 588, 52)])
base = inpaint(a, clean, 'fsr_best')
# ---------- 2. character sprites ----------
meta = {'chars': {}, 'holes': HOLES}
for k, (hole, box, col) in CHARS.items():
    m = M[k].astype(np.float32)
    alpha = cv2.GaussianBlur(m, (0, 0), 0.6)
    alpha = np.where(m > 0, np.maximum(alpha, 0.5), alpha * 0.8)
    cx, cy, ea, eb = HOLES[hole]['inner']
    ys, xs = np.where(m > 0)
    x0, x1 = xs.min() - 2, xs.max() + 3
    y0, y1 = ys.min() - 2, int(cy + eb) + 34
    rgb = base[y0:min(y1, H), x0:x1].astype(np.float32)
    al = alpha[y0:min(y1, H), x0:x1]
    if rgb.shape[0] < y1 - y0:  # pad below image bottom
        padn = y1 - y0 - rgb.shape[0]
        rgb = np.concatenate([rgb, np.repeat(rgb[-1:], padn, 0)], 0)
        al = np.concatenate([al, np.zeros((padn, al.shape[1]), np.float32)], 0)
    mm = np.zeros_like(al); 
    sub = m[y0:min(y1, H), x0:x1]; mm[:sub.shape[0]] = sub
    # extend body colour straight down below the rim line (hidden by the rim clip in-game)
    for j in range(al.shape[1]):
        col_idx = np.where(mm[:, j] > 0)[0]
        if len(col_idx) == 0: continue
        yb = col_idx.max()
        xg = x0 + j
        arc = cy + eb * np.sqrt(max(0.0, 1 - ((xg - cx) / ea) ** 2)) - y0
        if abs(yb - arc) > 4 or abs(xg - cx) > ea: continue
        src = rgb[max(0, yb - 4):yb - 1, j].mean(0)
        for yy in range(yb - 1, al.shape[0]):
            rgb[yy, j] = src * (1 - 0.35 * (yy - yb + 1) / 34.0)
            al[yy, j] = 1.0
    rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), (np.clip(al, 0, 1) * 255).astype(np.uint8)])
    save_rgba(f'{OUT}/char_{k}.png', rgba)
    meta['chars'][k] = dict(hole=hole, color=col, x=int(x0), y=int(y0), w=int(rgba.shape[1]), h=int(rgba.shape[0]))
print('sprites', round(time.time() - t0, 1))
# ---------- 3. remove characters from the background ----------
charm = np.zeros((H, W), bool)
for k in CHARS: charm |= M[k]
charm = cv2.dilate(charm.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
bgA = inpaint(base, charm, 'fsr_fast')
np.save(work('lvl_bgA.npy'), bgA)
np.save(work('lvl_base.npy'), base)
json.dump(meta, open(OUT + '/_meta.json', 'w'), indent=1)
print('done', round(time.time() - t0, 1))
