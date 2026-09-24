package com.colorpop.game;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * A control cut from the reference art: drawn at its reference position, touchable in its
 * reference touch area, and it sinks in while pressed and springs back on release.
 */
final class SpriteButton {
    private static final float PRESSED_SCALE = 0.92f, SLOP = 6f; // SLOP in art px

    final Bitmap bitmap;
    final float x, y, w, h;          // sprite rectangle, art px
    final float hx0, hy0, hx1, hy1;  // touch area, art px
    final boolean round;
    Xf xf;
    boolean pressed;
    private float scale = 1, velocity;
    private final RectF dst = new RectF();

    SpriteButton(Bitmap bitmap, float x, float y, float[] hit, boolean round, Xf xf) {
        this.bitmap = bitmap;
        this.x = x;
        this.y = y;
        this.w = bitmap.getWidth();
        this.h = bitmap.getHeight();
        hx0 = hit[0];
        hy0 = hit[1];
        hx1 = hit[2];
        hy1 = hit[3];
        this.round = round;
        this.xf = xf;
    }

    /** From an entry of home/_meta.json: {x, y, w, h, hit: [x0, y0, x1, y1]}. */
    static SpriteButton fromMeta(Art art, String dir, String name, JSONObject meta, boolean round, Xf xf) {
        JSONObject m = meta.optJSONObject(name);
        JSONArray hit = m.optJSONArray("hit");
        float[] r = {(float) hit.optDouble(0), (float) hit.optDouble(1), (float) hit.optDouble(2), (float) hit.optDouble(3)};
        return new SpriteButton(art.bitmap(dir + "/" + name + ".png"), (float) m.optDouble("x"), (float) m.optDouble("y"), r, round, xf);
    }

    boolean contains(float screenX, float screenY) {
        float ax = xf.artX(screenX), ay = xf.artY(screenY);
        if (round) {
            float cx = (hx0 + hx1) / 2, cy = (hy0 + hy1) / 2, r = (hx1 - hx0) / 2 + SLOP;
            return (ax - cx) * (ax - cx) + (ay - cy) * (ay - cy) <= r * r;
        }
        return ax >= hx0 - SLOP && ax <= hx1 + SLOP && ay >= hy0 - SLOP && ay <= hy1 + SLOP;
    }

    /** Spring towards the pressed / released size (a little overshoot on release). */
    void update(float dt) {
        float target = pressed ? PRESSED_SCALE : 1f;
        float step = 1f / 240;
        for (float t = 0; t < dt; t += step) {
            float d = Math.min(step, dt - t);
            velocity += (900f * (target - scale) - 28f * velocity) * d;
            scale += velocity * d;
        }
    }

    boolean settled() {
        return !pressed && Math.abs(scale - 1) < 0.001f && Math.abs(velocity) < 0.01f;
    }

    void draw(Canvas c, Paint paint) {
        xf.rect(x, y, w, h, dst);
        if (scale == 1f) {
            c.drawBitmap(bitmap, null, dst, paint);
            return;
        }
        int save = c.save();
        c.scale(scale, scale, xf.x((hx0 + hx1) / 2), xf.y((hy0 + hy1) / 2));
        c.drawBitmap(bitmap, null, dst, paint);
        c.restoreToCount(save);
    }
}
