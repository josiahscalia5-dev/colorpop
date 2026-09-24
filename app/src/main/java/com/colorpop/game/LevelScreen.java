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
import java.util.Random;

/**
 * Level 1, "HIT THE GREEN ONES!": characters pop up out of the six holes; tapping a green one
 * pops it (+score, one target less), red and yellow ones only react. 30 seconds, 12 greens.
 *
 * Layout (art = reference pixels, 622 x 1150, one uniform scale, see {@link Fit}): anchored to
 * the top, so the HUD and the scene are exactly as in the reference; the HUD moves down only if a
 * camera cutout reaches it (bg.png has sky above the art). A taller screen shows more ground below
 * the bottom holes (400 painted rows) and the bottom foliage (a foreground layer) stays at the
 * bottom edge of the screen; a shorter or wider one scales everything down together. Must-see:
 * from the top of the HUD (art y 66) to the bottom of the reference scene.
 */
final class LevelScreen extends Screen {
    static final float ROUND = 30f;
    static final int TARGETS = 12, POINTS = 10;
    private static final float RISE = 0.22f, SINK = 0.2f, POP = 0.2f, WOBBLE = 0.45f;
    private static final float INTRO_HOLD_UNTIL = 2.95f, SPAWN_FROM = 3.3f;
    private static final int PAUSE_RESUME = 1, PAUSE_HOME = 2, OVER_AGAIN = 3, OVER_HOME = 4;
    private static final int GREEN = 0, RED = 1, YELLOW = 2;

    // ------------------------------------------------------------------ art
    private static final float CONTENT_TOP = 66, REFERENCE_H = 1156;
    private final Fit.Backdrop bg;
    private final Bitmap fg;
    private final int artW, artH;
    private final float fgX, fgY;
    private final SpriteButton pauseButton;
    private final OutlineText.Slot timerSlot, targetSlot, scoreSlot;
    private final Hole[] holes;              // sorted back to front
    private final Look[][] lookFor;          // [colour][hole index]
    private final Xf xf = new Xf();
    private float fgShift;

    // ------------------------------------------------------------------ round state
    private final Random rnd = new Random();
    private float elapsed, nextSpawn, targetPulse, scorePulse, overT;
    private int score, targetsLeft;
    private boolean paused, over, won;
    private Ui.Dialog dialog;
    private boolean pausePressed;
    private final List<Particle> particles = new ArrayList<>();
    private final List<Floater> floaters = new ArrayList<>();

    private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
    private final Paint eraser = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fx = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ui = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF dst = new RectF(), layer = new RectF();

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

    /** A character sprite and the hole it was cut from (it can be shown in any hole, scaled). */
    static final class Look {
        final Bitmap bitmap;
        final float x, y;
        final Hole home;
        final int colour;

        Look(Bitmap bitmap, float x, float y, Hole home, int colour) {
            this.bitmap = bitmap;
            this.x = x;
            this.y = y;
            this.home = home;
            this.colour = colour;
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
                int sx = (int) ((px - l) / f), sy = (int) ((py - tp) / f);
                if (sx >= 0 && sy >= 0 && sx < b.getWidth() && sy < b.getHeight() && (b.getPixel(sx, sy) >>> 24) > 64) {
                    return true;
                }
            }
            return false;
        }

        void draw(Canvas c) {
            if (!visible()) {
                return;
            }
            float f = scale();
            xf.rect(left(), top(), look.bitmap.getWidth() * f, look.bitmap.getHeight() * f, dst);
            float grow = state == POPPED ? 1 + 0.35f * Math.min(1, t / POP) : 1;
            float m = dst.width() * 0.25f;
            layer.set(dst.left - m, dst.top - m, dst.right + m, dst.bottom + m);
            int save = c.saveLayer(layer, null);
            int moved = c.save();
            if (state == REACT) {
                float u = t / WOBBLE;
                float angle = (float) Math.sin(u * Math.PI * 5) * 9 * (1 - u);
                c.rotate(angle, xf.x(hole.cx), xf.y(hole.front()));
            } else if (state == POPPED) {
                c.scale(grow, grow, dst.centerX(), dst.centerY());
                paint.setAlpha((int) (255 * Math.max(0, 1 - t / POP)));
            }
            c.drawBitmap(look.bitmap, null, dst, paint);
            paint.setAlpha(255);
            c.restoreToCount(moved);
            c.drawPath(hole.hidden, eraser);   // the front rim stays where it is
            c.restoreToCount(save);
        }
    }

    static final class Particle {
        float x, y, vx, vy, life, age, size;
        int color;
        boolean star;
    }

    /** Floating "+10". */
    static final class Floater {
        float x, y, t;
    }

    LevelScreen(GameView game) {
        super(game);
        Art art = game.art;
        JSONObject L = art.json("level/level.json");
        JSONObject a = L.optJSONObject("art"), b = L.optJSONObject("bg"), f = L.optJSONObject("fg_bottom"), p = L.optJSONObject("pause");
        artW = a.optInt("w");
        artH = a.optInt("h");
        bg = new Fit.Backdrop(art.bitmap(b.optString("file")), b.optInt("pad_side"), b.optInt("pad_top"));
        fg = art.bitmap(f.optString("file"));
        fgX = (float) f.optDouble("x");
        fgY = (float) f.optDouble("y");
        JSONObject hit = p.optJSONObject("hit");
        float cx = (float) hit.optDouble("cx"), cy = (float) hit.optDouble("cy"), r = (float) hit.optDouble("r");
        pauseButton = new SpriteButton(art.bitmap(p.optString("file")), (float) p.optDouble("x"), (float) p.optDouble("y"),
                new float[]{cx - r, cy - r, cx + r, cy + r}, true, xf);
        JSONObject live = L.optJSONObject("live_text");
        timerSlot = new OutlineText.Slot(live.optJSONObject("timer"));
        targetSlot = new OutlineText.Slot(live.optJSONObject("target"));
        scoreSlot = new OutlineText.Slot(live.optJSONObject("score"));

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
        // every character as the reference shows it, then the best stand-in for each colour and hole
        JSONObject cs = L.optJSONObject("chars");
        List<Look> looks = new ArrayList<>();
        Look[] nativeLook = new Look[holes.length];
        for (Iterator<String> it = cs.keys(); it.hasNext(); ) {
            JSONObject c = cs.optJSONObject(it.next());
            Hole home = holes[Arrays.asList(sorted).indexOf(c.optString("hole"))];
            String col = c.optString("color");
            int colour = "green".equals(col) ? GREEN : "red".equals(col) ? RED : YELLOW;
            Look l = new Look(art.bitmap(c.optString("file")), (float) c.optDouble("x"), (float) c.optDouble("y"), home, colour);
            looks.add(l);
            nativeLook[home.index] = l;
        }
        referenceLooks = nativeLook;
        lookFor = new Look[3][holes.length];
        for (int colour = 0; colour < 3; colour++) {
            for (Hole hole : holes) {
                Look best = null;
                for (Look l : looks) {
                    if (l.colour != colour) {
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
    }

    private final Look[] referenceLooks;

    // ------------------------------------------------------------------ layout
    @Override
    void layout(int width, int height) {
        super.layout(width, height);
        android.graphics.Rect safe = game.safe;
        float topNeed = Fit.topNeed(game);
        float s = Fit.scale(artW, CONTENT_TOP, artH, w - safe.left - safe.right, h - safe.bottom, topNeed);
        xf.set(s, Fit.left(safe, w, artW, s), Math.max(0, topNeed - CONTENT_TOP * s));
        // the foliage sits on the bottom edge of the screen, wherever that falls in the scene
        fgShift = (h - xf.oy) / s - REFERENCE_H;
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
        elapsed = 0;
        score = 0;
        targetsLeft = TARGETS;
        paused = over = won = false;
        overT = 0;
        dialog = null;
        pausePressed = false;
        pauseButton.pressed = false;
        particles.clear();
        floaters.clear();
        nextSpawn = 0;
        // opening wave: every character rises into its reference pose and stays past 00:28
        for (int i = 0; i < holes.length; i++) {
            float wait = 0.04f * i;
            holes[i].mole.cooldown = 0;
            holes[i].mole.spawn(referenceLooks[i], wait, INTRO_HOLD_UNTIL + 0.07f * i - wait - RISE);
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
        if (over) {
            overT += dt;
            if (dialog == null && overT > 0.7f) {
                dialog = new Ui.Dialog(won ? "LEVEL COMPLETE!" : "TIME'S UP!")
                        .button(OVER_AGAIN, "PLAY AGAIN", true).button(OVER_HOME, "HOME", false);
                dialog.line = "SCORE: " + score;
                dialog.layout(w, h, xf.s, game.safe);
            }
        } else {
            elapsed += dt;
            if (elapsed >= ROUND) {
                elapsed = ROUND;
                finish(false);
            } else {
                spawn(dt);
            }
        }
        for (Hole hole : holes) {
            hole.mole.update(dt);
        }
        targetPulse = Math.max(0, targetPulse - dt);
        scorePulse = Math.max(0, scorePulse - dt);
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
    }

    private void spawn(float dt) {
        if (elapsed < SPAWN_FROM) {
            return;
        }
        nextSpawn -= dt;
        if (nextSpawn > 0) {
            return;
        }
        float progress = Math.min(1, (elapsed - SPAWN_FROM) / (ROUND - SPAWN_FROM));
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
        if (up < (progress < 0.35f ? 2 : 3) && !free.isEmpty()) {
            Hole hole = free.get(rnd.nextInt(free.size()));
            float r = rnd.nextFloat();
            int colour = r < 0.6f ? GREEN : r < 0.8f ? RED : YELLOW;
            float hold = (1.15f + 0.45f * rnd.nextFloat()) * (1 - 0.3f * progress);
            hole.mole.spawn(lookFor[colour][hole.index], 0, hold);
            nextSpawn = (0.45f + 0.35f * rnd.nextFloat()) * (1 - 0.25f * progress);
        } else {
            nextSpawn = 0.1f;
        }
    }

    /** A tap at screen point (x, y) during play. */
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
            if (m.look.colour == GREEN) {
                m.state = Mole.POPPED;
                m.t = 0;
                score += POINTS;
                targetsLeft--;
                targetPulse = scorePulse = 0.25f;
                burst(m);
                Floater plus = new Floater();
                plus.x = m.hole.cx;
                plus.y = m.top() + 10;
                floaters.add(plus);
                game.sfx.pop();
                if (targetsLeft == 0) {
                    finish(true);
                }
            } else {
                m.state = Mole.REACT;
                m.t = 0;
                game.sfx.bonk();
            }
            return;
        }
    }

    private void burst(Mole m) {
        float f = m.scale();
        float cx = m.hole.cx, cy = m.hole.front() - (m.look.home.front() - m.look.y) * f * 0.45f;
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
            q.color = q.star ? 0xffffffff : (i % 3 == 0 ? 0xffb6ff7a : 0xff37d43a);
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
            }
        } else if (action == MotionEvent.ACTION_MOVE && pausePressed) {
            pauseButton.pressed = pauseButton.contains(e.getX(0), e.getY(0));
        } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
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

    private void onDialog(int id) {
        if (id == PAUSE_RESUME) {
            paused = false;
            dialog = null;
        } else if (id == PAUSE_HOME || id == OVER_HOME) {
            game.show(game.home);
        } else if (id == OVER_AGAIN) {
            startRound();
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
    @Override
    void draw(Canvas c) {
        bg.draw(c, xf, w, h);
        for (Hole hole : holes) {                     // back to front
            hole.mole.draw(c);
        }
        xf.rect(fgX, fgY + fgShift, fg.getWidth(), fg.getHeight(), dst);
        c.drawBitmap(fg, null, dst, paint);
        drawEffects(c);

        pauseButton.draw(c, paint);
        OutlineText t = game.text;
        int secs = (int) Math.ceil(Math.max(0, ROUND - elapsed) - 1e-4);
        timerSlot.draw(c, t, "00:" + (secs < 10 ? "0" : "") + secs, xf);
        drawPulsed(c, targetSlot, String.valueOf(targetsLeft), targetPulse);
        drawPulsed(c, scoreSlot, String.valueOf(score), scorePulse);
        if (dialog != null) {
            dialog.draw(c, w, h, t, ui);
        }
    }

    private void drawPulsed(Canvas c, OutlineText.Slot slot, String text, float pulse) {
        if (pulse <= 0) {
            slot.draw(c, game.text, text, xf);
            return;
        }
        float k = 1 + 0.18f * (float) Math.sin(Math.PI * (1 - pulse / 0.25f));
        int save = c.save();
        float px = slot.align == OutlineText.CENTER ? xf.x((slot.left + slot.right) / 2) : xf.x(slot.left);
        c.scale(k, k, px, xf.y(slot.top + slot.size * 0.36f));
        slot.draw(c, game.text, text, xf);
        c.restoreToCount(save);
    }

    private void drawEffects(Canvas c) {
        float s = xf.s;
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
            game.text.draw(c, "+" + POINTS, xf.x(q.x), xf.y(y), OutlineText.CENTER, 54 * s, 0.9f, 3.4f * s, 3 * s, (int) (255 * a));
        }
    }

    // ------------------------------------------------------------------ for tests
    int score() {
        return score;
    }

    int targetsLeft() {
        return targetsLeft;
    }

    float elapsed() {
        return elapsed;
    }

    boolean isOver() {
        return over;
    }

    boolean isPaused() {
        return paused;
    }

    Hole[] holes() {
        return holes;
    }

    Xf xf() {
        return xf;
    }
}
