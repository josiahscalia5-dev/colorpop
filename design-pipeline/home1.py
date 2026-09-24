import numpy as np, cv2, json, time
from PIL import Image
from common import *
OUT = '/home/claude/out/home'; import os; os.makedirs(OUT, exist_ok=True)
a = fix_edges(np.asarray(Image.open('/home/claude/art/home_crop.png').convert('RGB')).copy())
H, W = a.shape[:2]
els = {
  'coin_pill': dict(kind='rrect', box=(204, 57, 465, 135), r=39, margin=2.5),
  'plus':      dict(kind='rrect', box=(400, 64, 461, 129), r=11, margin=1.0),
  'gear':      dict(kind='circle', c=(564.5, 101.5), r=40, margin=2.5),
  'play':      dict(kind='rrect', box=(50, 901, 568, 1045), r=58, margin=3.0),
  'nav_missions': dict(kind='rrect', box=(14, 1051, 157, 1149), r=13, margin=2.0),
  'nav_shop':     dict(kind='rrect', box=(163, 1051, 299, 1149), r=13, margin=2.0),
  'nav_rewards':  dict(kind='rrect', box=(306, 1051, 450, 1149), r=13, margin=2.0),
  'nav_profile':  dict(kind='rrect', box=(457, 1051, 606, 1149), r=13, margin=2.0),
}
alphas = {}
for k, e in els.items():
    if e['kind'] == 'rrect':
        x0, y0, x1, y1 = e['box']
        m = rrect_mask(a.shape, x0, y0, x1, y1, e['r'], e['margin'])
        if k == 'play':  # include the soft drop shadow under the button
            m = np.maximum(m, rrect_mask(a.shape, x0, y0 + 6, x1, y1 + 6, e['r'], 2.0) * 0.999)
    else:
        m = circle_mask(a.shape, e['c'][0], e['c'][1], e['r'], e['margin'])
    alphas[k] = m
clean = status_and_corner_mask(a, [(56, 20, 122, 54), (458, 18, 594, 54)])
ui = np.zeros((H, W), bool)
for k, m in alphas.items():
    if k != 'plus':
        ui |= m > 0.01
ui = cv2.dilate(ui.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
t = time.time()
base = inpaint(a, clean, 'fsr_best')          # clean status bar / bezel first
bg = inpaint(base, ui, 'fsr_fast')           # then remove UI
print('inpaint', round(time.time() - t, 1), 's')
Image.fromarray(base).save(OUT + '/_base_clean.png')
Image.fromarray(bg).save(OUT + '/_bg_core.png')
meta = {}
for k, m in alphas.items():
    rgba, (x0, y0) = cut_sprite(a, m)
    save_rgba(f'{OUT}/{k}.png', rgba)
    e = els[k]
    meta[k] = dict(x=x0, y=y0, w=rgba.shape[1], h=rgba.shape[0])
    if e['kind'] == 'rrect':
        meta[k]['hit'] = list(e['box'])
    else:
        cx, cy = e['c']; r = e['r']; meta[k]['hit'] = [cx - r, cy - r, cx + r, cy + r]
json.dump(meta, open(OUT + '/_meta.json', 'w'), indent=1)
print(json.dumps(meta))
