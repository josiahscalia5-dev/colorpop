"""Super-resolution of the character art (Levels 3, 6, 8, ...).

The screens of the second reference sheet were drawn ~355 px wide (no larger original exists: the
owner's uploads are enlargements of the same sheet); the app shows them ~4x that on a phone, so their
characters look soft next to Level 1's (cut from a full-size original). They are reconstructed at
twice the art resolution:
  1. the blur is inverted first (Richardson-Lucy deconvolution, Gaussian blur of `deblur` art px:
     ~1 px for characters in focus, 2-2.5 px for the ones the mockup paints out of focus);
  2. Real-ESRGAN (x4plus, run on the CPU with ncnn) upscales the deblurred art 4x, which is then
     reduced to 2x (crisp outlines, eyes, hat edges);
  3. the enlargement's own low frequencies (shapes, colours, shading, lighting) are kept, so the
     design and colours stay the owner's.

Models (not committed): design-pipeline/_models/realesrgan-x4plus.{param,bin}, from
https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip
(models/), `pip install ncnn`.
"""
import os
import numpy as np, cv2
from PIL import Image
from paths import ROOT

MODELS = os.path.join(ROOT, 'design-pipeline', '_models')
_net = {}


def _load(model):
    if model not in _net:
        import ncnn
        net = ncnn.Net()
        net.opt.use_vulkan_compute = False
        net.opt.num_threads = os.cpu_count() or 4
        net.load_param(os.path.join(MODELS, model + '.param'))
        net.load_model(os.path.join(MODELS, model + '.bin'))
        _net[model] = net
    return _net[model]


def upscale4(img, model='realesrgan-x4plus', tile=96, pad=10):
    """img: HxWx3 RGB (0..255) -> 4H x 4W x 3 float, tiled with overlap."""
    import ncnn
    net = _load(model)
    img = np.clip(img, 0, 255).astype(np.uint8)
    H, W = img.shape[:2]
    out = np.zeros((4 * H, 4 * W, 3), np.float32)
    src = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REFLECT_101)
    for y in range(0, H, tile):
        for x in range(0, W, tile):
            th, tw = min(tile, H - y), min(tile, W - x)
            crop = np.ascontiguousarray(src[y:y + th + 2 * pad, x:x + tw + 2 * pad])
            m = ncnn.Mat.from_pixels(crop, ncnn.Mat.PixelType.PIXEL_RGB, crop.shape[1], crop.shape[0])
            m.substract_mean_normalize([], [1 / 255.0] * 3)
            ex = net.create_extractor()
            ex.input('data', m)
            _, o = ex.extract('output')
            o = np.array(o).transpose(1, 2, 0) * 255.0
            out[4 * y:4 * (y + th), 4 * x:4 * (x + tw)] = o[4 * pad:4 * (pad + th), 4 * pad:4 * (pad + tw)]
    return np.clip(out, 0, 255)


def hires_canvas(name):
    """The screen at 2x art resolution, pixel-aligned with reference/screens/<name>.png (art pixel
    (x, y) = hires pixels [2x, 2x+2) x [2y, 2y+2)): the owner's enlargement where it covers the
    screen, the art upscaled elsewhere. Returns (image float RGB, covered mask)."""
    from screens_import import PHONE, ORIGIN
    art = np.asarray(Image.open(os.path.join(ROOT, 'reference', 'screens', name + '.png')).convert('RGB')).astype(np.float32)
    H, W = art.shape[:2]
    big = np.asarray(Image.open(os.path.join(ROOT, 'reference', 'sheet', name + '_4x.png')).convert('RGB')).astype(np.float32)
    x0, y0 = PHONE[name][:2]
    ox, oy = (ORIGIN[name][0] - x0) * 4, (ORIGIN[name][1] - y0) * 4      # in hires px
    canvas = cv2.resize(art, (2 * W, 2 * H), interpolation=cv2.INTER_CUBIC)
    have = np.zeros((2 * H, 2 * W), bool)
    ya, yb = max(0, oy), min(2 * H, oy + big.shape[0])
    xa, xb = max(0, ox), min(2 * W, ox + big.shape[1])
    canvas[ya:yb, xa:xb] = big[ya - oy:yb - oy, xa - ox:xb - ox]
    have[ya:yb, xa:xb] = True
    return canvas, have


def deblur(img, sigma, iters=25):
    """Richardson-Lucy deconvolution of a Gaussian blur of `sigma` px."""
    if sigma <= 0:
        return img
    k = int(np.ceil(sigma * 3)) * 2 + 1
    blur = lambda x: cv2.GaussianBlur(x, (k, k), sigma, borderType=cv2.BORDER_REFLECT)
    obs = img.astype(np.float32) + 1
    est = obs.copy()
    for _ in range(iters):
        est = np.clip(est * blur(obs / np.maximum(blur(est), 1e-3)), 1, 256)
    return est - 1


def sharp_region(hires, box, deblur_px=1.0, keep=6.0):
    """The reconstruction of hires[box] (x0, y0, x1, y1 in hires px, 2x art): the enlargement at art
    resolution, deblurred by `deblur_px` art px, upscaled x4 by the network and reduced to 2x art;
    below `keep` hires px the enlargement's own shading and colours."""
    x0, y0, x1, y1 = box
    x0, y0 = x0 - x0 % 4, y0 - y0 % 4
    x1, y1 = x1 + (-x1) % 4, y1 + (-y1) % 4
    crop = hires[y0:y1, x0:x1]
    art = cv2.resize(crop, ((x1 - x0) // 2, (y1 - y0) // 2), interpolation=cv2.INTER_AREA)
    up = upscale4(deblur(art, deblur_px))
    sr = cv2.resize(up, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    out = sr - cv2.GaussianBlur(sr, (0, 0), keep) + cv2.GaussianBlur(crop, (0, 0), keep)
    return np.clip(out, 0, 255), (x0, y0, x1, y1), sr
