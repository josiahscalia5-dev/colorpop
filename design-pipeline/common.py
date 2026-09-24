import numpy as np, cv2
from PIL import Image

SS = 4  # supersampling for antialiased masks

def rrect_mask(shape, x0, y0, x1, y1, r, margin=0.0, feather=1.2):
    """Anti-aliased rounded-rect alpha mask (float 0..1) in image of `shape`."""
    H, W = shape[:2]
    x0 -= margin; y0 -= margin; x1 += margin; y1 += margin; r += margin
    big = np.zeros((H * SS, W * SS), np.uint8)
    X0, Y0, X1, Y1, R = [int(round(v * SS)) for v in (x0, y0, x1, y1, r)]
    R = max(1, min(R, (X1 - X0) // 2, (Y1 - Y0) // 2))
    cv2.rectangle(big, (X0 + R, Y0), (X1 - R, Y1), 255, -1)
    cv2.rectangle(big, (X0, Y0 + R), (X1, Y1 - R), 255, -1)
    for cx, cy in [(X0 + R, Y0 + R), (X1 - R, Y0 + R), (X0 + R, Y1 - R), (X1 - R, Y1 - R)]:
        cv2.circle(big, (cx, cy), R, 255, -1)
    m = cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather * 0.5)
    return np.clip(m, 0, 1)

def circle_mask(shape, cx, cy, r, margin=0.0, feather=1.2):
    H, W = shape[:2]
    big = np.zeros((H * SS, W * SS), np.uint8)
    cv2.circle(big, (int(round(cx * SS)), int(round(cy * SS))), int(round((r + margin) * SS)), 255, -1)
    m = cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather * 0.5)
    return np.clip(m, 0, 1)

def ellipse_mask(shape, cx, cy, a, b, feather=1.0):
    H, W = shape[:2]
    big = np.zeros((H * SS, W * SS), np.uint8)
    cv2.ellipse(big, (int(round(cx * SS)), int(round(cy * SS))), (int(round(a * SS)), int(round(b * SS))), 0, 0, 360, 255, -1)
    m = cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather * 0.5)
    return np.clip(m, 0, 1)

def inpaint(img_rgb, mask_bool, method='fsr_best'):
    """img_rgb uint8 HxWx3, mask_bool True where to fill."""
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    valid = (~mask_bool).astype(np.uint8)  # xphoto: nonzero = valid pixel
    out = np.zeros_like(bgr)
    if method.startswith('fsr'):
        flag = cv2.xphoto.INPAINT_FSR_BEST if method == 'fsr_best' else cv2.xphoto.INPAINT_FSR_FAST
        cv2.xphoto.inpaint(bgr, valid, out, flag)
    else:
        out = cv2.inpaint(bgr, mask_bool.astype(np.uint8) * 255, 5, cv2.INPAINT_TELEA)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)

def cut_sprite(img_rgb, alpha, pad=2):
    """Return (rgba uint8 crop, (x0,y0)) for region where alpha>0.003."""
    ys, xs = np.where(alpha > 0.003)
    x0, x1 = max(0, xs.min() - pad), min(img_rgb.shape[1], xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(img_rgb.shape[0], ys.max() + 1 + pad)
    rgba = np.dstack([img_rgb[y0:y1, x0:x1], (alpha[y0:y1, x0:x1] * 255 + 0.5).astype(np.uint8)])
    return rgba, (int(x0), int(y0))

def status_and_corner_mask(a, rects):
    H, W = a.shape[:2]
    m = np.zeros((H, W), bool)
    for (x0, y0, x1, y1) in rects:
        m[y0:y1, x0:x1] = True
    dark = (a.astype(int).sum(2) < 200).astype(np.uint8)
    corner = np.zeros((H, W), bool)
    for (cx, cy, bw, bh) in [(0, 0, 75, 75), (W - 1, 0, 75, 75), (0, H - 1, 12, 12), (W - 1, H - 1, 12, 12)]:
        ff = dark.copy()
        if not ff[cy, cx]:
            continue
        # only allow the fill inside the small corner box
        box = np.zeros((H, W), np.uint8)
        box[max(0, cy - bh):cy + bh + 1, max(0, cx - bw):cx + bw + 1] = 1
        ff = ff & box
        msk = np.zeros((H + 2, W + 2), np.uint8)
        cv2.floodFill(ff, msk, (cx, cy), 2)
        corner |= (ff == 2)
    corner = cv2.dilate(corner.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    inside = rrect_mask((H, W), 4, 3, W - 5, H + 300, 60, 0, 0)
    corner |= inside < 0.99
    m |= corner
    return m

def save_rgba(path, rgba):
    Image.fromarray(rgba, 'RGBA').save(path, optimize=True)

def fix_edges(a):
    a = a.copy()
    a[:, 0] = a[:, 2]; a[:, 1] = a[:, 2]
    W = a.shape[1]
    a[:, W - 1] = a[:, W - 3]; a[:, W - 2] = a[:, W - 3]
    return a
