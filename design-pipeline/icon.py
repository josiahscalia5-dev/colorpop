"""Launcher icon cut from the reference Home art (the beaver's head) -> app/src/main/res/mipmap-*.

ic_launcher / ic_launcher_round: legacy icons (square with rounded corners / circle).
ic_launcher_background: full-bleed 108dp layer of the adaptive icon (API 26+); the head sits in
the 72dp safe zone, the launcher's mask cuts the rest.
"""
import os
import numpy as np
from PIL import Image, ImageDraw
from paths import ref, ROOT

home = Image.open(ref('home_crop.png')).convert('RGB')
CX, CY = 305, 612
RES = os.path.join(ROOT, 'app', 'src', 'main', 'res')
DENS = {'mdpi': 1, 'hdpi': 1.5, 'xhdpi': 2, 'xxhdpi': 3, 'xxxhdpi': 4}


def crop(size):
    return home.crop((CX - size // 2, CY - size // 2, CX + size // 2, CY + size // 2))


def mask(n, kind):
    S = 4
    m = Image.new('L', (n * S, n * S), 0)
    d = ImageDraw.Draw(m)
    if kind == 'round':
        d.ellipse((0, 0, n * S - 1, n * S - 1), fill=255)
    else:
        d.rounded_rectangle((0, 0, n * S - 1, n * S - 1), radius=int(n * S * 0.18), fill=255)
    return m.resize((n, n), Image.LANCZOS)


for name, k in DENS.items():
    out = os.path.join(RES, f'mipmap-{name}')
    os.makedirs(out, exist_ok=True)
    n = int(48 * k)
    face = crop(300).resize((n, n), Image.LANCZOS)
    for kind, fn in (('square', 'ic_launcher.png'), ('round', 'ic_launcher_round.png')):
        im = face.convert('RGBA')
        im.putalpha(mask(n, kind))
        im.save(os.path.join(out, fn), optimize=True)
    nb = int(108 * k)
    crop(int(300 * 108 / 72 * 0.8)).resize((nb, nb), Image.LANCZOS).save(os.path.join(out, 'ic_launcher_background.png'), optimize=True)
print('icons written to', RES)
