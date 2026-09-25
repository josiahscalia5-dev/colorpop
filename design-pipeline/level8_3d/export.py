"""Export the new Level 8 (approved mockup, Blender renders) into the app: app-assets/level8/.

  python3 export.py RENDER_DIR PORTRAIT.png

RENDER_DIR is what render_assets.py wrote. Everything is at twice the art resolution (art frame
724 x 1570 px; level.json entries carry "scale": 2), as crisp as Level 1 on a phone.

  bg.png        painted sky + the scene without characters + light bloom + the fixed HUD
                (panels, LEVEL 8, stopwatch, portrait, HIT THE GOLD ONES!, SCORE:), 24 art px of
                blurred reflection each side
  char_*.png    one per character of the reference moment (5 gold, the yellow and brown decoys);
                the app clips them at their hole's measured front edge
  glow_*.png    the gold miners' light (halo, sparkles, headlamp bloom): an additive layer
  pause.png, banner.png, level.json (rules unchanged)
The approved mockup is the visual reference: reference/level8_new/mockup.png (2x) and its art-size
version reference/screens/level8_new.png, which compare_renders.py uses for Level 8.
"""
import os, sys, json
import numpy as np, cv2
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose
from compose import Hud, ART_W, ART_H

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'app-assets', 'level8')
K = 2                                     # image px per art px
E = 140                                   # art px beyond each side of the screen (characters at the edges)
# gold miners' glow centres (art px: x, y, radius) -- as in the approved mockup
HOLE_ART = {'H1': (214, 700), 'H2': (510, 700), 'H3': (66, 852), 'H4': (362, 842), 'H5': (658, 852),
            'H6': (206, 1012), 'H7': (518, 1012), 'H8': (362, 1200)}
GOLD_SCALE = {'H1': 0.75, 'H4': 0.85, 'H5': 0.85, 'H7': 1.0, 'H8': 1.2}
GOLD = {k: (HOLE_ART[k][0], HOLE_ART[k][1] - 80 * s, 95 * s) for k, s in GOLD_SCALE.items()}


def gold_light():
    """Per gold miner: its halo + its sparkles (the same ones as in the approved mockup), full frame."""
    from compose import sparkle
    rnd = np.random.default_rng(5)
    out = {}
    for kk, (cx, cy, r) in GOLD.items():
        halo = np.zeros((ART_H * K, (ART_W + 2 * E) * K), np.float32)
        cx = cx + E
        cv2.circle(halo, (int(cx * K), int(cy * K)), int(r * 0.95 * K), 1.0, -1, cv2.LINE_AA)
        halo = cv2.GaussianBlur(halo, (0, 0), 26 * K / 2)
        light = halo[..., None] * np.array([255, 170, 40.0]) * 0.17
        sp = Image.new('RGBA', ((ART_W + 2 * E) * K, ART_H * K), (0, 0, 0, 0))
        for i in range(5):
            ang = rnd.uniform(0, 2 * np.pi); d = r * rnd.uniform(0.8, 1.25)
            sparkle(sp, (cx + d * np.cos(ang)) * K, (cy - abs(d * np.sin(ang)) * 0.9) * K, rnd.uniform(8, 16) * K, rnd.uniform(0.7, 1.0))
        for layer in (sp.filter(ImageFilter.GaussianBlur(3 * K)), sp):
            la = np.asarray(layer).astype(np.float32)
            light = light + la[..., :3] * la[..., 3:] / 255
        out[kk] = light
    return out
RULES_FROM = os.path.join(OUT, 'level.json')      # the rules stay exactly as they are


def save_rgba(path, arr):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA').save(path, optimize=True)


def srgb_to_linear(v):
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def front_edges(rim_path, geo):
    """Per hole, the top of its front rim stones seen from the camera, one y per art column."""
    rim = np.asarray(Image.open(rim_path).convert('RGBA')).astype(np.float32)
    ids = np.round(srgb_to_linear(rim[..., 0] / 255) * 10) * (rim[..., 3] > 128)
    keys = list(geo)
    edges = {}
    for i, k in enumerate(keys):
        cx, cy, a, b = geo[k]['opening']
        m = ids == (i + 1)
        x0, x1 = int(np.ceil(cx - a)), int(np.floor(cx + a))
        ys = []
        for x in range(x0, x1 + 1):
            arc = cy + b * np.sqrt(max(0.0, 1 - ((x + 0.5 - cx) / a) ** 2))
            best = None
            for xx in (2 * x, 2 * x + 1):
                if not 0 <= xx < m.shape[1]:
                    continue
                col = np.where(m[int(2 * cy):, xx])[0]
                if len(col):
                    y = (col[0] + int(2 * cy)) / 2
                    best = y if best is None else min(best, y)
            ys.append(arc if best is None else max(cy, best))
        ys = np.array(ys)
        sm = ys.copy()
        for j in range(1, len(ys) - 1):
            sm[j] = np.median(ys[j - 1:j + 2])
        edges[k] = {'x0': x0, 'y': [round(float(v), 2) for v in sm]}
    return edges


def hides_mask(hole, W, H):
    """Where the front rim hides a character in this hole (as LevelScreen.Hole.hides), image px."""
    cx, cy, a, b = hole['opening']
    ys = np.array(hole['edge']['y']); x0 = hole['edge']['x0']
    Y, X = np.mgrid[0:H, 0:W] / K + 0.5 / K
    xi = np.clip(np.floor(X - 0.5 - x0).astype(int), 0, len(ys) - 1)
    return (Y >= cy) & ((X < cx - a) | (X > cx + a) | (Y >= ys[xi]))


def cast_light(full_render, bg_render, level, sprites):
    """What the gold miners add around them in the approved mockup: their halo and sparkles, their
    headlamp bloom and the light they throw on their rims and holes = max(mockup - background with
    the characters, 0). Returns the full-frame RGB light (to share out per miner)."""
    img, _ = compose.scene_image(full_render)
    img, sp = compose.gold_glow(img, list(GOLD.values()), K)
    m = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
    m.alpha_composite(sp.filter(ImageFilter.GaussianBlur(3 * K))); m.alpha_composite(sp)
    mock = np.asarray(m.convert('RGB')).astype(np.float32)
    parts, _ = compose.scene_image(bg_render)
    H, W = parts.shape[:2]
    for hk in sorted(level['holes'], key=lambda k: level['holes'][k]['opening'][1]):
        if hk not in sprites:
            continue
        rgba, x2, y2 = sprites[hk]
        vis = ~hides_mask(level['holes'][hk], W, H)
        xa, ya, xb, yb = max(0, x2), max(0, y2), min(W, x2 + rgba.shape[1]), min(H, y2 + rgba.shape[0])
        sub = rgba[ya - y2:yb - y2, xa - x2:xb - x2]
        al = sub[..., 3:] / 255 * vis[ya:yb, xa:xb, None]
        parts[ya:yb, xa:xb] = parts[ya:yb, xa:xb] * (1 - al) + sub[..., :3] * al
    return cv2.GaussianBlur(np.clip(mock - parts, 0, 255), (0, 0), 0.8)


def trim(rgba, ox, oy):
    """Crop to the opaque part (even px offsets, so art px stay whole or half)."""
    a = rgba[..., 3]
    ys, xs = np.where(a > 2)
    x0, y0 = xs.min() - xs.min() % 2, ys.min() - ys.min() % 2
    x1, y1 = xs.max() + 1, rgba.shape[0]          # keep everything below (the body under the rim)
    x1 += x1 % 2
    return rgba[y0:y1, x0:x1], ox + x0, oy + y0


def main(render_dir, portrait, full_render):
    os.makedirs(OUT, exist_ok=True)
    geo = json.load(open(os.path.join(render_dir, 'geometry.json')))
    rules = json.load(open(RULES_FROM))['rules']
    level = {'id': 8, 'design': 'gold mine at night (design-pipeline/level8_3d)', 'reference': 'level8_new',
             'art': {'w': ART_W, 'h': ART_H}, 'content': {'top': 92, 'bottom': 1450}}

    # ------------------------------------------------ background: sky, scene, bloom, fixed HUD
    img, k = compose.scene_image(os.path.join(render_dir, 'bg_render.png'))
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
    h = Hud(base, K)
    compose.hud_static(h, portrait)
    bg = np.asarray(h.done()).astype(np.float32)
    PAD = 24
    full = cv2.copyMakeBorder(bg, 0, 0, PAD * K, PAD * K, cv2.BORDER_REFLECT_101)
    soft = cv2.GaussianBlur(full, (0, 0), 6 * K)
    ramp = np.clip((np.abs(np.arange(full.shape[1]) - (full.shape[1] - 1) / 2) - (ART_W * K / 2 - 1)) / (PAD * K), 0, 1)[None, :, None]
    Image.fromarray(np.clip(full * (1 - ramp) + soft * ramp, 0, 255).astype(np.uint8)).save(os.path.join(OUT, 'bg.png'), optimize=True)
    level['bg'] = {'file': 'level8/bg.png', 'pad_side': PAD, 'pad_top': 0, 'pad_bottom': 0, 'scale': K}

    # ------------------------------------------------ holes: opening + measured front edge
    edges = front_edges(os.path.join(render_dir, 'rim_ids.png'), geo)
    level['holes'] = {kk: {'opening': geo[kk]['opening'], 'edge': edges[kk]} for kk in sorted(geo)}

    # ------------------------------------------------ characters and the gold miners' light
    level['chars'] = {}
    synth = gold_light()
    # all sprites first (the light they add is measured with all of them in place)
    sprites = {}
    for fn in sorted(os.listdir(render_dir)):
        if fn.startswith('char_') and fn.endswith('.json'):
            meta = json.load(open(os.path.join(render_dir, fn)))
            rgba = np.asarray(Image.open(os.path.join(render_dir, fn[:-5] + '.png')).convert('RGBA')).astype(np.float32)
            sprites[meta['hole']] = trim(rgba, meta['x0'], meta['y0'])
    light = cast_light(full_render, os.path.join(render_dir, 'bg_render.png'), level, sprites)
    # share it out: each light pixel goes to the nearest gold miner
    gold_keys = [kk for kk in GOLD]
    Yg, Xg = np.mgrid[0:ART_H * K, 0:ART_W * K]
    dist = np.stack([np.hypot(Xg - GOLD[kk][0] * K, (Yg - GOLD[kk][1] * K) * 1.4) for kk in gold_keys])
    nearest = np.argmin(dist, 0)
    near_any = np.min(dist, 0) < 170 * K
    for fn in sorted(os.listdir(render_dir)):
        if not (fn.startswith('char_') and fn.endswith('.json')):
            continue
        meta = json.load(open(os.path.join(render_dir, fn)))
        kk, variant = meta['hole'], meta['variant']
        rgba, x2, y2 = sprites[kk]
        name = 'char_%s_%s' % (variant, kk)
        save_rgba(os.path.join(OUT, name + '.png'), rgba)
        e = {'file': 'level8/%s.png' % name, 'x': x2 / K, 'y': y2 / K, 'w': rgba.shape[1] / K, 'h': rgba.shape[0] / K,
             'scale': K, 'hole': kk, 'color': variant, 'role': 'target' if variant == 'gold' else 'distractor'}
        if variant == 'gold':
            # its share of the light: halo + sparkles around it, and the bloom of its own headlamp
            gx0, gy0 = max(-E * K, x2 - 60 * K), max(0, y2 - 60 * K)
            gx1, gy1 = min((ART_W + E) * K, x2 + rgba.shape[1] + 60 * K), min(ART_H * K, y2 + int(rgba.shape[0] * 0.75))
            mine = ((nearest == gold_keys.index(kk)) & near_any)[..., None] * light
            g = np.zeros((gy1 - gy0, gx1 - gx0, 3), np.float32)
            # inside the screen: the measured light; beyond its edge (a miner cut by it): the halo and
            # sparkles as drawn for the mockup
            g[:] = synth[kk][gy0:gy1, gx0 + E * K:gx1 + E * K]
            ia, ib = max(gx0, 0), min(gx1, ART_W * K)
            g[:, ia - gx0:ib - gx0] = mine[gy0:gy1, ia:ib]
            g = np.clip(g, 0, 255)
            gname = 'glow_' + kk
            Image.fromarray(g.astype(np.uint8)).save(os.path.join(OUT, gname + '.png'), optimize=True)
            e['glow'] = {'file': 'level8/%s.png' % gname, 'x': gx0 / K, 'y': gy0 / K, 'w': (gx1 - gx0) / K, 'h': (gy1 - gy0) / K, 'scale': K}
        level['chars'][name] = e

    # ------------------------------------------------ pause button, banner, live numbers
    size = (ART_W * K, ART_H * K)
    img_p, (px, py) = compose.sprite_layer(size, K, compose.pause_button)
    img_p.save(os.path.join(OUT, 'pause.png'), optimize=True)
    level['pause'] = {'file': 'level8/pause.png', 'x': px / K, 'y': py / K, 'w': img_p.size[0] / K, 'h': img_p.size[1] / K, 'scale': K,
                      'hit': dict(compose.PAUSE)}
    img_b, (bx, by) = compose.sprite_layer(size, K, compose.banner)
    img_b.save(os.path.join(OUT, 'banner.png'), optimize=True)
    level['banner'] = {'file': 'level8/banner.png', 'x': bx / K, 'y': by / K, 'w': img_b.size[0] / K, 'h': img_b.size[1] / K, 'scale': K}
    live = json.loads(json.dumps(compose.LIVE))
    live['score']['box'][0] = compose.score_layout()[1]
    level['live_text'] = live
    level['rules'] = rules
    json.dump(level, open(os.path.join(OUT, 'level.json'), 'w'), indent=1)
    # remove the previous design's files that are no longer used
    used = {os.path.basename(v['file']) for v in level['chars'].values()} | \
           {os.path.basename(v['glow']['file']) for v in level['chars'].values() if 'glow' in v} | {'bg.png', 'pause.png', 'banner.png', 'level.json'}
    for fn in os.listdir(OUT):
        if fn not in used:
            os.remove(os.path.join(OUT, fn))
    print('level8 exported:', sorted(os.listdir(OUT)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
