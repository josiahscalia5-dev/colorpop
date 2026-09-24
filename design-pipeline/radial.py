import numpy as np, cv2
def radial_fill(img, mask, cx, cy, avg=3, maxr=2000):
    """Fill masked pixels by interpolating along rays through (cx,cy)."""
    H, W = mask.shape
    out = img.astype(np.float32).copy()
    ys, xs = np.where(mask)
    f = img.astype(np.float32)
    for y, x in zip(ys, xs):
        dx, dy = x - cx, y - cy
        d = np.hypot(dx, dy)
        if d < 1: continue
        ux, uy = dx / d, dy / d
        samples = []
        for sgn in (-1, 1):
            t = 0
            while True:
                t += 1
                px, py = x + sgn * ux * t, y + sgn * uy * t
                ix, iy = int(round(px)), int(round(py))
                if ix < 0 or iy < 0 or ix >= W or iy >= H or t > maxr:
                    samples.append(None); break
                if not mask[iy, ix]:
                    acc = []
                    for k in range(avg):
                        jx, jy = int(round(px + sgn * ux * k)), int(round(py + sgn * uy * k))
                        if 0 <= jx < W and 0 <= jy < H and not mask[jy, jx]:
                            acc.append(f[jy, jx])
                    samples.append((t, np.mean(acc, 0)))
                    break
        a, b = samples
        if a and b:
            ta, ca = a; tb, cb = b
            out[y, x] = (ca * tb + cb * ta) / (ta + tb)
        elif a: out[y, x] = a[1]
        elif b: out[y, x] = b[1]
    return np.clip(out, 0, 255).astype(np.uint8)
