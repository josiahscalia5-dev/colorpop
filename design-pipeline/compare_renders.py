"""Compare the app's screens, rendered by ScreenRenderTest on many phone shapes, with the reference.

For every render, the layout numbers the test wrote (scale s, offsets) say where each reference
pixel landed. The reference is warped into screen space with that same transform and the same
bilinear sampling the app uses, and compared with the render pixel by pixel. Because the layout
uses one uniform scale, the same design must come out on every shape.

  python3 compare_renders.py RENDERS_DIR [OUT_DIR]

Regions compared (reference px):
  Home   main group  x 0-628,  y 160-1150  (title .. nav bar; anchored to the safe bottom)
         top group   the coin counter, + and gear sprites themselves (pinned to the top of the
                     screen, so the sky behind them legitimately differs on taller screens)
  Level  scene       x 0-622,  y 66-960    (HUD .. holes; the foliage below moves to the screen bottom)
         + on the reference shape the full screen from y 66 down.
  Levels 3, 6, ...   the level's must-see rows (level.json "content"), full width, against
         reference/screens/levelN.png (or level.json "reference": Level 8's approved new design),
         in the reference moment (LevelScreen.referenceMoment).
Rows above y 51/66 hold the reference photo's fake status bar and are not part of the game.
"""
import json, os, sys
import numpy as np, cv2
from PIL import Image
from paths import ref, ROOT

renders = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'app', 'build', 'renders')
out_dir = sys.argv[2] if len(sys.argv) > 2 else renders
REF = {'home': np.asarray(Image.open(ref('home_crop.png')).convert('RGB')).astype(np.float32),
       'level': np.asarray(Image.open(ref('lvl_crop.png')).convert('RGB')).astype(np.float32)}
HOME_META = json.load(open(os.path.join(ROOT, 'app-assets', 'home', '_meta.json')))


def to_screen(img, s, ox, oy, w, h, interp=cv2.INTER_LINEAR):
    """Reference image -> screen, like the app draws it (pixel centres at +0.5)."""
    M = np.float32([[s, 0, ox + 0.5 * s - 0.5], [0, s, oy + 0.5 * s - 0.5]])
    return cv2.warpAffine(img, M, (w, h), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def box_mask(s, ox, oy, w, h, x0, y0, x1, y1):
    m = np.zeros((h, w), bool)
    m[int(np.ceil(oy + y0 * s)):int(oy + y1 * s), int(np.ceil(ox + x0 * s)):int(ox + x1 * s)] = True
    return m


def sprite_mask(s, ox, oy, w, h):
    """Where the coin counter, + and gear sprites are opaque, in screen px."""
    m = np.zeros((h, w), np.float32)
    for name in ('coin_pill', 'plus', 'gear'):
        e = HOME_META[name]
        a = np.asarray(Image.open(os.path.join(ROOT, 'app-assets', 'home', name + '.png')).convert('RGBA'))[..., 3]
        full = np.zeros((1157, 628), np.float32)
        full[e['y']:e['y'] + a.shape[0], e['x']:e['x'] + a.shape[1]] = a / 255
        m = np.maximum(m, to_screen(full, s, ox, oy, w, h))
    return m > 0.98


rows = []
sheets = {}
for fn in sorted(os.listdir(renders)):
    if not fn.endswith('.json') or not (fn.startswith('home_') or fn.startswith('level')):
        continue
    kind, device = fn[:-5].split('_', 1)
    if kind != 'level' and kind not in REF:
        lvj = os.path.join(ROOT, 'app-assets', kind, 'level.json')
        refname = json.load(open(lvj)).get('reference', kind) if os.path.exists(lvj) else kind
        rp = os.path.join(ROOT, 'reference', 'screens', refname + '.png')
        if not os.path.exists(rp):
            continue
        REF[kind] = np.asarray(Image.open(rp).convert('RGB')).astype(np.float32)
    L = json.load(open(os.path.join(renders, fn)))
    img = np.asarray(Image.open(os.path.join(renders, fn[:-5] + '.png')).convert('RGB')).astype(np.float32)
    w, h, s_ = L['w'], L['h'], L['s']
    parts = []
    if kind == 'home':
        parts.append(('main', L['oy'], box_mask(s_, L['ox'], L['oy'], w, h, 0, 160, 628, 1150)))
        parts.append(('top', L['top_oy'], sprite_mask(s_, L['ox'], L['top_oy'], w, h)))
    elif kind != 'level':
        lv = json.load(open(os.path.join(ROOT, 'app-assets', kind, 'level.json')))
        c = lv['content']
        # inside the reference phone's bezel (the app shows the scene edge to edge instead)
        parts.append(('scene', L['oy'], box_mask(s_, L['ox'], L['oy'], w, h, 4, c['top'], lv['art']['w'] - 8, c['bottom'])))
    else:
        parts.append(('scene', L['oy'], box_mask(s_, L['ox'], L['oy'], w, h, 0, 66, 622, 960)))
        if device == 'reference_level':
            parts.append(('full', L['oy'], box_mask(s_, L['ox'], L['oy'], w, h, 0, 66, 622, 1150)))
    for name, oy, mask in parts:
        expect = to_screen(REF[kind], s_, L['ox'], oy, w, h)
        d = np.abs(img - expect).mean(-1)
        m, bad = float(d[mask].mean()), float((d[mask] > 40).mean() * 100)
        rows.append((kind, device, name, w, h, s_, m, bad))
        if (device in ('reference_home', 'reference_level') and name in ('main', 'full')) or (kind != 'level' and device == 'reference'):
            ys, xs = np.where(mask)
            sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
            heat = cv2.applyColorMap(np.clip(d[sl] * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)[..., ::-1]
            sheets[kind] = np.concatenate([expect[sl], img[sl], heat.astype(np.float32)], 1)

print('%-6s %-22s %-6s %11s %7s  %s  %s' % ('screen', 'device', 'part', 'size', 'scale', 'mean diff', '% px off >40'))
for kind, device, name, w, h, s, m, bad in rows:
    print('%-6s %-22s %-6s %5dx%-5d %7.4f  %6.2f/255  %6.2f%%' % (kind, device, name, w, h, s, m, bad))
json.dump([dict(zip(('screen', 'device', 'part', 'w', 'h', 'scale', 'mean_diff', 'pct_off'), r)) for r in rows],
          open(os.path.join(out_dir, 'compare.json'), 'w'), indent=1)
for kind, sh in sheets.items():
    Image.fromarray(np.clip(sh, 0, 255).astype(np.uint8)).save(os.path.join(out_dir, f'compare_{kind}_reference_vs_app_vs_diff.png'))
