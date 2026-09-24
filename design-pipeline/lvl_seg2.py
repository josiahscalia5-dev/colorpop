import numpy as np, cv2, json
from PIL import Image
from common import *
a = fix_edges(np.asarray(Image.open('/home/claude/art/lvl_crop.png').convert('RGB')).copy())
H, W = a.shape[:2]
hsv = cv2.cvtColor(a, cv2.COLOR_RGB2HSV).astype(int)
hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
# holes: inner opening ellipse (cx, cy, a, b) and outer rim ellipse
HOLES = {
 'h1': dict(inner=(241, 668, 86, 26), outer=(241, 677, 111, 43)),
 'h2': dict(inner=(489, 686, 90, 27), outer=(491, 692, 112, 42)),
 'h3': dict(inner=(112, 812, 98, 36), outer=(116, 822, 128, 56)),
 'h4': dict(inner=(499, 815, 99, 35), outer=(497, 824, 126, 54)),
 'h5': dict(inner=(321, 963, 126, 50), outer=(318, 978, 158, 73)),
 'h6': dict(inner=(502, 1076, 108, 50), outer=(501, 1090, 140, 72)),
}
CHARS = {  # hole, box, color
 'c1': ('h1', (172, 562, 312, 700), 'g'),
 'c2': ('h2', (418, 578, 562, 718), 'g'),
 'c3': ('h3', (20, 690, 190, 852), 'g'),
 'c4': ('h4', (418, 712, 580, 855), 'r'),
 'c5': ('h5', (218, 826, 412, 1016), 'g'),
 'c6': ('h6', (412, 948, 590, 1130), 'y'),
}
def colmask(c):
    if c == 'g': return (hh >= 35) & (hh <= 95) & (ss > 90) & (vv > 70)
    if c == 'r': return ((hh <= 8) | (hh >= 160)) & (ss > 80) & (vv > 60)
    if c == 'y': return (hh >= 19) & (hh <= 36) & (ss > 80) & (vv > 150)
def below_front_arc(hole, pad=0):
    cx, cy, ea, eb = HOLES[hole]['inner']
    yy, xx = np.mgrid[0:H, 0:W]
    inside_x = np.abs(xx - cx) < ea
    arc = cy + eb * np.sqrt(np.clip(1 - ((xx - cx) / ea) ** 2, 0, 1))
    return (yy > arc + pad) | (~inside_x & (yy > cy))
masks = {}
for k, (hole, box, c) in CHARS.items():
    x0, y0, x1, y1 = box
    gc = np.full((H, W), cv2.GC_BGD, np.uint8)
    gc[y0:y1, x0:x1] = cv2.GC_PR_BGD
    cm = colmask(c)
    inbox = np.zeros((H, W), bool); inbox[y0:y1, x0:x1] = True
    cm &= inbox
    cm = cv2.morphologyEx(cm.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    n, lab, st, cen = cv2.connectedComponentsWithStats(cm.astype(np.uint8), 8)
    big = 1 + np.argmax(st[1:, 4]); cm = lab == big
    filled = cm.copy().astype(np.uint8)
    cnts, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    hull = np.zeros((H, W), np.uint8); cv2.drawContours(hull, cnts, -1, 1, -1)
    gc[hull.astype(bool)] = cv2.GC_PR_FGD
    core = cv2.erode(hull, np.ones((9, 9), np.uint8)).astype(bool)
    gc[core] = cv2.GC_FGD
    if k == 'c1':
        yy, xx = np.mgrid[0:H, 0:W]
        gc[(yy < 592) & (np.abs(xx - 241) > 19) & inbox] = cv2.GC_BGD
    if k == 'c2':
        yy, xx = np.mgrid[0:H, 0:W]
        gc[(yy < 600) & (np.abs(xx - 489) > 19) & inbox] = cv2.GC_BGD
    if k == 'c4':
        hel = np.zeros((H, W), np.uint8)
        cv2.ellipse(hel, (500, 768), (46, 36), 0, 180, 360, 1, -1)
        gc[hel.astype(bool)] = cv2.GC_FGD
        cv2.circle(hel, (497, 734), 6, 1, -1)
        gc[hel.astype(bool) & (gc != cv2.GC_FGD)] = cv2.GC_PR_FGD
    blw = below_front_arc(hole, 1)
    gc[blw & inbox] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(a, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    m = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    big = 1 + np.argmax(st[1:, 4]); m = (lab == big).astype(np.uint8)
    # fill holes
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    m = np.zeros((H, W), np.uint8); cv2.drawContours(m, cnts, -1, 1, -1)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    if k == 'c4':
        allfg = (((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)) & inbox).astype(np.uint8)
        pts = cv2.findNonZero(allfg)
        hull = cv2.convexHull(pts)
        m = np.zeros((H, W), np.uint8); cv2.fillConvexPoly(m, hull, 1)
    m[blw] = 0
    masks[k] = m.astype(bool)
    print(k, m.sum())
np.savez_compressed('/home/claude/out/_lvl_masks.npz', **masks)
json.dump(dict(HOLES=HOLES, CHARS={k: [v[0], list(v[1]), v[2]] for k, v in CHARS.items()}), open('/home/claude/out/_lvl_geom.json', 'w'), indent=1)
# overlay preview
ov = a.copy().astype(np.float32)
allm = np.zeros((H, W), bool)
for m in masks.values(): allm |= m
ov[~allm] *= 0.35
ov = ov.astype(np.uint8)
im = Image.fromarray(ov)
from PIL import ImageDraw
d = ImageDraw.Draw(im)
for hk, g in HOLES.items():
    for key, col in (('inner', (255, 255, 0)), ('outer', (0, 255, 255))):
        cx, cy, ea, eb = g[key]
        d.ellipse([cx - ea, cy - eb, cx + ea, cy + eb], outline=col)
im.crop((0, 540, 622, 1156)).save('/home/claude/art/_seg_prev.png')
Image.fromarray(a).crop((0, 540, 622, 1156)).save('/home/claude/art/_seg_orig.png')
