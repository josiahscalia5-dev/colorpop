"""Shared image operations for the screens of the second reference sheet (reference/screens/*.png).

A screen's picture I is split into a background B (the scene with every moving / live element
removed) and sprites cut from I. Everything removed is re-drawable, so drawing B plus every sprite
at its home position gives back I; the reconstructed parts of B only show once things move.

  * sprites: RGBA cut with a (feathered) mask straight from I; glows around them are a separate
    additive layer G = max(I - B, 0) so they light whatever lies beneath wherever they are drawn
  * holes: an ellipse for the opening and one for the outside of the brick rim; hidden rim/interior
    parts are rebuilt from a donor hole in ring coordinates (rho 0 = opening edge, 1 = outer edge)
  * other hidden parts: exemplar (patch) fill from nearby clean pixels, then a Poisson merge
"""
import os
import json
import numpy as np, cv2
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from PIL import Image
from paths import ROOT

REF_DIR = os.path.join(ROOT, 'reference', 'screens')


def load_ref(name):
    return np.asarray(Image.open(os.path.join(REF_DIR, name + '.png')).convert('RGB')).astype(np.float64)


def save_png(path, arr):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(path, optimize=True)


# ---------------------------------------------------------------- masks
def grid(shape):
    H, W = shape[:2]
    return np.mgrid[0:H, 0:W].astype(np.float64)


def ell_d(e, X, Y):
    cx, cy, a, b = e[:4]
    return ((X - cx) / a) ** 2 + ((Y - cy) / b) ** 2


def ellipse_mask(shape, e, grow=0.0):
    Y, X = grid(shape)
    cx, cy, a, b = e[:4]
    return ell_d((cx, cy, a + grow, b + grow), X, Y) < 1


def poly_mask(shape, pts):
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [np.round(np.array(pts, np.float64)).astype(np.int32)], 1)
    return m.astype(bool)


def rect_mask(shape, r):
    m = np.zeros(shape[:2], bool)
    x0, y0, x1, y1 = [int(round(v)) for v in r]
    m[max(0, y0):y1, max(0, x0):x1] = True
    return m


def dilate(m, r):
    if r <= 0:
        return m.copy()
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.dilate(m.astype(np.uint8), k).astype(bool)


def erode(m, r):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.erode(m.astype(np.uint8), k).astype(bool)


def rounded_outside(shape, r):
    """True in the four rounded screen corners (the page colour of the sheet shows there)."""
    H, W = shape[:2]
    m = np.zeros((H, W), np.uint8)
    cv2.rectangle(m, (r, 0), (W - 1 - r, H - 1), 1, -1)
    cv2.rectangle(m, (0, r), (W - 1, H - 1 - r), 1, -1)
    for cx, cy in ((r, r), (W - 1 - r, r), (r, H - 1 - r), (W - 1 - r, H - 1 - r)):
        cv2.circle(m, (cx, cy), r, 1, -1)
    return ~m.astype(bool)


def bbox(mask, pad=0, shape=None):
    ys, xs = np.where(mask)
    H, W = (shape or mask.shape)[:2]
    return max(0, ys.min() - pad), min(H, ys.max() + pad + 1), max(0, xs.min() - pad), min(W, xs.max() + pad + 1)


# ---------------------------------------------------------------- Poisson
def poisson_merge(dst, src, mask):
    """Solve lap(f) = lap(src) inside mask (guidance only along edges inside the mask), f = dst outside."""
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return dst.copy()
    idx = -np.ones(mask.shape, np.int64); idx[ys, xs] = np.arange(len(ys))
    n = len(ys)
    rows, cols, vals = [], [], []
    b = np.zeros((n, dst.shape[2])); diag = np.zeros(n)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ny, nx = ys + dy, xs + dx
        ok = (ny >= 0) & (ny < mask.shape[0]) & (nx >= 0) & (nx < mask.shape[1])
        diag += ok
        nyc, nxc = np.clip(ny, 0, mask.shape[0] - 1), np.clip(nx, 0, mask.shape[1] - 1)
        inside = ok & mask[nyc, nxc]
        b += (src[ys, xs] - src[nyc, nxc]) * inside[:, None]
        rows.append(np.where(inside)[0]); cols.append(idx[nyc, nxc][inside]); vals.append(-np.ones(inside.sum()))
        edge = ok & ~mask[nyc, nxc]
        b[edge] += dst[nyc[edge], nxc[edge]]
    A = sp.csr_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [np.arange(n)]),
                       np.concatenate(cols + [np.arange(n)]))), shape=(n, n))
    solve = spla.factorized(A.tocsc())
    out = dst.copy()
    for c in range(dst.shape[2]):
        out[ys, xs, c] = solve(b[:, c])
    return out


def merge_region(img, src, mask, pad=3):
    """poisson_merge restricted to the bounding box of mask (fast)."""
    if not mask.any():
        return img
    y0, y1, x0, x1 = bbox(mask, pad, img.shape)
    out = img.copy()
    out[y0:y1, x0:x1] = poisson_merge(img[y0:y1, x0:x1], src[y0:y1, x0:x1], mask[y0:y1, x0:x1])
    return out


# ---------------------------------------------------------------- holes
def ring_coords(inner, outer, X, Y):
    """rho 0 on the opening ellipse, 1 on the outer rim ellipse (negative inside the opening:
    the opening scaled down); theta: ellipse angle."""
    lo = np.full(X.shape, -1.0); hi = np.full(X.shape, 1.8)
    lerp = lambda i, r: inner[i] + (outer[i] - inner[i]) * r
    for _ in range(28):
        mid = (lo + hi) / 2
        pos = mid >= 0
        # inside the opening: shrink the opening itself (rho = -1 at its centre)
        cx = np.where(pos, lerp(0, mid), inner[0]); cy = np.where(pos, lerp(1, mid), inner[1])
        a = np.where(pos, lerp(2, mid), inner[2] * (1 + mid)); b = np.where(pos, lerp(3, mid), inner[3] * (1 + mid))
        inside = ((X - cx) / np.maximum(a, 1e-3)) ** 2 + ((Y - cy) / np.maximum(b, 1e-3)) ** 2 < 1
        hi = np.where(inside, mid, hi); lo = np.where(inside, lo, mid)
    rho = (lo + hi) / 2
    pos = rho >= 0
    cx = np.where(pos, lerp(0, rho), inner[0]); cy = np.where(pos, lerp(1, rho), inner[1])
    a = np.where(pos, lerp(2, rho), inner[2] * (1 + rho)); b = np.where(pos, lerp(3, rho), inner[3] * (1 + rho))
    th = np.arctan2((Y - cy) / np.maximum(b, 1e-3), (X - cx) / np.maximum(a, 1e-3))
    return rho, th


def ring_point(inner, outer, rho, th):
    pos = rho >= 0
    lerp = lambda i: inner[i] + (outer[i] - inner[i]) * rho
    cx = np.where(pos, lerp(0), inner[0]); cy = np.where(pos, lerp(1), inner[1])
    a = np.where(pos, lerp(2), inner[2] * (1 + rho)); b = np.where(pos, lerp(3), inner[3] * (1 + rho))
    return cx + a * np.cos(th), cy + b * np.sin(th)


def sample(img, mx, my):
    """Bilinear samples of img at (mx, my) (any shape; long 1-D maps are folded for cv2.remap)."""
    shp = mx.shape
    n = mx.size
    wdt = 1024
    rows = (n + wdt - 1) // wdt
    fx = np.zeros(rows * wdt, np.float32); fy = np.zeros(rows * wdt, np.float32)
    fx[:n] = mx.ravel(); fy[:n] = my.ravel()
    fx = fx.reshape(rows, wdt); fy = fy.reshape(rows, wdt)
    out = np.stack([cv2.remap(img[..., c].astype(np.float32), fx, fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                    for c in range(img.shape[2])], -1).reshape(-1, img.shape[2])[:n]
    return out.reshape(shp + (img.shape[2],)).astype(np.float64)


def hole_guidance(img, hole, donors, fill, bad, rho_max=1.12):
    """Guidance pixels for `fill` inside hole's ring+opening, copied from donor holes at the same
    (rho, theta) (optionally mirrored left-right). Donor pixels in `bad` are not used; the first
    donor that is clean wins per pixel. Returns (guide, covered)."""
    H, W = img.shape[:2]
    Y, X = grid(img.shape)
    inner, outer = hole['inner'], hole['outer']
    rho, th = ring_coords(inner, outer, X, Y)
    region = fill & (rho <= rho_max)
    guide = img.copy()
    covered = np.zeros((H, W), bool)
    ys, xs = np.where(region)
    r, t = rho[ys, xs], th[ys, xs]
    for d in donors:
        tt = (np.pi - t) if d.get('mirror') else t
        mx, my = ring_point(d['inner'], d['outer'], r, tt)
        ix, iy = np.round(mx).astype(int), np.round(my).astype(int)
        ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
        ok[ok] &= ~bad[iy[ok], ix[ok]]
        ok &= ~covered[ys, xs]
        if ok.any():
            vals = sample(img, mx[ok][None], my[ok][None])[0]
            guide[ys[ok], xs[ok]] = vals
            covered[ys[ok], xs[ok]] = True
    return guide, covered


# ---------------------------------------------------------------- exemplar fill
def exemplar_fill(img, mask, src_ok, ps=9, vs=40, hs=160, near=0.02):
    """Criminisi-style patch fill of `mask`, copying only from `src_ok` pixels within +-vs rows and
    +-hs columns of the patch (keeps perspective / lighting local)."""
    R = ps // 2
    P = R + 1
    im = cv2.copyMakeBorder(img.astype(np.float32), P, P, P, P, cv2.BORDER_REFLECT)
    todo = cv2.copyMakeBorder(mask.astype(np.uint8), P, P, P, P, cv2.BORDER_CONSTANT, value=0).astype(bool)
    ok = cv2.copyMakeBorder((src_ok & ~mask).astype(np.uint8), P, P, P, P, cv2.BORDER_CONSTANT, value=0)
    cand = cv2.erode(ok, np.ones((ps, ps), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    conf = (~todo).astype(np.float32)
    ys, xs = np.where(todo)
    if len(ys) == 0:
        return img.copy()
    by0, by1 = max(0, ys.min() - ps), min(im.shape[0], ys.max() + ps + 1)
    bx0, bx1 = max(0, xs.min() - ps), min(im.shape[1], xs.max() + ps + 1)
    k3 = np.ones((3, 3), np.uint8)
    guard = 0
    while todo.any():
        guard += 1
        if guard > 200000:
            raise RuntimeError('exemplar fill did not converge')
        t = todo[by0:by1, bx0:bx1]
        front = t & cv2.dilate((~t).astype(np.uint8), k3).astype(bool)
        c = cv2.boxFilter(conf[by0:by1, bx0:bx1], -1, (ps, ps), normalize=True)
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
        sy0, sy1 = max(R, py - vs), min(im.shape[0] - R - 1, py + vs)
        sx0, sx1 = max(R, px - hs), min(im.shape[1] - R - 1, px + hs)
        region = im[sy0 - R:sy1 + R + 1, sx0 - R:sx1 + R + 1]
        if kn.sum() > 0:
            res = cv2.matchTemplate(region, tpl, cv2.TM_SQDIFF, mask=np.dstack([kn] * 3)) / kn.sum()
        else:
            res = np.zeros((sy1 - sy0 + 1, sx1 - sx0 + 1), np.float32)
        dy_, dx_ = np.mgrid[sy0:sy1 + 1, sx0:sx1 + 1]
        res = res + near * np.hypot(dy_ - py, (dx_ - px) * 0.5) * 10
        res[~cand[sy0:sy1 + 1, sx0:sx1 + 1]] = np.inf
        if not np.isfinite(res).any():
            # widen the search once
            vs, hs = vs * 2, hs * 2
            continue
        qy, qx = np.unravel_index(np.argmin(res), res.shape)
        qy += sy0; qx += sx0
        sl = (slice(py - R, py + R + 1), slice(px - R, px + R + 1))
        fill = todo[sl]
        im[sl][fill] = im[qy - R:qy + R + 1, qx - R:qx + R + 1][fill]
        conf[sl][fill] = c[py - by0, px - bx0]
        todo[sl][fill] = False
    return im[P:-P, P:-P].astype(np.float64)


# ---------------------------------------------------------------- segmentation
def grabcut(img, box, fg=None, pr_fg=None, bg=None, iters=6):
    """GrabCut inside box (x0, y0, x1, y1): fg/pr_fg/bg are extra boolean seeds (full image)."""
    H, W = img.shape[:2]
    gc = np.full((H, W), cv2.GC_BGD, np.uint8)
    x0, y0, x1, y1 = [int(v) for v in box]
    gc[max(0, y0):y1, max(0, x0):x1] = cv2.GC_PR_BGD
    if pr_fg is not None:
        gc[pr_fg & (gc != cv2.GC_BGD)] = cv2.GC_PR_FGD
    if fg is not None:
        gc[fg] = cv2.GC_FGD
    if bg is not None:
        gc[bg] = cv2.GC_BGD
    bgm, fgm = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR), gc, None, bgm, fgm, iters, cv2.GC_INIT_WITH_MASK)
    m = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if n > 1:
        m = lab == (1 + np.argmax(st[1:, 4]))
    # fill holes
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = np.zeros((H, W), np.uint8); cv2.drawContours(out, cnts, -1, 1, -1)
    return out.astype(bool)


def hsv(img):
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(int)


# ---------------------------------------------------------------- sprites
def cut_sprite(img, mask, feather=0.7, pad=2, extend_below=None):
    """RGBA crop of img where mask (feathered edge). extend_below: (edge_y(x) function, rows) to
    extend the body colour straight down under the front rim so it can rise without a gap."""
    m = mask.astype(np.float32)
    alpha = cv2.GaussianBlur(m, (0, 0), feather) if feather > 0 else m
    alpha = np.where(mask, np.maximum(alpha, 0.5), alpha * 0.85)
    y0, y1, x0, x1 = bbox(alpha > 0.01, pad, img.shape)
    rgb = img[y0:y1, x0:x1].copy(); al = alpha[y0:y1, x0:x1].copy()
    if extend_below is not None:
        edge_at, rows = extend_below
        extra = rows + 4
        rgb = np.concatenate([rgb, np.repeat(rgb[-1:], extra, 0)], 0)
        al = np.concatenate([al, np.zeros((extra, al.shape[1]), np.float32)], 0)
        mm = np.zeros(al.shape, bool); mm[:y1 - y0] = mask[y0:y1, x0:x1]
        for j in range(al.shape[1]):
            xg = x0 + j
            e = edge_at(xg)
            if e is None:
                continue
            col = np.where(mm[:, j])[0]
            if len(col) == 0:
                continue
            yb = col.max()
            if abs((y0 + yb) - e) > 5:
                continue
            src = img[max(0, y0 + yb - 4):y0 + yb - 1, xg].mean(0)
            start = min(yb, int(e) - y0) - 1
            for yy in range(max(0, start), al.shape[0]):
                rgb[yy, j] = src * (1 - 0.35 * max(0, yy - start) / rows)
                al[yy, j] = 1.0
    rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(al, 0, 1) * 255])
    return rgba, (int(x0), int(y0))


def save_rgba(path, rgba):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), 'RGBA').save(path, optimize=True)


def glow_layer(img, bg, region, gain=1.0):
    """Additive light: max(I - B, 0) inside region (soft edge). Returns RGB crop and its origin."""
    w = cv2.GaussianBlur(region.astype(np.float32), (0, 0), 3)[..., None]
    g = np.clip(img - bg, 0, 255) * w * gain
    y0, y1, x0, x1 = bbox(region, 4, img.shape)
    return g[y0:y1, x0:x1], (int(x0), int(y0))


def white_glyphs(img, box, vmin=200, smax=60):
    """Bounding box of the white lettering inside box."""
    x0, y0, x1, y1 = box
    h = hsv(img[y0:y1, x0:x1])
    m = (h[..., 2] > vmin) & (h[..., 1] < smax)
    ys, xs = np.where(m)
    return (int(x0 + xs.min()), int(y0 + ys.min()), int(x0 + xs.max() + 1), int(y0 + ys.max() + 1))


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, 'w'), indent=1)


# ---------------------------------------------------------------- openings / front edges
def fit_front(inner, mask):
    """The lower half of a hole's opening where a character's body meets the front rim: fitted
    to the bottom of the character mask (same cx and a as `inner`). Returns the adjusted opening
    (the upper half keeps the stored back edge) and the per-column edge {x0, y}."""
    cx, cy, a, b = inner
    Xs, Ys = [], []
    for x in range(int(np.ceil(cx - a * 0.9)), int(cx + a * 0.9) + 1):
        if not 0 <= x < mask.shape[1]:
            continue
        col = np.where(mask[:, x])[0]
        if len(col) == 0:
            continue
        yb = col.max() + 0.5
        arc = cy + b * np.sqrt(max(0.0, 1 - ((x - cx) / a) ** 2))
        if abs(yb - arc) < max(10, 0.45 * b):
            Xs.append(x); Ys.append(yb)
    if len(Xs) < 8:
        return tuple(inner), edge_columns(tuple(inner), {}, 0)
    Xs = np.array(Xs, float); Ys = np.array(Ys)
    s = np.sqrt(np.clip(1 - ((Xs - cx) / a) ** 2, 0, 1))
    A = np.stack([np.ones_like(s), s], 1)
    keep = np.ones(len(Xs), bool)
    for _ in range(6):
        (c0, bf), *_ = np.linalg.lstsq(A[keep], Ys[keep], rcond=None)
        err = np.abs(Ys - (c0 + bf * s))
        keep = err <= max(np.percentile(err[keep], 85), 1.0)
    top, bot = cy - b, c0 + bf
    opening = (cx, (top + bot) / 2, a, (bot - top) / 2)
    meas = {int(x): float(y) for x, y, k in zip(Xs, Ys, keep) if k}
    return tuple(round(v, 1) for v in opening), edge_columns(opening, meas, 3)


def edge_columns(opening, measured, blend=3):
    """Per-column front edge: measured values (median-smoothed) where present, the opening's lower
    arc elsewhere, cross-faded over `blend` px."""
    cx, cy, a, b = opening
    x0, x1 = int(np.ceil(cx - a)), int(np.floor(cx + a))
    xs = np.arange(x0, x1 + 1)
    arc = cy + b * np.sqrt(np.clip(1 - ((xs - cx) / a) ** 2, 0, 1))
    meas = np.array([measured.get(int(x), np.nan) for x in xs])
    sm = meas.copy()
    for i in range(1, len(xs) - 1):
        w = meas[i - 1:i + 2]
        if np.isfinite(w).all():
            sm[i] = np.median(w)
    ok = np.isfinite(sm)
    out = arc.copy()
    if ok.any() and blend > 0:
        idx = np.arange(len(xs))
        filled = np.interp(idx, idx[ok], sm[ok])
        dist = np.array([np.min(np.abs(idx[ok] - i)) for i in idx], float)
        wgt = np.clip(1 - dist / blend, 0, 1)
        out = arc * (1 - wgt) + filled * wgt
    return {'x0': int(x0), 'y': [round(float(v), 2) for v in out]}


def edge_fn(edge):
    ys = edge['y']; x0 = edge['x0']
    def f(x):
        i = int(round(x)) - x0
        return ys[i] if 0 <= i < len(ys) else None
    return f


# ---------------------------------------------------------------- difference matte
def diff_matte(img, bg, region, lo=10.0, hi=40.0, feather=0.8):
    """RGBA of what `img` has on top of `bg` inside region: alpha from the colour difference,
    colour un-premultiplied so that alpha*F + (1-alpha)*B = I (where alpha > 0)."""
    d = np.abs(img - bg).max(-1)
    a = np.clip((d - lo) / (hi - lo), 0, 1) * region
    a = cv2.GaussianBlur(a.astype(np.float32), (0, 0), feather) * dilate(region, 2) if feather > 0 else a
    a = np.clip(a, 0, 1)
    F = np.where(a[..., None] > 0.02, (img - (1 - a[..., None]) * bg) / np.maximum(a[..., None], 0.02), img)
    F = np.clip(F, 0, 255)
    y0, y1, x0, x1 = bbox(a > 0.01, 2, img.shape)
    return np.dstack([F[y0:y1, x0:x1], a[y0:y1, x0:x1] * 255]), (int(x0), int(y0))


# ---------------------------------------------------------------- compositing like the app
def hides_mask(shape, opening, edge):
    """True where the front rim hides a character standing in this hole (as LevelScreen.Hole.hides)."""
    Y, X = grid(shape)
    cx, cy, a, b = opening
    ys = np.array(edge['y']); x0 = edge['x0']
    xi = np.clip(np.round(X - 0.5 - x0).astype(int), 0, len(ys) - 1)
    ey = ys[xi]
    out = (Y >= cy) & ((X < cx - a) | (X > cx + a) | (Y >= ey))
    return out


def composite(base, layers):
    """Draw RGBA layers [(rgba, x, y, visible_mask_or_None)] over base (float RGB)."""
    out = base.copy()
    H, W = base.shape[:2]
    for rgba, x, y, vis in layers:
        h, w = rgba.shape[:2]
        x0, y0 = max(0, x), max(0, y); x1, y1 = min(W, x + w), min(H, y + h)
        if x0 >= x1 or y0 >= y1:
            continue
        s = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
        a = s[..., 3:4] / 255.0
        if vis is not None:
            a = a * vis[y0:y1, x0:x1, None]
        out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - a) + s[..., :3] * a
    return out


def matte_sprite(img, bg, region, core, edge=None, ext=30, lo=8.0, hi=36.0):
    """A character: difference matte of img over bg inside region, solid (alpha 1) on core. With
    an edge, the body colour continues `ext` px straight down below the front rim (so it can rise
    above its reference pose without a gap; the rim clip hides it at rest)."""
    rgba, (x0, y0) = diff_matte(img, bg, region, lo, hi)
    h, w = rgba.shape[:2]
    c = core[y0:y0 + h, x0:x0 + w]
    rgba[..., :3][c] = img[y0:y0 + h, x0:x0 + w][c]
    rgba[..., 3][c] = 255
    if edge is not None:
        f = edge_fn(edge)
        extra = np.zeros((ext + 4, w, 4)); rgba = np.concatenate([rgba, extra], 0)
        for j in range(w):
            xg = x0 + j
            e = f(xg)
            if e is None:
                continue
            col = np.where(core[:, xg])[0] if 0 <= xg < core.shape[1] else []
            if len(col) == 0 or abs(col.max() - e) > 6:
                continue
            yb = col.max()
            src = img[max(0, yb - 4):yb - 1, xg].mean(0)
            start = int(min(yb, e)) - 1 - y0
            for yy in range(max(0, start), rgba.shape[0]):
                rgba[yy, j, :3] = src * (1 - 0.35 * max(0, yy - start) / ext)
                rgba[yy, j, 3] = 255
    return rgba, (int(x0), int(y0))


# ---------------------------------------------------------------- lettering (same drawing as the app's OutlineText)
FONT_PATH = os.path.join(ROOT, 'design-pipeline', 'fonts', 'LilitaOne-Regular.ttf')


def draw_text(img, text, spec, S=4):
    """spec: box (x0,y0,x1,y1 of the digit ink), align left|center|right, size (px), scale_x, outline
    (px outside the glyph), shadow (px, outline repeated lower), rotate (deg, around the ink centre),
    fill_top, fill_bottom, outline_color (RGB)."""
    from PIL import ImageFont, ImageDraw
    H, W = img.shape[:2]
    x0, y0, x1, y1 = spec['box']
    size = spec['size'] * S
    font = ImageFont.truetype(FONT_PATH, int(round(size)))
    stroke = max(1, int(round(spec['outline'] * S)))
    lw, lh = int(font.getlength(text) + 8 * stroke), int(size * 1.6)

    def mask(extra):
        m = Image.new('L', (lw, lh), 0)
        ImageDraw.Draw(m).text((4 * stroke, 0), text, font=font, fill=255, stroke_width=extra, stroke_fill=255)
        return m.resize((max(1, int(lw * spec.get('scale_x', 1.0))), lh), Image.LANCZOS)
    fa = np.asarray(mask(0)).astype(np.float32) / 255
    oa = np.asarray(mask(stroke)).astype(np.float32) / 255
    ys, xs = np.where(fa > 0.5)
    gy0, gy1, gx0, gx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    al = spec.get('align', 'left')
    if al == 'left':
        tx = x0 * S - gx0
    elif al == 'right':
        tx = x1 * S - gx1
    else:
        tx = ((x0 + x1) / 2) * S - (gx0 + gx1) / 2
    ty = y0 * S - gy0
    big = cv2.resize(img.astype(np.float32), (W * S, H * S), interpolation=cv2.INTER_CUBIC)
    rot = spec.get('rotate', 0.0)
    cxr, cyr = tx + (gx0 + gx1) / 2, ty + (gy0 + gy1) / 2

    def place(a, oy):
        M = np.float32([[1, 0, tx], [0, 1, ty + oy]])
        if rot:
            R = cv2.getRotationMatrix2D((float(cxr), float(cyr)), -rot, 1.0)
            M = (np.vstack([R, [0, 0, 1]]) @ np.vstack([M, [0, 0, 1]]))[:2].astype(np.float32)
        return cv2.warpAffine(a, M, (W * S, H * S))[..., None]
    oc = np.array(spec.get('outline_color', (6, 12, 28)), np.float32)
    for oy in ((spec.get('shadow', 0) * S, 0) if spec.get('shadow', 0) else (0,)):
        aa = place(oa, oy); big = big * (1 - aa) + oc * aa
    aa = place(fa, 0)
    t = np.clip((np.arange(H * S)[:, None, None] - (ty + gy0)) / max(gy1 - gy0, 1), 0, 1)
    ft = np.array(spec.get('fill_top', (255, 255, 255)), np.float32); fb = np.array(spec.get('fill_bottom', (236, 238, 244)), np.float32)
    big = big * (1 - aa) + (ft * (1 - t) + fb * t) * aa
    return cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA).astype(np.float64)


def calibrate_text(ref, base, text, spec, grid_=None, margin=10):
    """Grid-search the lettering parameters so draw_text(base) matches ref around the box."""
    x0, y0, x1, y1 = spec['box']
    cy0, cy1, cx0, cx1 = max(0, y0 - margin), y1 + margin + 6, max(0, x0 - margin), x1 + margin
    sub_b = base[cy0:cy1, cx0:cx1]; sub_r = ref[cy0:cy1, cx0:cx1]

    def err(sp):
        s2 = dict(sp, box=(x0 - cx0, y0 - cy0, x1 - cx0, y1 - cy0))
        return float(np.abs(draw_text(sub_b, text, s2) - sub_r).mean())
    best = (err(spec), dict(spec))
    grid_ = grid_ or {}
    import itertools
    keys = list(grid_)
    for combo in itertools.product(*[grid_[k] for k in keys]):
        cand = dict(spec)
        for k, v in zip(keys, combo):
            cand[k] = v(spec) if callable(v) else v
        e = err(cand)
        if e < best[0]:
            best = (e, cand)
    return best
