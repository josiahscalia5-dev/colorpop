import numpy as np, cv2, json, time
from PIL import Image
from common import *
from radial import radial_fill
from paths import work, asset_dir
OUT = asset_dir('home')
base = np.asarray(Image.open(work('home_base_clean.png')).convert('RGB'))
bg = np.asarray(Image.open(work('home_bg_core.png')).convert('RGB')).copy()
H, W = bg.shape[:2]
CX, CY = 314, 300
# HUD zone (coin pill + gear): refill along light rays instead of generic inpaint
hud = np.maximum(rrect_mask(bg.shape, 204, 57, 465, 135, 39, 5), circle_mask(bg.shape, 564.5, 101.5, 40, 5)) > 0.01
t = time.time()
bg2 = radial_fill(base, hud, CX, CY)
print('radial fill', round(time.time() - t, 1))
# smooth only inside the filled zone
sm = cv2.GaussianBlur(bg2, (0, 0), 2.0)
w = cv2.GaussianBlur(hud.astype(np.float32), (0, 0), 1.5)[..., None]
bg2 = (bg2 * (1 - w) + sm * w).astype(np.uint8)
bg[:170] = bg2[:170]
Image.fromarray(bg).save(work('home_bg_core2.png'))

# ---- upward extension projected along the rays ----
PT = 400
band = cv2.GaussianBlur(bg[0:40].astype(np.float32), (0, 0), 2.5)
ext_h = PT + 40
ys = np.arange(ext_h)[:, None] - PT              # rows -PT .. 39
xs = np.arange(W)[None, :].astype(np.float32)
ty = 20.0
t = (ty - CY) / (ys - CY)
sx = np.clip(CX + (xs - CX) * t, 0, W - 1)
x0 = np.floor(sx).astype(int); x1 = np.minimum(x0 + 1, W - 1); fx = (sx - x0)[..., None]
row = band[20]
proj = row[x0] * (1 - fx) + row[x1] * fx
# gentle darkening toward the very top (matches the deeper blue at the top of the reference)
dark = np.clip((-ys) / 400.0, 0, 1)[..., None] * 0.10
proj = proj * (1 - dark)
full = np.concatenate([proj[:PT], bg.astype(np.float32)], 0)
# crossfade art rows 0..39 with the projection so there is no seam
for i in range(40):
    wa = i / 39.0
    full[PT + i] = bg[i] * wa + proj[PT + i] * (1 - wa)
full = np.clip(full, 0, 255).astype(np.uint8)
# side bleed (only ever a few px visible on short screens): clamp + blur
PS = 24
full = cv2.copyMakeBorder(full, 0, 0, PS, PS, cv2.BORDER_REPLICATE)
edge = cv2.GaussianBlur(full, (0, 0), 6)
full[:, :PS] = edge[:, :PS]; full[:, -PS:] = edge[:, -PS:]
Image.fromarray(full).save(OUT + '/bg_full.png')
m = json.load(open(OUT + '/_meta.json'))
m['_bg'] = dict(pad_top=PT, pad_side=PS, art_w=W, art_h=H)
json.dump(m, open(OUT + '/_meta.json', 'w'), indent=1)
Image.fromarray(full[:PT + 220]).save(work('home_ext_top.png'))
print(full.shape)
