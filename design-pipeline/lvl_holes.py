"""Level 1: remove the six characters from the background so every hole is empty.

Second version (the first attempt left jagged back rims on holes 2/5 and green smears where the
antennas were). Everything outside the characters' masks stays the untouched reference pixels;
only the occluded pixels are rebuilt, each kind from its own source:

  * ground/grass behind a head  -> the same rows shifted sideways (continues the horizontal
                                   structure: grass border, dirt), chosen by boundary match
  * back rim behind a body       -> the hole's own front rim, sampled in ring coordinates
                                   (rho, theta) -> (1 - rho, -theta) so bricks keep their
                                   top-surface-then-face order, colour-matched to the visible
                                   back rim
  * hole interior                -> colour profile measured on the visible interior pixels
  * strip under the character    -> the rim a few px lower (character colour bleeds there)

The rebuilt pixels are merged with a Poisson (gradient-domain) solve so the seams vanish.
Also fits the real front edge of each opening (the characters' clip line in-game), which sits
up to 8 px above the stored inner ellipse.

Input:  _work/lvl_base.npy (from lvl_build.py)
Output: _work/lvl_bg_holes.npy, _work/lvl_front_edges.json, preview _work/lvl_bg_holes.png
"""
import json
import numpy as np, cv2
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from PIL import Image
from paths import work

from lvl_geom import VALID_H, load, openings, front_edge_columns
import lvl_geom

base = np.load(work('lvl_base.npy')).astype(np.float64)
H, W = base.shape[:2]
HOLES, CHARS, M = load()
char_of = {v[0]: k for k, v in CHARS.items()}
YY, XX = np.mgrid[0:H, 0:W].astype(np.float64)


# ---------------------------------------------------------------- geometry helpers
def ell_d(e, X=XX, Y=YY):
    return lvl_geom.ell_d(e, X, Y)


def ring_coords(hole, X, Y):
    return lvl_geom.ring_coords(HOLES[hole], X, Y)


def ring_point(hole, rho, th):
    return lvl_geom.ring_point(HOLES[hole], rho, th)


# The opening used from here on (interior, ring inner edge, in-game clip): one ellipse from the
# stored back edge of the opening to the fitted front edge, so both arcs meet at the sides.
import copy
HOLES_STORED = copy.deepcopy(HOLES)
FRONT, OPEN = openings(HOLES, CHARS, M, base)
for h in HOLES:
    HOLES[h]['inner_stored'] = HOLES[h]['inner']
    HOLES[h]['inner'] = OPEN[h]


def front_curve(hole, X):
    cx, cy, a, b = HOLES[hole]['inner']
    return cy + b * np.sqrt(np.clip(1 - ((X - cx) / a) ** 2, 0, 1))


def ell_polar(hole, X, Y):
    """q: 0 at the centre, 1 on the opening edge, 2 on the outer rim edge (1+rho beyond);
    phi: ellipse angle. Rings of constant q follow the hole's perspective."""
    ci, co = HOLES[hole]['inner'], HOLES[hole]['outer']
    d = np.sqrt(ell_d(ci, X, Y))
    rho, th = ring_coords(hole, X, Y)
    q = np.where(d < 1, d, 1 + rho)
    phi = np.where(d < 1, np.arctan2((Y - ci[1]) / ci[3], (X - ci[0]) / ci[2]), th)
    return q, phi


def ell_point(hole, q, phi):
    ci, co = HOLES[hole]['inner'], HOLES[hole]['outer']
    inside = q < 1
    r = np.clip(q - 1, 0, None)
    cx = np.where(inside, ci[0], ci[0] + (co[0] - ci[0]) * r)
    cy = np.where(inside, ci[1], ci[1] + (co[1] - ci[1]) * r)
    a = np.where(inside, ci[2] * q, ci[2] + (co[2] - ci[2]) * r)
    b = np.where(inside, ci[3] * q, ci[3] + (co[3] - ci[3]) * r)
    return cx + a * np.cos(phi), cy + b * np.sin(phi)


def arc_mirror_fill(img, hole, fill, visible, qmin, qmax, fade=0.35):
    """Fill `fill` pixels of the hole's back half by continuing the visible pixels at the same q
    around the ellipse from both sides (mirrored at the occlusion edges, cross-faded)."""
    ys, xs = np.where(fill)
    q, phi = ell_polar(hole, xs.astype(float), ys.astype(float))
    NPHI = 2048
    grid_phi = np.linspace(-np.pi, np.pi, NPHI, endpoint=False)
    qb = np.clip(((q - qmin) / (qmax - qmin) * 256).astype(int), 0, 255)
    qc = qmin + (np.arange(256) + 0.5) / 256 * (qmax - qmin)
    vis_tab = np.zeros((256, NPHI), bool)
    for i in range(256):
        px, py = ell_point(hole, np.full(NPHI, qc[i]), grid_phi)
        ix, iy = np.round(px).astype(int), np.round(py).astype(int)
        inb = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < VALID_H)
        vis_tab[i] = inb & visible[np.clip(iy, 0, H - 1), np.clip(ix, 0, W - 1)]
    res = np.zeros((len(ys), 3)); ok = np.zeros(len(ys), bool)
    src = img.astype(np.float32)
    k = np.round((phi + np.pi) / (2 * np.pi) * NPHI).astype(int) % NPHI
    for i in np.unique(qb):
        sel = np.where(qb == i)[0]
        v = vis_tab[i]
        if not v.any():
            continue
        # nearest visible phi on each side (circular)
        idx = np.arange(NPHI)
        vi = idx[v]
        for j in sel:
            kk = k[j]
            dl = (kk - vi) % NPHI; dr = (vi - kk) % NPHI
            L = vi[np.argmin(dl)]; R = vi[np.argmin(dr)]
            gap = (R - L) % NPHI
            if gap == 0:
                continue
            u = ((kk - L) % NPHI) / gap
            sl = (L - ((kk - L) % NPHI)) % NPHI      # mirror across the left edge
            sr = (R + ((R - kk) % NPHI)) % NPHI      # mirror across the right edge
            if not v[sl]: sl = L
            if not v[sr]: sr = R
            pts = ell_point(hole, np.array([q[j], q[j]]), grid_phi[[sl, sr]])
            cl = cv2.getRectSubPix(src, (1, 1), (float(pts[0][0]), float(pts[1][0])))[0, 0]
            cr = cv2.getRectSubPix(src, (1, 1), (float(pts[0][1]), float(pts[1][1])))[0, 0]
            w = np.clip((u - 0.5) / fade + 0.5, 0, 1); w = w * w * (3 - 2 * w)
            res[j] = cl * (1 - w) + cr * w; ok[j] = True
    return ys[ok], xs[ok], res[ok]


# ---------------------------------------------------------------- masks
all_chars = np.zeros((H, W), bool)
for k in CHARS:
    all_chars |= M[k]
occl = cv2.dilate(all_chars.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
# every hole ring (+ margin): never use these as a sideways source for ground
rings = np.zeros((H, W), bool)
for h, g in HOLES.items():
    cx, cy, a, b = g['outer']
    rings |= ell_d((cx, cy, a + 8, b + 6)) < 1


# ---------------------------------------------------------------- Poisson merge
def poisson_merge(dst, src, mask):
    """Solve lap(f) = lap(src) inside mask with f = dst on the boundary."""
    ys, xs = np.where(mask)
    idx = -np.ones(mask.shape, np.int64); idx[ys, xs] = np.arange(len(ys))
    n = len(ys)
    rows, cols, vals = [], [], []
    b = np.zeros((n, 3))
    diag = np.zeros(n)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ny, nx = ys + dy, xs + dx
        ok = (ny >= 0) & (ny < mask.shape[0]) & (nx >= 0) & (nx < mask.shape[1])
        diag += ok
        nyc, nxc = np.clip(ny, 0, mask.shape[0] - 1), np.clip(nx, 0, mask.shape[1] - 1)
        inside = ok & mask[nyc, nxc]
        # guidance only along edges inside the mask: across the boundary `src` is not the
        # rebuilt content any more, and its jump there is exactly the seam to be removed
        b += (src[ys, xs] - src[nyc, nxc]) * inside[:, None]
        rows.append(np.where(inside)[0]); cols.append(idx[nyc, nxc][inside]); vals.append(-np.ones(inside.sum()))
        edge = ok & ~mask[nyc, nxc]
        b[edge] += dst[nyc[edge], nxc[edge]]
    A = sp.csr_matrix((np.concatenate(vals + [diag]),
                       (np.concatenate(rows + [np.arange(n)]), np.concatenate(cols + [np.arange(n)]))), shape=(n, n))
    solve = spla.factorized(A.tocsc())
    out = dst.copy()
    for c in range(3):
        out[ys, xs, c] = solve(b[:, c])
    return out


# ---------------------------------------------------------------- interior colour profile
def interior_t(hole, X, Y):
    cx, cy, a, b = HOLES[hole]['inner']
    top = cy - b * np.sqrt(np.clip(1 - ((X - cx) / a) ** 2, 0, 1))
    bot = front_curve(hole, X)
    return np.clip((Y - top) / np.maximum(bot - top, 1), 0, 1), np.clip(np.abs(X - cx) / a, 0, 1)


TB, SB = 12, 4
prof = np.zeros((TB, SB, 3)); pc = np.zeros((TB, SB))
for h in HOLES:
    inner = ell_d(HOLES[h]['inner']) < 0.9
    vis = inner & ~occl & (YY < front_curve(h, XX) - 1.5) & (YY < VALID_H)
    t, s = interior_t(h, XX[vis], YY[vis])
    ti = np.minimum((t * TB).astype(int), TB - 1); si = np.minimum((s * SB).astype(int), SB - 1)
    np.add.at(prof, (ti, si), base[vis]); np.add.at(pc, (ti, si), 1)
filled = pc >= 20
prof = prof / np.maximum(pc, 1)[..., None]
fi, fj = np.where(filled)
for i in range(TB):  # sparse bins (sides of the opening): nearest filled bin, same depth preferred
    for j in range(SB):
        if not filled[i, j]:
            k = np.argmin(np.abs(fi - i) * 3 + np.abs(fj - j))
            prof[i, j] = prof[fi[k], fj[k]]
prof_img = cv2.resize(prof.astype(np.float32), (SB * 8, TB * 8), interpolation=cv2.INTER_LINEAR)


def interior_colour(hole, X, Y):
    t, s = interior_t(hole, X, Y)
    px = np.clip(s * SB * 8 - 0.5, 0, SB * 8 - 1).astype(np.float32)
    py = np.clip(t * TB * 8 - 0.5, 0, TB * 8 - 1).astype(np.float32)
    return cv2.remap(prof_img, px, py, cv2.INTER_LINEAR)


# ---------------------------------------------------------------- exemplar (Criminisi) fill
SRC_OK = ~occl & ~rings & (YY < VALID_H) & (YY > 420)
PS, VS, HS = 13, 8, 220   # patch size; search window: +-VS rows (keeps the grass border height), +-HS columns
_hsv = cv2.cvtColor(np.clip(base, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(int)
GREEN = ((_hsv[..., 0] >= 30) & (_hsv[..., 0] <= 95) & (_hsv[..., 1] > 60)).astype(np.float32)
# small features on the dirt that must not be smeared sideways: sprouts (yellow-green..green) and
# sparkles (bright, unsaturated); slightly dilated to catch their soft edges
FEATURE = cv2.dilate((((_hsv[..., 0] >= 24) & (_hsv[..., 0] <= 95) & (_hsv[..., 1] > 50))
                      | ((_hsv[..., 2] > 200) & (_hsv[..., 1] < 90))).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
BED_Y = 632  # below this row the field is dirt; above it the flower bed along the fence


def exemplar_fill(img, mask):
    """Fill `mask` in `img` (float RGB) patch by patch, copying only from SRC_OK pixels."""
    R = PS // 2
    P = R + 1
    im = cv2.copyMakeBorder(img.astype(np.float32), P, P, P, P, cv2.BORDER_REFLECT)
    todo = cv2.copyMakeBorder(mask.astype(np.uint8), P, P, P, P, cv2.BORDER_CONSTANT, value=0).astype(bool)
    ok = cv2.copyMakeBorder((SRC_OK & ~mask).astype(np.uint8), P, P, P, P, cv2.BORDER_CONSTANT, value=0)
    cand = cv2.erode(ok, np.ones((PS, PS), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    conf = (~todo).astype(np.float32)
    green = cv2.copyMakeBorder(GREEN, P, P, P, P, cv2.BORDER_CONSTANT, value=0)
    green_patch = cv2.boxFilter(green, -1, (PS, PS), normalize=True)
    ys, xs = np.where(todo)
    by0, by1, bx0, bx1 = ys.min() - PS, ys.max() + PS + 1, xs.min() - PS, xs.max() + PS + 1
    k3 = np.ones((3, 3), np.uint8)
    while todo.any():
        t = todo[by0:by1, bx0:bx1]
        front = t & cv2.dilate((~t).astype(np.uint8), k3).astype(bool)
        c = cv2.boxFilter(conf[by0:by1, bx0:bx1], -1, (PS, PS), normalize=True)
        # data term: isophote strength across the front (normalised convolution of the known image)
        known = (~t).astype(np.float32)
        g = cv2.cvtColor(im[by0:by1, bx0:bx1], cv2.COLOR_RGB2GRAY) * known
        gb = cv2.GaussianBlur(g, (0, 0), 1.2) / np.maximum(cv2.GaussianBlur(known, (0, 0), 1.2), 1e-3)
        gx, gy = cv2.Sobel(gb, cv2.CV_32F, 1, 0), cv2.Sobel(gb, cv2.CV_32F, 0, 1)
        nx, ny = cv2.Sobel(t.astype(np.float32), cv2.CV_32F, 1, 0), cv2.Sobel(t.astype(np.float32), cv2.CV_32F, 0, 1)
        nn = np.sqrt(nx ** 2 + ny ** 2) + 1e-6
        d = np.abs(-gy * nx / nn + gx * ny / nn) / 255.0
        pr = np.where(front, c * (d + 0.05), -1)
        py, px = np.unravel_index(np.argmax(pr), pr.shape)
        py += by0; px += bx0
        tpl = im[py - R:py + R + 1, px - R:px + R + 1]
        kn = (~todo[py - R:py + R + 1, px - R:px + R + 1]).astype(np.float32)
        sy0, sy1 = max(R, py - VS), min(im.shape[0] - R - 1, py + VS)
        sx0, sx1 = max(R, px - HS), min(im.shape[1] - R - 1, px + HS)
        region = im[sy0 - R:sy1 + R + 1, sx0 - R:sx1 + R + 1]
        res = cv2.matchTemplate(region, tpl, cv2.TM_SQDIFF, mask=np.dstack([kn] * 3))
        res = res / max(kn.sum(), 1)
        oky = cand[sy0:sy1 + 1, sx0:sx1 + 1]
        # slight preference for nearby sources (lighting drifts across the field)
        dy_, dx_ = np.mgrid[sy0:sy1 + 1, sx0:sx1 + 1]
        res = res + 0.02 * np.hypot(dy_ - py, (dx_ - px) * 0.5)
        # never bring more grass into a patch than its known part already shows
        g_known = float((green[py - R:py + R + 1, px - R:px + R + 1] * kn).sum() / max(kn.sum(), 1))
        res = res + 4000.0 * np.maximum(green_patch[sy0:sy1 + 1, sx0:sx1 + 1] - g_known - 0.05, 0)
        res[~oky] = np.inf
        if not np.isfinite(res).any():
            raise RuntimeError(f'no source patch for ({py - P}, {px - P})')
        qy, qx = np.unravel_index(np.argmin(res), res.shape)
        qy += sy0; qx += sx0
        sl = (slice(py - R, py + R + 1), slice(px - R, px + R + 1))
        fill = todo[sl]
        im[sl][fill] = im[qy - R:qy + R + 1, qx - R:qx + R + 1][fill]
        conf[sl][fill] = c[py - by0, px - bx0]
        todo[sl][fill] = False
    return im[P:-P, P:-P].astype(np.float64)


def row_mirror_fill(img, mask, fade=0.35, taps=1, step=4, far=15):
    """Fill each horizontal run of `mask` with its left and right neighbours mirrored inward,
    cross-faded over the middle `fade` of the run. Each side is the median of `taps` samples
    `step` px apart, so single small features (a sprout, a sparkle, a flower) are not smeared
    into streaks. Blocked sources are skipped outward; pixels whose nearest clean source on both
    sides is more than `far` px from the run are returned in `membrane` for a smooth fill."""
    o = img.copy()
    membrane = np.zeros(mask.shape, bool)
    bad = mask | blocked | RINGS_ANY | (YY >= VALID_H) | FEATURE  # no sprouts/sparkles smeared over the dirt
    for y in np.unique(np.where(mask)[0]):
        xs = np.where(mask[y])[0]
        ok = ~bad[y]
        for r in np.split(xs, np.where(np.diff(xs) > 1)[0] + 1):
            xl, xr = r[0], r[-1]
            span = 3 * len(r) + 60 + taps * step
            left = [x for x in range(xl - 1, max(-1, xl - 1 - span), -1) if ok[x]]
            right = [x for x in range(xr + 1, min(W, xr + 1 + span)) if ok[x]]
            lfar = not left or (xl - left[0]) > far
            rfar = not right or (right[0] - xr) > far
            if lfar and rfar:
                membrane[y, r] = True
                continue

            def side(seq, i):
                if not seq:
                    return None
                idx = [min(i + t * step, len(seq) - 1) for t in range(taps)]
                return np.median(img[y, [seq[j] for j in idx]], axis=0)
            for i, x in enumerate(r):
                cl = None if lfar else side(left, i)
                cr = None if rfar else side(right, len(r) - 1 - i)
                if cl is None or cr is None:
                    o[y, x] = cr if cl is None else cl
                    continue
                u = (i + 0.5) / len(r)
                w = np.clip((u - 0.5) / fade + 0.5, 0, 1)
                w = w * w * (3 - 2 * w)
                o[y, x] = cl * (1 - w) + cr * w
    return o, membrane


# ---------------------------------------------------------------- per hole
out = base.copy()
rng = np.random.default_rng(3)
REBUILT = np.zeros((H, W), bool)
report = {h: {} for h in HOLES}
RHO = {h: ring_coords(h, XX, YY) for h in HOLES}
RING = {h: (RHO[h][0] <= 1.1) & (ell_d(HOLES[h]['inner']) >= 1) & (YY < VALID_H) for h in HOLES}
RINGS_ANY = np.zeros((H, W), bool)
for _h in HOLES:
    RINGS_ANY |= RING[_h] | (ell_d(HOLES[_h]['inner']) < 1)
blocked = cv2.dilate(all_chars.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
GLOW_ANY = cv2.dilate(all_chars.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))).astype(bool)
CONTAM = cv2.dilate(all_chars.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))).astype(bool)


def bbox(mask, pad):
    ys, xs = np.where(mask)
    return max(0, ys.min() - pad), min(H, ys.max() + pad + 1), max(0, xs.min() - pad), min(W, xs.max() + pad + 1)


# 0. front rims hidden by *another* hole's character (h2 by c4, h5 by c6): the same ring rotated
#    by the angle whose surroundings match best. Done first: the back rims are mirrored from them.
def repair_rims(out):
    for h in HOLES:
        occ = RING[h] & np.zeros((H, W), bool)
        for k, (hk, _, _) in CHARS.items():
            if hk != h:
                occ |= RING[h] & cv2.dilate(M[k].astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))).astype(bool)  # + glow
        if not occ.any():
            continue
        y0, y1, x0, x1 = bbox(occ, 10)
        o = occ[y0:y1, x0:x1]
        rho, th = RHO[h][0][y0:y1, x0:x1], RHO[h][1][y0:y1, x0:x1]
        band = cv2.dilate(o.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & ~o & RING[h][y0:y1, x0:x1]
        src = out.astype(np.float32)
        cands = [('rot %+.2f' % d, h, rho, th + d) for d in np.concatenate([np.linspace(-0.5, -0.1, 21), np.linspace(0.1, 0.5, 21)])]
        cands.append(('mirror', h, rho, np.pi - th))
        cands += [('donor %s %+.2f' % (d, dd), d, rho, th + dd) for d in HOLES if d != h
                  for dd in np.linspace(-0.3, 0.3, 25)]
        best = None
        for name, dh, rr, tt in cands:
            mx, my = ring_point(dh, rr, tt)
            ix, iy = np.clip(np.round(mx).astype(int), 0, W - 1), np.clip(np.round(my).astype(int), 0, H - 1)
            if all_chars[iy[o], ix[o]].any() or blocked[iy[o], ix[o]].mean() > 0.03:
                continue
            if ((my[o] > VALID_H - 2) | (mx[o] < 0) | (mx[o] > W - 1)).any():
                continue
            cmp_ = band & ~blocked[iy, ix]
            if cmp_.sum() < 30:
                continue
            samp = cv2.remap(src, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR)
            # compare after removing the mean colour difference (Poisson absorbs that anyway)
            dif = samp[cmp_] - out[y0:y1, x0:x1][cmp_]
            cost = float(((dif - dif.mean(0)) ** 2).mean())
            if best is None or cost < best[0]:
                best = (cost, name, samp)
        report[h]['front_rim_source'] = best[1]
        S = out[y0:y1, x0:x1].copy()
        S[o] = best[2][o]
        out[y0:y1, x0:x1] = poisson_merge(out[y0:y1, x0:x1], S, o)
        REBUILT[y0:y1, x0:x1] |= o

    return out


out = repair_rims(out)
for h in sorted(HOLES, key=lambda k: HOLES[k]['inner'][1]):
    ck = char_of[h]
    ci, co = HOLES[h]['inner'], HOLES[h]['outer']
    F = cv2.dilate(M[ck].astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
    # plus the 1-2 px of character colour between the mask bottom and the real front edge
    fcx = front_curve(h, XX)
    char_cols = np.zeros(W, bool)
    for x in range(W):
        ys_ = np.where(M[ck][:, x])[0]
        char_cols[x] = len(ys_) > 0 and ys_.max() > (front_curve(h, np.array([float(x)]))[0] - 6)
    F |= char_cols[None, :] & (np.abs(XX - ci[0]) < ci[2]) & (YY < fcx + 2.5) & (YY > fcx - 4)
    # the character's glow tints the visible dark interior next to it: rebuild that too
    near = cv2.dilate(M[ck].astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))).astype(bool)
    F |= near & (ell_d(ci) < 1)                                        # opening
    F |= near & (ell_d(co) < 1) & (YY < ci[1])                         # back half of the rim
    F &= YY < VALID_H
    for k in HOLES:
        if k != h:
            F &= ~RING[k]  # already repaired above
    y0, y1, x0, x1 = bbox(F, 12)
    X, Y = XX[y0:y1, x0:x1], YY[y0:y1, x0:x1]
    f = F[y0:y1, x0:x1]
    S = out[y0:y1, x0:x1].copy()
    rho, th = RHO[h][0][y0:y1, x0:x1], RHO[h][1][y0:y1, x0:x1]
    fc = front_curve(h, X)
    in_open = (ell_d(ci, X, Y) < 1) & (Y < fc)
    in_ring = (rho <= 1.06) & ~in_open
    back = in_ring & (np.sin(th) < 0.12) & (Y < fc)
    under = f & ~in_open & (Y >= fc - 0.5) & (np.abs(X - ci[0]) < ci[2]) & (np.sin(th) >= 0.12)
    # the outline/glow of the head reaches a little further over the ground and the back rim:
    # take 2 more px there (not on the front rim, where the character ends at the opening)
    wide = cv2.dilate(M[ck].astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))).astype(bool)[y0:y1, x0:x1]
    extra = wide & ~f & ~in_open & (Y < VALID_H) & ((np.sin(th) < 0.12) | ~in_ring)
    for k in HOLES:
        if k != h:
            extra &= ~RING[k][y0:y1, x0:x1]
    f = f | extra
    back = back & f
    ground = f & ~in_open & ~in_ring & ~under

    # 1. ground/grass behind the head: each row continues from both sides (mirrored), which keeps
    #    the horizontal structure of the field (grass border, dirt bands) at the right height
    membrane = np.zeros(f.shape, bool)
    # rows of the hidden area whose visible neighbours (left/right) are flower bed, not dirt
    bed = np.zeros_like(ground)
    for yy_ in np.unique(np.where(ground & (Y < BED_Y + 4))[0]):
        xs_ = np.where(ground[yy_])[0]
        nb = [x0 + xs_.min() - k for k in range(3, 12)] + [x0 + xs_.max() + k for k in range(3, 12)]
        nb = [x for x in nb if 0 <= x < W]
        if nb and GREEN[yy_ + y0, nb].mean() >= 0.2:
            bed[yy_] = ground[yy_]
    dirt = ground & ~bed
    if bed.any():
        # the head reaches into the flower bed (holes 1, 2): one sideways-shifted block of the bed
        # (a horizontal band, so it lines up) keeps the flowers whole
        gy, gx = np.where(bed)
        bw = gx.max() - gx.min() + 1
        ring_b = cv2.dilate(bed.astype(np.uint8), np.ones((11, 11), np.uint8)).astype(bool) & ~f & (Y < BED_Y + 4)
        by, bx = np.where(ring_b)
        best = None
        for dx in [sg * d for d in range(bw + 4, bw + 200, 2) for sg in (-1, 1)]:
            sx, sbx = gx + x0 + dx, bx + x0 + dx
            if min(sx.min(), sbx.min()) < 0 or max(sx.max(), sbx.max()) >= W:
                continue
            if (GLOW_ANY | RINGS_ANY)[gy + y0, sx].any():
                continue
            cost = float(((out[by + y0, sbx] - out[by + y0, bx + x0]) ** 2).mean())
            if best is None or cost < best[0]:
                best = (cost, dx)
        if best is None:
            dirt = ground
        else:
            report[h]['bed_shift'] = best[1]
            S[bed] = out[gy + y0, gx + x0 + best[1]]
    if dirt.any():
        gmask = np.zeros((H, W), bool); gmask[y0:y1, x0:x1] = dirt
        filled, memb = row_mirror_fill(out, gmask)
        S[dirt] = filled[y0:y1, x0:x1][dirt]
        membrane = memb[y0:y1, x0:x1]

    # 2. interior from the measured profile (+ faint grain) ...
    col = interior_colour(h, X, Y).astype(np.float64)
    col += rng.normal(0, 1.2, col.shape) * (col.mean(-1, keepdims=True) > 12)
    io = f & in_open
    S[io] = col[io]

    # 3. ... then the back rim and the lit back wall under it continue around the ellipse from the
    #    visible back sides (same q = same place on the rim/wall, perspective kept)
    qq, pp = ell_polar(h, X, Y)
    arc = f & (qq >= 0.55) & (qq <= 2.08) & (np.sin(pp) < 0.25) & (Y < fc)
    Fg = np.zeros((H, W), bool); Fg[y0:y1, x0:x1] = f
    visible = ~CONTAM & ~Fg
    for k in HOLES:
        if k != h:
            visible |= RING[k]  # already repaired
    am = np.zeros((H, W), bool); am[y0:y1, x0:x1] = arc
    ay, ax, av = arc_mirror_fill(out, h, am, visible & ~am, 0.55, 2.08)
    # blend from profile (deep) to arc fill (upper wall and rim)
    qa = qq[ay - y0, ax - x0]
    sa = np.sin(pp[ay - y0, ax - x0])
    wa = (np.clip((qa - 0.6) / 0.3, 0, 1) * np.clip((0.25 - sa) / 0.35, 0, 1))
    wa = (wa * wa * (3 - 2 * wa))[:, None]
    S[ay - y0, ax - x0] = S[ay - y0, ax - x0] * (1 - wa) + av * wa

    # 4. strip under the character on the front rim: rim pixels 3 px lower
    if under.any():
        uy, ux = np.where(under)
        sy = np.ceil(fc[uy, ux] + 4).astype(int)
        S[uy, ux] = out[np.minimum(sy, VALID_H - 1), ux + x0]

    # soft shadow where the rebuilt back rim meets the opening
    edge_w = np.clip(1.5 - (np.sqrt(ell_d(ci, X, Y)) - 1) * max(ci[2], ci[3]), 0, 1) * (Y < fc + 0.5) * f * ~in_open
    S = S * (1 - edge_w[..., None] * 0.5) + col * (edge_w[..., None] * 0.5)

    out[y0:y1, x0:x1] = poisson_merge(out[y0:y1, x0:x1], S, f)
    REBUILT[y0:y1, x0:x1] |= f
    if membrane.any():  # narrow gaps with no clean source nearby: smooth fill from all around
        reg = out[y0:y1, x0:x1]
        out[y0:y1, x0:x1] = poisson_merge(reg, np.zeros_like(reg), membrane)
        report[h]['membrane_px'] = int(membrane.sum())
    # the characters glow softly (up to +12 L, fading over ~12 px): on the dirt around the head,
    # keep only the fine texture and take the low frequencies from a boundary outside the glow
    others = np.zeros((H, W), bool)
    for k in CHARS:
        if k != ck:
            others |= cv2.dilate(M[k].astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    glow = (cv2.dilate(M[ck].astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))).astype(bool)
            & ~RINGS_ANY & ~others & (YY >= BED_Y) & (YY < VALID_H - 2))
    glow[y0:y1, x0:x1] &= ~(f & ~ground) | dirt  # rim/interior pixels stay as merged
    if glow.any():
        gy0, gy1, gx0, gx1 = bbox(glow, 3)
        reg = out[gy0:gy1, gx0:gx1]
        g = glow[gy0:gy1, gx0:gx1]
        hp = reg - cv2.GaussianBlur(reg.astype(np.float32), (0, 0), 3.0).astype(np.float64)
        out[gy0:gy1, gx0:gx1] = poisson_merge(reg, hp, g)

# rims hidden by another character once more, now that the surroundings are clean (the first
# pass blended against that character's own pixels)
out = repair_rims(out)

# safety net: character colour that leaked into the field or a rim through some source or blend
# boundary (pink/red/yellow/green glow). Flag pixels near a character whose hue is not the field's
# orange-brown -- unless the reference itself has that colour there (sprouts, flowers) -- and
# re-solve them keeping only their fine texture, low frequencies from the clean surroundings.
def off_palette(img):
    hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(int)
    return (((hsv[..., 0] < 4) | (hsv[..., 0] > 24)) & (hsv[..., 1] > 70) & (hsv[..., 2] > 90)) \
        | ((img[..., 2] < 18) & (img[..., 0] > 120) & (hsv[..., 2] > 90))


near_chars = cv2.dilate(all_chars.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))).astype(bool)
real_feature = off_palette(base) & ~blocked
leak = near_chars & off_palette(out) & ~real_feature & (YY >= BED_Y) & (YY < VALID_H - 1)
leak = cv2.dilate(leak.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))).astype(bool) & (YY < VALID_H - 1)
leak &= ~(real_feature & ~cv2.dilate(off_palette(out).astype(np.uint8) & ~real_feature, np.ones((3, 3), np.uint8)).astype(bool))
n_lab, lab = cv2.connectedComponents(leak.astype(np.uint8))
for i in range(1, n_lab):
    comp = lab == i
    ly0, ly1, lx0, lx1 = bbox(comp, 3)
    reg = out[ly0:ly1, lx0:lx1]
    hp = reg - cv2.GaussianBlur(reg.astype(np.float32), (0, 0), 2.0).astype(np.float64)
    out[ly0:ly1, lx0:lx1] = poisson_merge(reg, hp, comp[ly0:ly1, lx0:lx1])
report['leak_px'] = int(leak.sum())

# The front rim is bumpy: the brick tops rise above the smooth opening ellipse the rebuild above
# used. Where a character's body met the rim, put the reference's own rim pixels back below the
# measured edge (they are exactly what the player sees under a character), so that an empty
# hole's rim and the in-game clip line are the same line.
_hb = cv2.cvtColor(np.clip(base, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(int)
CHAR_COLOUR = (((_hb[..., 0] >= 35) & (_hb[..., 0] <= 95) & (_hb[..., 1] > 60) & (_hb[..., 2] > 30))      # green, lit or shaded
               | (((_hb[..., 0] <= 5) | (_hb[..., 0] >= 160)) & (_hb[..., 1] > 120) & (_hb[..., 2] > 90))  # red
               | ((_hb[..., 0] >= 22) & (_hb[..., 0] <= 36) & (_hb[..., 1] > 80) & (_hb[..., 2] > 170)))   # yellow
EDGES = {}
for h in HOLES:
    e = front_edge_columns(h, HOLES_STORED, CHARS, M, base, HOLES[h]['inner'])
    EDGES[h] = e
    ck = char_of[h]
    near_other = np.zeros((H, W), bool)
    for k in CHARS:
        if k != ck:
            near_other |= cv2.dilate(M[k].astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    restored = 0
    done_cols, gap_cols = [], []
    for i, (yb, wv) in enumerate(zip(e['y'], e['w'])):
        x = e['x0'] + i
        if wv < 1 or not 0 <= x < W:
            continue
        y_in = int(np.ceil(yb))
        y_end = min(VALID_H - 1, int(front_curve(h, np.array([float(x)]))[0]) + 8)
        hit = np.flatnonzero(near_other[y_in:y_end + 1, x])
        if len(hit):
            y_end = y_in + hit[0] - 1          # stop where another character (in front) begins
        if y_in + 2 > y_end:
            gap_cols.append((x, yb))
            continue
        cover = y_in - yb                                   # rim share of the straddling pixel
        out[y_in, x] = base[y_in + 1, x]                    # first full row: can hold body colour, skip it
        out[y_in + 1:y_end + 1, x] = base[y_in + 1:y_end + 1, x]
        if y_in - 1 >= 0:
            out[y_in - 1, x] = out[y_in - 1, x] * (1 - cover) + base[y_in + 1, x] * cover
        # the V of a brick joint dips below the smoothed edge: body colour left there -> brick below
        for y in range(max(0, y_in - 1), min(VALID_H - 1, y_in + 6)):
            if CHAR_COLOUR[y, x]:
                y2 = y + 1
                while y2 < min(VALID_H - 1, y + 10) and CHAR_COLOUR[y2, x]:
                    y2 += 1
                out[y, x] = base[y2, x]
        restored += 1
        done_cols.append((x, yb))
    # columns right above another character: carry the brick-top rows across from the nearest
    # restored columns on both sides (only over what is still dark interior)
    for x, yb in gap_cols:
        left = [c for c in done_cols if c[0] < x]
        right = [c for c in done_cols if c[0] > x]
        if not left or not right:
            continue
        (xl, yl), (xr, yr) = left[-1], right[0]
        if xr - xl > 40:
            continue
        u = (x - xl) / (xr - xl)
        y_in = int(np.ceil(yb))
        for dy in range(0, 9):
            y = y_in + dy
            if y >= VALID_H or near_other[y, x]:
                break
            src = out[int(np.ceil(yl)) + dy, xl] * (1 - u) + out[int(np.ceil(yr)) + dy, xr] * u
            if out[y, x].sum() < 240:          # interior, not rim
                out[y, x] = src
    report[h]['rim_top_columns_restored'] = restored
    report[h]['rim_top_columns_bridged'] = len(gap_cols)
out = np.clip(out, 0, 255)
np.save(work('lvl_bg_holes.npy'), out.astype(np.uint8))
json.dump({'opening': {h: HOLES[h]['inner'] for h in HOLES}, 'front_fit': FRONT, 'edge': EDGES, 'report': report}, open(work('lvl_front_edges.json'), 'w'), indent=1)
Image.fromarray(out.astype(np.uint8)).save(work('lvl_bg_holes.png'))
print(json.dumps(report))
print('openings', {h: HOLES[h]['inner'] for h in HOLES})
