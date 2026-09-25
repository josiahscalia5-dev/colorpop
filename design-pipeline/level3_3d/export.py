"""Export the new Level 3 (approved mockup, Blender renders) into the app: app-assets/level3/.

  python3 export.py RENDER_DIR PORTRAIT.png FULL_RENDER.png

RENDER_DIR is what render_assets.py wrote (plus its --extra pass). Everything is at twice the art
resolution (art frame 724 x 1570 px; level.json entries carry "scale": 2), as crisp as Level 1.

  bg.png          painted sky + the scene without characters + bloom + the fixed HUD (panels,
                  LEVEL 3, stopwatch, icon, HIT THE PURPLE ONES!, SCORE:), 24 art px of blurred
                  reflection each side
  char_*.png      the opening wave's critters (2 purple, the pink, the red) and two pop-up-only decoy
                  looks for the big holes ("spawn_only"); the app clips them at their hole's front edge
  combo_word.png  "COMBO!" (the live "3x" above it is drawn by the app), pause.png
  hand.png        kept: the opening demonstration's glove (levels/level3_fire.py)
  level.json      Level 3's rules (gameplay unchanged); only the shots' launch point and the
                  demonstration's hole are given in the new frame
The approved design is the visual reference: reference/level3_new/mockup.png (2x) and its art-size
version reference/screens/level3_new.png (the reference moment as the app shows it, with the
demonstration's glove), which compare_renders.py uses for Level 3.
"""
import os, sys, json
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose
from compose import Hud, ART_W, ART_H, C8

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'app-assets', 'level3')
K = 2                                     # image px per art px
CONTENT_BOTTOM = 1450
FIRE_FROM = [362, CONTENT_BOTTOM]         # the shots leave from the player's side: bottom centre


def save_rgba(path, arr):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA').save(path, optimize=True)


def srgb_to_linear(v):
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def front_edges(rim_path, geo):
    """Per hole, the top of its front rim bricks seen from the camera, one y per art column."""
    rim = np.asarray(Image.open(rim_path).convert('RGBA')).astype(np.float32)
    ids = np.round(srgb_to_linear(rim[..., 0] / 255) * 10) * (rim[..., 3] > 128)
    edges = {}
    for i, k in enumerate(list(geo)):
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


def trim(rgba, ox, oy):
    """Crop to the opaque part (even px offsets); keep everything below (the body under the rim)."""
    ys, xs = np.where(rgba[..., 3] > 2)
    x0, y0 = xs.min() - xs.min() % 2, ys.min() - ys.min() % 2
    x1 = xs.max() + 1
    x1 += x1 % 2
    return rgba[y0:, x0:x1], ox + x0, oy + y0


def layer_sprite(img):
    """A full-frame RGBA layer cropped to its content: (RGBA, (x, y) px), even offsets."""
    bb = img.getbbox()
    x0, y0 = bb[0] - bb[0] % 2, bb[1] - bb[1] % 2
    return img.crop((x0, y0, bb[2] + bb[2] % 2, bb[3] + bb[3] % 2)), (x0, y0)


def main(render_dir, portrait, full_render):
    old = json.load(open(os.path.join(OUT, 'level.json')))
    geo = json.load(open(os.path.join(render_dir, 'geometry.json')))
    level = {'id': 3, 'design': 'farmyard rebuilt in 3D (design-pipeline/level3_3d)', 'reference': 'level3_new',
             'art': {'w': ART_W, 'h': ART_H}, 'content': {'top': 92, 'bottom': CONTENT_BOTTOM}}

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
    level['bg'] = {'file': 'level3/bg.png', 'pad_side': PAD, 'pad_top': 0, 'pad_bottom': 0, 'scale': K}

    # ------------------------------------------------ holes: opening + measured front edge
    edges = front_edges(os.path.join(render_dir, 'rim_ids.png'), geo)
    level['holes'] = {kk: {'opening': geo[kk]['opening'], 'edge': edges[kk]} for kk in sorted(geo)}

    # ------------------------------------------------ characters
    level['chars'] = {}
    for fn in sorted(os.listdir(render_dir)):
        if not ((fn.startswith('char_') or fn.startswith('extra_')) and fn.endswith('.json')):
            continue
        meta = json.load(open(os.path.join(render_dir, fn)))
        rgba = np.asarray(Image.open(os.path.join(render_dir, fn[:-5] + '.png')).convert('RGBA')).astype(np.float32)
        rgba, x2, y2 = trim(rgba, meta['x0'], meta['y0'])
        kk, variant = meta['hole'], meta['variant']
        name = 'char_%s_%s' % (variant, kk)
        save_rgba(os.path.join(OUT, name + '.png'), rgba)
        e = {'file': 'level3/%s.png' % name, 'x': x2 / K, 'y': y2 / K, 'w': rgba.shape[1] / K, 'h': rgba.shape[0] / K,
             'scale': K, 'hole': kk, 'color': variant, 'role': 'target' if variant == 'purple' else 'distractor'}
        if meta.get('extra'):
            e['spawn_only'] = True
        level['chars'][name] = e

    # ------------------------------------------------ combo badge, pause button, live numbers, glove
    size = (ART_W * K, ART_H * K)
    word, (wx, wy) = layer_sprite(compose.combo_word(size, K))
    word.save(os.path.join(OUT, 'combo_word.png'), optimize=True)
    level['combo'] = {'word': {'file': 'level3/combo_word.png', 'x': wx / K, 'y': wy / K, 'w': word.size[0] / K, 'h': word.size[1] / K,
                               'scale': K},
                      'number': json.loads(json.dumps(compose.COMBO_NUMBER))}
    img_p, (px, py) = C8.sprite_layer(size, K, C8.pause_button)
    img_p.save(os.path.join(OUT, 'pause.png'), optimize=True)
    level['pause'] = {'file': 'level3/pause.png', 'x': px / K, 'y': py / K, 'w': img_p.size[0] / K, 'h': img_p.size[1] / K, 'scale': K,
                      'hit': dict(C8.PAUSE)}
    live = json.loads(json.dumps(compose.LIVE))
    live['score']['box'][0] = compose.score_layout()[1]
    level['live_text'] = live
    level['hand'] = old['hand']
    # ------------------------------------------------ rules: unchanged, in the new frame
    rules = old['rules']
    rules['fire']['from'] = FIRE_FROM
    rules['demo']['hole'] = 'H4'                      # the front purple, as before
    level['rules'] = rules
    json.dump(level, open(os.path.join(OUT, 'level.json'), 'w'), indent=1)
    # remove the previous design's files that are no longer used
    used = {os.path.basename(v['file']) for v in level['chars'].values()} | \
           {'bg.png', 'pause.png', 'combo_word.png', 'hand.png', 'level.json'}
    for fn in os.listdir(OUT):
        if fn not in used:
            os.remove(os.path.join(OUT, fn))
    print('level3 exported:', sorted(os.listdir(OUT)))
    reference(full_render, portrait, level)


def reference(full_render, portrait, level):
    """The approved design in the app's reference moment (LevelScreen.referenceMoment: every critter of
    the opening wave up, the rules' reference_state on the HUD, the demonstration's glove over the
    front purple): reference/level3_new/mockup.png (2x) and reference/screens/level3_new.png (art px)."""
    st = level['rules']['reference_state']
    secs = int(round(level['rules']['duration'] - st['elapsed']))
    tmp = os.path.join(ROOT, 'design-pipeline', '_work', 'l3_reference_2x.png')
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    compose.compose(full_render, portrait, tmp, {'timer': '%02d:%02d' % (secs // 60, secs % 60), 'left': str(st['targets_left']),
                                                 'score': '{:,}'.format(st['score']), 'combo': st['combo']})
    img = Image.open(tmp).convert('RGBA')
    # the glove where the app draws it: its fingertip just off the middle of the demonstration purple
    hk = level['rules']['demo']['hole']
    ch = [c for c in level['chars'].values() if c['hole'] == hk and not c.get('spawn_only')][0]
    cx, cy, a, b = level['holes'][hk]['opening']
    front = cy + b
    tip_x, tip_y = ch['x'] + ch['w'] / 2 + 16, front - (front - ch['y']) * 0.45 + 12
    hand = level['hand']
    hx, hy = tip_x - (hand['tip'][0] - hand['x']), tip_y - (hand['tip'][1] - hand['y'])
    glove = Image.open(os.path.join(OUT, 'hand.png')).convert('RGBA').resize((int(round(hand['w'] * K)), int(round(hand['h'] * K))), Image.LANCZOS)
    img.alpha_composite(glove, (int(round(hx * K)), int(round(hy * K))))
    d = os.path.join(ROOT, 'reference', 'level3_new')
    os.makedirs(d, exist_ok=True)
    img.convert('RGB').save(os.path.join(d, 'mockup.png'), optimize=True)
    img.convert('RGB').resize((ART_W, ART_H), Image.LANCZOS).save(os.path.join(ROOT, 'reference', 'screens', 'level3_new.png'), optimize=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
