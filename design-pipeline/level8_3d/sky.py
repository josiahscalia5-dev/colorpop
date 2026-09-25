"""The night sky behind the new Level 8 (painted in 2D, composited under the 3D render)."""
import numpy as np, cv2


def sky(w, h, seed=3):
    """w x h float RGB: deep navy at the top, violet, a warm glow low down, stars, a crescent moon."""
    y = np.linspace(0, 1, h)[:, None, None]
    top = np.array([10, 14, 46.0]); mid = np.array([52, 30, 104.0]); low = np.array([196, 92, 120.0]); glow = np.array([255, 166, 110.0])
    col = np.where(y < 0.18, top + (mid - top) * (y / 0.18),
                   np.where(y < 0.30, mid + (low - mid) * ((y - 0.18) / 0.12), low + (glow - low) * np.clip((y - 0.30) / 0.05, 0, 1)))
    img = np.broadcast_to(col, (h, w, 3)).astype(np.float32).copy()
    rnd = np.random.default_rng(seed)
    s = w / 1448
    # stars: many tiny ones, a few bright with a soft cross, fading towards the glow
    for i in range(int(420 * s * s * 1.0)):
        x, yy = rnd.uniform(0, w), rnd.uniform(0, h * 0.30)
        b = rnd.uniform(0.25, 1.0) * np.clip(1.3 - yy / (h * 0.3), 0, 1)
        r = rnd.uniform(0.8, 2.2) * s
        cv2.circle(img, (int(x), int(yy)), max(1, int(r)), tuple(float(v) for v in (img[int(yy), int(x)] + (255 - img[int(yy), int(x)]) * b)), -1, cv2.LINE_AA)
    glowl = np.zeros((h, w), np.float32)
    for i in range(int(26 * s * s)):
        x, yy = int(rnd.uniform(0, w)), int(rnd.uniform(0, h * 0.26))
        L = rnd.uniform(10, 22) * s
        cv2.line(glowl, (int(x - L), yy), (int(x + L), yy), 1.0, max(1, int(1.5 * s)), cv2.LINE_AA)
        cv2.line(glowl, (x, int(yy - L)), (x, int(yy + L)), 1.0, max(1, int(1.5 * s)), cv2.LINE_AA)
        cv2.circle(glowl, (x, yy), max(2, int(3 * s)), 1.0, -1, cv2.LINE_AA)
    glowl = cv2.GaussianBlur(glowl, (0, 0), 1.2 * s) * 1.6 + cv2.GaussianBlur(glowl, (0, 0), 6 * s) * 0.8
    img += glowl[..., None] * np.array([220, 225, 255.0])
    # crescent moon (upper right, behind the timer area it is partly hidden -> place mid right)
    mx, my, mr = int(0.84 * w), int(0.235 * h), int(62 * s)
    moon = np.zeros((h, w), np.float32)
    cv2.circle(moon, (mx, my), mr, 1.0, -1, cv2.LINE_AA)
    cv2.circle(moon, (mx + int(0.42 * mr), my - int(0.2 * mr)), int(mr * 0.92), 0.0, -1, cv2.LINE_AA)
    halo = cv2.GaussianBlur(moon, (0, 0), 40 * s) * 0.9
    img = img + halo[..., None] * np.array([180, 170, 255.0]) * 0.6
    img = img * (1 - moon[..., None]) + moon[..., None] * np.array([255, 244, 205.0])
    return np.clip(img, 0, 255)
