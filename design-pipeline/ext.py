import numpy as np, cv2
def radial_top_extension(img, pad, cx, cy, y0=8, band=14, blur=3):
    """Extend image upward by `pad` rows by projecting rows toward (cx,cy) (radiating light rays)."""
    H, W = img.shape[:2]
    src = img[y0:y0 + band].astype(np.float32)
    src = cv2.GaussianBlur(src, (0, 0), blur)
    ref = src.mean(0)  # 1 x W x 3 averaged band
    ext = np.zeros((pad, W, 3), np.float32)
    ys = np.arange(pad)[:, None] - pad  # negative y in image coords
    xs = np.arange(W)[None, :].astype(np.float32)
    ty = y0 + band / 2.0
    t = (ty - cy) / (ys - cy)
    sx = cx + (xs - cx) * t
    sx = np.clip(sx, 0, W - 1)
    x0 = np.floor(sx).astype(int); x1 = np.minimum(x0 + 1, W - 1); fx = (sx - x0)[..., None]
    ext = ref[x0] * (1 - fx) + ref[x1] * fx
    out = np.concatenate([ext, img.astype(np.float32)], 0)
    # soften seam: blend a few rows across the seam
    seam = pad
    k = 10
    for i in range(k):
        w = (i + 1) / (k + 1)
        out[seam + i] = out[seam + i] * w + out[seam - 1] * (1 - w) * 0 + out[seam + i] * 0 if False else out[seam + i]
    return np.clip(out, 0, 255).astype(np.uint8)

def mirror_pad(img, top=0, bottom=0, left=0, right=0):
    return cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_REFLECT_101)
