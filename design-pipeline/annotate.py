"""Helpers for measuring/checking reference geometry: zoomed crops with a grid and overlays."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from paths import ROOT

FONT = ROOT + '/design-pipeline/fonts/LilitaOne-Regular.ttf'


def zoom(img, box, scale=3, grid=10, ellipses=(), boxes=(), points=(), label_every=50):
    """Crop `box` (x0, y0, x1, y1) of `img` (PIL or array), enlarge, draw a grid every `grid` px
    (labelled every `label_every`), ellipses [(cx, cy, a, b, colour)], boxes and points."""
    if not isinstance(img, Image.Image):
        img = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    x0, y0, x1, y1 = box
    im = img.crop(box).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST).convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')
    f = ImageFont.truetype(FONT, 12)
    for x in range((x0 // grid + 1) * grid, x1, grid):
        major = x % label_every == 0
        d.line([((x - x0) * scale, 0), ((x - x0) * scale, im.size[1])], fill=(255, 255, 255, 90 if major else 35))
        if major:
            d.text(((x - x0) * scale + 2, 2), str(x), font=f, fill=(255, 0, 255))
    for y in range((y0 // grid + 1) * grid, y1, grid):
        major = y % label_every == 0
        d.line([(0, (y - y0) * scale), (im.size[0], (y - y0) * scale)], fill=(255, 255, 255, 90 if major else 35))
        if major:
            d.text((2, (y - y0) * scale + 2), str(y), font=f, fill=(255, 0, 255))
    for e in ellipses:
        cx, cy, a, b = e[:4]
        col = e[4] if len(e) > 4 else (0, 255, 255)
        pts = [((cx + a * np.cos(t) - x0) * scale, (cy + b * np.sin(t) - y0) * scale) for t in np.linspace(0, 2 * np.pi, 240)]
        d.line(pts + [pts[0]], fill=col, width=2)
    for bx in boxes:
        col = bx[4] if len(bx) > 4 else (255, 255, 0)
        d.rectangle([(bx[0] - x0) * scale, (bx[1] - y0) * scale, (bx[2] - x0) * scale, (bx[3] - y0) * scale], outline=col, width=2)
    for p in points:
        col = p[2] if len(p) > 2 else (255, 0, 0)
        d.ellipse([(p[0] - x0) * scale - 3, (p[1] - y0) * scale - 3, (p[0] - x0) * scale + 3, (p[1] - y0) * scale + 3], fill=col)
    return im
