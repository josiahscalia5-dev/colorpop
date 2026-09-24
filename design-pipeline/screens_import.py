"""Import the second reference sheet (Levels 3, 6, 8, 10, Level Complete, Worlds).

reference/sheet/color_pop_sheet.jpg is the owner's 8-screen sheet (each phone ~355 px wide).
reference/sheet/<screen>_4x.png are the owner's enlargements of single phones: exactly 4x the sheet
(registered to correlation 0.9995), cleaner than the JPEG sheet, but cropped: they miss a few px
at the phone edges, and for Levels 3 and 6 the bottom ~18 %.

Output, per screen: reference/screens/<screen>.png -- the phone interior at 2x the sheet (the
art coordinate system of that screen). Pixels come from the enlargement (area-downscaled 2x);
where it is missing, from the sheet upscaled with a filter learnt on the overlap so that both
parts have the same sharpness and colour.
"""
import os
import numpy as np, cv2
from PIL import Image
from paths import ROOT

SHEET = os.path.join(ROOT, 'reference', 'sheet', 'color_pop_sheet.jpg')
OUT = os.path.join(ROOT, 'reference', 'screens')
# phone boxes in sheet px (x0, y0, x1, y1), exclusive -- bounded by the white gaps between phones
PHONE = {'level3': (725, 0, 1076, 743), 'level6': (1085, 0, 1441, 743), 'level8': (0, 747, 362, 1532),
         'level10': (366, 746, 717, 1532), 'complete': (724, 747, 1081, 1532), 'worlds': (1086, 747, 1441, 1536)}
# where each enlargement's top-left pixel sits in the sheet (scale exactly 4)
ORIGIN = {'level3': (725, 3), 'level6': (1087, 3), 'level8': (3, 616), 'level10': (364, 616),
          'complete': (725, 616), 'worlds': (1087, 616)}
K = 2          # art px per sheet px
R = 4          # learnt filter radius (9x9)


def learn_filter(src, dst, valid):
    """Least-squares (2R+1)^2 kernel per channel with src * k ~ dst on `valid` pixels."""
    ys, xs = np.where(valid)
    rng = np.random.default_rng(1)
    pick = rng.choice(len(ys), size=min(60000, len(ys)), replace=False)
    ys, xs = ys[pick], xs[pick]
    ks = []
    for c in range(3):
        pad = cv2.copyMakeBorder(src[..., c], R, R, R, R, cv2.BORDER_REFLECT)
        A = np.stack([pad[ys + dy, xs + dx] for dy in range(2 * R + 1) for dx in range(2 * R + 1)], 1)
        A = np.concatenate([A, np.ones((len(ys), 1))], 1)
        sol, *_ = np.linalg.lstsq(A, dst[ys, xs, c], rcond=None)
        ks.append(sol)
    return ks


def apply_filter(src, ks):
    out = np.zeros_like(src)
    for c in range(3):
        k = ks[c][:-1].reshape(2 * R + 1, 2 * R + 1).astype(np.float32)
        out[..., c] = cv2.filter2D(src[..., c], -1, k, borderType=cv2.BORDER_REFLECT) + ks[c][-1]
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    sheet = np.asarray(Image.open(SHEET).convert('RGB')).astype(np.float32)
    for name, (x0, y0, x1, y1) in PHONE.items():
        w, h = (x1 - x0) * K, (y1 - y0) * K
        # sheet part, upscaled 2x (bicubic), phone box only
        sh = cv2.resize(sheet[y0:y1, x0:x1], (w, h), interpolation=cv2.INTER_CUBIC)
        # enlargement part, area-downscaled 4x -> 2x, placed in phone-box coordinates
        big = np.asarray(Image.open(os.path.join(ROOT, 'reference', 'sheet', f'{name}_4x.png')).convert('RGB')).astype(np.float32)
        up = cv2.resize(big, (big.shape[1] // 2, big.shape[0] // 2), interpolation=cv2.INTER_AREA)
        ox, oy = (ORIGIN[name][0] - x0) * K, (ORIGIN[name][1] - y0) * K
        canvas = np.zeros((h, w, 3), np.float32)
        have = np.zeros((h, w), bool)
        ya, yb = max(0, oy), min(h, oy + up.shape[0])
        xa, xb = max(0, ox), min(w, ox + up.shape[1])
        canvas[ya:yb, xa:xb] = up[ya - oy:yb - oy, xa - ox:xb - ox]
        have[ya:yb, xa:xb] = True
        # learn sheet -> enlargement on the overlap (away from its borders), fill the rest
        inner = cv2.erode(have.astype(np.uint8), np.ones((2 * R + 9, 2 * R + 9), np.uint8)).astype(bool)
        ks = learn_filter(sh, canvas, inner)
        filled = apply_filter(sh, ks)
        err_before = float(np.abs(sh[inner] - canvas[inner]).mean())
        err_after = float(np.abs(filled[inner] - canvas[inner]).mean())
        # soft seam: blend over 8 px inside the enlargement's edge
        wgt = cv2.distanceTransform(have.astype(np.uint8), cv2.DIST_L2, 5)
        wgt = np.clip(wgt / 8.0, 0, 1)[..., None]
        out = canvas * wgt + filled * (1 - wgt)
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(OUT, name + '.png'), optimize=True)
        print('%-8s %dx%d  from enlargement %.0f%%  sheet->enlargement filter: error %.2f -> %.2f'
              % (name, w, h, have.mean() * 100, err_before, err_after))


if __name__ == '__main__':
    main()
