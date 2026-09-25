package com.colorpop.game;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.Shader;
import android.graphics.Typeface;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Lettering in the style of the reference: Lilita One, white fill with a slight downward
 * gradient, a dark outline, and the outline repeated a little lower as a drop shadow.
 */
final class OutlineText {
    static final int LEFT = 0, CENTER = 1;

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.SUBPIXEL_TEXT_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.SUBPIXEL_TEXT_FLAG);
    private final Rect ink = new Rect(), digit = new Rect();
    private final int fillTop, fillBottom;
    private LinearGradient gradient;
    private float gradientTop = Float.NaN, gradientBottom;

    OutlineText(Typeface font, JSONObject style) {
        fillTop = rgb(style.optJSONArray("fill_top"), 0xffffffff);
        fillBottom = rgb(style.optJSONArray("fill_bottom"), 0xffe2e4ec);
        fill.setTypeface(font);
        stroke.setTypeface(font);
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeJoin(Paint.Join.ROUND);
        stroke.setColor(rgb(style.optJSONArray("outline"), 0xff060c1c));
    }

    private static int rgb(JSONArray a, int fallback) {
        return a == null ? fallback : Color.rgb(a.optInt(0), a.optInt(1), a.optInt(2));
    }

    /**
     * Draws {@code text} with its ink either starting at {@code x} (LEFT) or centred on it; the
     * top of a digit sits at {@code top}. Sizes are screen pixels.
     */
    void draw(Canvas c, String text, float x, float top, int align, float size, float scaleX,
              float outline, float shadow, int alpha) {
        fill.setTextSize(size);
        stroke.setTextSize(size);
        fill.setTextScaleX(scaleX);
        stroke.setTextScaleX(scaleX);
        stroke.setStrokeWidth(2 * outline);
        fill.getTextBounds(text, 0, text.length(), ink);
        fill.getTextBounds("0", 0, 1, digit);
        float drawX = align == CENTER ? x - (ink.left + ink.right) / 2f : x - ink.left;
        float base = top - digit.top;
        float gTop = base + digit.top, gBottom = base + digit.bottom;
        if (gradient == null || gTop != gradientTop || gBottom != gradientBottom) {
            gradient = new LinearGradient(0, gTop, 0, gBottom, fillTop, fillBottom, Shader.TileMode.CLAMP);
            gradientTop = gTop;
            gradientBottom = gBottom;
        }
        fill.setShader(gradient);
        fill.setAlpha(alpha);
        stroke.setAlpha(alpha);
        if (shadow > 0) {
            c.drawText(text, drawX, base + shadow, stroke);
        }
        c.drawText(text, drawX, base, stroke);
        c.drawText(text, drawX, base, fill);
    }

    /** Height of a digit's ink at the given size (to place labels by their visible middle). */
    float digitHeight(float size) {
        fill.setTextSize(size);
        fill.getTextBounds("0", 0, 1, digit);
        return digit.height();
    }

    /** One of the HUD numbers of level.json ("live_text"), placed in its reference box. */
    static final class Slot {
        final float left, top, right, size, scaleX, outline, shadow, rotate;
        final int align;

        Slot(JSONObject spec) {
            JSONArray box = spec.optJSONArray("box");
            left = (float) box.optDouble(0);
            top = (float) box.optDouble(1);
            right = (float) box.optDouble(2);
            size = (float) spec.optDouble("size");
            scaleX = (float) spec.optDouble("scale_x", 1);
            outline = (float) spec.optDouble("outline");
            shadow = (float) spec.optDouble("shadow");
            rotate = (float) spec.optDouble("rotate", 0);
            align = "center".equals(spec.optString("align")) ? CENTER : LEFT;
        }

        void draw(Canvas c, OutlineText t, String text, Xf xf) {
            float x = align == CENTER ? xf.x((left + right) / 2) : xf.x(left);
            if (rotate == 0) {
                t.draw(c, text, x, xf.y(top), align, size * xf.s, scaleX, outline * xf.s, shadow * xf.s, 255);
                return;
            }
            // tilted around the middle of the lettering (degrees, clockwise positive)
            int save = c.save();
            c.rotate(rotate, xf.x((left + right) / 2), xf.y(top) + t.digitHeight(size * xf.s) / 2);
            t.draw(c, text, x, xf.y(top), align, size * xf.s, scaleX, outline * xf.s, shadow * xf.s, 255);
            c.restoreToCount(save);
        }
    }
}
