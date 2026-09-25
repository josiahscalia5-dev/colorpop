package com.colorpop.game;

import android.graphics.Bitmap;
import android.graphics.BitmapShader;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.PorterDuffXfermode;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;

/**
 * Responsive layout. Every screen is laid out in reference-art pixels and mapped to the device
 * with ONE uniform scale (never separate x/y scales, so nothing is ever stretched or squashed).
 *
 * The scale is the largest at which
 *   - the full art width fits between the safe left and right edges, and
 *   - the screen's must-see rows [contentTop, contentBottom] fit between the safe top (plus a
 *     small gap, only if something covers the top) and the safe bottom.
 * On the reference shape with nothing covering the screen this is exactly the reference (width
 * fit). Taller screens show more of the painted sky/ground around the content, shorter or wider
 * ones a few px of the painted side padding; see {@link Backdrop} for what lies beyond.
 */
final class Fit {
    private Fit() {
    }

    /**
     * @param availW  safe width in px
     * @param availH  px from the screen top to the safe bottom
     * @param topNeed px from the screen top the content must stay below (0 if nothing covers it)
     */
    static float scale(float artW, float contentTop, float contentBottom, float availW, float availH, float topNeed) {
        float s = Math.min(availW / artW, availH / contentBottom);
        if (topNeed > contentTop * s) {
            s = Math.min(availW / artW, (availH - topNeed) / (contentBottom - contentTop));
        }
        return s;
    }

    static float topNeed(GameView game) {
        return game.safe.top > 0 ? game.safe.top + game.safeMargin() : 0;
    }

    /** Left edge of art that is {@code artW * s} wide, centred in the safe width. */
    static float left(Rect safe, int w, float artW, float s) {
        return safe.left + (w - safe.left - safe.right - artW * s) / 2;
    }

    /**
     * A background picture (reference art plus painted padding) drawn over the whole screen at
     * the layout's scale. Up and down it mirrors beyond its padding (sky, grass, dirt). A window
     * wider than the picture (foldable inner screen, split screen) gets a soft, darker copy of the
     * scene behind it, uniformly scaled to cover, and the picture's blurred side padding fades
     * into it -- nothing is stretched and no screen shape shows an empty or streaked band.
     */
    static final class Backdrop {
        private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG);
        private final Paint softPaint = new Paint(Paint.FILTER_BITMAP_FLAG);
        private final BitmapShader softShader;
        private final Matrix softMatrix = new Matrix();
        private final Paint fade = new Paint();
        private final BitmapShader shader;
        private final Matrix matrix = new Matrix();
        private final float padLeft, padTop, width, height, density;
        private float softW, softH;

        Backdrop(Bitmap bitmap, float padLeft, float padTop) {
            this(bitmap, padLeft, padTop, 1);
        }

        /** density: bitmap px per art px (2 for a picture drawn at twice the art resolution). */
        Backdrop(Bitmap bitmap, float padLeft, float padTop, float density) {
            this.padLeft = padLeft;
            this.padTop = padTop;
            this.density = density;
            width = bitmap.getWidth() / density;
            height = bitmap.getHeight() / density;
            shader = new BitmapShader(bitmap, Shader.TileMode.CLAMP, Shader.TileMode.MIRROR);
            paint.setShader(shader);
            softShader = new BitmapShader(blurred(bitmap, 8, 3), Shader.TileMode.CLAMP, Shader.TileMode.CLAMP);
            softPaint.setShader(softShader);
            softPaint.setColorFilter(new PorterDuffColorFilter(0x59000000, PorterDuff.Mode.SRC_ATOP));
            fade.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.DST_IN));
        }

        void draw(Canvas c, Xf xf, int w, int h) {
            matrix.setScale(xf.s / density, xf.s / density);
            matrix.postTranslate(xf.x(-padLeft), xf.y(-padTop));
            shader.setLocalMatrix(matrix);
            float left = xf.x(-padLeft), right = left + width * xf.s;
            if (left <= 0.5f && right >= w - 0.5f) {
                c.drawRect(0, 0, w, h, paint);
                return;
            }
            float cover = Math.max(w / width, h / height);
            softMatrix.setScale(width * cover / softW, height * cover / softH);
            softMatrix.postTranslate((left + right) / 2 - width * cover / 2, (h - height * cover) / 2);
            softShader.setLocalMatrix(softMatrix);
            c.drawRect(0, 0, w, h, softPaint);
            float l = Math.max(0, left), r = Math.min(w, right), f = padLeft * xf.s;
            int layer = c.saveLayer(l, 0, r, h, null);
            c.drawRect(l, 0, r, h, paint);
            fade.setShader(new LinearGradient(left, 0, right, 0,
                    new int[]{0, 0xff000000, 0xff000000, 0},
                    new float[]{0, f / (right - left), 1 - f / (right - left), 1}, Shader.TileMode.CLAMP));
            c.drawRect(l, 0, r, h, fade);
            c.restoreToCount(layer);
        }

        /** 1/{@code div} size copy, box-blurred {@code passes} times (a soft fill, not a picture). */
        private Bitmap blurred(Bitmap src, int div, int passes) {
            Bitmap small = Bitmap.createScaledBitmap(src, Math.max(1, src.getWidth() / div), Math.max(1, src.getHeight() / div), true);
            int bw = small.getWidth(), bh = small.getHeight();
            softW = bw;
            softH = bh;
            int[] px = new int[bw * bh], tmp = new int[bw * bh];
            small.getPixels(px, 0, bw, 0, 0, bw, bh);
            for (int p = 0; p < passes; p++) {
                box(px, tmp, bw, bh, 1, bw, 2);   // rows
                box(tmp, px, bh, bw, bw, 1, 2);   // columns
            }
            Bitmap out = Bitmap.createBitmap(bw, bh, Bitmap.Config.ARGB_8888);
            out.setPixels(px, 0, bw, 0, 0, bw, bh);
            return out;
        }

        /** Box blur of radius r along lines of length n (step between samples, stride between lines). */
        private static void box(int[] in, int[] out, int n, int lines, int step, int stride, int r) {
            for (int line = 0; line < lines; line++) {
                int base = line * stride;
                for (int i = 0; i < n; i++) {
                    int sr = 0, sg = 0, sb = 0, cnt = 0;
                    for (int k = -r; k <= r; k++) {
                        int j = Math.max(0, Math.min(n - 1, i + k));
                        int c = in[base + j * step];
                        sr += (c >> 16) & 255;
                        sg += (c >> 8) & 255;
                        sb += c & 255;
                        cnt++;
                    }
                    out[base + i * step] = 0xff000000 | (sr / cnt << 16) | (sg / cnt << 8) | (sb / cnt);
                }
            }
        }
    }
}
