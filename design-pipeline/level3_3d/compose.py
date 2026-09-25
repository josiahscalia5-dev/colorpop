"""Compose the new Level 3 screen: painted sky + 3D render + the HUD, all at 2x the art resolution.

  python3 compose.py RENDER.png PORTRAIT.png OUT.png

The HUD is the reference's (Level 3 layout: score on the left, the combo badge on the right), drawn
with vector shapes and the game's font (Lilita One) by the Level 8 compositor's Hud, so it is as
crisp as the 3D art.
"""
import sys, os, json, importlib.util
import numpy as np
from PIL import Image, ImageFont

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


# the live numbers (drawn by the app; level.json "live_text"): the Level 8 HUD's slots
LIVE = json.loads(json.dumps(C8.LIVE))
SCORE_LABEL, SCORE_SAMPLE = 'SCORE: ', '320'
# the combo badge: "COMBO!" (a picture) under the live "3x", tilted 5 degrees like the reference
COMBO_X, COMBO_NUM_Y, COMBO_WORD_Y, COMBO_TILT = 572, 358, 426, 5.0
COMBO_NUMBER = dict(fill_top=[255, 244, 120], fill_bottom=[246, 150, 20], outline_color=[48, 18, 6],
                    box=[COMBO_X - 70, COMBO_NUM_Y, COMBO_X + 70, COMBO_NUM_Y + 50], align='center', size=66,
                    scale_x=1.08, outline=6.5, shadow=4.0, rotate=-COMBO_TILT)


def score_layout():
    """x of the "SCORE:" label and of the live number: "SCORE: 320" centred in the score panel."""
    font = ImageFont.truetype(C8.FONT, 400)
    f = 44 / 400 * 0.92
    full = SCORE_LABEL + SCORE_SAMPLE
    bb = font.getbbox(full)
    xl = (SCORE_BOX[0] + SCORE_BOX[2]) / 2 - (bb[2] - bb[0]) * f / 2
    xn = xl + (font.getlength(SCORE_LABEL) + font.getbbox(SCORE_SAMPLE)[0] - bb[0]) * f
    return round(xl, 1), round(xn, 1)


def hud_static(h, portrait_path):
    """Everything of the HUD that does not change during play (drawn into the background)."""
    h.panel((250, 106, 474, 168), r=24, alpha=190)
    h.text('LEVEL 3', 362, 118, 44, align='center', shadow=2.5)
    h.panel((488, 102, 700, 172), r=30, alpha=220)
    h.paste(C8.stopwatch(60), (510, 112, 556, 158))
    h.panel((26, 204, 698, 344), r=26, alpha=205)
    if portrait_path:
        h.paste(Image.open(portrait_path), (24, 180, 186, 342))
    h.text('HIT THE PURPLE ONES!', 184, 252, 40, shadow=2.5, scale_x=0.88)
    h.panel(SCORE_BOX, r=30, alpha=170)
    h.text(SCORE_LABEL.strip(), score_layout()[0], 382, 44, shadow=2.5)


def live(h, key, text):
    sp = LIVE[key]
    x = (sp['box'][0] + sp['box'][2]) / 2 if sp['align'] == 'center' else sp['box'][0]
    h.text(text, x, sp['box'][1], sp['size'], align=sp['align'], fill_top=tuple(sp['fill_top']), fill_bot=tuple(sp['fill_bottom']),
           outline=tuple(sp['outline_color']), ow=sp['outline'], shadow=sp['shadow'], scale_x=sp['scale_x'])


def _tilted(size, k, draw, cx, cy):
    """A HUD element drawn level on a transparent layer, then turned COMBO_TILT degrees about (cx, cy) art px."""
    h = Hud(Image.new('RGBA', size, (0, 0, 0, 0)), k)
    draw(h)
    return h.done_rgba().rotate(COMBO_TILT, resample=Image.BICUBIC, center=(cx * k, cy * k))


def combo_word(size, k):
    return _tilted(size, k, lambda h: h.text('COMBO!', COMBO_X, COMBO_WORD_Y, 64, align='center', ow=6.5, shadow=4.0,
                                             fill_top=(255, 244, 120), fill_bot=(246, 150, 20), outline=(48, 18, 6)),
                   COMBO_X, COMBO_WORD_Y + 22)


def combo_number(size, k, n):
    """As the app draws the live "3x" (OutlineText.Slot with rotate: about the middle of its digits)."""
    sp = COMBO_NUMBER
    digit_h = ImageFont.truetype(C8.FONT, 400).getbbox('0')
    digit_h = (digit_h[3] - digit_h[1]) / 400 * sp['size']
    def draw(h):
        h.text('%dx' % n, COMBO_X, sp['box'][1], sp['size'], align='center', ow=sp['outline'], shadow=sp['shadow'],
               scale_x=sp['scale_x'], fill_top=tuple(sp['fill_top']), fill_bot=tuple(sp['fill_bottom']), outline=tuple(sp['outline_color']))
    return _tilted(size, k, draw, COMBO_X, sp['box'][1] + digit_h / 2)


def compose(render_path, portrait_path, out_path, state=None, hud_on=True):
    """The mockup (the approved one was made from these same parts)."""
    state = state or REFERENCE_STATE
    img, k = scene_image(render_path)
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
    if not hud_on:
        base.convert('RGB').save(out_path)
        return
    h = Hud(base, k)
    C8.pause_button(h)
    hud_static(h, portrait_path)
    live(h, 'timer', state['timer'])
    live(h, 'target', state['left'])
    xl, xn = score_layout()
    LIVE['score']['box'][0] = xn
    live(h, 'score', state['score'])
    screen = h.done_rgba()
    if state.get('combo', 0) >= 2:
        screen.alpha_composite(combo_word(screen.size, k))
        screen.alpha_composite(combo_number(screen.size, k, state['combo']))
    screen.convert('RGB').save(out_path)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    compose(args[0], args[1], args[2], hud_on='--nohud' not in sys.argv)
