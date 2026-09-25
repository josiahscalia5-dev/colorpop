"""Level 3's tap-and-fire: the demonstration hand and the rules (python3 levels/level3_fire.py).

Works on the superseded sheet-based Level 3 (app-assets/level3_sheet/, written by levels/level3.py);
the app's Level 3 (design-pipeline/level3_3d/export.py) keeps the glove it made: app-assets/level3/hand.png.

The hand is the white glove of the reference's hint (app-assets/level3/hint.png), cut alone -- the
gem, trail and sparks around it are now drawn by the game (the shot and the hit burst) -- and
reconstructed at twice the art resolution like the Level 3 characters (sr.sharp_region on the
owner's enlargement). Writes app-assets/level3/hand.png and its entry in app-assets/level3/level.json,
the front purple of the opening wave (see below) and the rules of levels/level3.py (with "fire" and
"demo"); the rest of level.json is left as it is.
"""
import os, sys, json
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import asset_dir
import sr

OUT = asset_dir('level3_sheet')
LEVEL = os.path.join(OUT, 'level.json')
L = json.load(open(LEVEL))
HX, HY = L['hint']['x'], L['hint']['y']

# ---------------------------------------------------------------- the glove, at 1x in the hint
hint = np.asarray(Image.open(os.path.join(OUT, 'hint.png')).convert('RGBA')).astype(np.float32)
hsv = cv2.cvtColor(hint[..., :3].astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
white = ((hsv[..., 1] < 60) & (hsv[..., 2] > 150) & (hint[..., 3] > 128)).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(white, 8)
# the glove: the large white component in the lower right (the hand of the demonstration)
cands = [i for i in range(1, n) if st[i, 0] > 300 and st[i, 1] > 150 and st[i, 4] > 5000]
glove = max(cands, key=lambda i: st[i, 4])
x, y, w, h = st[glove, :4]
M = 10                                                  # art px of margin (the outline, softness)
box = (HX + x - M, HY + y - M, HX + x + w + M, HY + y + h + M)     # art px

# ---------------------------------------------------------------- reconstructed at 2x
hires, _ = sr.hires_canvas('level3')
img, (X0, Y0, X1, Y1), _ = sr.sharp_region(hires, tuple(int(v * 2) for v in box), deblur_px=1.0)
hsv2 = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
# inside of the glove: its white and light-grey shading, grown from the 1x component
seed = np.zeros(img.shape[:2], np.uint8)
comp = (lab[y:y + h, x:x + w] == glove).astype(np.uint8)
ox, oy = int(2 * (HX + x)) - X0, int(2 * (HY + y)) - Y0
seed[oy:oy + 2 * h, ox:ox + 2 * w] = cv2.resize(comp, (2 * w, 2 * h), interpolation=cv2.INTER_NEAREST)
light = (hsv2[..., 1] < 70) & (hsv2[..., 2] > 120)
inside = seed.copy()
for _ in range(6):                                      # follow the light pixels into the fingers' edges
    inside = (cv2.dilate(inside, np.ones((3, 3), np.uint8)) & light.astype(np.uint8)) | seed
cnts, _ = cv2.findContours(inside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
fill = np.zeros_like(inside)
cv2.drawContours(fill, [max(cnts, key=cv2.contourArea)], -1, 1, -1)
# the black outline around it: dark pixels within 7 px (2x) of the glove
dark = hsv2[..., 2] < 95
ring = cv2.dilate(fill, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))) & ~fill.astype(bool)
outline = ring.astype(bool) & dark
mask = fill.astype(bool) | outline
mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
mask = np.zeros_like(mask)
cv2.drawContours(mask, [max(cnts, key=cv2.contourArea)], -1, 1, -1)
# a clean dark rim all round (where the outline was lost next to the gem or the trail)
edge = mask.astype(bool) & ~cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
rgb = img.copy()
rgb[edge & ~dark] = rgb[edge & ~dark] * 0.25 + np.array([18, 16, 30.0]) * 0.75
alpha = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 0.7)
ys, xs = np.nonzero(alpha > 0.02)
cx0, cy0, cx1, cy1 = xs.min() & ~1, ys.min() & ~1, (xs.max() + 2) & ~1, (ys.max() + 2) & ~1
out = np.dstack([rgb, alpha * 255])[cy0:cy1, cx0:cx1]
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'hand.png'))
hx, hy = (X0 + cx0) / 2, (Y0 + cy0) / 2                 # art px of the picture's top left
# the fingertip: the glove's highest point (the index finger points up and to the left)
tip_y = ys.min()
tip_x = int(xs[ys == tip_y].mean())
tip = [round((X0 + tip_x) / 2, 1), round((Y0 + tip_y) / 2 + 4, 1)]

# ---------------------------------------------------------------- the front purple of the opening wave
# The reference hides half of it behind the gem and the hand, so its cut-out (char_purple2.png) is
# damaged on that side; the demonstration now shows it uncovered, so it is the complete purple of h2
# (the same character) placed in h4, scaled to that hole.
p = L['chars']['purple']
o2, o4 = L['holes']['h2']['opening'], L['holes']['h4']['opening']
f = o4[2] / o2[2]
L['chars']['purple2'] = {'file': p['file'], 'x': round(o4[0] + (p['x'] - o2[0]) * f, 2),
                         'y': round(o4[1] + o4[3] + (p['y'] - (o2[1] + o2[3])) * f, 2),
                         'w': round(p['w'] * f, 2), 'h': round(p['h'] * f, 2), 'scale': round(p['scale'] / f, 5),
                         'hole': 'h4', 'color': 'purple', 'role': 'target', 'intro_only': True}

# ---------------------------------------------------------------- level.json
L['hand'] = {'file': 'level3/hand.png', 'x': hx, 'y': hy, 'w': (cx1 - cx0) / 2, 'h': (cy1 - cy0) / 2, 'scale': 2, 'tip': tip}
from levels.level3 import RULES
L['rules'] = RULES                    # with its "fire" and "demo" entries
json.dump(L, open(LEVEL, 'w'), indent=1)
print('hand', L['hand'])
