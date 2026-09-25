"""Compose the new Level 8 screen: painted sky + 3D render + light glow + sparkles + the HUD.

  python3 compose.py RENDER.png PORTRAIT.png OUT.png [--hud]

All drawing is at the render's resolution (2x the art px when rendered full size); the HUD is drawn
with vector shapes and the game's font (Lilita One), so it is as crisp as the 3D art.
"""
import sys, os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sky

FONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts', 'LilitaOne-Regular.ttf')
ART_W, ART_H = 724, 1570


def glow(img, thresh=0.88, s=1.0):
    """Bloom: very bright pixels (lamps, lanterns, gold highlights) bleed soft light around them."""
    lum = img.mean(-1) / 255
    b = np.clip((lum - thresh) / (1 - thresh), 0, 1)[..., None] * img
    g = cv2.GaussianBlur(b, (0, 0), 6 * s) * 0.55 + cv2.GaussianBlur(b, (0, 0), 22 * s) * 0.45
    return np.clip(img + g * 0.9, 0, 255)


def sparkle(layer, x, y, r, a=1.0):
    """A 4-pointed twinkle."""
    d = ImageDraw.Draw(layer)
    col = (255, 244, 200, int(255 * a))
    w = max(1, r * 0.16)
    d.polygon([(x, y - r), (x + w, y - w), (x + r, y), (x + w, y + w), (x, y + r), (x - w, y + w), (x - r, y), (x - w, y - w)], fill=col)
    d.ellipse([x - w * 1.3, y - w * 1.3, x + w * 1.3, y + w * 1.3], fill=(255, 255, 255, int(255 * a)))


class Hud:
    """The Color Pop HUD, drawn at scale k (art px -> image px)."""
    NAVY = (14, 26, 64); RIM = (64, 206, 255); EDGE = (6, 12, 30)

    def __init__(self, img, k):
        self.base = img.convert('RGBA')
        self.k = k
        self.S = 3                       # supersampling for smooth edges
        W, H = self.base.size
        self.layer = Image.new('RGBA', (W * self.S, H * self.S), (0, 0, 0, 0))

    def f(self, v):
        return v * self.k * self.S

    def rrect(self, box, r, fill, outline=None, width=0):
        d = ImageDraw.Draw(self.layer)
        b = [self.f(v) for v in box]
        d.rounded_rectangle(b, radius=self.f(r), fill=fill, outline=outline, width=int(self.f(width)))

    def panel(self, box, r=26, alpha=200):
        x0, y0, x1, y1 = box
        self.rrect((x0, y0 + 5, x1, y1 + 5), r, (0, 0, 0, 90))                       # drop shadow
        self.rrect(box, r, (*self.EDGE, 235))
        self.rrect((x0 + 3, y0 + 3, x1 - 3, y1 - 3), r - 3, (*self.RIM, 255))
        self.rrect((x0 + 6, y0 + 6, x1 - 6, y1 - 6), r - 6, (*self.NAVY, alpha))
        # gloss on the upper part
        g = Image.new('RGBA', self.layer.size, (0, 0, 0, 0))
        dg = ImageDraw.Draw(g)
        dg.rounded_rectangle([self.f(x0 + 9), self.f(y0 + 9), self.f(x1 - 9), self.f(y0 + (y1 - y0) * 0.46)],
                             radius=self.f(r - 9), fill=(255, 255, 255, 34))
        self.layer.alpha_composite(g)

    def text(self, s, x, y, size, align='left', fill_top=(255, 255, 255), fill_bot=(228, 232, 245), outline=(6, 12, 28),
             ow=3.5, shadow=3.0, scale_x=0.92):
        """Game lettering: gradient fill, dark outline, the outline repeated lower as a shadow.
        (x, y) = left / centre / right of the ink, top of the capitals."""
        S = self.S
        font = ImageFont.truetype(FONT, int(self.f(size)))
        stroke = int(self.f(ow))
        tw = int(font.getlength(s)) + 4 * stroke
        th = int(self.f(size) * 1.5)
        def mask(extra):
            m = Image.new('L', (tw, th), 0)
            ImageDraw.Draw(m).text((2 * stroke, 0), s, font=font, fill=255, stroke_width=extra, stroke_fill=255)
            return m.resize((max(1, int(tw * scale_x)), th), Image.LANCZOS)
        fm, om = mask(0), mask(stroke)
        bb = fm.getbbox()
        px = {'left': self.f(x) - bb[0], 'center': self.f(x) - (bb[0] + bb[2]) / 2, 'right': self.f(x) - bb[2]}[align]
        py = self.f(y) - bb[1]
        grad = Image.new('RGBA', fm.size)
        ga = np.zeros((fm.size[1], fm.size[0], 4), np.uint8)
        t = np.clip((np.arange(fm.size[1]) - bb[1]) / max(1, bb[3] - bb[1]), 0, 1)[:, None]
        for c in range(3):
            ga[..., c] = (fill_top[c] * (1 - t) + fill_bot[c] * t).astype(np.uint8)
        ga[..., 3] = np.asarray(fm)
        grad = Image.fromarray(ga, 'RGBA')
        ol = Image.new('RGBA', om.size, (*outline, 255)); ol.putalpha(om)
        if shadow:
            self.layer.alpha_composite(ol, (int(px), int(py + self.f(shadow))))
        self.layer.alpha_composite(ol, (int(px), int(py)))
        self.layer.alpha_composite(grad, (int(px), int(py)))

    def paste(self, im, box):
        x0, y0, x1, y1 = [int(self.f(v)) for v in box]
        self.layer.alpha_composite(im.convert('RGBA').resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))

    def done_rgba(self):
        small = self.layer.resize(self.base.size, Image.LANCZOS)
        out = self.base.copy()
        out.alpha_composite(small)
        return out

    def done(self):
        return self.done_rgba().convert('RGB')


def stopwatch(size):
    S = 4 * size
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    red = (236, 52, 52, 255)
    d.rounded_rectangle([S * 0.40, S * 0.02, S * 0.60, S * 0.16], radius=S * 0.04, fill=red)
    d.ellipse([S * 0.1, S * 0.15, S * 0.9, S * 0.95], outline=red, width=int(S * 0.1))
    d.line([S * 0.5, S * 0.55, S * 0.5, S * 0.32], fill=(255, 255, 255, 255), width=int(S * 0.08))
    d.line([S * 0.5, S * 0.55, S * 0.66, S * 0.55], fill=(255, 255, 255, 255), width=int(S * 0.07))
    return im


def flame(size):
    """A cartoon flame: outer orange tongue with two side licks, a yellow core."""
    import math
    S = 4 * size
    def shape(cx, base, w, h, lean=0.0):
        pts = []
        for i in range(120):
            t = i / 119
            a = t * 2 * math.pi
            # teardrop: round bottom, pointed top that leans
            x = math.sin(a) * w * (1 - 0.55 * max(0.0, math.cos(a)) ** 0.6)
            y = -math.cos(a) * h * (0.35 if math.cos(a) < 0 else 1.0)
            x += lean * max(0.0, -y / h) ** 2 * w
            pts.append(((cx + x) * S, (base + y) * S))
        return pts
    m = Image.new('L', (S, S), 0)
    d = ImageDraw.Draw(m)
    d.polygon(shape(0.5, 0.74, 0.30, 0.66, lean=0.25), fill=255)
    d.polygon(shape(0.30, 0.80, 0.14, 0.42, lean=-0.8), fill=255)
    d.polygon(shape(0.72, 0.80, 0.13, 0.36, lean=0.9), fill=255)
    core = Image.new('L', (S, S), 0)
    ImageDraw.Draw(core).polygon(shape(0.52, 0.80, 0.15, 0.36, lean=0.2), fill=255)
    core = core.filter(ImageFilter.GaussianBlur(S * 0.015))
    y = np.linspace(0, 1, S)[:, None] * np.ones((1, S))
    g = np.zeros((S, S, 4), np.uint8)
    g[..., 0] = 255
    g[..., 1] = (40 + 130 * y).astype(np.uint8)
    g[..., 2] = (10 + 20 * y).astype(np.uint8)
    g[..., 3] = np.asarray(m)
    im = Image.fromarray(g, 'RGBA')
    yl = Image.new('RGBA', (S, S), (255, 238, 130, 255))
    yl.putalpha(core)
    im.alpha_composite(yl)
    return im


# the live numbers (drawn by the app; level.json "live_text") -- art px, Lilita One, like OutlineText
WHITE = {'fill_top': [255, 255, 255], 'fill_bottom': [228, 232, 245], 'outline_color': [6, 12, 28]}
LIVE = {
    'timer':  dict(WHITE, box=[568, 120, 700, 152], align='left', size=42, scale_x=0.86, outline=3.5, shadow=2.0),
    'target': dict(WHITE, box=[586, 238, 666, 300], align='center', size=86, scale_x=0.92, outline=4.0, shadow=3.0),
    'score':  dict(WHITE, box=[0, 382, 574, 414], align='left', size=44, scale_x=0.92, outline=3.5, shadow=2.5),
}
SCORE_LABEL = 'SCORE: '
REFERENCE_STATE = {'timer': '00:20', 'left': '15', 'score': '2,480'}


def score_layout(k=1.0):
    """x of the "SCORE:" label and of the live number, so that "SCORE: 2,480" is centred at 362."""
    font = ImageFont.truetype(FONT, 400)
    f = 44 / 400 * 0.92
    full = SCORE_LABEL + REFERENCE_STATE['score']
    bb_full = font.getbbox(full)
    width = (bb_full[2] - bb_full[0]) * f
    xl = 362 - width / 2
    num_left = font.getlength(SCORE_LABEL) + font.getbbox(REFERENCE_STATE['score'])[0]
    xn = xl + (num_left - bb_full[0]) * f
    return round(xl, 1), round(xn, 1)


def live(h, key, text):
    sp = LIVE[key]
    x = (sp['box'][0] + sp['box'][2]) / 2 if sp['align'] == 'center' else sp['box'][0]
    h.text(text, x, sp['box'][1], sp['size'], align=sp['align'], fill_top=tuple(sp['fill_top']), fill_bot=tuple(sp['fill_bottom']),
           outline=tuple(sp['outline_color']), ow=sp['outline'], shadow=sp['shadow'], scale_x=sp['scale_x'])


def hud_static(h, portrait_path):
    """Everything of the HUD that does not change during play (drawn into the background)."""
    h.panel((250, 106, 474, 168), r=24, alpha=190)
    h.text('LEVEL 8', 362, 118, 44, align='center', shadow=2.5)
    h.panel((488, 102, 700, 172), r=30, alpha=220)
    h.paste(stopwatch(60), (510, 112, 556, 158))
    h.panel((26, 204, 698, 344), r=26, alpha=205)
    if portrait_path:
        h.paste(Image.open(portrait_path), (38, 196, 176, 334))
    h.text('HIT THE GOLD ONES!', 184, 252, 42, shadow=2.5, fill_top=(255, 236, 140), fill_bot=(255, 178, 40), outline=(40, 16, 4), scale_x=0.9)
    h.panel((150, 366, 574, 436), r=30, alpha=170)
    xl, xn = score_layout()
    h.text(SCORE_LABEL.strip(), xl, 382, 44, shadow=2.5)


PAUSE = {'cx': 77, 'cy': 137, 'r': 43}
BANNER_BOX = (104, 1318, 620, 1438)


def pause_button(h):
    d = ImageDraw.Draw(h.layer)
    cx, cy, r = PAUSE['cx'], PAUSE['cy'], PAUSE['r']
    d.ellipse([h.f(cx - r), h.f(cy - r + 5), h.f(cx + r), h.f(cy + r + 5)], fill=(0, 0, 0, 90))
    d.ellipse([h.f(cx - r), h.f(cy - r), h.f(cx + r), h.f(cy + r)], fill=(*h.EDGE, 240))
    d.ellipse([h.f(cx - r + 4), h.f(cy - r + 4), h.f(cx + r - 4), h.f(cy + r - 4)], fill=(*h.RIM, 255))
    d.ellipse([h.f(cx - r + 8), h.f(cy - r + 8), h.f(cx + r - 8), h.f(cy + r - 8)], fill=(*h.NAVY, 235))
    for sx in (-1, 1):
        d.rounded_rectangle([h.f(cx + sx * 11 - 6), h.f(cy - 17), h.f(cx + sx * 11 + 6), h.f(cy + 17)], radius=h.f(3), fill=(255, 255, 255, 255))


def banner(h):
    x0, y0, x1, y1 = BANNER_BOX
    h.rrect((x0, y0 + 7, x1, y1 + 7), 60, (0, 0, 0, 110))
    h.rrect((x0, y0, x1, y1), 60, (70, 18, 6, 245))
    h.rrect((x0 + 4, y0 + 4, x1 - 4, y1 - 4), 56, (255, 128, 32, 255))
    h.rrect((x0 + 9, y0 + 9, x1 - 9, y1 - 9), 51, (38, 10, 20, 240))
    h.paste(flame(96), (118, 1322, 214, 1418))
    h.text('SPEED INCREASED!', 402, 1352, 50, align='center', fill_top=(255, 244, 150), fill_bot=(255, 150, 30), outline=(50, 12, 4),
           ow=4, shadow=3, scale_x=0.9)


def sprite_layer(size, k, draw):
    """Draw one HUD element on a transparent full-size layer (scale k), return it cropped: (RGBA, (x, y) px)."""
    h = Hud(Image.new('RGBA', size, (0, 0, 0, 0)), k)
    draw(h)
    img = h.done_rgba()
    bb = img.getbbox()
    x0, y0 = bb[0] - bb[0] % 2, bb[1] - bb[1] % 2
    return img.crop((x0, y0, bb[2] + bb[2] % 2, bb[3] + bb[3] % 2)), (x0, y0)


def scene_image(render_path):
    rgba = np.asarray(Image.open(render_path).convert('RGBA')).astype(np.float32)
    H, W = rgba.shape[:2]
    a = rgba[..., 3:] / 255
    return glow(rgba[..., :3] * a + sky.sky(W, H) * (1 - a), s=W / ART_W / 2), W / ART_W


def gold_glow(img, gold_centres, k):
    """The gold miners' halo (added to img) and their sparkles (an RGBA layer)."""
    H, W = img.shape[:2]
    halo = np.zeros((H, W), np.float32)
    for (cx, cy, r) in gold_centres:
        cv2.circle(halo, (int(cx * k), int(cy * k)), int(r * 0.95 * k), 1.0, -1, cv2.LINE_AA)
    halo = cv2.GaussianBlur(halo, (0, 0), 26 * k / 2)
    img = np.clip(img + halo[..., None] * np.array([255, 170, 40.0]) * 0.17, 0, 255)
    sp = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    rnd = np.random.default_rng(5)
    for (cx, cy, r) in gold_centres:
        for i in range(5):
            ang = rnd.uniform(0, 2 * np.pi); d = r * rnd.uniform(0.8, 1.25)
            sparkle(sp, (cx + d * np.cos(ang)) * k, (cy - abs(d * np.sin(ang)) * 0.9) * k, rnd.uniform(8, 16) * k, rnd.uniform(0.7, 1.0))
    return img, sp


def compose(render_path, portrait_path, out_path, hud=True, gold_centres=(), state=None):
    """The mockup (the approved one was made with this function)."""
    state = state or dict(REFERENCE_STATE, banner=True)
    img, k = scene_image(render_path)
    img, sp = gold_glow(img, gold_centres, k)
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
    base.alpha_composite(sp.filter(ImageFilter.GaussianBlur(3 * k))); base.alpha_composite(sp)
    if not hud:
        base.convert('RGB').save(out_path)
        return
    h = Hud(base, k)
    pause_button(h)
    hud_static(h, portrait_path)
    live(h, 'timer', state['timer'])
    live(h, 'target', state['left'])
    xl, xn = score_layout()
    LIVE['score']['box'][0] = xn
    live(h, 'score', state['score'])
    if state.get('banner'):
        banner(h)
    h.done().save(out_path)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    import json
    gold = json.loads(open(args[3]).read()) if len(args) > 3 else []
    compose(args[0], args[1], args[2], hud='--nohud' not in sys.argv, gold_centres=gold)
