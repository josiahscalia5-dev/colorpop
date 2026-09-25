package com.colorpop.game;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.RectF;
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
    private static final float INTRO_HOLD_UNTIL = 2.95f, SPAWN_FROM = 3.3f;
    private static final float INTRO_FX_FADE = 2.4f, INTRO_FX_GONE = 3.0f, BURST_TIME = 0.32f, BANNER_TIME = 2.8f;
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
    private final JSONObject referenceState;

    // ------------------------------------------------------------------ art
    private final float contentTop, referenceH;
    private final Fit.Backdrop bg;
    private final Bitmap fg;
    private final int artW, artH;
    private final float fgX, fgY;
    private final SpriteButton pauseButton;
    private final OutlineText hudText, comboText;
    private final OutlineText.Slot timerSlot, targetSlot, scoreSlot, comboSlot;
    private final Sprite comboWord, hint, burst, banner;
    private final float burstAnchorX, burstAnchorY;
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
    private boolean paused, over, won;
    private Ui.Dialog dialog;
    private boolean pausePressed, swiping;
    private final List<Particle> particles = new ArrayList<>();
    private final List<Floater> floaters = new ArrayList<>();
    private final List<Burst> bursts = new ArrayList<>();

    private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
    private final Paint light = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Paint eraser = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fx = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ui = new Paint(Paint.ANTI_ALIAS_FLAG);
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
        Look look;

        Mole(Hole hole) {
            this.hole = hole;
        }

        void spawn(Look l, float wait, float holdTime) {
            look = l;
            delay = wait;
            hold = holdTime;
            t = 0;
            state = wait > 0 ? WAIT : RISING;
        }

        void sink() {
            if (state == RISING || state == UP || state == REACT) {
                float p = pose();
                state = SINKING;
                t = SINK * (float) Math.sqrt(1 - Math.max(0, Math.min(1, p)));  // continue from the current height
            } else if (state == WAIT) {
                state = HIDDEN;
            }
        }

        void update(float dt) {
            t += dt;
            switch (state) {
                case WAIT:
                    if (t >= delay) {
                        state = RISING;
                        t = 0;
                    }
                    break;
                case RISING:
                    if (t >= RISE) {
                        state = UP;
                        t = 0;
                    }
                    break;
                case UP:
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
                    if (t >= SINK) {
                        state = HIDDEN;
                        cooldown = 0.35f;
                    }
                    break;
                case POPPED:
                    if (t >= POP) {
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
                    float u = Math.min(1, t / RISE), c = 1.3f, v = u - 1;
                    return 1 + (c + 1) * v * v * v + c * v * v;
                }
                case UP:
                case POPPED:
                case REACT:
                    return 1;
                case SINKING: {
                    float u = Math.min(1, t / SINK);
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
            return (state == RISING && t > RISE * 0.3f) || state == UP;
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
            c.drawBitmap(look.bitmap, null, dst, paint);
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
        referenceState = legacy ? null : rules.optJSONObject("reference_state");

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
            nativeLook[home.index] = l;
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
        targetPulse = scorePulse = timerPulse = comboPulse = 0;
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
        if (!paused && !over) {
            paused = true;
            dialog = new Ui.Dialog("PAUSED").button(PAUSE_RESUME, "RESUME", true).button(PAUSE_HOME, "HOME", false);
            dialog.layout(w, h, xf.s, game.safe);
        }
    }

    private void finish(boolean allHit) {
        over = true;
        won = allHit;
        overT = 0;
        for (Hole hole : holes) {
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
        if (over) {
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
                finish(false);
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
            float hold = (holdMin + holdSpread * rnd.nextFloat()) * (1 - 0.3f * progress) * (fast ? speedHold : 1);
            if (quick > 0 && rnd.nextFloat() < quick) {
                hold *= 0.6f;                         // a quick one: less time to react
            }
            hole.mole.spawn(look, 0, hold);
            nextSpawn = (gapMin + gapSpread * rnd.nextFloat()) * (1 - 0.25f * progress) * (fast ? speedGap : 1);
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

    /** A target went back into its hole without being hit: the combo is broken. */
    private void escaped(Mole m) {
        if (m.look.role == TARGET && !over) {
            combo = 0;
        }
    }

    /** A tap (or, where the level allows it, a swipe) at screen point (x, y) during play. */
    void tap(float x, float y) {
        if (paused || over) {
            return;
        }
        float ax = xf.artX(x), ay = xf.artY(y);
        for (int i = holes.length - 1; i >= 0; i--) {   // front-most first
            Mole m = holes[i].mole;
            if (!m.tappable() || !m.hit(ax, ay)) {
                continue;
            }
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
            } else {
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
            return;
        }
    }

    private void burst(Mole m) {
        float f = m.scale();
        float cx = m.hole.cx, cy = m.hole.front() - (m.look.home.front() - m.look.y) * f * 0.45f;
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
                tap(x, y);
                swiping = swipe;
            }
        } else if (action == MotionEvent.ACTION_MOVE && pausePressed) {
            pauseButton.pressed = pauseButton.contains(e.getX(0), e.getY(0));
        } else if (action == MotionEvent.ACTION_MOVE && swiping) {
            // slicing through characters: every point of the finger's path counts as a tap
            for (int k = 0; k < e.getHistorySize(); k++) {
                tap(e.getHistoricalX(0, k), e.getHistoricalY(0, k));
            }
            tap(e.getX(0), e.getY(0));
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
        drawSprite(c, burst, intro);
        drawSprite(c, hint, intro);
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
