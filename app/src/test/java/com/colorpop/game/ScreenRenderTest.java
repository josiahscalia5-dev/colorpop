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
}
