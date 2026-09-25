"""Compose the new Level 3 screen: painted sky + 3D render + the HUD, all at 2x the art resolution.

  python3 compose.py RENDER.png PORTRAIT.png OUT.png

The HUD is the reference's (Level 3 layout: score on the left, the combo badge on the right), drawn
with vector shapes and the game's font (Lilita One) by the Level 8 compositor's Hud, so it is as
crisp as the 3D art.
"""
import sys, os, importlib.util
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C8 = _load('compose8', os.path.join(HERE, '..', 'level8_3d', 'compose.py'))
sky3 = _load('sky3', os.path.join(HERE, 'sky.py'))
Hud = C8.Hud
ART_W, ART_H = 724, 1570

REFERENCE_STATE = {'timer': '00:18', 'left': '8', 'score': '320', 'combo': 3}
COMBO_TEXT = dict(fill_top=(255, 244, 120), fill_bot=(246, 150, 20), outline=(48, 18, 6))
SCORE_BOX = (26, 366, 392, 436)


def scene_image(render_path):
    rgba = np.asarray(Image.open(render_path).convert('RGBA')).astype(np.float32)
    H, W = rgba.shape[:2]
    a = rgba[..., 3:] / 255
    return C8.glow(rgba[..., :3] * a + sky3.sky(W, H) * (1 - a), thresh=0.94, s=W / ART_W / 2), W / ART_W


def hud(h, portrait_path, state):
    C8.pause_button(h)
    h.panel((250, 106, 474, 168), r=24, alpha=190)
    h.text('LEVEL 3', 362, 118, 44, align='center', shadow=2.5)
    h.panel((488, 102, 700, 172), r=30, alpha=220)
    h.paste(C8.stopwatch(60), (510, 112, 556, 158))
    h.text(state['timer'], 568, 120, 42, scale_x=0.86, shadow=2.0)
    h.panel((26, 204, 698, 344), r=26, alpha=205)
    if portrait_path:
        h.paste(Image.open(portrait_path), (24, 180, 186, 342))
    h.text('HIT THE PURPLE ONES!', 184, 252, 40, shadow=2.5, scale_x=0.88)
    h.text(state['left'], 626, 238, 86, align='center', ow=4.0, shadow=3.0)
    h.panel(SCORE_BOX, r=30, alpha=170)
    h.text('SCORE: ' + state['score'], (SCORE_BOX[0] + SCORE_BOX[2]) / 2, 382, 44, align='center', shadow=2.5)


def combo_badge(size, k, n):
    """'3x' over 'COMBO!', tilted like the reference (drawn level, then turned 5 degrees)."""
    h = Hud(Image.new('RGBA', size, (0, 0, 0, 0)), k)
    h.text('%dx' % n, 572, 358, 66, align='center', ow=6.5, shadow=4.0, scale_x=1.08, **COMBO_TEXT)
    h.text('COMBO!', 572, 426, 64, align='center', ow=6.5, shadow=4.0, scale_x=1.0, **COMBO_TEXT)
    return h.done_rgba().rotate(5, resample=Image.BICUBIC, center=(572 * k, 426 * k))


def compose(render_path, portrait_path, out_path, state=None, hud_on=True):
    state = state or REFERENCE_STATE
    img, k = scene_image(render_path)
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
    if not hud_on:
        base.convert('RGB').save(out_path)
        return
    h = Hud(base, k)
    hud(h, portrait_path, state)
    screen = h.done_rgba()
    screen.alpha_composite(combo_badge(screen.size, k, state['combo']))
    screen.convert('RGB').save(out_path)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    compose(args[0], args[1], args[2], hud_on='--nohud' not in sys.argv)
