"""Level 1: bottom foliage as a foreground layer + extra ground for tall phones.

The reference (1.85:1) is shorter than most phones (~2.2:1). The scene stays exactly as in the
reference from the top; the extra height becomes more ground below the bottom holes:

  * the bush + flowers at the bottom left and the grass in front of hole 6 are cut out as one
    foreground sprite, drawn over the characters and anchored to the bottom of the screen
    (at the reference aspect it lands exactly where it is in the reference)
  * the background behind them and the PB rows below the reference are rebuilt: dirt painted in
    the style of the reference dirt (colours measured on it), hole 6's cut-off front rim from
    another hole's front rim at the same ring coordinates; one Poisson solve merges it all with
    the untouched reference pixels
  * the bezel shading on the outer 4-5 columns is replaced by mirrored neighbours, and PAD_SIDE
    columns are added on both sides (only seen on screens wider than the reference)

Input:  _work/lvl_bg_hud.npy (lvl_hud.py), _work/lvl_front_edges.json (lvl_holes.py)
Output: app-assets/level/bg.png, app-assets/level/fg_bottom.png, _work/lvl_ground.json
"""
import json
import numpy as np, cv2
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from PIL import Image
from paths import work, asset_dir
from common import save_rgba
from lvl_geom import VALID_H, load, ell_d, ring_coords, ring_point

bg = np.load(work('lvl_bg_hud.npy')).astype(np.float64)
H0, W = bg.shape[:2]
PB = 400               # extra rows (enough for ~2.5:1 screens)
PAD_SIDE = 32
FG_EXT = 10            # rows the foreground continues below the reference, to always reach the screen edge
HOLES, CHARS, M = load()
OPEN = json.load(open(work('lvl_front_edges.json')))['opening']
rng = np.random.default_rng(11)
HH = VALID_H + PB
OUT = asset_dir('level')

# ---------------------------------------------------------------- 0. bezel shading at the sides
bg[:, 0:4] = bg[:, 8:4:-1]
bg[:, 617:622] = bg[:, 615:610:-1]
img8 = np.clip(bg, 0, 255).astype(np.uint8)
hsv = cv2.cvtColor(img8, cv2.COLOR_RGB2HSV).astype(int)
Y0, X0 = np.mgrid[0:H0, 0:W].astype(np.float64)
all_chars = np.zeros((H0, W), bool)
for m in M.values():
    all_chars |= m

# ---------------------------------------------------------------- 1. foliage segmentation
FY0 = 930
green = (hsv[..., 0] >= 25) & (hsv[..., 0] <= 100) & (hsv[..., 1] > 60) & (hsv[..., 2] > 40)
purple = (hsv[..., 0] >= 115) & (hsv[..., 0] <= 165) & (hsv[..., 1] > 50)
petal = (hsv[..., 1] < 60) & (hsv[..., 2] > 215)
yellow = (hsv[..., 0] >= 18) & (hsv[..., 0] <= 36) & (hsv[..., 1] > 120) & (hsv[..., 2] > 200)
orange = (hsv[..., 0] >= 8) & (hsv[..., 0] <= 22) & (hsv[..., 1] > 200) & (hsv[..., 2] > 240)
flower = (img8[..., 0].astype(int) > 120) & (img8[..., 2].astype(int) < 25)   # orange/yellow petals, lit or shaded (dirt has B~50)
RIMS = np.zeros((H0, W), bool)   # on the brick rims only green blades can be foliage
for g_ in HOLES.values():
    RIMS |= ell_d((g_['outer'][0], g_['outer'][1], g_['outer'][2] + 4, g_['outer'][3] + 4), X0, Y0) < 1
seed = (green | purple | yellow | flower) & ~(RIMS & ~green)
near_seed = cv2.dilate(seed.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))).astype(bool)
seed |= (petal | orange) & near_seed
seed[:FY0] = False; seed[VALID_H:] = False
seed = cv2.morphologyEx(seed.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
# foliage = the seed components that reach (nearly) the bottom of the picture, plus anything within
# a few px of them (blade tips, petals); lone sprouts on the dirt stay in the background
n, lab, st, _ = cv2.connectedComponentsWithStats(seed.astype(np.uint8), 8)
keep = np.isin(lab, [i for i in range(1, n) if st[i, 1] + st[i, 3] >= VALID_H - 30 and st[i, 4] > 40])
for _ in range(3):
    near = cv2.dilate(keep.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))).astype(bool)
    keep = np.isin(lab, np.unique(lab[near & seed])) & (lab > 0)
fol_seed = keep
# GrabCut for the real outline (leaves have dark shaded parts the colour test misses); the colour
# seed itself is certain foreground -- thin grass blades would vanish if it were eroded
gc = np.full((H0, W), cv2.GC_BGD, np.uint8)
band = cv2.dilate(fol_seed.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))).astype(bool)
band[:FY0] = False; band[VALID_H:] = False
gc[band] = cv2.GC_PR_BGD
gc[cv2.dilate(fol_seed.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & band] = cv2.GC_PR_FGD
gc[fol_seed] = cv2.GC_FGD
dirt_like = (hsv[..., 0] >= 3) & (hsv[..., 0] <= 20) & (hsv[..., 1] > 90) & (hsv[..., 2] < 238) & ~seed & (img8[..., 2] > 30)
gc[dirt_like & band & ~cv2.dilate(fol_seed.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)] = cv2.GC_BGD
gc[RIMS & ~cv2.dilate(green.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)] = cv2.GC_BGD
bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
cv2.grabCut(cv2.cvtColor(img8, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
fol = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD))
n, lab, st, _ = cv2.connectedComponentsWithStats(fol.astype(np.uint8), 8)
fol = np.isin(lab, [i for i in range(1, n) if (fol_seed & (lab == i)).any()])
cnts, _ = cv2.findContours(fol.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
fol = np.zeros((H0, W), np.uint8); cv2.drawContours(fol, cnts, -1, 1, -1); fol = fol.astype(bool)
fol[VALID_H:] = False
fol_alpha = cv2.GaussianBlur(fol.astype(np.float32), (0, 0), 0.7)
fol_alpha = np.where(fol, np.maximum(fol_alpha, 0.5), fol_alpha * 0.8)
print('foliage px', int(fol.sum()))

# foreground sprite: reference pixels (+ FG_EXT rows mirrored below the art)
ys, xs = np.where(fol_alpha > 0.01)
fy0 = int(ys.min()) - 1
rgb = np.concatenate([bg[fy0:VALID_H], bg[VALID_H - 1:VALID_H - 1 - FG_EXT:-1]], 0)    # mirrored below the art
al = np.concatenate([fol_alpha[fy0:VALID_H], fol_alpha[VALID_H - 1:VALID_H - 1 - FG_EXT:-1]], 0)
fg = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), (np.clip(al, 0, 1) * 255).astype(np.uint8)])
save_rgba(OUT + '/fg_bottom.png', fg)

# ---------------------------------------------------------------- 2. dirt, painted for the full height
# The reference dirt is soft cartoon ground: one warm tone with gentle large variations, a few
# slightly darker soft-edged blotches, tiny cracks and pebbles. (Quilting from the little clean
# dirt the photo has repeats visibly.) Colours are measured on the reference.
not_dirt = np.zeros((H0, W), bool)
for h, g in HOLES.items():
    cx, cy, a, b = g['outer']
    not_dirt |= ell_d((cx, cy, a + 10, b + 8), X0, Y0) < 1
not_dirt |= cv2.dilate((green | purple | petal | fol).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
not_dirt |= cv2.dilate(((hsv[..., 1] < 140) & (hsv[..., 2] > 110)).astype(np.uint8), np.ones((21, 21), np.uint8)).astype(bool)
ref_px = bg[1040:VALID_H][~not_dirt[1040:VALID_H]]
base_col = np.median(ref_px, 0)
dark_col = np.median(ref_px[ref_px.sum(1) < np.percentile(ref_px.sum(1), 8)], 0)
print('dirt tone', base_col.round(), 'blotch tone', dark_col.round())


def smooth_noise(sigma, aniso=1.0):
    n_ = rng.normal(0, 1, (HH, W)).astype(np.float32)
    n_ = cv2.GaussianBlur(n_, (0, 0), sigmaX=sigma * aniso, sigmaY=sigma)
    return (n_ - n_.mean()) / (n_.std() + 1e-6)


t = np.clip((np.arange(HH) - VALID_H) / PB, 0, 1)[:, None]
low = smooth_noise(45, 1.6)                                  # broad light/shadow drift
blot = smooth_noise(15, 2.0) + 0.45 * smooth_noise(4, 1.5)   # blotch shapes, wider than tall
blot_a = np.clip((blot - 1.25) / 0.35, 0, 1)                 # a few soft-edged patches (~9%)
blot_a = cv2.GaussianBlur(blot_a.astype(np.float32), (0, 0), 1.4)[..., None]
light_col = base_col * np.array([1.07, 1.10, 1.06])          # sunlit dirt is a little more yellow
lw = np.clip(low, 0, 1)[..., None]
dirt = base_col * (1 + 0.05 * np.minimum(low, 0)[..., None]) * (1 - 0.6 * lw) + light_col * 0.6 * lw
dirt = dirt * (1 - blot_a * 0.5) + dark_col * (blot_a * 0.5)
lit = np.clip(-cv2.Sobel(blot_a[..., 0], cv2.CV_32F, 0, 1, ksize=3), 0, None)   # light lip on the far edge
dirt += cv2.GaussianBlur(lit, (0, 0), 0.8)[..., None] * 5
for _ in range(int(22 * HH / 440)):                          # tiny cracks
    cx_, cy_ = rng.uniform(0, W), rng.uniform(0, HH)
    L = rng.uniform(4, 9) * (1 + 0.4 * t[int(cy_), 0]); ang = rng.uniform(-0.5, 0.5)
    p0 = (int(cx_ - L * np.cos(ang)), int(cy_ - L * np.sin(ang) * 0.4)); p1 = (int(cx_ + L * np.cos(ang)), int(cy_ + L * np.sin(ang) * 0.4))
    m = np.zeros((HH, W), np.float32); cv2.line(m, p0, p1, 1.0, 1, cv2.LINE_AA)
    dirt = dirt * (1 - 0.22 * cv2.GaussianBlur(m, (0, 0), 0.9)[..., None])
dirt += rng.normal(0, 1.6, dirt.shape)                      # grain
dirt *= (1 - 0.10 * t)[..., None]                            # deeper tone towards the viewer
# a few pebbles in the new ground (cut from the reference with their shadow, a little larger)
PEBBLES = [(326, 742, 15, 7), (258, 831, 15, 10), (37, 904, 13, 7), (571, 965, 14, 12)]
placed = []
for _ in range(4):
    for _try in range(80):
        px, py = rng.uniform(25, W - 25), rng.uniform(VALID_H + 40, HH - 20)
        if all(np.hypot(px - qx, (py - qy) * 1.6) > 150 for qx, qy in placed):
            break
    placed.append((px, py))
    x, y, w, h = PEBBLES[rng.integers(len(PEBBLES))]
    m = 5
    patch = bg[y - m:y + h + m + 3, x - m:x + w + m].copy()
    ring = np.concatenate([bg[y - m - 4:y - m, x - m:x + w + m].reshape(-1, 3), bg[y + h + m + 3:y + h + m + 7, x - m:x + w + m].reshape(-1, 3)])
    local = np.median(ring, 0)
    pa = np.clip((np.abs(patch - local).sum(-1) - 14) / 45, 0, 1).astype(np.float32)
    pa[:2] = 0; pa[-2:] = 0; pa[:, :2] = 0; pa[:, -2:] = 0
    pa = cv2.GaussianBlur(pa, (0, 0), 0.8)
    sc = rng.uniform(1.4, 1.8) * (1 + 0.35 * t[int(py), 0])
    patch = cv2.resize(patch.astype(np.float32), None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC).astype(np.float64)
    pa = cv2.resize(pa, (patch.shape[1], patch.shape[0]), interpolation=cv2.INTER_LINEAR)[..., None]
    if rng.random() < 0.5:
        patch, pa = patch[:, ::-1], pa[:, ::-1]
    patch = patch - local + dirt[int(py), int(px)]  # keep the pebble's contrast, adopt the new ground tone
    y0_, x0_ = int(py - patch.shape[0] / 2), int(px - patch.shape[1] / 2)
    ya, yb = max(0, y0_), min(HH, y0_ + patch.shape[0]); xa, xb = max(0, x0_), min(W, x0_ + patch.shape[1])
    if ya < yb and xa < xb:
        pp = patch[ya - y0_:yb - y0_, xa - x0_:xb - x0_]; aa = pa[ya - y0_:yb - y0_, xa - x0_:xb - x0_]
        dirt[ya:yb, xa:xb] = dirt[ya:yb, xa:xb] * (1 - aa) + pp * aa

# ---------------------------------------------------------------- 3. rebuild behind the foliage + below
canvas = np.concatenate([bg[:VALID_H], dirt[VALID_H:]], 0)
YY, XX = np.mgrid[0:HH, 0:W].astype(np.float64)
R = np.zeros((HH, W), bool)
R[:VALID_H] = cv2.dilate(fol.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)[:VALID_H]
R[VALID_H:] = True
S = dirt.copy()                                   # guidance: painted dirt ...
report = {}
hidden = np.zeros((HH, W), bool); hidden[:VALID_H] = R[:VALID_H]
bad_src = all_chars | hidden[:H0]


def sample(img, mx, my):
    return np.stack([cv2.remap(img[..., c].astype(np.float32), mx.astype(np.float32)[None], my.astype(np.float32)[None],
                               cv2.INTER_LINEAR)[0] for c in range(3)], -1).astype(np.float64)


# Hole 6's stored outer ellipse (eyeballed) is right on the upper-left side but ~10 px too low at
# the front, where the photo cuts the rim off. Refitted to the dark line under its front bricks:
FRONT_OUTER = {'h6': [501, 1089.0, 140.4, 62.9]}
for hk, g in HOLES.items():                       # ... and brick rim where a hole's front rim is hidden
    if hk in FRONT_OUTER:
        g = dict(g, outer=FRONT_OUTER[hk])
    rho, th = ring_coords(g, XX, YY)
    inside_open = ell_d(OPEN[hk], XX, YY) < 1
    rim = R & (rho <= 1.08) & ~inside_open & (np.sin(th) > -0.2)
    if not rim.any():
        continue
    # the visible part of this rim just outside the hidden area, to choose the donor by
    vis = (~R) & (rho <= 1.0) & ~inside_open & (np.sin(th) > 0.2) & (YY < VALID_H)
    vis &= cv2.dilate(rim.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
    best = None
    for dk, dg in HOLES.items():
        if dk == hk:
            continue
        for dth in np.linspace(-0.25, 0.25, 11):
            mx, my = ring_point(dg, rho[rim], th[rim] + dth)
            ix, iy = np.round(mx).astype(int), np.round(my).astype(int)
            if (ix < 0).any() or (ix >= W).any() or (iy >= VALID_H - 1).any() or bad_src[np.clip(iy, 0, H0 - 1), ix].any():
                continue
            cost = 0.0
            if vis.sum() >= 20:
                vx, vy = ring_point(dg, rho[vis], th[vis] + dth)
                d = sample(bg, vx, vy) - canvas[vis]
                cost = float(((d - d.mean(0)) ** 2).mean())
            if best is None or cost < best[0]:
                best = (cost, dk, round(float(dth), 3), sample(bg, mx, my))
    if best is None:
        print('no donor rim for', hk)
        continue
    S[rim] = best[3]
    report[hk] = {'rim_donor': best[1], 'rotation': best[2], 'px': int(rim.sum())}
print('rims', report)
# match the guidance to the reference at the bottom edge of the photo (per column, smoothed), fading
# out downwards, so the solve has no step to reproduce there
off = canvas[VALID_H - 2:VALID_H].mean(0) - S[VALID_H:VALID_H + 2].mean(0)
off[R[VALID_H - 1]] = 0                            # foliage above: nothing of the reference kept there
off = cv2.GaussianBlur(off[None].astype(np.float32), (0, 0), sigmaX=12, sigmaY=0.1)[0]
S[VALID_H:] += off[None] * np.exp(-np.arange(PB)[:, None, None] / 25.0)


def poisson_merge(dst, src, mask):
    """lap(f) = lap(src) inside mask (guidance only along edges inside the mask), f = dst outside."""
    ys_, xs_ = np.where(mask)
    idx = -np.ones(mask.shape, np.int64); idx[ys_, xs_] = np.arange(len(ys_))
    n_ = len(ys_)
    rows, cols, vals = [], [], []
    b = np.zeros((n_, 3)); diag = np.zeros(n_)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ny, nx = ys_ + dy, xs_ + dx
        ok = (ny >= 0) & (ny < mask.shape[0]) & (nx >= 0) & (nx < mask.shape[1])
        diag += ok
        nyc, nxc = np.clip(ny, 0, mask.shape[0] - 1), np.clip(nx, 0, mask.shape[1] - 1)
        inside = ok & mask[nyc, nxc]
        b += (src[ys_, xs_] - src[nyc, nxc]) * inside[:, None]
        rows.append(np.where(inside)[0]); cols.append(idx[nyc, nxc][inside]); vals.append(-np.ones(inside.sum()))
        edge = ok & ~mask[nyc, nxc]
        b[edge] += dst[nyc[edge], nxc[edge]]
    A = sp.csr_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [np.arange(n_)]),
                       np.concatenate(cols + [np.arange(n_)]))), shape=(n_, n_))
    solve = spla.factorized(A.tocsc())
    out_ = dst.copy()
    for c in range(3):
        out_[ys_, xs_, c] = solve(b[:, c])
    return out_


canvas = np.clip(poisson_merge(canvas, S, R), 0, 255)

# ---------------------------------------------------------------- 4. side padding
full = cv2.copyMakeBorder(canvas.astype(np.float32), 0, 0, PAD_SIDE, PAD_SIDE, cv2.BORDER_REFLECT_101)
soft = cv2.GaussianBlur(full, (0, 0), 6)
ramp = np.clip((np.abs(np.arange(W + 2 * PAD_SIDE) - (W + 2 * PAD_SIDE - 1) / 2) - (W / 2 - 1)) / PAD_SIDE, 0, 1)
ramp = (ramp ** 0.7)[None, :, None]
full = np.clip(full * (1 - ramp) + soft * ramp, 0, 255).astype(np.uint8)
Image.fromarray(full).save(OUT + '/bg.png', optimize=True)
meta = dict(art_w=W, art_h=VALID_H, pad_side=PAD_SIDE, pad_bottom=PB,
            fg_bottom=dict(x=0, y=fy0, w=int(fg.shape[1]), h=int(fg.shape[0]), rows_below_art=FG_EXT),
            rebuilt_rims=report)
json.dump(meta, open(work('lvl_ground.json'), 'w'), indent=1)


# previews: the reference aspect, and a 20:9 phone (foreground moved down to the screen bottom)
def with_fg(img, shift):
    o = img.copy()
    fa = fg[..., 3:4].astype(np.float32) / 255
    y0_ = fy0 + shift
    y1_ = min(o.shape[0], y0_ + fg.shape[0])
    o[y0_:y1_] = o[y0_:y1_] * (1 - fa[:y1_ - y0_]) + fg[:y1_ - y0_, :, :3] * fa[:y1_ - y0_]
    return o


prev = full[:, PAD_SIDE:PAD_SIDE + W].astype(np.float32)
tall_rows = int(round(W * 20 / 9))
Image.fromarray(np.clip(with_fg(prev, 0)[:1156], 0, 255).astype(np.uint8)).save(work('lvl_view_ref.png'))
Image.fromarray(np.clip(with_fg(prev, tall_rows - VALID_H)[:tall_rows], 0, 255).astype(np.uint8)).save(work('lvl_view_20x9.png'))
print('bg', full.shape, 'fg', fg.shape, 'fg y', fy0)
