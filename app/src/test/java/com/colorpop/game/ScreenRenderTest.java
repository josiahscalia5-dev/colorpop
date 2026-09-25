package com.colorpop.game;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.media.SoundPool;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.ConscryptMode;
import org.robolectric.annotation.GraphicsMode;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.util.Locale;

/**
 * Draws the real screens with Android's real graphics (Robolectric native graphics) on common
 * phone shapes -- with and without camera cutouts and visible system bars -- and checks that:
 * everything that matters stays inside the safe area, the scale is uniform, and every control and
 * character is hit where it is drawn. Writes PNGs + layout numbers to build/renders/ (or
 * -Dcolorpop.out) for the comparison with the reference (design-pipeline/compare_renders.py).
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 35)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@ConscryptMode(ConscryptMode.Mode.OFF)
public class ScreenRenderTest {
    private static final float FRAME = 1 / 60f;

    /** name, width, height, density qualifier, safe insets left/top/right/bottom (px). */
    static final class Device {
        final String name, dpi;
        final int w, h, l, t, r, b;

        Device(String name, int w, int h, String dpi, int l, int t, int r, int b) {
            this.name = name;
            this.w = w;
            this.h = h;
            this.dpi = dpi;
            this.l = l;
            this.t = t;
            this.r = r;
            this.b = b;
        }
    }

    static final Device[] DEVICES = {
            new Device("reference_home", 1080, 1990, "xxhdpi", 0, 0, 0, 0),   // Home reference shape (628x1157)
            new Device("reference_level", 1080, 2007, "xxhdpi", 0, 0, 0, 0),  // Level reference shape (622x1156)
            new Device("hd_16x9", 720, 1280, "xhdpi", 0, 0, 0, 0),
            new Device("fhd_16x9", 1080, 1920, "xxhdpi", 0, 0, 0, 0),
            new Device("fhd_18x9", 1080, 2160, "xxhdpi", 0, 0, 0, 0),
            new Device("notch_19x9", 1080, 2280, "xxhdpi", 0, 90, 0, 0),
            new Device("punchhole_19.5x9", 1080, 2340, "xxhdpi", 0, 110, 0, 0),
            new Device("fhd_20x9", 1080, 2400, "xxhdpi", 0, 0, 0, 0),
            new Device("punchhole_20x9", 1080, 2400, "xxhdpi", 0, 128, 0, 0),
            new Device("qhd_20x9", 1440, 3200, "xxxhdpi", 0, 145, 0, 0),
            new Device("tall_21x9", 1080, 2520, "xxhdpi", 0, 100, 0, 0),
            new Device("bars_shown_20x9", 1080, 2400, "xxhdpi", 0, 128, 0, 132),  // status + 3-button nav bar visible
            new Device("curved_edges_20x9", 1080, 2400, "xxhdpi", 24, 110, 24, 0),
            new Device("foldable_inner", 1812, 2176, "xxhdpi", 0, 100, 0, 0),
    };

    private GameView view(Device d) {
        RuntimeEnvironment.setQualifiers(d.dpi);
        Context context = RuntimeEnvironment.getApplication();
        String dir = System.getProperty("colorpop.assets", "");
        Art.Source source = dir.isEmpty() ? Art.Source.of(context.getAssets()) : files(new File(dir));
        GameView v = new GameView(context, source);
        v.setSafeInsets(d.l, d.t, d.r, d.b);
        v.measure(View.MeasureSpec.makeMeasureSpec(d.w, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(d.h, View.MeasureSpec.EXACTLY));
        v.layout(0, 0, d.w, d.h);
        v.level.seed(7);
        return v;
    }

    /** Assets straight from a folder (used when the tests run outside the Android build). */
    private static Art.Source files(final File root) {
        return new Art.Source() {
            @Override
            InputStream open(String path) throws IOException {
                return new FileInputStream(new File(root, path));
            }

            @Override
            Typeface font(String path) {
                return Typeface.createFromFile(new File(root, path));
            }

            @Override
            int loadSound(SoundPool pool, String path) {
                return pool.load(new File(root, path).getPath(), 1);
            }
        };
    }

    private static void run(GameView v, float seconds) {
        for (float t = 0; t < seconds - 1e-4f; t += FRAME) {
            v.step(FRAME);
        }
    }

    private static void openLevel(GameView v) {
        v.show(v.level);
        run(v, 0.2f);                  // fade out, switch (the round starts here)
        assertTrue(v.current() == v.level);
    }

    private static File outDir() {
        File out = new File(System.getProperty("colorpop.out", "build/renders"));
        assertTrue(out.isDirectory() || out.mkdirs());
        return out;
    }

    private static void render(GameView v, String name) throws IOException {
        Bitmap b = Bitmap.createBitmap(v.getWidth(), v.getHeight(), Bitmap.Config.ARGB_8888);
        v.draw(new Canvas(b));
        try (FileOutputStream f = new FileOutputStream(new File(outDir(), name + ".png"))) {
            b.compress(Bitmap.CompressFormat.PNG, 100, f);
        }
    }

    private static void writeLayout(String name, String json) throws IOException {
        try (Writer w = new OutputStreamWriter(new FileOutputStream(new File(outDir(), name + ".json")), "UTF-8")) {
            w.write(json);
        }
    }

    private static void touch(GameView v, int action, float x, float y) {
        long now = SystemClock.uptimeMillis();
        MotionEvent e = MotionEvent.obtain(now, now, action, x, y, 0);
        v.onTouchEvent(e);
        e.recycle();
    }

    private static void tap(GameView v, float x, float y) {
        touch(v, MotionEvent.ACTION_DOWN, x, y);
        touch(v, MotionEvent.ACTION_UP, x, y);
    }

    private static RectF safeRect(Device d) {
        return new RectF(d.l, d.t, d.w - d.r, d.h - d.b);
    }

    private static void assertInside(String what, RectF inner, RectF outer) {
        float e = 0.51f;
        assertTrue(what + " " + inner + " must be inside " + outer,
                inner.left >= outer.left - e && inner.top >= outer.top - e
                        && inner.right <= outer.right + e && inner.bottom <= outer.bottom + e);
    }

    private static RectF screenRect(Xf xf, float x0, float y0, float x1, float y1) {
        return new RectF(xf.x(x0), xf.y(y0), xf.x(x1), xf.y(y1));
    }

    // ------------------------------------------------------------------ Home
    @Test
    public void homeOnEveryPhone() throws IOException {
        for (Device d : DEVICES) {
            GameView v = view(d);
            run(v, 0.5f);
            HomeScreen home = v.home;
            Xf main = home.mainXf(), top = home.topXf();
            RectF safe = safeRect(d);
            assertEquals("one scale for both control groups", main.s, top.s, 0f);
            // the whole art width and the must-see rows (coin counter .. nav bar) are visible
            assertInside(d.name + " home art", screenRect(main, 0, 160, 628, 1157), safe);
            for (SpriteButton b : home.controls()) {
                Xf xf = b.xf;
                assertInside(d.name + " control", screenRect(xf, b.hx0, b.hy0, b.hx1, b.hy1), safe);
            }
            // the pinned counter/gear never run into the title
            assertTrue(d.name + " top controls clear of the title", top.y(148) <= main.y(160) + 0.5f);
            render(v, "home_" + d.name);
            writeLayout("home_" + d.name, String.format(Locale.US,
                    "{\"w\":%d,\"h\":%d,\"s\":%.6f,\"ox\":%.3f,\"oy\":%.3f,\"top_oy\":%.3f,\"safe\":[%d,%d,%d,%d]}",
                    d.w, d.h, main.s, main.ox, main.oy, top.oy, d.l, d.t, d.r, d.b));
        }
    }

    @Test
    public void homeControlsAreHitWhereTheyAreDrawn() {
        for (Device d : DEVICES) {
            // controls(): coin, plus, gear, play, 4 x nav
            for (int i : new int[]{1, 4, 5, 6, 7}) {   // + and the nav tabs: "coming soon"
                GameView v = view(d);
                SpriteButton b = v.home.controls()[i];
                tap(v, b.xf.x((b.hx0 + b.hx1) / 2), b.xf.y((b.hy0 + b.hy1) / 2));
                assertTrue(d.name + " control " + i, v.home.toast().showing());
            }
            GameView v = view(d);
            SpriteButton gear = v.home.controls()[2];
            tap(v, gear.xf.x((gear.hx0 + gear.hx1) / 2), gear.xf.y((gear.hy0 + gear.hy1) / 2));
            assertTrue(d.name + " settings", v.home.settingsOpen());
            v = view(d);
            SpriteButton play = v.home.controls()[3];
            // a tap near the button's corner still counts, one 40 art px above it does not
            tap(v, play.xf.x(play.hx0 + 30), play.xf.y(play.hy1 - 20));
            run(v, 0.3f);
            assertTrue(d.name + " play", v.current() == v.level);
            v = view(d);
            tap(v, play.xf.x(play.hx0 + 30), play.xf.y(play.hy0 - 40));
            run(v, 0.3f);
            assertTrue(d.name + " above play", v.current() == v.home);
        }
    }

    @Test
    public void homeOverlays() throws IOException {
        GameView v = view(DEVICES[8]);
        v.home.toast().show("COMING SOON!");
        run(v, 0.4f);
        render(v, "state_home_toast");
        v = view(DEVICES[8]);
        v.home.openSettings();
        run(v, 0.5f);
        render(v, "state_home_settings");
    }

    // ------------------------------------------------------------------ Level 1
    @Test
    public void levelOnEveryPhone() throws IOException {
        for (Device d : DEVICES) {
            GameView v = view(d);
            openLevel(v);
            run(v, 2.5f);               // the reference screenshot reads 00:28
            Xf xf = v.level.xf();
            RectF safe = safeRect(d);
            // HUD .. bottom holes, the full width
            assertInside(d.name + " level", screenRect(xf, 0, 66, 622, 1150), safe);
            for (LevelScreen.Hole hole : v.level.holes()) {
                assertInside(d.name + " hole " + hole.index,
                        screenRect(xf, Math.max(0, hole.cx - hole.a), hole.cy - hole.b, Math.min(622, hole.cx + hole.a), hole.front()), safe);
            }
            render(v, "level_" + d.name);
            writeLayout("level_" + d.name, String.format(Locale.US,
                    "{\"w\":%d,\"h\":%d,\"s\":%.6f,\"ox\":%.3f,\"oy\":%.3f,\"safe\":[%d,%d,%d,%d]}",
                    d.w, d.h, xf.s, xf.ox, xf.oy, d.l, d.t, d.r, d.b));
        }
    }

    @Test
    public void greensCountRedAndYellowDoNotOnEveryPhone() throws IOException {
        for (Device d : DEVICES) {
            GameView v = view(d);
            openLevel(v);
            run(v, 1.0f);
            Xf xf = v.level.xf();
            int greens = 0;
            for (LevelScreen.Hole hole : v.level.holes()) {
                LevelScreen.Mole m = hole.mole;
                // aim at the middle of the character's face, in screen px
                float ax = hole.cx, ay = m.top() + (hole.front() - m.top()) * 0.45f;
                int before = v.level.score();
                tap(v, xf.x(ax), xf.y(ay));
                if (m.look.colour == 0) {
                    greens++;
                    assertEquals(d.name, before + LevelScreen.POINTS, v.level.score());
                } else {
                    assertEquals(d.name, before, v.level.score());
                }
                run(v, 0.05f);
                if (greens == 2 && d == DEVICES[8]) {
                    render(v, "state_level_pop");
                }
            }
            assertEquals(4, greens);        // the reference has four greens, one red, one yellow
            assertEquals(LevelScreen.TARGETS - 4, v.level.targetsLeft());
            // a tap on the front rim, just below a character, does not count
            LevelScreen.Hole h1 = v.level.holes()[0];
            run(v, 3f);
            assertFalse(h1.hides(h1.cx, h1.edgeAt(h1.cx) - 2));
            assertTrue(h1.hides(h1.cx, h1.edgeAt(h1.cx) + 2));
        }
    }

    @Test
    public void pauseFreezesTheRound() throws IOException {
        for (Device d : DEVICES) {
            GameView v = view(d);
            openLevel(v);
            run(v, 1.0f);
            Xf xf = v.level.xf();
            tap(v, xf.x(65), xf.y(116));    // the pause button, where it is drawn
            assertTrue(d.name, v.level.isPaused());
            float t = v.level.elapsed();
            run(v, 3f);
            assertEquals(t, v.level.elapsed(), 1e-4f);
            if (d == DEVICES[8]) {
                render(v, "state_level_paused");
            }
        }
    }

    @Test
    public void roundEndsWhenTheTimeIsUp() throws IOException {
        GameView v = view(DEVICES[8]);
        openLevel(v);
        run(v, 31f);
        assertTrue(v.level.isOver());
        assertFalse(v.level.isPaused());
        render(v, "state_level_timesup");
    }

    // ------------------------------------------------------------------ Levels 3, 6 (level.json driven)
    private static final int[] NEW_LEVELS = {3, 6, 8};
    /** Phone shapes of the new references (art 702 / 712 / 724 wide): the render compared with them. */
    private static final Device[] REFERENCE_SHAPES = {
            new Device("reference", 1080, 2286, "xxhdpi", 0, 0, 0, 0),
            new Device("reference", 1080, 2254, "xxhdpi", 0, 0, 0, 0),
            new Device("reference", 1080, 2342, "xxhdpi", 0, 0, 0, 0)};

    private static LevelScreen openLevel(GameView v, int id) {
        LevelScreen l = v.levelScreen(id);
        l.seed(7);
        v.show(l);
        run(v, 0.2f);                  // fade out, switch (the round starts here)
        assertTrue(v.current() == l);
        return l;
    }

    /** Aim at the middle of a character's face / a star's middle, in art px. */
    private static float[] aim(LevelScreen.Mole m) {
        LevelScreen.Hole hole = m.hole;
        return new float[]{hole.cx, m.top() + (hole.front() - m.top()) * 0.45f};
    }

    @Test
    public void newLevelsOnEveryPhone() throws IOException {
        for (int k = 0; k < NEW_LEVELS.length; k++) {
            int id = NEW_LEVELS[k];
            Device[] shapes = new Device[DEVICES.length + 1];
            shapes[0] = REFERENCE_SHAPES[k];
            System.arraycopy(DEVICES, 0, shapes, 1, DEVICES.length);
            for (Device d : shapes) {
                GameView v = view(d);
                LevelScreen l = openLevel(v, id);
                run(v, 0.5f);
                l.referenceMoment();       // the moment the reference shows
                Xf xf = l.xf();
                RectF safe = safeRect(d);
                assertInside(d.name + " level " + id, screenRect(xf, 0, l.contentTop(), l.artWidth(), l.contentBottom()), safe);
                SpriteButton p = l.pauseButton();
                assertInside(d.name + " pause " + id, screenRect(xf, p.hx0, p.hy0, p.hx1, p.hy1), safe);
                render(v, "level" + id + "_" + d.name);
                writeLayout("level" + id + "_" + d.name, String.format(Locale.US,
                        "{\"w\":%d,\"h\":%d,\"s\":%.6f,\"ox\":%.3f,\"oy\":%.3f,\"safe\":[%d,%d,%d,%d]}",
                        d.w, d.h, xf.s, xf.ox, xf.oy, d.l, d.t, d.r, d.b));
            }
        }
    }

    @Test
    public void newLevelsTargetsCountOthersDoNotOnEveryPhone() throws IOException {
        for (int id : NEW_LEVELS) {
            for (Device d : DEVICES) {
                GameView v = view(d);
                LevelScreen l = openLevel(v, id);
                run(v, 1.0f);              // the opening wave is up: every reference character
                Xf xf = l.xf();
                int targets = 0, others = 0, bombs = 0, combo = 0, expected = 0;
                java.util.List<LevelScreen.Mole> order = new java.util.ArrayList<>();
                for (LevelScreen.Hole hole : l.holes()) {
                    if (hole.mole.visible() && hole.mole.look.role == LevelScreen.TARGET) {
                        order.add(hole.mole);
                    }
                }
                for (LevelScreen.Hole hole : l.holes()) {
                    if (hole.mole.visible() && hole.mole.look.role != LevelScreen.TARGET) {
                        order.add(hole.mole);
                    }
                }
                for (LevelScreen.Mole m : order) {
                    if (l.decoyFails() && others > 0) {
                        others++;          // the round already failed on the first decoy
                        continue;
                    }
                    float[] a = aim(m);
                    int left = l.targetsLeft();
                    float t = l.elapsed();
                    tap(v, xf.x(a[0]), xf.y(a[1]));
                    if (l.fires()) {
                        // Level 3: the tap fires a shot; nothing counts until it lands
                        assertEquals(d.name + " L" + id + " shot fired", 1, l.shotsInFlight());
                        assertEquals(d.name + " L" + id + " not before it lands", left, l.targetsLeft());
                        land(v, l);
                    }
                    if (m.look.role == LevelScreen.TARGET) {
                        targets++;
                        combo = l.combos() ? combo + 1 : 1;
                        expected += l.points() * combo;
                        assertEquals(d.name + " L" + id + " target counts", left - 1, l.targetsLeft());
                    } else {
                        others++;
                        combo = 0;
                        assertEquals(d.name + " L" + id + " no target", left, l.targetsLeft());
                        if (l.decoyFails()) {
                            // Level 8: a decoy fails the round at once; it starts again a moment later
                            assertTrue(d.name + " L" + id + " decoy fails the round", l.isFailing());
                            assertEquals(1, l.failures());
                            if (d == DEVICES[8]) {
                                run(v, 0.4f);
                                render(v, "state_level" + id + "_wrong_miner");
                            }
                            run(v, 2.0f);
                            assertFalse(d.name + " L" + id + " restarted", l.isFailing());
                            assertEquals(d.name + " L" + id + " restarted: all targets back", l.goal(), l.targetsLeft());
                            assertEquals(d.name + " L" + id + " restarted: score 0", 0, l.score());
                            assertTrue(d.name + " L" + id + " restarted: timer from the start", l.elapsed() < 2.1f);
                            expected = 0;
                            continue;
                        }
                        if (m.look.role == LevelScreen.BOMB) {
                            bombs++;
                            assertEquals(d.name + " L" + id + " bomb costs time", t + l.bombPenalty(), l.elapsed(), 1e-3f);
                        }
                    }
                    if (l.decoyFails() && others > 0) {
                        continue;
                    }
                    assertEquals(d.name + " L" + id + " score", expected, l.score());
                    assertEquals(d.name + " L" + id + " combo", l.combos() ? combo : 0, l.combo());
                    run(v, 0.05f);
                    if (d == DEVICES[8] && targets == 2 && m.look.role == LevelScreen.TARGET) {
                        render(v, "state_level" + id + "_pop");
                    }
                }
                // Level 3: 2 purples, pink, red; Level 6: 3 stars, red, the masked bomb;
                // Level 8: 5 gold miners, the yellow and the brown-hat look-alikes
                assertEquals(d.name + " L" + id + " targets", id == 3 ? 2 : id == 6 ? 3 : 5, targets);
                assertEquals(d.name + " L" + id + " others", 2, others);
                assertEquals(d.name + " L" + id + " bombs", id == 6 ? 1 : 0, bombs);
            }
        }
    }

    @Test
    public void newLevelsPauseAndTimeUp() throws IOException {
        for (int id : NEW_LEVELS) {
            for (Device d : DEVICES) {
                GameView v = view(d);
                LevelScreen l = openLevel(v, id);
                run(v, 1.0f);
                SpriteButton p = l.pauseButton();
                Xf xf = l.xf();
                tap(v, xf.x((p.hx0 + p.hx1) / 2), xf.y((p.hy0 + p.hy1) / 2));   // where it is drawn
                assertTrue(d.name + " L" + id, l.isPaused());
                float t = l.elapsed();
                run(v, 3f);
                assertEquals(t, l.elapsed(), 1e-4f);
                if (d == DEVICES[8]) {
                    render(v, "state_level" + id + "_paused");
                }
            }
            GameView v = view(DEVICES[8]);
            LevelScreen l = openLevel(v, id);
            run(v, l.duration() + 1);
            assertTrue(l.isOver());
            assertFalse(l.isWon());
            render(v, "state_level" + id + "_timesup");
        }
    }

    /** Steps until every shot in flight has landed (tap-and-fire). */
    private static void land(GameView v, LevelScreen l) {
        for (int f = 0; f < 60 && l.shotsInFlight() > 0; f++) {
            v.step(FRAME);
        }
        assertEquals("the shot landed", 0, l.shotsInFlight());
    }

    private static LevelScreen.Mole visible(LevelScreen l, int role) {
        for (LevelScreen.Hole hole : l.holes()) {
            if (hole.mole.tappable() && hole.mole.look.role == role) {
                return hole.mole;
            }
        }
        return null;
    }

    @Test
    public void level3TapFiresAShotThatScoresWhenItLands() throws IOException {
        for (Device d : new Device[]{DEVICES[8], PIXEL_PRO_XL}) {
            String pre = d == PIXEL_PRO_XL ? "pixel_level3_fire_" : "state_level3_fire_";
            GameView v = view(d);
            LevelScreen l = openLevel(v, 3);
            assertTrue(l.fires());
            Xf xf = l.xf();
            // the opening demonstration: the hand taps the front purple, its shot strikes it (no points)
            run(v, 1.1f);
            render(v, pre + "1_demo_hand");
            for (int f = 0; f < 120 && l.shotsInFlight() == 0; f++) {
                v.step(FRAME);
            }
            assertEquals("the demonstration fires", 1, l.shotsInFlight());
            run(v, 0.1f);
            render(v, pre + "2_demo_shot");
            land(v, l);
            assertEquals("the demonstration scores nothing", 0, l.score());
            assertEquals(l.goal(), l.targetsLeft());
            assertEquals("the demonstration's hit bursts", 1, l.energyBursts());
            run(v, 0.07f);
            render(v, pre + "3_demo_hit");
            // the player: tap a purple -> a shot leaves the player's side, flies to it, strikes, scores
            LevelScreen.Mole purple = visible(l, LevelScreen.TARGET);
            assertTrue("a purple is up", purple != null);
            float[] a = aim(purple);
            tap(v, xf.x(a[0]), xf.y(a[1]));
            assertEquals(1, l.shotsInFlight());
            assertTrue("the purple waits for the shot", purple.locked);
            tap(v, xf.x(a[0]), xf.y(a[1]));
            assertEquals("one shot per character", 1, l.shotsInFlight());
            assertEquals("nothing before it lands", 0, l.score());
            float[] from = l.fireFrom();
            run(v, 0.1f);
            float[] at = l.shotAt();
            assertTrue("the shot travels: " + at[0] + "," + at[1], at[1] < from[1] - 40 && at[1] > purple.aimY() + 20);
            render(v, pre + "4_shot");
            land(v, l);
            assertEquals("the purple counts", l.goal() - 1, l.targetsLeft());
            assertEquals("the purple scores", l.points(), l.score());
            assertEquals(LevelScreen.Mole.POPPED, purple.state);
            assertTrue("the purple bursts", l.energyBursts() >= 1);
            run(v, 0.05f);
            render(v, pre + "5_hit_burst");
            run(v, 0.1f);
            render(v, pre + "6_hit_pop");
            // a red one (or the pink): struck, but no credit
            LevelScreen.Mole red = visible(l, LevelScreen.DISTRACTOR);
            assertTrue("a decoy is up", red != null);
            int bursts = l.energyBursts();
            a = aim(red);
            tap(v, xf.x(a[0]), xf.y(a[1]));
            assertEquals(1, l.shotsInFlight());
            land(v, l);
            assertEquals("no credit for a red one", l.goal() - 1, l.targetsLeft());
            assertEquals("no points for a red one", l.points(), l.score());
            assertEquals("the combo is broken", 0, l.combo());
            assertEquals(LevelScreen.Mole.REACT, red.state);
            assertTrue("no purple burst on a red one", l.energyBursts() <= bursts);
            run(v, 0.05f);
            render(v, pre + "7_red_no_credit");
            // the bare ground: the shot lands there, nothing counts
            tap(v, xf.x(560), xf.y(1180));
            assertEquals(1, l.shotsInFlight());
            land(v, l);
            assertEquals(l.goal() - 1, l.targetsLeft());
            assertEquals(l.points(), l.score());
        }
        // the other levels hit at once, as before
        for (int id : new int[]{6, 8}) {
            GameView v = view(DEVICES[8]);
            LevelScreen l = openLevel(v, id);
            assertFalse(l.fires());
        }
    }

    /** Plays like a perfect player: hits every target as soon as it can be hit. */
    private static void playToWin(GameView v, LevelScreen l) {
        Xf xf = l.xf();
        for (int f = 0; f < 60 * 40 && !l.isOver(); f++) {
            for (LevelScreen.Hole hole : l.holes()) {
                LevelScreen.Mole m = hole.mole;
                if (m.tappable() && m.look.role == LevelScreen.TARGET && m.state == LevelScreen.Mole.UP) {
                    float[] a = aim(m);
                    tap(v, xf.x(a[0]), xf.y(a[1]));
                }
            }
            v.step(FRAME);
        }
    }

    @Test
    public void winningUnlocksTheNextLevel() throws IOException {
        GameView v = view(DEVICES[8]);
        assertEquals(1, v.playLevel());
        openLevel(v);
        playToWin(v, v.level);
        assertTrue("Level 1 won", v.level.isOver() && v.level.isWon());
        assertEquals(3, v.playLevel());
        run(v, 1f);
        render(v, "state_level_complete");
        for (int id : NEW_LEVELS) {
            LevelScreen l = openLevel(v, id);
            run(v, 0.5f);
            playToWin(v, l);
            assertTrue("Level " + id + " won", l.isOver() && l.isWon());
            assertEquals(0, l.targetsLeft());
            run(v, 1f);
            render(v, "state_level" + id + "_complete");
        }
        assertEquals(8, v.playLevel());      // the last level so far stays the one PLAY starts
    }

    /** Pixel 10/11 Pro XL class phone: 1344 x 2992, camera punch-hole at the top. */
    static final Device PIXEL_PRO_XL = new Device("pixel_pro_xl", 1344, 2992, "xxxhdpi", 0, 132, 0, 0);

    @Test
    public void newLevelsOnAPixelProXl() throws IOException {
        GameView v1 = view(PIXEL_PRO_XL);
        openLevel(v1);
        run(v1, 2.5f);                     // Level 1's reference moment (00:28)
        render(v1, "pixel_level1_reference_moment");
        for (int id : NEW_LEVELS) {
            GameView v = view(PIXEL_PRO_XL);
            LevelScreen l = openLevel(v, id);
            run(v, 0.5f);
            l.referenceMoment();
            render(v, "pixel_level" + id + "_reference_moment");
            v = view(PIXEL_PRO_XL);
            l = openLevel(v, id);
            run(v, 7.3f);                  // characters popping up in other holes
            render(v, "pixel_level" + id + "_play");
        }
    }

    @Test
    public void level8SpeedsUpAtTwentySeconds() throws IOException {
        GameView v = view(DEVICES[8]);
        LevelScreen l = openLevel(v, 8);
        run(v, 19.5f);
        assertFalse(l.spedUp());
        assertFalse(l.bannerShowing());
        run(v, 1.0f);                        // 00:20 left
        assertTrue(l.spedUp());
        assertTrue(l.bannerShowing());
        render(v, "state_level8_speedup");
        run(v, 3.0f);
        assertFalse("the banner goes away again", l.bannerShowing());
        assertTrue(l.spedUp());
    }

    @Test
    public void levelsPanelReplaysAnyReachedLevel() throws IOException {
        GameView v = view(DEVICES[8]);
        SpriteButton play = v.home.controls()[3];
        v.prefs.setUnlocked(2);             // Levels 1 and 3 won: Level 6 is next, Level 8 locked
        tap(v, play.xf.x((play.hx0 + play.hx1) / 2), play.xf.y((play.hy0 + play.hy1) / 2));
        run(v, 0.4f);
        Ui.Dialog panel = v.home.levelsPanel();
        assertTrue("PLAY opens LEVELS", panel != null && v.current() == v.home);
        render(v, "state_home_levels");
        float[] locked = panel.buttonCentre(8);
        tap(v, locked[0], locked[1]);
        run(v, 0.4f);
        assertTrue("a locked level does not open", v.current() == v.home);
        float[] one = panel.buttonCentre(1);
        tap(v, one[0], one[1]);
        run(v, 0.4f);
        assertTrue("Level 1 can be played again", v.current() == v.level);
        v.show(v.home);
        run(v, 0.5f);
        tap(v, play.xf.x((play.hx0 + play.hx1) / 2), play.xf.y((play.hy0 + play.hy1) / 2));
        run(v, 0.4f);
        float[] three = v.home.levelsPanel().buttonCentre(3);
        tap(v, three[0], three[1]);
        run(v, 0.4f);
        assertTrue("Level 3 can be played again", v.current() == v.levelScreen(3));
    }

    /**
     * A human-like player on a phone: reacts 0.45-0.85 s after a character shows (spotting it,
     * moving the finger), needs 0.25 s between taps, misses one tap in eight and now and then taps
     * a decoy by mistake. Returns {won, seconds left}.
     */
    private static float[] playLikeAHuman(GameView v, LevelScreen l, long seed) {
        return playLikeAHuman(v, l, seed, false);
    }

    /**
     * careful: where a decoy fails the round, a player looks twice -- 0.05 s longer to react and
     * one decoy in 50 tapped by mistake instead of one in 12.
     */
    private static float[] playLikeAHuman(GameView v, LevelScreen l, long seed, boolean careful) {
        java.util.Random r = new java.util.Random(seed);
        java.util.Map<LevelScreen.Mole, Float> seen = new java.util.HashMap<>();
        java.util.Map<LevelScreen.Mole, Boolean> decided = new java.util.HashMap<>();
        Xf xf = l.xf();
        float now = 0, lastTap = -1;
        for (int f = 0; f < 60 * 60 && !l.isOver(); f++) {
            for (LevelScreen.Hole hole : l.holes()) {
                LevelScreen.Mole m = hole.mole;
                if (!m.tappable()) {
                    seen.remove(m);
                    decided.remove(m);
                    continue;
                }
                if (!seen.containsKey(m)) {
                    seen.put(m, now + 0.45f + 0.4f * r.nextFloat() + (careful ? 0.05f : 0));
                    decided.put(m, m.look.role == LevelScreen.TARGET || r.nextFloat() < (careful ? 0.02f : 0.08f));
                }
                if (decided.get(m) && now >= seen.get(m) && now - lastTap >= 0.25f) {
                    float[] a = aim(m);
                    float dx = r.nextFloat() < 0.125f ? 70 : 0;     // a miss
                    tap(v, xf.x(a[0] + dx), xf.y(a[1]));
                    lastTap = now;
                    decided.put(m, false);
                }
            }
            v.step(FRAME);
            now += FRAME;
            if (l.failures() > 0) {
                return new float[]{0, 0};     // tapped a decoy: the round is lost
            }
        }
        return new float[]{l.isWon() ? 1 : 0, l.duration() - l.elapsed()};
    }

    /** {win rate, average seconds left, rounds lost on a decoy, average targets hit} over `runs` rounds. */
    private float[] measure(int id, int runs, boolean careful) {
        float wins = 0, left = 0, decoy = 0, hit = 0;
        for (int seed = 0; seed < runs; seed++) {
            GameView v = view(DEVICES[8]);
            LevelScreen l = openLevel(v, id);
            l.seed(100 + seed);
            float[] res = playLikeAHuman(v, l, 1000 + seed, careful);
            wins += res[0];
            left += res[1];
            decoy += l.failures() > 0 ? 1 : 0;
            hit += l.goal() - l.targetsLeft();
        }
        return new float[]{wins / runs, left / runs, decoy, hit / runs};
    }

    @Test
    public void difficultyRisesGraduallyAndStaysFair() {
        int[] ids = {1, 3, 6};
        float[] rate = new float[ids.length], spare = new float[ids.length];
        StringBuilder report = new StringBuilder();
        for (int k = 0; k < ids.length; k++) {
            float[] r = measure(ids[k], 12, false);
            rate[k] = r[0];
            spare[k] = r[1];
            report.append(String.format(Locale.US, "Level %d: won %.0f%%, %.1f s left on average%n", ids[k], rate[k] * 100, spare[k]));
        }
        // Level 8: a decoy fails the round, so a player looks twice before tapping (careful);
        // the casual player's result is shown for comparison
        float[] l8 = measure(8, 24, true), l8casual = measure(8, 24, false);
        report.append(String.format(Locale.US, "Level 8 (careful player): won %.0f%%, %.1f s left on average; lost on a decoy %.0f of 24, gold hit %.1f of 28 on average%n",
                l8[0] * 100, l8[1], l8[2], l8[3]));
        report.append(String.format(Locale.US, "Level 8 (casual player, 1 decoy in 12 tapped): won %.0f%%; lost on a decoy %.0f of 24, gold hit %.1f%n",
                l8casual[0] * 100, l8casual[2], l8casual[3]));
        System.out.print(report);
        try {
            writeLayout("difficulty", report.toString());
        } catch (IOException ignored) {
        }
        for (int k = 0; k < ids.length; k++) {
            assertTrue("Level " + ids[k] + " must stay winnable: " + report, rate[k] >= 0.4f);
        }
        for (int k = 1; k < ids.length; k++) {
            // each level leaves a good player less time to spare than the one before
            assertTrue("Level " + ids[k] + " harder than Level " + ids[k - 1] + ": " + report, spare[k] < spare[k - 1]);
            assertTrue(rate[k] <= rate[k - 1] + 1e-3f);
        }
        // Level 8: clearly harder than Level 6, but a careful player still wins it
        assertTrue("Level 8 harder than Level 6: " + report, l8[0] < rate[2]);
        assertTrue("Level 8 winnable by a careful player: " + report, l8[0] >= 0.3f);
        assertTrue("carelessness is punished on Level 8: " + report, l8casual[0] < l8[0]);
    }

    @Test
    public void level8CharactersChangeHolesAndGetFaster() {
        GameView v = view(DEVICES[8]);
        LevelScreen l = openLevel(v, 8);
        l.seed(3);
        // watch a whole round without tapping: how long each appearance stays up, early and late
        java.util.Map<LevelScreen.Mole, Float> since = new java.util.HashMap<>();
        float early = 0, late = 0;
        int nEarly = 0, nLate = 0;
        float now = 0;
        for (int f = 0; f < 60 * 41 && !l.isOver(); f++) {
            for (LevelScreen.Hole hole : l.holes()) {
                LevelScreen.Mole m = hole.mole;
                boolean up = m.state == LevelScreen.Mole.UP;
                if (up && !since.containsKey(m)) {
                    since.put(m, now);
                } else if (!up && since.containsKey(m)) {
                    float d = now - since.remove(m);
                    if (now > 4 && now < 14) {
                        early += d;
                        nEarly++;
                    } else if (now > 28) {
                        late += d;
                        nLate++;
                    }
                }
            }
            v.step(FRAME);
            now += FRAME;
        }
        assertTrue("characters change holes: " + l.hops(), l.hops() >= 3);
        assertTrue("they stay up less and less: early " + early / nEarly + " s, late " + late / nLate + " s",
                late / nLate < 0.8f * (early / nEarly));
        assertEquals("no tap, no failure", 0, l.failures());
    }
}
