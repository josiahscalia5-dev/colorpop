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
