package com.colorpop.game;

import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.MotionEvent;

import java.util.ArrayList;
import java.util.List;

/**
 * Placeholder UI for things the reference does not show yet (settings, pause, round over,
 * "coming soon"), drawn in the style of the reference HUD: navy panels with a cyan rim and
 * Lilita One lettering. Coordinates are art px relative to the centre of the screen.
 */
final class Ui {
    private Ui() {
    }

    static final int NAVY_TOP = 0xff1b4ea6, NAVY_BOTTOM = 0xff0a1d4d, RIM = 0xff39c8ff, EDGE = 0xff06102a;

    static float easeOutBack(float t) {
        t = Math.max(0, Math.min(1, t));
        float c = 1.6f;
        float u = t - 1;
        return 1 + (c + 1) * u * u * u + c * u * u;
    }

    /** Rounded panel: dark edge, cyan rim, navy gradient body, soft highlight on top. */
    static void panel(Canvas c, RectF r, float radius, float s, Paint p) {
        p.setShader(null);
        p.setStyle(Paint.Style.FILL);
        p.setColor(0x66000000);
        RectF sh = new RectF(r.left, r.top + 8 * s, r.right, r.bottom + 8 * s);
        c.drawRoundRect(sh, radius, radius, p);
        p.setColor(EDGE);
        c.drawRoundRect(r, radius, radius, p);
        RectF rim = new RectF(r.left + 3 * s, r.top + 3 * s, r.right - 3 * s, r.bottom - 3 * s);
        p.setColor(RIM);
        c.drawRoundRect(rim, radius - 3 * s, radius - 3 * s, p);
        RectF body = new RectF(rim.left + 5 * s, rim.top + 5 * s, rim.right - 5 * s, rim.bottom - 5 * s);
        p.setShader(new LinearGradient(0, body.top, 0, body.bottom, NAVY_TOP, NAVY_BOTTOM, Shader.TileMode.CLAMP));
        c.drawRoundRect(body, radius - 8 * s, radius - 8 * s, p);
        p.setShader(new LinearGradient(0, body.top, 0, body.top + body.height() * 0.45f, 0x33ffffff, 0x00ffffff, Shader.TileMode.CLAMP));
        c.drawRoundRect(body, radius - 8 * s, radius - 8 * s, p);
        p.setShader(null);
    }

    /** Glossy pill (green like PLAY, or blue). */
    static void pill(Canvas c, RectF r, boolean green, float s, Paint p) {
        float rad = r.height() / 2;
        p.setShader(null);
        p.setStyle(Paint.Style.FILL);
        p.setColor(0x55000000);
        c.drawRoundRect(new RectF(r.left, r.top + 6 * s, r.right, r.bottom + 6 * s), rad, rad, p);
        p.setColor(green ? 0xff0b5d16 : 0xff0b2e6e);
        c.drawRoundRect(r, rad, rad, p);
        RectF in = new RectF(r.left + 4 * s, r.top + 4 * s, r.right - 4 * s, r.bottom - 4 * s);
        p.setShader(new LinearGradient(0, in.top, 0, in.bottom,
                green ? 0xff86f250 : 0xff5ccaff, green ? 0xff22a82a : 0xff1a6fd8, Shader.TileMode.CLAMP));
        c.drawRoundRect(in, rad - 4 * s, rad - 4 * s, p);
        RectF gloss = new RectF(in.left + in.height() * 0.3f, in.top + 3 * s, in.right - in.height() * 0.3f, in.centerY());
        p.setShader(new LinearGradient(0, gloss.top, 0, gloss.bottom, 0x77ffffff, 0x10ffffff, Shader.TileMode.CLAMP));
        c.drawRoundRect(gloss, gloss.height() / 2, gloss.height() / 2, p);
        p.setShader(null);
    }

    /** A pill button with a label and the same springy press as the sprite buttons. */
    static final class Button {
        final int id;
        final String label;
        final boolean green;
        final RectF art = new RectF();
        boolean pressed;
        private float scale = 1, velocity;

        Button(int id, String label, boolean green) {
            this.id = id;
            this.label = label;
            this.green = green;
        }

        void update(float dt) {
            float target = pressed ? 0.93f : 1f;
            for (float t = 0; t < dt; t += 1f / 240) {
                float d = Math.min(1f / 240, dt - t);
                velocity += (900f * (target - scale) - 28f * velocity) * d;
                scale += velocity * d;
            }
        }

        void draw(Canvas c, Xf xf, OutlineText text, Paint p) {
            RectF r = xf.rect(art.left, art.top, art.width(), art.height(), new RectF());
            int save = c.save();
            c.scale(scale, scale, r.centerX(), r.centerY());
            pill(c, r, green, xf.s, p);
            float size = 46 * xf.s;
            text.draw(c, label, r.centerX(), r.centerY() - text.digitHeight(size) / 2 - 2 * xf.s,
                    OutlineText.CENTER, size, 0.92f, 3 * xf.s, 2.5f * xf.s, 255);
            c.restoreToCount(save);
        }
    }

    /** An on/off switch with a label on its left. */
    static final class Toggle {
        final int id;
        final String label;
        boolean on;
        float knob;           // 0 = off .. 1 = on (animated)
        final RectF art = new RectF();

        Toggle(int id, String label, boolean on) {
            this.id = id;
            this.label = label;
            this.on = on;
            knob = on ? 1 : 0;
        }

        void update(float dt) {
            float target = on ? 1 : 0;
            knob += Math.signum(target - knob) * Math.min(Math.abs(target - knob), dt * 7);
        }

        void draw(Canvas c, Xf xf, OutlineText text, Paint p, float labelLeft) {
            RectF r = xf.rect(art.left, art.top, art.width(), art.height(), new RectF());
            float size = 42 * xf.s;
            text.draw(c, label, xf.x(labelLeft), r.centerY() - text.digitHeight(size) / 2,
                    OutlineText.LEFT, size, 0.92f, 3 * xf.s, 2.5f * xf.s, 255);
            float rad = r.height() / 2;
            p.setShader(null);
            p.setStyle(Paint.Style.FILL);
            p.setColor(EDGE);
            c.drawRoundRect(r, rad, rad, p);
            RectF in = new RectF(r.left + 4 * xf.s, r.top + 4 * xf.s, r.right - 4 * xf.s, r.bottom - 4 * xf.s);
            p.setColor(blend(0xff5b6479, 0xff2fc43a, knob));
            c.drawRoundRect(in, rad - 4 * xf.s, rad - 4 * xf.s, p);
            float kr = in.height() / 2 - 3 * xf.s;
            float kx = in.left + 3 * xf.s + kr + knob * (in.width() - 2 * kr - 6 * xf.s);
            p.setColor(0x55000000);
            c.drawCircle(kx, in.centerY() + 3 * xf.s, kr, p);
            p.setColor(0xffffffff);
            c.drawCircle(kx, in.centerY(), kr, p);
        }
    }

    static int blend(int a, int b, float t) {
        int ar = (a >> 16) & 255, ag = (a >> 8) & 255, ab = a & 255;
        int br = (b >> 16) & 255, bg = (b >> 8) & 255, bb = b & 255;
        return 0xff000000 | ((int) (ar + (br - ar) * t) << 16) | ((int) (ag + (bg - ag) * t) << 8) | (int) (ab + (bb - ab) * t);
    }

    /** A centred modal panel with a title, an optional line of text, toggles and buttons. */
    static final class Dialog {
        static final float WIDTH = 540;
        final String title;
        String line;
        final List<Toggle> toggles = new ArrayList<>();
        final List<Button> buttons = new ArrayList<>();
        final Xf xf = new Xf();
        private final RectF box = new RectF();
        private float appear;
        private Button down;

        Dialog(String title) {
            this.title = title;
        }

        Dialog toggle(int id, String label, boolean on) {
            toggles.add(new Toggle(id, label, on));
            return this;
        }

        Dialog button(int id, String label, boolean green) {
            buttons.add(new Button(id, label, green));
            return this;
        }

        /** Lays the content out top to bottom around the centre of the safe area. */
        void layout(int w, int h, float s, android.graphics.Rect safe) {
            xf.set(s, (safe.left + w - safe.right) / 2f, (safe.top + h - safe.bottom) / 2f);
            float height = 40 + 70 + (line != null ? 70 : 0) + toggles.size() * 92 + buttons.size() * 118 + 26;
            box.set(-WIDTH / 2, -height / 2, WIDTH / 2, height / 2);
            float y = box.top + 40 + 70 + (line != null ? 70 : 0) + 10;
            for (Toggle t : toggles) {
                t.art.set(90, y, 210, y + 64);
                y += 92;
            }
            for (Button b : buttons) {
                b.art.set(-175, y + 4, 175, y + 100);
                y += 118;
            }
        }

        void update(float dt) {
            appear = Math.min(1, appear + dt / 0.22f);
            for (Toggle t : toggles) {
                t.update(dt);
            }
            for (Button b : buttons) {
                b.update(dt);
            }
        }

        void draw(Canvas c, int w, int h, OutlineText text, Paint p) {
            p.setShader(null);
            p.setStyle(Paint.Style.FILL);
            p.setColor((int) (150 * Math.min(1, appear * 2)) << 24);
            c.drawRect(0, 0, w, h, p);
            int save = c.save();
            float sc = 0.8f + 0.2f * easeOutBack(appear);
            c.scale(sc, sc, xf.ox, xf.oy);
            float s = xf.s;
            panel(c, xf.rect(box.left, box.top, box.width(), box.height(), new RectF()), 40 * s, s, p);
            float size = 62 * s;
            text.draw(c, title, xf.x(0), xf.y(box.top + 40), OutlineText.CENTER, size, 0.92f, 3.5f * s, 3 * s, 255);
            if (line != null) {
                float ls = 46 * s;
                text.draw(c, line, xf.x(0), xf.y(box.top + 40 + 72), OutlineText.CENTER, ls, 0.9f, 3 * s, 2.5f * s, 255);
            }
            for (Toggle t : toggles) {
                t.draw(c, xf, text, p, box.left + 50);
            }
            for (Button b : buttons) {
                b.draw(c, xf, text, p);
            }
            c.restoreToCount(save);
        }

        /** Returns the id of a button released over itself, or -1. Toggles flip on release. */
        int touch(MotionEvent e, Sfx sfx) {
            float ax = xf.artX(e.getX()), ay = xf.artY(e.getY());
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    down = null;
                    for (Button b : buttons) {
                        if (b.art.contains(ax, ay)) {
                            down = b;
                            b.pressed = true;
                        }
                    }
                    return -1;
                case MotionEvent.ACTION_MOVE:
                    if (down != null) {
                        down.pressed = down.art.contains(ax, ay);
                    }
                    return -1;
                case MotionEvent.ACTION_UP:
                    for (Toggle t : toggles) {
                        RectF hit = new RectF(box.left, t.art.top - 14, box.right, t.art.bottom + 14);
                        if (hit.contains(ax, ay)) {
                            t.on = !t.on;
                            sfx.click();
                            return t.id;
                        }
                    }
                    if (down != null) {
                        Button b = down;
                        down = null;
                        b.pressed = false;
                        if (b.art.contains(ax, ay)) {
                            sfx.click();
                            return b.id;
                        }
                    }
                    return -1;
                case MotionEvent.ACTION_CANCEL:
                    if (down != null) {
                        down.pressed = false;
                        down = null;
                    }
                    return -1;
                default:
                    return -1;
            }
        }
    }

    /** "COMING SOON!" bubble: pops in, stays a moment, fades out. */
    static final class Toast {
        private String text;
        private float t = -1;
        private static final float IN = 0.18f, HOLD = 1.1f, OUT = 0.3f;

        void show(String message) {
            text = message;
            t = 0;
        }

        boolean showing() {
            return t >= 0;
        }

        void update(float dt) {
            if (t >= 0) {
                t += dt;
                if (t > IN + HOLD + OUT) {
                    t = -1;
                }
            }
        }

        void draw(Canvas c, float cx, float cy, float s, OutlineText out, Paint p) {
            if (t < 0) {
                return;
            }
            float a = t < IN ? t / IN : t > IN + HOLD ? 1 - (t - IN - HOLD) / OUT : 1;
            float sc = t < IN ? 0.7f + 0.3f * easeOutBack(t / IN) : 1;
            float size = 44 * s;
            float hw = 200 * s, hh = 46 * s;
            int save = c.save();
            c.scale(sc, sc, cx, cy);
            int layer = c.saveLayerAlpha(new RectF(cx - hw - 20 * s, cy - hh - 20 * s, cx + hw + 20 * s, cy + hh + 20 * s), (int) (255 * a));
            panel(c, new RectF(cx - hw, cy - hh, cx + hw, cy + hh), hh, s, p);
            out.draw(c, text, cx, cy - out.digitHeight(size) / 2, OutlineText.CENTER, size, 0.92f, 3 * s, 2.5f * s, 255);
            c.restoreToCount(layer);
            c.restoreToCount(save);
        }
    }
}
