package com.colorpop.game;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Color;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.PorterDuffXfermode;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.view.MotionEvent;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Random;

/**
 * One level: characters pop up out of the holes; tapping a target pops it (+score, one target
 * less), other characters only react, a bomb costs time. The round is won when every target is
 * hit before the timer runs out.
 *
 * Every level is described by its folder of art (see design-pipeline/): level.json holds the
 * holes, the characters cut from the reference, the HUD number slots and (new levels) the rules.
 * Level 1 ("level/", HIT THE GREEN ONES!) keeps its own format: 30 s, 12 greens, red and yellow
 * only react, and a foreground layer for the bottom foliage.
 *
 * Layout (art = reference pixels, one uniform scale, see {@link Fit}): anchored to the top, so the
 * HUD and the scene are exactly as in the reference; the HUD moves down only if a camera cutout
 * reaches it. A taller screen shows more ground below the scene, a shorter or wider one scales
 * everything down together. Must-see: from the top of the HUD to the bottom of the scene
 * (Level 1: art y 66 .. 1150; new levels: level.json "content").
 */
final class LevelScreen extends Screen {
    static final float ROUND = 30f;                  // Level 1
    static final int TARGETS = 12, POINTS = 10;      // Level 1
    static final int TARGET = 0, DISTRACTOR = 1, BOMB = 2;
    private static final float RISE = 0.22f, SINK = 0.2f, POP = 0.2f, WOBBLE = 0.45f, MAX_ENLARGE = 1.3f;
    private static final float HOP_SINK = 0.12f, HOP_RISE = 0.16f, FAIL_TIME = 1.6f;
    private static final float INTRO_HOLD_UNTIL = 2.95f, SPAWN_FROM = 3.3f;
    private static final float INTRO_FX_FADE = 2.4f, INTRO_FX_GONE = 3.0f, BURST_TIME = 0.32f, BANNER_TIME = 2.8f;
    private static final float HIT_TIME = 0.45f, STRUCK_POP = 0.2f, MUZZLE = 0.12f;   // tap-and-fire (Level 3)
    private static final int PAUSE_RESUME = 1, PAUSE_HOME = 2, OVER_AGAIN = 3, OVER_HOME = 4, OVER_NEXT = 5;
    private static final int GREEN = 0, RED = 1, YELLOW = 2;       // Level 1 colours

    final int id;
    private final boolean legacy;                    // Level 1's art format

    // ------------------------------------------------------------------ rules
    private final float duration, bombPenalty;
    private final int goal, points;
    private final boolean combos, swipe;
    private final float mixTarget, mixDistractor;    // bombs: the rest
    private final float holdMin, holdSpread, gapMin, gapSpread;
    private final int upEarly, upLate;
    private final float quick;                        // share of quick pop-ups (0.6 x the hold)
    private final float speedAt, speedHold, speedGap; // "SPEED INCREASED!" (speedAt < 0: never)
    private final int speedUp;
    private final boolean decoyFails;                 // tapping a decoy fails the round (it restarts)
    private final float hopChance0, hopChance1, hopAfterMin, hopAfterSpread;   // characters changing holes
    private final float rampHold, rampGap, rampRise;  // steady speed-up: factors reached at the end
    private final JSONObject referenceState;
    // tap-and-fire: a tap launches a shot from the player's side; it scores when it lands
    private final boolean fires;
    private final float fireX, fireY, fireSpeed, fireMin, fireMax, fieldTop;
    private final int demoHole;                       // the opening demonstration taps this hole's character (-1: none)
    private final float demoPress;

    // ------------------------------------------------------------------ art
    private final float contentTop, referenceH;
    private final Fit.Backdrop bg;
    private final Bitmap fg;
    private final int artW, artH;
    private final float fgX, fgY;
    private final SpriteButton pauseButton;
    private final OutlineText hudText, comboText;
    private final OutlineText.Slot timerSlot, targetSlot, scoreSlot, comboSlot;
    private final Sprite comboWord, hint, burst, banner, hand;
    private final float burstAnchorX, burstAnchorY;
    private final float handTipX, handTipY;
    private final Hole[] holes;              // sorted back to front
    private final Look[][] lookFor;          // Level 1: [colour][hole index]
    private final List<List<Look>> byRole = new ArrayList<>();
    private final Look[] referenceLooks;     // [hole index]: the character the reference shows there
    private final Xf xf = new Xf();
    private float fgShift;

    // ------------------------------------------------------------------ round state
    private final Random rnd = new Random();
    private float elapsed, sinceStart, nextSpawn, targetPulse, scorePulse, timerPulse, comboPulse, overT;
    private float bannerT = -1;                       // time since the banner appeared (< 0: hidden)
    private boolean fast;                             // sped up
    private int score, targetsLeft, combo, maxCombo;
    private boolean paused, over, won, failing;
    private float failT;
    private int failures, hops;
    private Ui.Dialog dialog;
    private boolean pausePressed, swiping;
    private final List<Particle> particles = new ArrayList<>();
    private final List<Floater> floaters = new ArrayList<>();
    private final List<Burst> bursts = new ArrayList<>();
    private final List<Shot> shots = new ArrayList<>();
    private final List<Hit> hits = new ArrayList<>();
    private boolean demoOn, demoFired;
    private float demoOff = -1;                       // when the player's first tap ended the demonstration

    private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
    private final Paint light = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Paint eraser = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fx = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ui = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint energy = new Paint(Paint.ANTI_ALIAS_FLAG);   // coloured light (glows, rays)
    private final Path path = new Path();
    private final float[] pt = new float[2], pt2 = new float[2];
    private final RectF dst = new RectF(), layer = new RectF();

    /** A picture cut from the reference, drawn at its reference position (art px). */
    static final class Sprite {
        final Bitmap bitmap;
        final float x, y, w, h;            // art px

        Sprite(Bitmap bitmap, float x, float y, float density) {
            this.bitmap = bitmap;
            this.x = x;
            this.y = y;
            this.w = bitmap.getWidth() / density;
            this.h = bitmap.getHeight() / density;
        }

        /** From a level.json entry {file, x, y, scale (bitmap px per art px, default 1)}. */
        static Sprite of(Art art, JSONObject e) {
            return e == null ? null : new Sprite(art.bitmap(e.optString("file")), (float) e.optDouble("x"), (float) e.optDouble("y"),
                    (float) e.optDouble("scale", 1));
        }
    }

    /**
     * A hole: its opening ellipse, and the real front edge a character disappears behind -- the
     * front rim is bumpy (each brick's rounded top), so it is one measured y per art column.
     */
    static final class Hole {
        final int index;
        final float cx, cy, a, b;
        final int edgeX0;
        final float[] edge;
        final Path hidden = new Path();   // screen px: everything below the front edge
        Mole mole;

        Hole(int index, JSONObject json) {
            this.index = index;
            JSONArray e = json.optJSONArray("opening");
            cx = (float) e.optDouble(0);
            cy = (float) e.optDouble(1);
            a = (float) e.optDouble(2);
            b = (float) e.optDouble(3);
            JSONObject fe = json.optJSONObject("edge");
            JSONArray ys = fe.optJSONArray("y");
            edgeX0 = fe.optInt("x0");
            edge = new float[ys.length()];
            for (int i = 0; i < edge.length; i++) {
                edge[i] = (float) ys.optDouble(i);
            }
        }

        /** Lowest point of the opening (the reference poses are measured from it). */
        float front() {
            return cy + b;
        }

        /** The front edge at art x (column centres are at x0 + i + 0.5). */
        float edgeAt(float ax) {
            float f = ax - 0.5f - edgeX0;
            if (f <= 0) {
                return edge[0];
            }
            int i = (int) f;
            if (i >= edge.length - 1) {
                return edge[edge.length - 1];
            }
            return edge[i] + (edge[i + 1] - edge[i]) * (f - i);
        }

        /** Art point is below the front edge (hidden by the front rim)? */
        boolean hides(float ax, float ay) {
            if (ay < cy) {
                return false;
            }
            if (ax < cx - a || ax > cx + a) {
                return true;
            }
            return ay >= edgeAt(ax);
        }

        void layout(Xf xf, int w, int h) {
            Path below = new Path();
            below.addRect(-w, xf.y(cy), 2 * w, 2 * h, Path.Direction.CW);
            // the opening: upper half of the ellipse, then back along the measured front edge
            Path opening = new Path();
            RectF oval = new RectF(xf.x(cx - a), xf.y(cy - b), xf.x(cx + a), xf.y(cy + b));
            opening.arcTo(oval, 180, 180, true);
            for (int i = edge.length - 1; i >= 0; i--) {
                opening.lineTo(xf.x(edgeX0 + i + 0.5f), xf.y(edge[i]));
            }
            opening.close();
            hidden.reset();
            hidden.op(below, opening, Path.Op.DIFFERENCE);
        }
    }

    /**
     * A character sprite and the hole it was cut from (it can be shown in any hole, scaled), with
     * its light (halo, rays) as an additive layer that moves with it, if it has one.
     */
    static final class Look {
        final Bitmap bitmap;
        final float x, y;
        float density = 1;                // bitmap px per art px (2: drawn from a double-resolution picture)
        final Hole home;
        final int colour, role;
        final boolean introOnly;
        Bitmap glow;
        float glowX, glowY, glowDensity = 1;
        int tint = 0xffffffff;

        Look(Bitmap bitmap, float x, float y, Hole home, int colour, int role, boolean introOnly) {
            this.bitmap = bitmap;
            this.x = x;
            this.y = y;
            this.home = home;
            this.colour = colour;
            this.role = role;
            this.introOnly = introOnly;
        }

        /** Size in art px. */
        float width() {
            return bitmap.getWidth() / density;
        }

        float height() {
            return bitmap.getHeight() / density;
        }
    }

    /** What pops out of one hole. */
    final class Mole {
        static final int HIDDEN = 0, WAIT = 1, RISING = 2, UP = 3, SINKING = 4, POPPED = 5, REACT = 6;
        final Hole hole;
        int state = HIDDEN;
        float t, delay, hold, cooldown;
        float rise = RISE, sinkTime = SINK;   // this appearance's timing
        float hopAt = -1;                     // seconds up after which it moves to another hole (< 0: never)
        boolean locked;                       // a shot is on its way to it: it waits for it
        Look look;

        Mole(Hole hole) {
            this.hole = hole;
        }

        void spawn(Look l, float wait, float holdTime) {
            look = l;
            delay = wait;
            hold = holdTime;
            t = 0;
            rise = RISE;
            sinkTime = SINK;
            hopAt = -1;
            locked = false;
            state = wait > 0 ? WAIT : RISING;
        }

        void sink() {
            if (state == RISING || state == UP || state == REACT) {
                float p = pose();
                state = SINKING;
                t = sinkTime * (float) Math.sqrt(1 - Math.max(0, Math.min(1, p)));  // continue from the current height
            } else if (state == WAIT) {
                state = HIDDEN;
            }
        }

        void update(float dt) {
            if (locked && state != WAIT && state != RISING) {
                return;                           // held where it is until the shot lands
            }
            t += dt;
            switch (state) {
                case WAIT:
                    if (t >= delay) {
                        state = RISING;
                        t = 0;
                    }
                    break;
                case RISING:
                    if (t >= rise) {
                        state = UP;
                        t = 0;
                    }
                    break;
                case UP:
                    if (hopAt >= 0 && t >= hopAt && t < hold && hop(this)) {
                        break;                        // ducked: it pops up in another hole
                    }
                    if (t >= hold) {
                        state = SINKING;
                        t = 0;
                        escaped(this);
                    }
                    break;
                case REACT:
                    if (t >= WOBBLE) {
                        state = SINKING;
                        t = 0;
                    }
                    break;
                case SINKING:
                    if (t >= sinkTime) {
                        state = HIDDEN;
                        cooldown = 0.35f;
                    }
                    break;
                case POPPED:
                    if (t >= (fires ? STRUCK_POP : POP)) {
                        state = HIDDEN;
                        cooldown = 0.5f;
                    }
                    break;
                default:
                    cooldown -= dt;
                    break;
            }
        }

        /** 0 = inside the hole .. 1 = reference pose (a little over 1 while bouncing up). */
        float pose() {
            switch (state) {
                case RISING: {
                    float u = Math.min(1, t / rise), c = 1.3f, v = u - 1;
                    return 1 + (c + 1) * v * v * v + c * v * v;
                }
                case UP:
                case POPPED:
                case REACT:
                    return 1;
                case SINKING: {
                    float u = Math.min(1, t / sinkTime);
                    return 1 - u * u;
                }
                default:
                    return 0;
            }
        }

        boolean visible() {
            return state == RISING || state == UP || state == SINKING || state == POPPED || state == REACT;
        }

        boolean tappable() {
            return !locked && ((state == RISING && t > rise * 0.3f) || state == UP);
        }

        /** Where a shot strikes it: the middle of its body (art px). */
        float aimX() {
            return left() + look.width() * scale() / 2;
        }

        float aimY() {
            return hole.front() - (hole.front() - top()) * 0.45f;
        }

        float scale() {
            return hole.a / look.home.a;
        }

        /** Art-px top-left of the sprite at the current pose. */
        float left() {
            return hole.cx + (look.x - look.home.cx) * scale();
        }

        float top() {
            float f = scale();
            float hideDrop = (look.home.front() - look.y) * f + 6;
            return hole.front() + (look.y - look.home.front()) * f + (1 - pose()) * hideDrop;
        }

        /** Does the art point touch this character (its visible, opaque part, with some slack)? */
        boolean hit(float ax, float ay) {
            float f = scale(), l = left(), tp = top();
            Bitmap b = look.bitmap;
            float slack = 14;
            float[] dx = {0, -slack, slack, 0, 0}, dy = {0, 0, 0, -slack, slack};
            for (int i = 0; i < dx.length; i++) {
                float px = ax + dx[i], py = ay + dy[i];
                if (hole.hides(px, py)) {
                    continue;
                }
                int sx = (int) ((px - l) / f * look.density), sy = (int) ((py - tp) / f * look.density);
                if (sx >= 0 && sy >= 0 && sx < b.getWidth() && sy < b.getHeight() && (b.getPixel(sx, sy) >>> 24) > 64) {
                    return true;
                }
            }
            return false;
        }

        /** Rotation / scale of the whole character (sprite and light) for a reaction or a pop. */
        private float transform(Canvas c) {
            if (state == REACT) {
                float u = t / WOBBLE;
                float angle = (float) Math.sin(u * Math.PI * 5) * 9 * (1 - u);
                c.rotate(angle, xf.x(hole.cx), xf.y(hole.front()));
            } else if (state == POPPED && fires) {
                // struck by a shot: squashed by the impact, springs back, then pops (grows and fades)
                float s = (float) Math.sin(Math.PI * Math.min(1, t / 0.12f)) * (t < 0.06f ? 1 : 0.6f);
                c.scale(1 + 0.16f * s, 1 - 0.2f * s, xf.x(hole.cx), xf.y(hole.front()));
                float u = Math.max(0, (t - 0.06f) / 0.13f);
                float grow = 1 + 0.3f * easeOut(u);
                c.scale(grow, grow, dst.centerX(), dst.centerY());
                return u <= 0 ? 1 : Math.max(0, 1 - (float) Math.pow(u, 1.2));
            } else if (state == POPPED) {
                float grow = 1 + 0.35f * Math.min(1, t / POP);
                c.scale(grow, grow, dst.centerX(), dst.centerY());
                return Math.max(0, 1 - t / POP);
            }
            return 1;
        }

        void draw(Canvas c) {
            if (!visible()) {
                return;
            }
            float f = scale();
            xf.rect(left(), top(), look.width() * f, look.height() * f, dst);
            float m = dst.width() * 0.25f;
            layer.set(dst.left - m, dst.top - m, dst.right + m, dst.bottom + m);
            int save = c.saveLayer(layer, null);
            int moved = c.save();
            float alpha = transform(c);
            paint.setAlpha((int) (255 * alpha));
            // the flash of the hit, then it bursts into light as it goes
            float flash = state == POPPED && fires ? Math.max(0.85f * fade(t, 0, 0.14f), 0.95f * clamp01((t - 0.07f) / 0.08f)) : 0;
            if (flash > 0) {
                paint.setColorFilter(new PorterDuffColorFilter(Color.argb((int) (255 * flash), 255, 246, 255), PorterDuff.Mode.SRC_ATOP));
            }
            c.drawBitmap(look.bitmap, null, dst, paint);
            paint.setColorFilter(null);
            paint.setAlpha(255);
            c.restoreToCount(moved);
            c.drawPath(hole.hidden, eraser);   // the front rim stays where it is
            c.restoreToCount(save);
            if (look.glow != null) {
                // the character's light: added to whatever lies beneath, not clipped by the rim
                float p = Math.max(0, Math.min(1, pose()));
                RectF g = xf.rect(left() + (look.glowX - look.x) * f, top() + (look.glowY - look.y) * f,
                        look.glow.getWidth() / look.glowDensity * f, look.glow.getHeight() / look.glowDensity * f, new RectF());
                int s2 = c.save();
                alpha = transform(c);
                light.setAlpha((int) (255 * alpha * p * p));
                c.drawBitmap(look.glow, null, g, light);
                c.restoreToCount(s2);
            }
        }
    }

    static final class Particle {
        float x, y, vx, vy, life, age, size;
        int color;
        boolean star;
    }

    /** Floating "+10" / "-3s". */
    static final class Floater {
        float x, y, t;
        String text;
    }

    /** The reference's hit flash (Level 3) where a target was hit. */
    static final class Burst {
        float x, y, scale, t;
    }

    /**
     * A shot (tap-and-fire): a purple gem with a golden trail, from the player's side to a
     * character -- following it if it is still rising -- or to a spot on the ground.
     */
    final class Shot {
        Mole mole;                  // null: a spot on the ground (tx, ty)
        float tx, ty, t, time, side;
        boolean demo;               // the opening demonstration's: pops its character, scores nothing

        float endX() {
            return mole != null ? mole.aimX() : tx;
        }

        float endY() {
            return mole != null ? mole.aimY() : ty;
        }

        /** The point of the flight path at u (0: launch .. 1: the target), art px. */
        void at(float u, float[] out) {
            float ex = endX(), ey = endY();
            float dx = ex - fireX, dy = ey - fireY;
            // a curve: the control point is pushed sideways, the shot comes round a little
            float cx = (fireX + ex) / 2 - dy * 0.16f * side, cy = (fireY + ey) / 2 + dx * 0.16f * side;
            float v = 1 - u;
            out[0] = v * v * fireX + 2 * v * u * cx + u * u * ex;
            out[1] = v * v * fireY + 2 * v * u * cy + u * u * ey;
        }
    }

    /** The energy burst where a shot struck a purple (and the dull puff where it struck anything else). */
    static final class Hit {
        float x, y, r, t, spin;
        boolean dull;
    }

    LevelScreen(GameView game, int id, String dir) {
        super(game);
        this.id = id;
        Art art = game.art;
        JSONObject L = art.json(dir + "/level.json");
        JSONObject rules = L.optJSONObject("rules");
        legacy = rules == null;
        JSONObject a = L.optJSONObject("art"), b = L.optJSONObject("bg"), p = L.optJSONObject("pause");
        artW = a.optInt("w");
        artH = a.optInt("h");
        bg = new Fit.Backdrop(art.bitmap(b.optString("file")), b.optInt("pad_side"), b.optInt("pad_top"), (float) b.optDouble("scale", 1));
        JSONObject f = L.optJSONObject("fg_bottom");
        fg = f == null ? null : art.bitmap(f.optString("file"));
        fgX = f == null ? 0 : (float) f.optDouble("x");
        fgY = f == null ? 0 : (float) f.optDouble("y");
        JSONObject content = L.optJSONObject("content");
        contentTop = content == null ? 66 : (float) content.optDouble("top");
        referenceH = content == null ? 1156 : artH;
        if (content != null) {
            // new levels: the must-see rows end with the scene, not the art
            artHMust = (float) content.optDouble("bottom");
        } else {
            artHMust = artH;
        }
        JSONObject hit = p.optJSONObject("hit");
        float cx = (float) hit.optDouble("cx"), cy = (float) hit.optDouble("cy"), r = (float) hit.optDouble("r");
        pauseButton = new SpriteButton(art.bitmap(p.optString("file")), (float) p.optDouble("x"), (float) p.optDouble("y"),
                new float[]{cx - r, cy - r, cx + r, cy + r}, true, xf, (float) p.optDouble("scale", 1));
        JSONObject live = L.optJSONObject("live_text");
        hudText = legacy ? game.text : new OutlineText(art.font, style(live.optJSONObject("timer")));
        timerSlot = new OutlineText.Slot(live.optJSONObject("timer"));
        targetSlot = new OutlineText.Slot(live.optJSONObject("target"));
        scoreSlot = new OutlineText.Slot(live.optJSONObject("score"));
        JSONObject cb = L.optJSONObject("combo");
        comboWord = cb == null ? null : Sprite.of(art, cb.optJSONObject("word"));
        comboSlot = cb == null ? null : new OutlineText.Slot(cb.optJSONObject("number"));
        comboText = cb == null ? null : new OutlineText(art.font, style(cb.optJSONObject("number")));
        hint = Sprite.of(art, L.optJSONObject("hint"));
        banner = Sprite.of(art, L.optJSONObject("banner"));
        burst = Sprite.of(art, L.optJSONObject("burst"));
        JSONArray anchor = L.optJSONObject("burst") == null ? null : L.optJSONObject("burst").optJSONArray("anchor");
        burstAnchorX = anchor == null ? 0 : (float) anchor.optDouble(0);
        burstAnchorY = anchor == null ? 0 : (float) anchor.optDouble(1);
        hand = Sprite.of(art, L.optJSONObject("hand"));
        JSONArray tip = L.optJSONObject("hand") == null ? null : L.optJSONObject("hand").optJSONArray("tip");
        handTipX = tip == null ? 0 : (float) tip.optDouble(0);
        handTipY = tip == null ? 0 : (float) tip.optDouble(1);

        // rules (Level 1: the original constants)
        duration = legacy ? ROUND : (float) rules.optDouble("duration", 30);
        goal = legacy ? TARGETS : rules.optInt("goal", 12);
        points = legacy ? POINTS : rules.optInt("points", 10);
        combos = !legacy && rules.optBoolean("combo", false);
        swipe = !legacy && rules.optBoolean("swipe", false);
        bombPenalty = legacy ? 0 : (float) rules.optDouble("bomb_penalty", 3);
        JSONObject mix = legacy ? null : rules.optJSONObject("mix");
        mixTarget = mix == null ? 0.6f : (float) mix.optDouble("target", 0.6);
        mixDistractor = mix == null ? 0.4f : (float) mix.optDouble("distractor", 0.4);
        JSONArray hold = legacy ? null : rules.optJSONArray("hold");
        holdMin = hold == null ? 1.15f : (float) hold.optDouble(0);
        holdSpread = hold == null ? 0.45f : (float) (hold.optDouble(1) - hold.optDouble(0));
        JSONArray gap = legacy ? null : rules.optJSONArray("gap");
        gapMin = gap == null ? 0.45f : (float) gap.optDouble(0);
        gapSpread = gap == null ? 0.35f : (float) (gap.optDouble(1) - gap.optDouble(0));
        JSONArray up = legacy ? null : rules.optJSONArray("up_max");
        upEarly = up == null ? 2 : up.optInt(0);
        upLate = up == null ? 3 : up.optInt(1);
        quick = legacy ? 0 : (float) rules.optDouble("quick", 0);
        JSONObject sp = legacy ? null : rules.optJSONObject("speedup");
        speedAt = sp == null ? -1 : (float) sp.optDouble("at");
        speedHold = sp == null ? 1 : (float) sp.optDouble("hold", 1);
        speedGap = sp == null ? 1 : (float) sp.optDouble("gap", 1);
        speedUp = sp == null ? 0 : sp.optInt("up", 0);
        decoyFails = !legacy && rules.optBoolean("decoy_fails", false);
        JSONObject hop = legacy ? null : rules.optJSONObject("hop");
        JSONArray hc = hop == null ? null : hop.optJSONArray("chance");
        JSONArray ha = hop == null ? null : hop.optJSONArray("after");
        hopChance0 = hc == null ? 0 : (float) hc.optDouble(0);
        hopChance1 = hc == null ? 0 : (float) hc.optDouble(1);
        hopAfterMin = ha == null ? 0.4f : (float) ha.optDouble(0);
        hopAfterSpread = ha == null ? 0.2f : (float) (ha.optDouble(1) - ha.optDouble(0));
        JSONObject ramp = legacy ? null : rules.optJSONObject("ramp");
        rampHold = ramp == null ? 1 : (float) ramp.optDouble("hold", 1);
        rampGap = ramp == null ? 1 : (float) ramp.optDouble("gap", 1);
        rampRise = ramp == null ? 1 : (float) ramp.optDouble("rise", 1);
        referenceState = legacy ? null : rules.optJSONObject("reference_state");
        JSONObject fire = legacy ? null : rules.optJSONObject("fire");
        fires = fire != null;
        JSONArray from = fire == null ? null : fire.optJSONArray("from");
        fireX = from == null ? 0 : (float) from.optDouble(0);
        fireY = from == null ? 0 : (float) from.optDouble(1);
        fireSpeed = fire == null ? 1 : (float) fire.optDouble("speed", 2600);
        JSONArray ft = fire == null ? null : fire.optJSONArray("time");
        fireMin = ft == null ? 0.12f : (float) ft.optDouble(0);
        fireMax = ft == null ? 0.3f : (float) ft.optDouble(1);
        fieldTop = fire == null ? 0 : (float) fire.optDouble("field_top", 0);
        JSONObject demo = legacy ? null : rules.optJSONObject("demo");
        demoPress = demo == null ? -1 : (float) demo.optDouble("press", 1.5);

        JSONObject hs = L.optJSONObject("holes");
        List<String> ids = new ArrayList<>();
        for (Iterator<String> it = hs.keys(); it.hasNext(); ) {
            ids.add(it.next());
        }
        final JSONObject holesJson = hs;
        String[] sorted = ids.toArray(new String[0]);
        Arrays.sort(sorted, new java.util.Comparator<String>() {
            @Override
            public int compare(String x, String y) {
                double ax = holesJson.optJSONObject(x).optJSONArray("opening").optDouble(1);
                double ay = holesJson.optJSONObject(y).optJSONArray("opening").optDouble(1);
                return Double.compare(ax, ay);
            }
        });
        holes = new Hole[sorted.length];
        for (int i = 0; i < sorted.length; i++) {
            holes[i] = new Hole(i, hs.optJSONObject(sorted[i]));
            holes[i].mole = new Mole(holes[i]);
        }
        demoHole = demo == null || !fires || hand == null ? -1 : Arrays.asList(sorted).indexOf(demo.optString("hole"));
        // every character as the reference shows it, then the stand-ins for each role and hole
        JSONObject cs = L.optJSONObject("chars");
        List<Look> looks = new ArrayList<>();
        Look[] nativeLook = new Look[holes.length];
        for (int k = 0; k < 3; k++) {
            byRole.add(new ArrayList<Look>());
        }
        for (Iterator<String> it = cs.keys(); it.hasNext(); ) {
            JSONObject c = cs.optJSONObject(it.next());
            Hole home = holes[Arrays.asList(sorted).indexOf(c.optString("hole"))];
            String col = c.optString("color");
            int colour = "green".equals(col) ? GREEN : "red".equals(col) ? RED : YELLOW;
            String rl = c.optString("role", colour == GREEN ? "target" : "distractor");
            int role = "target".equals(rl) ? TARGET : "bomb".equals(rl) ? BOMB : DISTRACTOR;
            Look l = new Look(art.bitmap(c.optString("file")), (float) c.optDouble("x"), (float) c.optDouble("y"), home,
                    legacy ? colour : -1, role, c.optBoolean("intro_only", false));
            JSONObject g = c.optJSONObject("glow");
            if (g != null) {
                l.glow = art.bitmap(g.optString("file"));
                l.glowX = (float) g.optDouble("x");
                l.glowY = (float) g.optDouble("y");
                l.glowDensity = (float) g.optDouble("scale", 1);
            }
            l.density = (float) c.optDouble("scale", 1);
            l.tint = averageColour(l.bitmap);
            looks.add(l);
            if (!c.optBoolean("spawn_only", false)) {
                nativeLook[home.index] = l;           // (a pop-up-only look is not in the opening wave)
            }
            if (!l.introOnly) {
                byRole.get(role).add(l);
            }
        }
        referenceLooks = nativeLook;
        lookFor = new Look[3][holes.length];
        for (int colour = 0; colour < 3; colour++) {
            for (Hole hole : holes) {
                Look best = null;
                for (Look l : looks) {
                    if (l.colour != colour || l.introOnly) {
                        continue;
                    }
                    if (l.home == hole) {
                        best = l;
                        break;
                    }
                    if (best == null || Math.abs(l.home.a - hole.a) < Math.abs(best.home.a - hole.a)) {
                        best = l;
                    }
                }
                lookFor[colour][hole.index] = best;
            }
        }
        eraser.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.DST_OUT));
        light.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.ADD));
    }

    private final float artHMust;

    /** Lettering colours of a level.json text spec, in OutlineText's style format. */
    private static JSONObject style(JSONObject spec) {
        JSONObject s = new JSONObject();
        try {
            s.put("fill_top", spec.optJSONArray("fill_top"));
            s.put("fill_bottom", spec.optJSONArray("fill_bottom"));
            s.put("outline", spec.optJSONArray("outline_color"));
        } catch (org.json.JSONException ignored) {
        }
        return s;
    }

    /** Mean colour of a sprite's opaque pixels (for its pop particles). */
    private static int averageColour(Bitmap b) {
        long r = 0, g = 0, bl = 0, n = 0;
        int step = Math.max(1, Math.min(b.getWidth(), b.getHeight()) / 24);
        for (int y = 0; y < b.getHeight(); y += step) {
            for (int x = 0; x < b.getWidth(); x += step) {
                int c = b.getPixel(x, y);
                if ((c >>> 24) > 200) {
                    r += (c >> 16) & 255;
                    g += (c >> 8) & 255;
                    bl += c & 255;
                    n++;
                }
            }
        }
        if (n == 0) {
            return 0xffffffff;
        }
        return 0xff000000 | (int) (r / n) << 16 | (int) (g / n) << 8 | (int) (bl / n);
    }

    // ------------------------------------------------------------------ layout
    @Override
    void layout(int width, int height) {
        super.layout(width, height);
        android.graphics.Rect safe = game.safe;
        float topNeed = Fit.topNeed(game);
        float s = Fit.scale(artW, contentTop, artHMust, w - safe.left - safe.right, h - safe.bottom, topNeed);
        xf.set(s, Fit.left(safe, w, artW, s), Math.max(0, topNeed - contentTop * s));
        // Level 1: the foliage sits on the bottom edge of the screen, wherever that falls in the scene
        fgShift = (h - xf.oy) / s - referenceH;
        for (Hole hole : holes) {
            hole.layout(xf, w, h);
        }
        if (dialog != null) {
            dialog.layout(w, h, s, safe);
        }
    }

    // ------------------------------------------------------------------ round
    @Override
    void onShow() {
        startRound();
    }

    void seed(long seed) {
        rnd.setSeed(seed);
    }

    void startRound() {
        elapsed = sinceStart = 0;
        score = 0;
        combo = maxCombo = 0;
        targetsLeft = goal;
        paused = over = won = false;
        overT = 0;
        dialog = null;
        pausePressed = swiping = false;
        pauseButton.pressed = false;
        particles.clear();
        floaters.clear();
        bursts.clear();
        shots.clear();
        hits.clear();
        demoOn = demoHole >= 0;
        demoFired = false;
        demoOff = -1;
        targetPulse = scorePulse = timerPulse = comboPulse = 0;
        failing = false;
        failT = 0;
        bannerT = -1;
        fast = false;
        nextSpawn = 0;
        // opening wave: every character rises into its reference pose and stays a few seconds
        for (int i = 0; i < holes.length; i++) {
            holes[i].mole.state = Mole.HIDDEN;
            holes[i].mole.cooldown = 0;
            if (referenceLooks[i] != null) {
                float wait = 0.04f * i;
                holes[i].mole.spawn(referenceLooks[i], wait, INTRO_HOLD_UNTIL + 0.07f * i - wait - RISE);
            }
        }
    }

    private void pauseGame() {
        if (!paused && !over && !failing) {
            paused = true;
            dialog = new Ui.Dialog("PAUSED").button(PAUSE_RESUME, "RESUME", true).button(PAUSE_HOME, "HOME", false);
            dialog.layout(w, h, xf.s, game.safe);
        }
    }

    private void finish(boolean allHit) {
        over = true;
        won = allHit;
        overT = 0;
        shots.clear();                                // (any shot still flying has nothing left to win)
        for (Hole hole : holes) {
            hole.mole.locked = false;
            hole.mole.sink();
        }
        if (allHit) {
            game.levelWon(id);
        }
        game.sfx.end();
    }

    @Override
    void onPause() {
        pauseGame();
    }

    @Override
    void update(float dt) {
        pauseButton.update(dt);
        if (dialog != null) {
            dialog.update(dt);
        }
        if (paused) {
            return;
        }
        sinceStart += dt;
        if (failing) {
            failT += dt;                              // "WRONG MINER!", then the level starts again
            if (failT >= FAIL_TIME) {
                startRound();
                return;
            }
        } else if (over) {
            overT += dt;
            if (dialog == null && overT > 0.7f) {
                dialog = new Ui.Dialog(won ? "LEVEL COMPLETE!" : "TIME'S UP!");
                if (won && game.nextLevel(id) > 0) {
                    dialog.button(OVER_NEXT, "NEXT LEVEL", true).button(OVER_HOME, "HOME", false);
                } else {
                    dialog.button(OVER_AGAIN, "PLAY AGAIN", true).button(OVER_HOME, "HOME", false);
                }
                dialog.line = "SCORE: " + format(score);
                dialog.layout(w, h, xf.s, game.safe);
            }
        } else {
            elapsed += dt;
            if (elapsed >= duration) {
                elapsed = duration;
                if (shots.isEmpty()) {                // a shot fired in time still counts when it lands
                    finish(false);
                }
            } else {
                if (!fast && speedAt >= 0 && elapsed >= speedAt) {
                    fast = true;                     // "SPEED INCREASED!"
                    bannerT = 0;
                    game.sfx.pop();
                }
                spawn(dt);
            }
        }
        if (bannerT >= 0) {
            bannerT += dt;
            if (bannerT > BANNER_TIME) {
                bannerT = -1;
            }
        }
        for (Hole hole : holes) {
            hole.mole.update(dt);
        }
        if (demoOn && !demoFired && !over && !failing && sinceStart >= demoPress + 0.05f) {
            demoFired = true;                         // the demonstration's hand has pressed: its shot leaves
            Mole m = holes[demoHole].mole;
            if (m.tappable()) {
                fire(m, 0, 0, true);
            }
        }
        for (int i = 0; i < shots.size(); i++) {
            Shot q = shots.get(i);
            q.t += dt;
            if (q.t >= q.time) {
                shots.remove(i--);
                land(q);
                if (over) {
                    break;
                }
            }
        }
        for (Iterator<Hit> it = hits.iterator(); it.hasNext(); ) {
            Hit q = it.next();
            q.t += dt;
            if (q.t > HIT_TIME) {
                it.remove();
            }
        }
        targetPulse = Math.max(0, targetPulse - dt);
        scorePulse = Math.max(0, scorePulse - dt);
        timerPulse = Math.max(0, timerPulse - dt);
        comboPulse = Math.max(0, comboPulse - dt);
        for (Iterator<Particle> it = particles.iterator(); it.hasNext(); ) {
            Particle q = it.next();
            q.age += dt;
            if (q.age >= q.life) {
                it.remove();
                continue;
            }
            q.vy += 900 * dt;
            q.vx *= (1 - 1.5f * dt);
            q.x += q.vx * dt;
            q.y += q.vy * dt;
        }
        for (Iterator<Floater> it = floaters.iterator(); it.hasNext(); ) {
            Floater q = it.next();
            q.t += dt;
            if (q.t > 0.8f) {
                it.remove();
            }
        }
        for (Iterator<Burst> it = bursts.iterator(); it.hasNext(); ) {
            Burst q = it.next();
            q.t += dt;
            if (q.t > BURST_TIME) {
                it.remove();
            }
        }
    }

    private void spawn(float dt) {
        if (elapsed < SPAWN_FROM) {
            return;
        }
        nextSpawn -= dt;
        if (nextSpawn > 0) {
            return;
        }
        float progress = Math.min(1, (elapsed - SPAWN_FROM) / (duration - SPAWN_FROM));
        int up = 0;
        List<Hole> free = new ArrayList<>();
        for (Hole hole : holes) {
            Mole m = hole.mole;
            if (m.state == Mole.HIDDEN) {
                if (m.cooldown <= 0) {
                    free.add(hole);
                }
            } else if (m.state != Mole.SINKING && m.state != Mole.POPPED) {
                up++;
            }
        }
        int upMax = (progress < 0.35f ? upEarly : upLate) + (fast ? speedUp : 0);
        if (up < upMax && !free.isEmpty()) {
            Hole hole = free.get(rnd.nextInt(free.size()));
            float r = rnd.nextFloat();
            Look look;
            if (legacy) {
                int colour = r < 0.6f ? GREEN : r < 0.8f ? RED : YELLOW;
                look = lookFor[colour][hole.index];
            } else {
                int role = r < mixTarget ? TARGET : r < mixTarget + mixDistractor ? DISTRACTOR : BOMB;
                if (byRole.get(role).isEmpty()) {
                    role = byRole.get(DISTRACTOR).isEmpty() ? TARGET : DISTRACTOR;
                }
                look = pick(byRole.get(role), hole);
            }
            float hold = (holdMin + holdSpread * rnd.nextFloat()) * (1 - 0.3f * progress) * (fast ? speedHold : 1)
                    * lerp(1, rampHold, progress);
            if (quick > 0 && rnd.nextFloat() < quick) {
                hold *= 0.6f;                         // a quick one: less time to react
            }
            Mole m = hole.mole;
            m.spawn(look, 0, hold);
            m.rise = RISE * lerp(1, rampRise, progress);
            // (only levels with hops draw this number: the others keep their exact pop-up sequence)
            if (hopChance1 > 0 && rnd.nextFloat() < lerp(hopChance0, hopChance1, progress)) {
                m.hopAt = Math.min(hold * 0.7f, hopAfterMin + hopAfterSpread * rnd.nextFloat());
            }
            nextSpawn = (gapMin + gapSpread * rnd.nextFloat()) * (1 - 0.25f * progress) * (fast ? speedGap : 1)
                    * lerp(1, rampGap, progress);
        } else {
            nextSpawn = 0.1f;
        }
    }

    /**
     * A look of the role for this hole: its own if it has one (half the time), else any that need
     * not be enlarged much to fit it (a far-away character blown up in a front hole looks soft);
     * if none, the largest one.
     */
    private Look pick(List<Look> looks, Hole hole) {
        if (rnd.nextBoolean()) {
            for (Look l : looks) {
                if (l.home == hole) {
                    return l;
                }
            }
        }
        List<Look> fit = new ArrayList<>();
        Look largest = null;
        for (Look l : looks) {
            if (hole.a / l.home.a <= MAX_ENLARGE) {
                fit.add(l);
            }
            if (largest == null || l.home.a > largest.home.a) {
                largest = l;
            }
        }
        return fit.isEmpty() ? largest : fit.get(rnd.nextInt(fit.size()));
    }

    private static float lerp(float a, float b, float u) {
        return a + (b - a) * u;
    }

    private static float clamp01(float u) {
        return Math.max(0, Math.min(1, u));
    }

    private static float easeOut(float u) {
        float v = 1 - clamp01(u);
        return 1 - v * v * v;
    }

    /** 1 before t0, 0 after t1, smooth in between. */
    private static float fade(float t, float t0, float t1) {
        float u = clamp01((t - t0) / (t1 - t0));
        return 1 - u * u * (3 - 2 * u);
    }

    /**
     * A character ducks and pops up in another free hole a moment later (the rest of its time up
     * there). Returns false (it stays) if no hole is free.
     */
    private boolean hop(Mole m) {
        List<Hole> free = new ArrayList<>();
        for (Hole hole : holes) {
            if (hole != m.hole && hole.mole.state == Mole.HIDDEN && hole.mole.cooldown <= 0) {
                free.add(hole);
            }
        }
        if (free.isEmpty() || over || failing) {
            m.hopAt = -1;
            return false;
        }
        Hole to = free.get(rnd.nextInt(free.size()));
        float left = Math.max(0.45f, m.hold - m.t);
        m.state = Mole.SINKING;
        m.sinkTime = HOP_SINK;
        m.t = 0;
        to.mole.spawn(m.look, HOP_SINK + 0.05f, left);
        to.mole.rise = HOP_RISE;
        hops++;
        return true;
    }

    /** A decoy was tapped where decoys fail the round: it starts again (after a moment). */
    private void fail(Mole m) {
        failing = true;
        failT = 0;
        failures++;
        m.state = Mole.REACT;
        m.t = 0;
        for (Hole hole : holes) {
            if (hole.mole != m) {
                hole.mole.sink();
            }
        }
        game.sfx.bonk();
        game.sfx.buzz(140);
        dialog = new Ui.Dialog("WRONG MINER!");
        dialog.line = "ONLY TAP THE GOLD ONES!";
        dialog.layout(w, h, xf.s, game.safe);
    }

    /** A target went back into its hole without being hit: the combo is broken. */
    private void escaped(Mole m) {
        if (m.look.role == TARGET && !over) {
            combo = 0;
        }
    }

    /**
     * A tap (down: the finger touched; else, where the level allows it, a swipe going over) at screen
     * point (x, y) during play. Tap-and-fire levels launch a shot at the character (or, for a tap,
     * at the spot on the ground); the others hit at once.
     */
    void tap(float x, float y, boolean down) {
        if (paused || over || failing || elapsed >= duration) {
            return;
        }
        float ax = xf.artX(x), ay = xf.artY(y);
        if (fires && demoOn) {
            demoOn = false;                           // the player has started: the demonstration steps aside
            demoOff = sinceStart;
        }
        if (fires && down && ay >= fieldTop) {
            Hit ring = new Hit();                     // where the finger touched
            ring.x = ax;
            ring.y = ay;
            ring.r = 20;
            ring.dull = true;
            hits.add(ring);
        }
        for (int i = holes.length - 1; i >= 0; i--) {   // front-most first
            Mole m = holes[i].mole;
            if (m.locked && m.visible() && m.hit(ax, ay)) {
                return;                               // a shot is already on its way to it
            }
            if (!m.tappable() || !m.hit(ax, ay)) {
                continue;
            }
            if (fires) {
                fire(m, 0, 0, false);
            } else {
                strike(m);
            }
            return;
        }
        if (fires && down && ay >= fieldTop && ay <= artHMust && ax >= 0 && ax <= artW) {
            fire(null, ax, ay, false);                // a miss: the shot lands on the ground
        }
    }

    /** A shot leaves the player's side for the character m (or the spot ax, ay). */
    private void fire(Mole m, float ax, float ay, boolean demo) {
        Shot q = new Shot();
        q.mole = m;
        q.tx = ax;
        q.ty = ay;
        q.demo = demo;
        if (m != null) {
            m.locked = true;
        }
        float dx = q.endX() - fireX, dy = q.endY() - fireY;
        q.time = Math.max(fireMin, Math.min(fireMax, (float) Math.hypot(dx, dy) / fireSpeed));
        q.side = Math.abs(dx) > 40 ? Math.signum(dx) : (shots.size() % 2 == 0 ? 1 : -1);
        shots.add(q);
        for (int i = 0; i < 6; i++) {                 // sparks at the launch
            Particle p = new Particle();
            double ang = -Math.PI / 2 + (rnd.nextDouble() - 0.5) * 2.2;
            float speed = 180 + 220 * rnd.nextFloat();
            p.x = fireX;
            p.y = fireY;
            p.vx = (float) Math.cos(ang) * speed;
            p.vy = (float) Math.sin(ang) * speed;
            p.life = 0.25f + 0.15f * rnd.nextFloat();
            p.star = i % 3 == 0;
            p.size = p.star ? 10 : 4 + 3 * rnd.nextFloat();
            p.color = i % 2 == 0 ? 0xffffe27a : 0xffffffff;
            particles.add(p);
        }
        game.sfx.shoot();
    }

    /** A shot has arrived. */
    private void land(Shot q) {
        Mole m = q.mole;
        if (m == null) {
            puff(q.tx, q.ty, 0.8f, 0xffcfa477);      // on the ground: a little dust
            return;
        }
        m.locked = false;
        if (!m.tappable() && m.state != Mole.RISING) {
            return;
        }
        if (q.demo) {
            m.state = Mole.POPPED;                    // the demonstration: the full hit, no points
            m.t = 0;
            burst(m);
            game.sfx.pop();
            return;
        }
        strike(m);
    }

    /** m is hit (tapped, or struck by a shot): a target pops and scores, the others react. */
    private void strike(Mole m) {
        if (m.look.role == TARGET) {
            m.state = Mole.POPPED;
            m.t = 0;
            if (combos) {
                combo++;
                maxCombo = Math.max(maxCombo, combo);
                if (combo >= 2) {
                    comboPulse = 0.3f;
                }
            }
            int gain = points * Math.max(1, combos ? combo : 1);
            score += gain;
            targetsLeft--;
            targetPulse = scorePulse = 0.25f;
            burst(m);
            Floater plus = new Floater();
            plus.x = m.hole.cx;
            plus.y = m.top() + 10;
            plus.text = "+" + gain;
            floaters.add(plus);
            game.sfx.pop();
            if (targetsLeft == 0) {
                finish(true);
            }
        } else if (decoyFails && m.look.role == DISTRACTOR) {
            fail(m);
        } else {
            if (fires) {
                puff(m.aimX(), m.aimY(), m.scale(), 0xffe9e4f2);   // struck, but no credit: a dull puff
            }
            m.state = Mole.REACT;
            m.t = 0;
            combo = 0;
            if (m.look.role == BOMB) {
                elapsed = Math.min(duration - 0.01f, elapsed + bombPenalty);
                timerPulse = 0.5f;
                Floater minus = new Floater();
                minus.x = m.hole.cx;
                minus.y = m.top() + 10;
                minus.text = "-" + Math.round(bombPenalty) + "s";
                floaters.add(minus);
                game.sfx.bonk();
                game.sfx.buzz(80);
            } else {
                game.sfx.bonk();
            }
        }
    }

    /** A small dull impact: a grey ring and a few specks of `color`. */
    private void puff(float x, float y, float f, int color) {
        Hit h = new Hit();
        h.x = x;
        h.y = y;
        h.r = 34 * f;
        h.dull = true;
        hits.add(h);
        for (int i = 0; i < 7; i++) {
            Particle p = new Particle();
            double ang = rnd.nextDouble() * Math.PI * 2;
            float speed = (120 + 140 * rnd.nextFloat()) * f;
            p.x = x;
            p.y = y;
            p.vx = (float) Math.cos(ang) * speed;
            p.vy = (float) Math.sin(ang) * speed - 160;
            p.life = 0.3f + 0.15f * rnd.nextFloat();
            p.size = (4 + 4 * rnd.nextFloat()) * f;
            p.color = color;
            particles.add(p);
        }
    }

    private void burst(Mole m) {
        float f = m.scale();
        float cx = m.hole.cx, cy = m.hole.front() - (m.look.home.front() - m.look.y) * f * 0.45f;
        if (fires) {
            // the energy burst: its sparkles and orbs are part of it (drawHit)
            Hit h = new Hit();
            h.x = m.aimX();
            h.y = m.aimY();
            h.r = m.look.width() * f * 0.42f;
            h.spin = rnd.nextFloat() * 360;
            hits.add(h);
            return;
        }
        if (burst != null) {
            Burst q = new Burst();
            q.x = cx;
            q.y = cy;
            q.scale = f;
            bursts.add(q);
        }
        int tint = m.look.tint;
        for (int i = 0; i < 16; i++) {
            Particle q = new Particle();
            double ang = rnd.nextDouble() * Math.PI * 2;
            float speed = (260 + 320 * rnd.nextFloat()) * f;
            q.x = cx;
            q.y = cy;
            q.vx = (float) Math.cos(ang) * speed;
            q.vy = (float) Math.sin(ang) * speed - 260;
            q.life = 0.45f + 0.3f * rnd.nextFloat();
            q.star = i % 4 == 0;
            q.size = (q.star ? 13 : 7 + 7 * rnd.nextFloat()) * f;
            if (legacy) {
                q.color = q.star ? 0xffffffff : (i % 3 == 0 ? 0xffb6ff7a : 0xff37d43a);
            } else {
                q.color = q.star ? 0xffffffff : (i % 3 == 0 ? Ui.blend(tint, 0xffffffff, 0.45f) : Ui.blend(tint, 0xff000000, 0.05f));
            }
            particles.add(q);
        }
    }

    // ------------------------------------------------------------------ input
    @Override
    void touch(MotionEvent e) {
        if (dialog != null) {
            onDialog(dialog.touch(e, game.sfx));
            return;
        }
        int action = e.getActionMasked();
        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
            int i = e.getActionIndex();
            float x = e.getX(i), y = e.getY(i);
            if (action == MotionEvent.ACTION_DOWN && pauseButton.contains(x, y)) {
                pausePressed = true;
                pauseButton.pressed = true;
            } else {
                tap(x, y, true);
                swiping = swipe;
            }
        } else if (action == MotionEvent.ACTION_MOVE && pausePressed) {
            pauseButton.pressed = pauseButton.contains(e.getX(0), e.getY(0));
        } else if (action == MotionEvent.ACTION_MOVE && swiping) {
            // slicing through characters: every point of the finger's path counts as a tap
            for (int k = 0; k < e.getHistorySize(); k++) {
                tap(e.getHistoricalX(0, k), e.getHistoricalY(0, k), false);
            }
            tap(e.getX(0), e.getY(0), false);
        } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
            swiping = false;
            if (pausePressed) {
                boolean inside = action == MotionEvent.ACTION_UP && pauseButton.contains(e.getX(), e.getY());
                pausePressed = false;
                pauseButton.pressed = false;
                if (inside) {
                    game.sfx.click();
                    pauseGame();
                }
            }
        }
    }

    private void onDialog(int dialogId) {
        if (dialogId == PAUSE_RESUME) {
            paused = false;
            dialog = null;
        } else if (dialogId == PAUSE_HOME || dialogId == OVER_HOME) {
            game.show(game.home);
        } else if (dialogId == OVER_AGAIN) {
            startRound();
        } else if (dialogId == OVER_NEXT) {
            game.show(game.levelScreen(game.nextLevel(id)));
        }
    }

    @Override
    boolean back() {
        if (failing) {
            return true;
        }
        if (over) {
            if (dialog != null) {
                game.show(game.home);
            }
        } else if (paused) {
            paused = false;
            dialog = null;
        } else {
            pauseGame();
        }
        return true;
    }

    // ------------------------------------------------------------------ drawing
    static String format(int n) {
        return String.format(Locale.US, "%,d", n);
    }

    /** Hint and flash of the reference moment: shown while the opening wave is up. */
    private float introFx() {
        if (sinceStart >= INTRO_FX_GONE) {
            return 0;
        }
        return sinceStart <= INTRO_FX_FADE ? 1 : 1 - (sinceStart - INTRO_FX_FADE) / (INTRO_FX_GONE - INTRO_FX_FADE);
    }

    private void drawSprite(Canvas c, Sprite sp, float alpha) {
        if (sp == null || alpha <= 0) {
            return;
        }
        xf.rect(sp.x, sp.y, sp.w, sp.h, dst);
        paint.setAlpha((int) (255 * alpha));
        c.drawBitmap(sp.bitmap, null, dst, paint);
        paint.setAlpha(255);
    }

    @Override
    void draw(Canvas c) {
        bg.draw(c, xf, w, h);
        for (Hole hole : holes) {                     // back to front
            hole.mole.draw(c);
        }
        if (fg != null) {
            xf.rect(fgX, fgY + fgShift, fg.getWidth(), fg.getHeight(), dst);
            c.drawBitmap(fg, null, dst, paint);
        }
        float intro = introFx();
        if (!fires) {
            drawSprite(c, burst, intro);
            drawSprite(c, hint, intro);
        }
        drawHand(c);
        drawEffects(c);
        if (banner != null && bannerT >= 0) {
            float in = Math.min(1, bannerT / 0.25f);
            float a = bannerT > BANNER_TIME - 0.4f ? (BANNER_TIME - bannerT) / 0.4f : 1;
            float k = 0.85f + 0.15f * Ui.easeOutBack(in);
            int save = c.save();
            c.scale(k, k, xf.x(banner.x + banner.w / 2f), xf.y(banner.y + banner.h / 2f));
            drawSprite(c, banner, Math.max(0, Math.min(1, a * in * 1.5f)));
            c.restoreToCount(save);
        }

        if (comboWord != null && combo >= 2) {
            float k = comboPulse > 0 ? 1 + 0.2f * (float) Math.sin(Math.PI * (1 - comboPulse / 0.3f)) : 1;
            int save = c.save();
            c.scale(k, k, xf.x(comboWord.x + comboWord.w / 2f), xf.y(comboWord.y + comboWord.h / 2f));
            drawSprite(c, comboWord, 1);
            comboSlot.draw(c, comboText, combo + "x", xf);
            c.restoreToCount(save);
        }
        pauseButton.draw(c, paint);
        int secs = (int) Math.ceil(Math.max(0, duration - elapsed) - 1e-4);
        String timer = String.format(Locale.US, "%02d:%02d", secs / 60, secs % 60);
        drawPulsed(c, timerSlot, timer, timerPulse, 0.5f);
        drawPulsed(c, targetSlot, String.valueOf(targetsLeft), targetPulse, 0.25f);
        drawPulsed(c, scoreSlot, format(score), scorePulse, 0.25f);
        if (dialog != null) {
            dialog.draw(c, w, h, game.text, ui);
        }
    }

    private void drawPulsed(Canvas c, OutlineText.Slot slot, String text, float pulse, float length) {
        if (pulse <= 0) {
            slot.draw(c, hudText, text, xf);
            return;
        }
        float k = 1 + 0.18f * (float) Math.sin(Math.PI * (1 - pulse / length));
        int save = c.save();
        float px = slot.align == OutlineText.CENTER ? xf.x((slot.left + slot.right) / 2) : xf.x(slot.left);
        c.scale(k, k, px, xf.y(slot.top + slot.size * 0.36f));
        slot.draw(c, hudText, text, xf);
        c.restoreToCount(save);
    }

    private void drawEffects(Canvas c) {
        float s = xf.s;
        for (Hit q : hits) {
            drawHit(c, q);
        }
        for (Shot q : shots) {
            drawShot(c, q);
        }
        for (Burst q : bursts) {
            float u = q.t / BURST_TIME;
            float k = q.scale * (0.6f + 0.55f * u);
            float bw = burst.w * k, bh = burst.h * k;
            float left = q.x - (burstAnchorX - burst.x) * k, top = q.y - (burstAnchorY - burst.y) * k;
            xf.rect(left, top, bw, bh, dst);
            paint.setAlpha((int) (255 * Math.max(0, 1 - u * u)));
            c.drawBitmap(burst.bitmap, null, dst, paint);
            paint.setAlpha(255);
        }
        for (Particle q : particles) {
            float a = 1 - q.age / q.life;
            fx.setColor(q.color);
            fx.setAlpha((int) (255 * Math.min(1, a * 1.6f)));
            float x = xf.x(q.x), y = xf.y(q.y), r = q.size * s * (0.6f + 0.4f * a);
            if (q.star) {
                Path star = new Path();
                for (int k = 0; k < 8; k++) {
                    double ang = Math.PI / 4 * k + q.age * 6;
                    float rr = k % 2 == 0 ? r : r * 0.35f;
                    float px = x + (float) Math.cos(ang) * rr, py = y + (float) Math.sin(ang) * rr;
                    if (k == 0) {
                        star.moveTo(px, py);
                    } else {
                        star.lineTo(px, py);
                    }
                }
                star.close();
                c.drawPath(star, fx);
            } else {
                c.drawCircle(x, y, r, fx);
            }
        }
        for (Floater q : floaters) {
            float a = q.t < 0.4f ? 1 : Math.max(0, 1 - (q.t - 0.4f) / 0.4f);
            float y = q.y - 80 * (1 - (1 - q.t / 0.8f) * (1 - q.t / 0.8f));
            hudText.draw(c, q.text, xf.x(q.x), xf.y(y), OutlineText.CENTER, 54 * s, 0.9f, 3.4f * s, 3 * s, (int) (255 * a));
        }
    }

    // ------------------------------------------------------------------ tap-and-fire
    private static final int[] SPARK_ANGLE = {20, 75, 130, 170, 215, 260, 300, 340};
    private static final float[] SPARK_SIZE = {1f, 0.8f, 1.1f, 0.75f, 0.95f, 0.7f, 1.05f, 0.85f};
    private static final int[] SPARK_COLOUR = {0xffffffff, 0xffffec96, 0xffe8c8ff, 0xffffaae8};
    private static final float[] ORB_SPEED = {1f, 0.7f, 0.9f, 0.6f, 1.1f, 0.8f, 0.65f, 0.95f, 0.75f, 1f, 0.7f, 0.85f, 0.9f, 0.6f};
    private static final int[] ORB_COLOUR = {0xffc478ff, 0xffff78de, 0xffffde78};

    /** A 4-pointed (thin 0.2) or 8-pointed star around (x, y), screen px. */
    private Path star(float x, float y, float r, double rot, float thin) {
        path.reset();
        for (int k = 0; k < 8; k++) {
            double ang = rot + Math.PI / 4 * k;
            float rr = k % 2 == 0 ? r : r * thin;
            float px = x + (float) Math.cos(ang) * rr, py = y + (float) Math.sin(ang) * rr;
            if (k == 0) {
                path.moveTo(px, py);
            } else {
                path.lineTo(px, py);
            }
        }
        path.close();
        return path;
    }

    /** A soft round light of colour `color` (alpha = strength). */
    private void glowDot(Canvas c, float x, float y, float r, int color, float strength) {
        if (r <= 0.5f || strength <= 0) {
            return;
        }
        energy.setShader(new RadialGradient(x, y, r, new int[]{color, color & 0x00ffffff}, null, Shader.TileMode.CLAMP));
        energy.setAlpha((int) (255 * Math.min(1, strength)));
        c.drawCircle(x, y, r, energy);
        energy.setShader(null);
        energy.setAlpha(255);
    }

    /**
     * The purple burst where a shot struck (t: time since): a white-hot core, magenta rays, an
     * expanding ring, sparkles and energy orbs flung out. A dull hit only shows a grey ring.
     */
    private void drawHit(Canvas c, Hit h) {
        float s = xf.s, X = xf.x(h.x), Y = xf.y(h.y), R = h.r * s, t = h.t;
        fx.setStyle(Paint.Style.STROKE);
        if (h.dull) {
            float u = easeOut(t / 0.3f), a = fade(t, 0.05f, 0.3f);
            fx.setStrokeWidth(R * 0.16f * (1 - u) + 1.5f * s);
            fx.setColor(0xffeeeaf4);
            fx.setAlpha((int) (210 * a));
            c.drawCircle(X, Y, R * (0.4f + 0.9f * u), fx);
            fx.setStyle(Paint.Style.FILL);
            return;
        }
        double spin = Math.toRadians(h.spin);
        // the expanding ring (glow under a bright line)
        if (t >= 0.02f && t <= 0.32f) {
            float u = easeOut((t - 0.02f) / 0.3f), a = fade(t, 0.12f, 0.32f);
            float rr = R * (0.5f + 1.25f * u), wd = R * (0.16f * (1 - u) + 0.025f);
            energy.setStyle(Paint.Style.STROKE);
            energy.setStrokeWidth(wd * 3);
            energy.setColor(0xffa050ff);
            energy.setAlpha((int) (150 * a));
            c.drawCircle(X, Y, rr, energy);
            energy.setStyle(Paint.Style.FILL);
            energy.setAlpha(255);
            fx.setStrokeWidth(wd);
            fx.setColor(0xfff0daff);
            fx.setAlpha((int) (255 * a));
            c.drawCircle(X, Y, rr, fx);
        }
        fx.setStyle(Paint.Style.FILL);
        // the hot core: white, pale gold, hot pink, violet
        float coreR = R * (0.5f + 0.75f * easeOut(t / 0.07f)) * 1.2f;
        float coreA = Math.min(1, 0.25f + t / 0.03f) * fade(t, 0.06f, 0.2f);
        if (coreA > 0) {
            energy.setShader(new RadialGradient(X, Y, coreR, new int[]{0xffffffff, 0xfffff2b0, 0xffff5ad2, 0xcc9040ff, 0x009040ff},
                    new float[]{0, 0.14f, 0.36f, 0.62f, 1}, Shader.TileMode.CLAMP));
            energy.setAlpha((int) (255 * coreA));
            c.drawCircle(X, Y, coreR, energy);
            energy.setShader(null);
            energy.setAlpha(255);
        }
        // rays: shoot out, then thin and fade
        float grow = easeOut(t / 0.11f), rayA = fade(t, 0.10f, 0.24f), thin = 1 - 0.6f * easeOut((t - 0.05f) / 0.2f);
        if (rayA > 0) {
            for (int pass = 0; pass < 2; pass++) {
                Paint p = pass == 0 ? energy : fx;
                p.setColor(pass == 0 ? 0xffff3cd2 : 0xfffff0c8);
                p.setAlpha((int) (255 * rayA * (pass == 0 ? 0.8f : 1)));
                for (int i = 0; i < 10; i++) {
                    float ln = i % 2 == 0 ? 1 : 0.62f;
                    double a = spin + Math.toRadians(i * 36 + (i % 2 == 1 ? 9 : -4));
                    float r0 = R * (0.35f + 0.35f * grow), r1 = R * (0.55f + 1.25f * ln * grow) * (pass == 0 ? 1.08f : 1);
                    float rm = r0 + (r1 - r0) * 0.3f, w = R * 0.13f * ln * thin * (pass == 0 ? 2.2f : 0.8f);
                    float ux = (float) Math.cos(a), uy = (float) Math.sin(a);
                    path.reset();
                    path.moveTo(X + ux * r0, Y + uy * r0);
                    path.lineTo(X + ux * rm - uy * w, Y + uy * rm + ux * w);
                    path.lineTo(X + ux * r1, Y + uy * r1);
                    path.lineTo(X + ux * rm + uy * w, Y + uy * rm - ux * w);
                    path.close();
                    c.drawPath(path, p);
                }
            }
            energy.setAlpha(255);
        }
        // sparkles flung out, twinkling
        if (t > 0.01f) {
            for (int i = 0; i < SPARK_ANGLE.length; i++) {
                double a = spin + Math.toRadians(SPARK_ANGLE[i]);
                float sp = SPARK_SIZE[i];
                float d = R * (0.4f + 1.55f * sp * easeOut(t / 0.34f));
                float r = R * 0.26f * sp * Math.min(1, t / 0.05f) * fade(t, 0.12f, 0.42f);
                if (r > 0.5f) {
                    float x = X + (float) Math.cos(a) * d, y = Y + (float) Math.sin(a) * d;
                    glowDot(c, x, y, r * 1.3f, 0xffc070ff, 0.5f);
                    fx.setColor(SPARK_COLOUR[i % SPARK_COLOUR.length]);
                    c.drawPath(star(x, y, r, t * 5 + a, 0.18f), fx);
                }
            }
        }
        // energy orbs: outward, falling a little
        if (t > 0.015f) {
            for (int i = 0; i < ORB_SPEED.length; i++) {
                double a = spin + Math.toRadians(8 + 26 * i);
                float sp = ORB_SPEED[i];
                float d = R * (0.45f + 1.9f * sp * easeOut(t / 0.4f));
                float x = X + (float) Math.cos(a) * d, y = Y + (float) Math.sin(a) * d + R * 0.9f * (t / HIT_TIME) * (t / HIT_TIME);
                float r = R * 0.065f * (0.7f + 0.5f * sp) * fade(t, 0.2f, HIT_TIME);
                if (r > 0.4f) {
                    int col = ORB_COLOUR[i % ORB_COLOUR.length];
                    glowDot(c, x, y, r * 2.8f, col, 0.45f);
                    fx.setColor(col);
                    c.drawCircle(x, y, r, fx);
                }
            }
        }
    }

    /** A shot in flight: a purple gem with a golden trail; sparks where it left. */
    private void drawShot(Canvas c, Shot q) {
        float s = xf.s;
        if (q.t < MUZZLE) {
            float u = q.t / MUZZLE;
            glowDot(c, xf.x(fireX), xf.y(fireY), 46 * s * (0.6f + 0.6f * u), 0xffffd970, 1 - u);
        }
        float u = Math.min(1, q.t / q.time);
        q.at(u, pt);
        float hx = xf.x(pt[0]), hy = xf.y(pt[1]);
        float depth = clamp01((fireY - pt[1]) / (fireY - 640));
        float r = (30 - 11 * depth) * s;                         // smaller further away
        // the trail: three golden streaks, widest and brightest at the gem
        final int n = 12;
        float u0 = Math.max(0, u - 0.5f);
        energy.setStyle(Paint.Style.STROKE);
        energy.setStrokeCap(Paint.Cap.ROUND);
        q.at(u0, pt2);
        float gx = xf.x(pt2[0]), gy = xf.y(pt2[1]);
        for (int i = 1; i <= n; i++) {
            q.at(u0 + (u - u0) * i / n, pt2);
            float x = xf.x(pt2[0]), y = xf.y(pt2[1]), f = (float) i / n;
            energy.setStrokeWidth(r * 2.6f * f);
            energy.setColor(0xffffc040);
            energy.setAlpha((int) (70 * f));
            c.drawLine(gx, gy, x, y, energy);
            gx = x;
            gy = y;
        }
        energy.setStyle(Paint.Style.FILL);
        energy.setStrokeCap(Paint.Cap.BUTT);
        energy.setAlpha(255);
        fx.setStyle(Paint.Style.STROKE);
        fx.setStrokeCap(Paint.Cap.ROUND);
        for (int k = -1; k <= 1; k++) {
            q.at(u0, pt2);
            float px = xf.x(pt2[0]), py = xf.y(pt2[1]);
            for (int i = 1; i <= n; i++) {
                q.at(u0 + (u - u0) * i / n, pt2);
                float x = xf.x(pt2[0]), y = xf.y(pt2[1]);
                float dx = x - px, dy = y - py, len = (float) Math.hypot(dx, dy);
                float f = (float) i / n, off = k * r * 0.5f * f;
                float nx = len > 0 ? -dy / len * off : 0, ny = len > 0 ? dx / len * off : 0;
                fx.setStrokeWidth(Math.max(1, r * (k == 0 ? 1.3f : 0.5f) * f));
                fx.setColor(k == 0 ? Ui.blend(0xffff8a1e, 0xfffff4b4, f * f) : Ui.blend(0xffffb02e, 0xffffffe0, f));
                fx.setAlpha((int) (255 * Math.min(1, f * 1.3f) * (k == 0 ? 1 : 0.85f)));
                c.drawLine(px + nx, py + ny, x + nx, y + ny, fx);
                px = x;
                py = y;
            }
        }
        fx.setStyle(Paint.Style.FILL);
        fx.setStrokeCap(Paint.Cap.BUTT);
        // the gem: violet glow, faceted body with a dark outline, a white glint
        glowDot(c, hx, hy, r * 2.4f, 0xffb46cff, 0.75f);
        double spin = q.t * 14;
        path.reset();
        for (int k = 0; k < 8; k++) {
            double a = spin + Math.PI / 4 * k;
            float rr = k % 2 == 0 ? r : r * 0.88f;
            float x = hx + (float) Math.cos(a) * rr, y = hy + (float) Math.sin(a) * rr;
            if (k == 0) {
                path.moveTo(x, y);
            } else {
                path.lineTo(x, y);
            }
        }
        path.close();
        fx.setShader(new RadialGradient(hx - 0.3f * r, hy - 0.35f * r, 1.4f * r, new int[]{0xffeedcff, 0xffb070ff, 0xff7a2ee0, 0xff3c0f8c},
                new float[]{0, 0.35f, 0.7f, 1}, Shader.TileMode.CLAMP));
        c.drawPath(path, fx);
        fx.setShader(null);
        fx.setStyle(Paint.Style.STROKE);
        fx.setStrokeWidth(Math.max(1, 0.13f * r));
        fx.setColor(0xff2a0b5c);
        c.drawPath(path, fx);
        fx.setStrokeWidth(Math.max(1, 0.07f * r));
        fx.setColor(0x99f0e0ff);
        for (int k = 0; k < 8; k += 2) {                          // facets
            double a = spin + Math.PI / 4 * k;
            c.drawLine(hx + (float) Math.cos(a) * r * 0.42f, hy + (float) Math.sin(a) * r * 0.42f,
                    hx + (float) Math.cos(a) * r * 0.95f, hy + (float) Math.sin(a) * r * 0.95f, fx);
        }
        fx.setStyle(Paint.Style.FILL);
        fx.setColor(0xffffffff);
        c.drawPath(star(hx - 0.3f * r, hy - 0.35f * r, 0.55f * r, spin * 0.5, 0.22f), fx);
    }

    /**
     * The opening demonstration (reference: the hand tapping the front purple): the glove comes in,
     * presses on the character, the shot leaves and strikes it; the player's first tap sends it away.
     */
    private void drawHand(Canvas c) {
        if (demoHole < 0) {
            return;
        }
        Mole m = holes[demoHole].mole;
        float st = sinceStart;
        float in = clamp01((st - 0.55f) / 0.3f);
        float out = demoOff >= 0 ? 1 - clamp01((st - demoOff) / 0.2f) : 1 - clamp01((st - 2.1f) / 0.3f);
        float a = in * out;
        if (a <= 0 || m.look == null) {
            return;
        }
        float tipX = m.aimX() + 16, tipY = m.aimY() + 12;       // the fingertip, just off the middle of its body
        float lift = st > demoPress + 0.2f ? easeOut((st - demoPress - 0.2f) / 0.4f) : 0;
        float ox = (1 - easeOut(in)) * 60 + lift * 30, oy = (1 - easeOut(in)) * 80 + lift * 40;
        float press = 1 - 0.1f * (float) Math.sin(Math.PI * clamp01((st - demoPress + 0.08f) / 0.16f));
        float sx = xf.x(tipX + ox), sy = xf.y(tipY + oy);
        if (st >= demoPress && st < demoPress + 0.3f) {           // the touch: a ring under the fingertip
            float u = (st - demoPress) / 0.3f;
            fx.setStyle(Paint.Style.STROKE);
            fx.setStrokeWidth(3 * xf.s * (1 - u) + 1);
            fx.setColor(0xffffffff);
            fx.setAlpha((int) (230 * (1 - u) * a));
            c.drawCircle(xf.x(tipX), xf.y(tipY), xf.s * (10 + 30 * easeOut(u)), fx);
            fx.setStyle(Paint.Style.FILL);
        }
        int save = c.save();
        c.scale(press, press, sx, sy);
        xf.rect(tipX + ox - (handTipX - hand.x), tipY + oy - (handTipY - hand.y), hand.w, hand.h, dst);
        paint.setAlpha((int) (255 * a));
        c.drawBitmap(hand.bitmap, null, dst, paint);
        paint.setAlpha(255);
        c.restoreToCount(save);
    }

    // ------------------------------------------------------------------ for tests
    /**
     * The moment the reference shows (new levels): every character in its reference pose, the
     * hint and flash, and the HUD values of level.json "reference_state".
     */
    void referenceMoment() {
        startRound();
        for (Hole hole : holes) {
            Mole m = hole.mole;
            if (referenceLooks[hole.index] != null) {
                m.look = referenceLooks[hole.index];
                m.state = Mole.UP;
                m.t = 0;
                m.hold = 60;
            }
        }
        sinceStart = 1;
        if (referenceState != null) {
            elapsed = (float) referenceState.optDouble("elapsed");
            targetsLeft = referenceState.optInt("targets_left");
            score = referenceState.optInt("score");
            combo = referenceState.optInt("combo");
        }
        if (speedAt >= 0 && elapsed >= speedAt) {
            fast = true;
            bannerT = 1;                          // fully in
        }
    }

    int score() {
        return score;
    }

    int targetsLeft() {
        return targetsLeft;
    }

    int combo() {
        return combo;
    }

    int goal() {
        return goal;
    }

    int points() {
        return points;
    }

    boolean combos() {
        return combos;
    }

    float duration() {
        return duration;
    }

    float bombPenalty() {
        return bombPenalty;
    }

    float contentTop() {
        return contentTop;
    }

    float contentBottom() {
        return artHMust;
    }

    int artWidth() {
        return artW;
    }

    float elapsed() {
        return elapsed;
    }

    boolean spedUp() {
        return fast;
    }

    boolean isFailing() {
        return failing;
    }

    int failures() {
        return failures;
    }

    int hops() {
        return hops;
    }

    boolean decoyFails() {
        return decoyFails;
    }

    boolean fires() {
        return fires;
    }

    int shotsInFlight() {
        return shots.size();
    }

    /** Where the first shot in flight is now (art px), or null. */
    float[] shotAt() {
        if (shots.isEmpty()) {
            return null;
        }
        Shot q = shots.get(0);
        float[] p = new float[2];
        q.at(Math.min(1, q.t / q.time), p);
        return p;
    }

    float[] fireFrom() {
        return new float[]{fireX, fireY};
    }

    int energyBursts() {
        int n = 0;
        for (Hit h : hits) {
            n += h.dull ? 0 : 1;
        }
        return n;
    }

    boolean bannerShowing() {
        return bannerT >= 0;
    }

    boolean isOver() {
        return over;
    }

    boolean isWon() {
        return won;
    }

    boolean isPaused() {
        return paused;
    }

    Hole[] holes() {
        return holes;
    }

    SpriteButton pauseButton() {
        return pauseButton;
    }

    Xf xf() {
        return xf;
    }
}
