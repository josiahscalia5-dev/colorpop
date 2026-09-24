"""Level 1 hole geometry shared by the level scripts.

_lvl_geom.json stores for each hole an 'inner' ellipse (the opening) and an 'outer' ellipse (outside
edge of the brick rim), measured by eye. The front edge of the opening -- where a character's body
disappears behind the front rim, i.e. the in-game clip line -- is fitted here on the reference,
and `openings()` returns one ellipse per hole from the stored back edge of the opening to that
fitted front edge.
"""
import json
import numpy as np, cv2
from paths import data

VALID_H = 1150  # rows below this still carry the bezel shadow of the reference photo


def load():
    G = json.load(open(data('_lvl_geom.json')))
    masks = {k: v.astype(bool) for k, v in np.load(data('_lvl_masks.npz')).items()}
    return G['HOLES'], G['CHARS'], masks


def ell_d(e, X, Y):
    cx, cy, a, b = e
    return ((X - cx) / a) ** 2 + ((Y - cy) / b) ** 2


def ring_coords(hole, X, Y):
    """rho: 0 on the inner (opening) ellipse, 1 on the outer rim ellipse; theta: ellipse angle."""
    ci, co = hole['inner'], hole['outer']
    lo = np.zeros(X.shape); hi = np.full(X.shape, 1.8)
    lerp = lambda i, r: ci[i] + (co[i] - ci[i]) * r
    for _ in range(26):
        mid = (lo + hi) / 2
        inside = ((X - lerp(0, mid)) / lerp(2, mid)) ** 2 + ((Y - lerp(1, mid)) / lerp(3, mid)) ** 2 < 1
        hi = np.where(inside, mid, hi); lo = np.where(inside, lo, mid)
    rho = (lo + hi) / 2
    cx, cy, ea, eb = (lerp(i, rho) for i in range(4))
    th = np.arctan2((Y - cy) / eb, (X - cx) / ea)
    return rho, th


def ring_point(hole, rho, th):
    ci, co = hole['inner'], hole['outer']
    lerp = lambda i: ci[i] + (co[i] - ci[i]) * rho
    return lerp(0) + lerp(2) * np.cos(th), lerp(1) + lerp(3) * np.sin(th)


def _fit_curve(inner, X, Y):
    cx, cy, a, b = inner
    s = np.sqrt(np.clip(1 - ((X - cx) / a) ** 2, 0, 1))
    A = np.stack([np.ones_like(s), s], 1)
    keep = np.ones(len(X), bool)
    for _ in range(6):  # trimmed least squares
        (c0, bf), *_ = np.linalg.lstsq(A[keep], Y[keep], rcond=None)
        err = np.abs(Y - (c0 + bf * s))
        keep = err <= max(np.percentile(err[keep], 85), 1.0)
    return [cx, round(float(c0), 1), a, round(float(bf), 1)]


def fit_front_edge(hk, holes, chars, masks, img):
    """Front edge of the opening of hole `hk` as [cx, cy, a, b] (lower half-ellipse).

    Two estimates, same cx/a as the stored inner ellipse: the bottom of the character mask, and
    the colour transition character -> rim just below it (the mask was clipped at the stored
    ellipse for some holes, where the body really reaches 1-2 px lower). The lower one wins so
    the in-game clip never hides a pixel the reference shows.
    """
    H, W = img.shape[:2]
    cx, cy, a, b = holes[hk]['inner']
    ck = next(k for k, v in chars.items() if v[0] == hk)
    m = masks[ck]
    others = np.zeros((H, W), bool)
    for k in chars:
        if k != ck:
            others |= cv2.dilate(masks[k].astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    mb = {x: np.where(m[:, x])[0].max() for x in range(int(cx - a * 0.92), int(cx + a * 0.92) + 1) if m[:, x].any()}
    by_mask = _fit_curve(holes[hk]['inner'], np.array(list(mb), float), np.array([mb[x] + 0.5 for x in mb]))
    C = np.median(np.concatenate([img[y - 4:y - 1, x] for x, y in mb.items()]), 0)
    Rm = np.median(np.concatenate([img[y + 6:y + 11, x] for x, y in mb.items()
                                   if y + 10 < VALID_H and not others[y + 6:y + 11, x].any()]), 0)
    dv = Rm - C
    Xc, Yc = [], []
    for x, y in mb.items():
        if y + 10 >= VALID_H or others[y - 3:y + 11, x].any():
            continue
        w = np.clip(((img[y - 3:y + 11, x].astype(np.float64) - C) @ dv) / (dv @ dv), 0, 1)
        idx = np.where(w > 0.5)[0]
        if len(idx) == 0 or idx[0] == 0:
            continue
        i = idx[0]
        Xc.append(x); Yc.append(y - 3 + (i - 1) + (0.5 - w[i - 1]) / max(w[i] - w[i - 1], 1e-3) + 0.5)
    by_colour = _fit_curve(holes[hk]['inner'], np.array(Xc, float), np.array(Yc))
    return max(by_mask, by_colour, key=lambda e: e[1] + e[3])


def openings(holes, chars, masks, img):
    """Per hole: (front-edge fit, opening ellipse from the stored back edge to the fitted front)."""
    front, opening = {}, {}
    for hk in holes:
        front[hk] = fit_front_edge(hk, holes, chars, masks, img)
        cx, cy, a, b = holes[hk]['inner']
        top, bot = cy - b, front[hk][1] + front[hk][3]
        opening[hk] = [cx, round((top + bot) / 2, 1), a, round((bot - top) / 2, 1)]
    return front, opening


def front_edge_columns(hk, holes, chars, masks, img, opening):
    """The real front edge of the opening, column by column: {x0, y: [...]} in art px.

    The front rim is bumpy (every brick's rounded top rises above the joints), so where the
    character's body meets the rim the edge is measured per column on the reference -- the
    body -> brick colour transition -- and lightly smoothed. Columns the body does not reach, or
    where another character is in front, follow the opening ellipse.
    """
    H, W = img.shape[:2]
    cx, cy, a, b = opening
    ck = next(k for k, v in chars.items() if v[0] == hk)
    m = masks[ck]
    others = np.zeros((H, W), bool)
    for k in chars:
        if k != ck:
            others |= cv2.dilate(masks[k].astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    x0, x1 = int(np.ceil(cx - a)), int(np.floor(cx + a))
    xs = np.arange(x0, x1 + 1)
    curve = cy + b * np.sqrt(np.clip(1 - ((xs - cx) / a) ** 2, 0, 1))
    mb = {}
    for x, cv in zip(xs, curve):
        col = np.where(m[:, x])[0]
        if len(col) and abs(col.max() + 0.5 - cv) <= 7:
            mb[x] = col.max()
    meas = np.full(len(xs), np.nan)
    if len(mb) > 10:
        C = np.median(np.concatenate([img[y - 4:y - 1, x] for x, y in mb.items()]), 0).astype(np.float64)
        Rs = [img[y + 6:y + 11, x] for x, y in mb.items() if y + 10 < VALID_H and not others[y + 6:y + 11, x].any()]
        Rm = np.median(np.concatenate(Rs), 0).astype(np.float64)
        dv = Rm - C
        for i, x in enumerate(xs):
            if x not in mb:
                continue
            y = mb[x]
            if y + 10 >= VALID_H or others[y - 3:y + 5, x].any():   # another character right at the edge
                continue
            w = np.clip(((img[y - 3:y + 11, x].astype(np.float64) - C) @ dv) / (dv @ dv), 0, 1)
            w[4 + np.flatnonzero(others[y + 1:y + 11, x])] = 1         # it may start a few px lower
            idx = np.where(w > 0.5)[0]
            if len(idx) == 0 or idx[0] == 0:
                continue
            j = idx[0]
            meas[i] = y - 3 + (j - 1) + (0.5 - w[j - 1]) / max(w[j] - w[j - 1], 1e-3) + 0.5
    # median-3 smoothing of the measured runs, drop wild points
    sm = meas.copy()
    for i in range(1, len(xs) - 1):
        win = meas[i - 1:i + 2]
        if np.isfinite(win).all():
            sm[i] = np.median(win)
    sm[np.abs(sm - curve) > 9] = np.nan
    # gaps of up to 12 columns: interpolate; blend into the ellipse over 5 px at the ends of each run
    ok = np.isfinite(sm)
    edge = curve.copy()
    wgt = np.zeros(len(xs))
    if ok.any():
        idx = np.arange(len(xs))
        filled = np.interp(idx, idx[ok], sm[ok])
        dist = np.full(len(xs), 99.0)
        last = -99
        for i in range(len(xs)):
            if ok[i]:
                last = i
            dist[i] = i - last
        nxt = 10 ** 6
        for i in range(len(xs) - 1, -1, -1):
            if ok[i]:
                nxt = i
            gap = nxt - i
            # inside a short gap between two measured columns (up to ~12 px -- a brick is 30-40
            # wide): keep the interpolation
            if dist[i] + gap <= 13:
                dist[i] = 0
            else:
                dist[i] = min(dist[i], gap)
        wgt = np.clip(1 - dist / 5.0, 0, 1)
        edge = curve * (1 - wgt) + filled * wgt
    # 'w': 1 where the edge is measured, fading to 0 where it follows the ellipse
    return {'x0': int(x0), 'y': [round(float(v), 2) for v in edge], 'w': [round(float(v), 2) for v in wgt],
            'measured': int(ok.sum())}
