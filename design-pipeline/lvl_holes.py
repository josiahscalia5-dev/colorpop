import numpy as np, cv2, json, time
from PIL import Image
from common import *
from paths import work, data
bgA = np.load(work('lvl_bgA.npy'))
base = np.load(work('lvl_base.npy'))
H, W = bgA.shape[:2]
G = json.load(open(data('_lvl_geom.json'))); HOLES, CHARS = G['HOLES'], G['CHARS']
M = dict(np.load(data('_lvl_masks.npz')))
charm = np.zeros((H, W), bool)
for k in CHARS: charm |= M[k]
charm = cv2.dilate(charm.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)

for k in CHARS:
    m = cv2.dilate(M[k].astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    ys, xs = np.where(m)
    x0, x1 = max(0, xs.min() - 30), min(W, xs.max() + 31); y0, y1 = max(0, ys.min() - 30), min(H, ys.max() + 31)
    loc = inpaint(base[y0:y1, x0:x1], m[y0:y1, x0:x1], 'fsr_best')
    bgA[y0:y1, x0:x1][m[y0:y1, x0:x1]] = loc[m[y0:y1, x0:x1]]
PB = 380  # ground extension rows below the reference
# ---------- ground extension ----------
rng = np.random.default_rng(7)
patches = [bgA[728:798, 252:370], bgA[890:1008, 486:620], bgA[884:962, 18:158], bgA[622:752, 2:118]]
ref = bgA[1090:1150, 300:380].reshape(-1, 3).astype(np.float32)
mean = ref.mean(0)
ext = np.ones((PB, W, 3), np.float32) * mean
low = cv2.GaussianBlur(rng.normal(0, 1, (PB, W)).astype(np.float32), (0, 0), 25)
ext += (low / (low.std() + 1e-6))[..., None] * np.array([10, 6, 4.0])
for _ in range(900):
    p = patches[rng.integers(len(patches))].astype(np.float32)
    ph, pw = p.shape[:2]
    sh, sw = int(rng.integers(26, min(60, ph))), int(rng.integers(40, min(100, pw)))
    py, px = int(rng.integers(0, ph - sh + 1)), int(rng.integers(0, pw - sw + 1))
    tile = p[py:py + sh, px:px + sw]
    if rng.random() < 0.5: tile = tile[:, ::-1]
    tile = tile - tile.reshape(-1, 3).mean(0) + mean + rng.normal(0, 4, 3)
    ty, tx = int(rng.integers(-sh // 2, PB - sh // 2)), int(rng.integers(-sw // 2, W - sw // 2))
    Yg, Xg = np.mgrid[0:sh, 0:sw]
    al = np.clip(1 - np.sqrt(((Xg - sw / 2) / (sw / 2)) ** 2 + ((Yg - sh / 2) / (sh / 2)) ** 2), 0, 1) ** 0.7
    ya, yb = max(0, ty), min(PB, ty + sh); xa, xb = max(0, tx), min(W, tx + sw)
    if ya >= yb or xa >= xb: continue
    tt = tile[ya - ty:yb - ty, xa - tx:xb - tx]; aa = al[ya - ty:yb - ty, xa - tx:xb - tx][..., None]
    ext[ya:yb, xa:xb] = ext[ya:yb, xa:xb] * (1 - aa) + tt * aa
yy = np.arange(PB)[:, None, None]
ext *= 1 - 0.12 * (yy / PB)
ext = np.clip(ext, 0, 255)
canvas = np.concatenate([bgA.astype(np.float32), ext], 0)
HH = canvas.shape[0]
# foliage clumps mirrored below the bottom-left flowers and the grass in front of hole 6
def mirror_patch(x0, x1, ys, depth, cxe, rx, ry):
    src = bgA[H - depth:H, x0:x1][::-1].astype(np.float32)
    Y, X = np.mgrid[0:depth, x0:x1]
    w = np.clip(1 - np.sqrt(((X - cxe) / rx) ** 2 + (Y / ry) ** 2), 0, 1)
    w = cv2.GaussianBlur(w.astype(np.float32), (0, 0), 6)[..., None]
    reg = canvas[H:H + depth, x0:x1]
    canvas[H:H + depth, x0:x1] = reg * (1 - w) + src * w
mirror_patch(0, 330, None, 130, 30, 250, 130)
mirror_patch(430, 622, None, 60, 560, 150, 60)
# seam softening
for i in range(10):
    w = (i + 1) / 11
    canvas[H + i] = canvas[H + i] * w + canvas[H - 1 - i] * (1 - w)
# ---------- empty holes ----------
def ring_coords(hole, X, Y):
    ci = HOLES[hole]['inner']; co = HOLES[hole]['outer']
    lo = np.zeros(X.shape); hi = np.ones(X.shape) * 1.6
    for _ in range(24):
        mid = (lo + hi) / 2
        cx = ci[0] + (co[0] - ci[0]) * mid; cy = ci[1] + (co[1] - ci[1]) * mid
        ea = ci[2] + (co[2] - ci[2]) * mid; eb = ci[3] + (co[3] - ci[3]) * mid
        d = ((X - cx) / ea) ** 2 + ((Y - cy) / eb) ** 2
        inside = d < 1
        hi = np.where(inside, mid, hi); lo = np.where(inside, lo, mid)
    rho = (lo + hi) / 2
    cx = ci[0] + (co[0] - ci[0]) * rho; cy = ci[1] + (co[1] - ci[1]) * rho
    ea = ci[2] + (co[2] - ci[2]) * rho; eb = ci[3] + (co[3] - ci[3]) * rho
    th = np.arctan2((Y - cy) / eb, (X - cx) / ea)
    return rho, th, cx, cy, ea, eb
src_img = canvas.copy()
for hk, g in HOLES.items():
    cxi, cyi, ai, bi = g['inner']; cxo, cyo, ao, bo = g['outer']
    x0, x1 = int(max(0, cxo - ao - 4)), int(min(W, cxo + ao + 5))
    y0, y1 = int(max(0, cyi - bi - 6)), int(min(HH, cyo + bo + 6))
    Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float64)
    rho, th, cx, cy, ea, eb = ring_coords(hk, X, Y)
    ring = (rho > 0) & (rho <= 1.0) & (((X - cxi) / ai) ** 2 + ((Y - cyi) / bi) ** 2 >= 1)
    occl = np.zeros_like(ring)
    cm = np.zeros((HH, W), bool); cm[:H] = charm
    occl = ring & ((cm[y0:y1, x0:x1] & (np.sin(th) < 0.2)) | (Y >= H))
    # back rim & cut-off rim: take the mirrored angle (front <-> back) at the same ring depth
    mx = cx + ea * np.cos(-th); my = cy + eb * np.sin(-th)
    my = np.clip(my, 0, H - 2)
    samp = cv2.remap(src_img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR)
    # back of the ring sits in shadow / further away -> slightly darker
    shade = np.where(np.sin(th) < 0, 0.88, 1.0)[..., None]
    reg = canvas[y0:y1, x0:x1]
    reg[occl] = (samp * shade)[occl]
    # interior: dark earth wall at the back fading to near-black
    ins = ellipse_mask((y1 - y0, x1 - x0), cxi - x0, cyi - y0, ai + 0.5, bi + 0.5, feather=1.2)
    tnorm = np.clip((Y - (cyi - bi)) / (2 * bi), 0, 1)
    wall_top = np.array([96, 52, 26.0]); wall_mid = np.array([48, 24, 12.0]); deep = np.array([20, 10, 6.0])
    colr = np.where(tnorm[..., None] < 0.45,
                    wall_top + (wall_mid - wall_top) * (tnorm[..., None] / 0.45),
                    wall_mid + (deep - wall_mid) * ((tnorm[..., None] - 0.45) / 0.55))
    # horizontal shading toward the sides
    side = np.clip(np.abs((X - cxi) / ai), 0, 1)[..., None]
    colr = colr * (1 - 0.35 * side ** 2)
    noise = rng.normal(0, 2.5, colr.shape)
    colr = colr + noise
    w = ins[..., None]
    reg[:] = reg * (1 - w) + colr * w
    canvas[y0:y1, x0:x1] = reg
out = np.clip(canvas, 0, 255).astype(np.uint8)
np.save(work('lvl_bg_holes.npy'), out)
Image.fromarray(out).save(work('lvl_bg_holes_prev.png'))
Image.fromarray(out[540:]).resize((W // 1, (HH - 540))).save(work('lvl_holes.png'))
print(out.shape)
