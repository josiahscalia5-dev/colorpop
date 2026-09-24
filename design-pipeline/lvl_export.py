"""Level 1: collect everything the app needs into app-assets/level/level.json.

All coordinates are reference-crop pixels (lvl_crop.png, 622 wide). The app scales them to the
screen; see LevelLayout in the Android code.

Input: _work/lvl_hud.json, _work/lvl_ground.json, _work/lvl_front_edges.json,
       app-assets/level/characters/_meta.json
"""
import json
from paths import work, asset_dir

OUT = asset_dir('level')
hud = json.load(open(work('lvl_hud.json')))
ground = json.load(open(work('lvl_ground.json')))
fe = json.load(open(work('lvl_front_edges.json')))
opening, edge = fe['opening'], fe['edge']
chars = json.load(open(OUT + '/characters/_meta.json'))['chars']
COLOR = {'g': 'green', 'r': 'red', 'y': 'yellow'}
p = hud['pause']
level = {
    'art': {'w': ground['art_w'], 'h': ground['art_h']},
    'bg': {'file': 'level/bg.png', 'pad_side': ground['pad_side'], 'pad_top': ground['pad_top'],
           'pad_bottom': ground['pad_bottom']},
    'fg_bottom': dict(file='level/fg_bottom.png', **{k: ground['fg_bottom'][k] for k in ('x', 'y', 'w', 'h')}),
    'pause': {'file': 'level/pause.png', 'x': p['x'], 'y': p['y'], 'w': p['w'], 'h': p['h'],
              'hit': {'cx': p['cx'], 'cy': p['cy'], 'r': p['r']}},
    # opening ellipse [cx, cy, a, b]; 'edge': the real (bumpy) front edge a character disappears
    # behind, one y per column from x0 (the lower half of the ellipse outside the measured part)
    'holes': {h: {'opening': opening[h], 'edge': {'x0': edge[h]['x0'], 'y': edge[h]['y']}} for h in sorted(opening)},
    'chars': {k: {'file': f'level/characters/char_{k}.png', 'hole': c['hole'], 'color': COLOR[c['color']],
                  'x': c['x'], 'y': c['y'], 'w': c['w'], 'h': c['h']} for k, c in sorted(chars.items())},
    'live_text': {k: {kk: v[kk] for kk in ('box', 'align', 'size', 'scale_x', 'outline', 'shadow')}
                  for k, v in hud['live_text'].items()},
    'text_style': hud['text_style'],
}
json.dump(level, open(OUT + '/level.json', 'w'), indent=1)
print(json.dumps(level)[:400], '...')
