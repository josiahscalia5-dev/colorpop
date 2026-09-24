package com.colorpop.game;

import android.graphics.RectF;

/** Maps reference-art pixels to screen pixels: screen = offset + art * scale. */
final class Xf {
    float s = 1, ox, oy;

    void set(float scale, float offsetX, float offsetY) {
        s = scale;
        ox = offsetX;
        oy = offsetY;
    }

    float x(float artX) {
        return ox + artX * s;
    }

    float y(float artY) {
        return oy + artY * s;
    }

    float artX(float screenX) {
        return (screenX - ox) / s;
    }

    float artY(float screenY) {
        return (screenY - oy) / s;
    }

    RectF rect(float artX, float artY, float artW, float artH, RectF out) {
        out.set(x(artX), y(artY), x(artX + artW), y(artY + artH));
        return out;
    }
}
