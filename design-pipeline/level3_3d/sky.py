"""The sky behind the new Level 3 (painted in 2D, composited under the 3D render): the reference's
bright blue afternoon sky with soft white clouds and a warm golden haze low on the left, where the
sun is."""
import numpy as np, cv2


def sky(w, h, seed=8):
    y = np.linspace(0, 1, h)[:, None, None]
    stops = [(0.0, (40, 110, 230)), (0.14, (70, 150, 245)), (0.26, (130, 195, 250)), (0.36, (190, 225, 250))]
    col = np.zeros((h, 1, 3), np.float32)
    for (y0, c0), (y1, c1) in zip(stops[:-1], stops[1:]):
        m = (y >= y0) & (y <= y1)
        u = np.clip((y - y0) / (y1 - y0), 0, 1)
        col = np.where(m, np.array(c0) + (np.array(c1) - np.array(c0)) * u, col)
    col = np.where(y > stops[-1][0], np.array(stops[-1][1], np.float32), col)
    img = np.broadcast_to(col, (h, w, 3)).astype(np.float32).copy()
    s = w / 1448
    rnd = np.random.default_rng(seed)
    # golden haze low on the left (the sun behind the trees)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    haze = np.exp(-(((xx - 0.05 * w) / (0.55 * w)) ** 2 + ((yy - 0.30 * h) / (0.12 * h)) ** 2))
    img = img * (1 - 0.65 * haze[..., None]) + 0.65 * haze[..., None] * np.array([255, 214, 130.0])
    # soft cumulus clouds: clusters of round puffs, white on top, a little blue-grey underneath
    for i in range(9):
        cx, cy = rnd.uniform(-0.05, 1.05) * w, rnd.uniform(0.03, 0.27) * h
        lay = np.zeros((h, w), np.float32)
        n = rnd.integers(5, 9)
        for j in range(n):
            ex, ey = cx + rnd.uniform(-150, 150) * s, cy + rnd.uniform(-22, 10) * s
            r = rnd.uniform(40, 80) * s
            cv2.circle(lay, (int(ex), int(ey)), int(r), 1.0, -1, cv2.LINE_AA)
        cv2.rectangle(lay, (int(cx - 170 * s), int(cy + 10 * s)), (int(cx + 170 * s), int(cy + 60 * s)), 0.0, -1)
        lay = cv2.GaussianBlur(lay, (0, 0), 6 * s)
        shade = np.clip(cv2.GaussianBlur(np.roll(lay, int(-26 * s), 0), (0, 0), 14 * s), 0, 1)
        white = np.array([255, 255, 255.0]) * (0.97 - 0.10 * (1 - shade[..., None])) + np.array([-40, -24, 0.0]) * (1 - shade[..., None])
        a = 0.92 * lay[..., None]
        img = img * (1 - a) + white * a
    return np.clip(img, 0, 255)
