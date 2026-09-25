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

    def done(self):
        small = self.layer.resize(self.base.size, Image.LANCZOS)
        out = self.base.copy()
        out.alpha_composite(small)
        return out.convert('RGB')


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


def compose(render_path, portrait_path, out_path, hud=True, gold_centres=(), state=None):
    state = state or {'timer': '00:20', 'left': '15', 'score': '2,480', 'banner': True}
    rgba = np.asarray(Image.open(render_path).convert('RGBA')).astype(np.float32)
    H, W = rgba.shape[:2]
    k = W / ART_W
    a = rgba[..., 3:] / 255
    img = rgba[..., :3] * a + sky.sky(W, H) * (1 - a)
    img = glow(img, s=k / 2)
    halo = np.zeros((H, W), np.float32)
    for (cx, cy, r) in gold_centres:
        cv2.circle(halo, (int(cx * k), int(cy * k)), int(r * 0.95 * k), 1.0, -1, cv2.LINE_AA)
    halo = cv2.GaussianBlur(halo, (0, 0), 26 * k / 2)
    img = np.clip(img + halo[..., None] * np.array([255, 170, 40.0]) * 0.17, 0, 255)
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')
    # sparkles around the gold miners
    sp = Image.new('RGBA', base.size, (0, 0, 0, 0))
    rnd = np.random.default_rng(5)
    for (cx, cy, r) in gold_centres:
        for i in range(5):
            ang = rnd.uniform(0, 2 * np.pi); d = r * rnd.uniform(0.8, 1.25)
            sparkle(sp, (cx + d * np.cos(ang)) * k, (cy - abs(d * np.sin(ang)) * 0.9) * k, rnd.uniform(8, 16) * k, rnd.uniform(0.7, 1.0))
    sp_blur = sp.filter(ImageFilter.GaussianBlur(3 * k))
    base.alpha_composite(sp_blur); base.alpha_composite(sp)
    if not hud:
        base.convert('RGB').save(out_path)
        return
    h = Hud(base, k)
    # top bar: pause, LEVEL 8, timer
    d = ImageDraw.Draw(h.layer)
    cx, cy, r = 77, 137, 43
    d.ellipse([h.f(cx - r), h.f(cy - r + 5), h.f(cx + r), h.f(cy + r + 5)], fill=(0, 0, 0, 90))
    d.ellipse([h.f(cx - r), h.f(cy - r), h.f(cx + r), h.f(cy + r)], fill=(*h.EDGE, 240))
    d.ellipse([h.f(cx - r + 4), h.f(cy - r + 4), h.f(cx + r - 4), h.f(cy + r - 4)], fill=(*h.RIM, 255))
    d.ellipse([h.f(cx - r + 8), h.f(cy - r + 8), h.f(cx + r - 8), h.f(cy + r - 8)], fill=(*h.NAVY, 235))
    for sx in (-1, 1):
        d.rounded_rectangle([h.f(cx + sx * 11 - 6), h.f(cy - 17), h.f(cx + sx * 11 + 6), h.f(cy + 17)], radius=h.f(3), fill=(255, 255, 255, 255))
    h.panel((250, 106, 474, 168), r=24, alpha=190)
    h.text('LEVEL 8', 362, 118, 44, align='center', shadow=2.5)
    h.panel((488, 102, 700, 172), r=30, alpha=220)
    h.paste(stopwatch(60), (510, 112, 556, 158))
    h.text(state['timer'], 568, 120, 42, shadow=2.0, scale_x=0.86)
    # instruction panel with the gold miner's portrait and the targets left
    h.panel((26, 204, 698, 344), r=26, alpha=205)
    if portrait_path:
        h.paste(Image.open(portrait_path), (38, 196, 176, 334))
    h.text('HIT THE GOLD ONES!', 184, 252, 42, shadow=2.5, fill_top=(255, 236, 140), fill_bot=(255, 178, 40), outline=(40, 16, 4), scale_x=0.9)
    h.text(state['left'], 626, 238, 86, align='center', ow=4, shadow=3)
    # score
    h.panel((150, 366, 574, 436), r=30, alpha=170)
    h.text('SCORE: ' + state['score'], 362, 382, 44, align='center', shadow=2.5)
    if state.get('banner'):
        x0, y0, x1, y1 = 104, 1318, 620, 1438
        h.rrect((x0, y0 + 7, x1, y1 + 7), 60, (0, 0, 0, 110))
        h.rrect((x0, y0, x1, y1), 60, (70, 18, 6, 245))
        h.rrect((x0 + 4, y0 + 4, x1 - 4, y1 - 4), 56, (255, 128, 32, 255))
        h.rrect((x0 + 9, y0 + 9, x1 - 9, y1 - 9), 51, (38, 10, 20, 240))
        h.paste(flame(96), (118, 1322, 214, 1418))
        h.text('SPEED INCREASED!', 402, 1352, 50, align='center', fill_top=(255, 244, 150), fill_bot=(255, 150, 30), outline=(50, 12, 4),
               ow=4, shadow=3, scale_x=0.9)
    h.done().save(out_path)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    import json
    gold = json.loads(open(args[3]).read()) if len(args) > 3 else []
    compose(args[0], args[1], args[2], hud='--nohud' not in sys.argv, gold_centres=gold)
