package com.colorpop.game;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Insets;
import android.graphics.Paint;
import android.graphics.Rect;
import android.os.Build;
import android.view.Choreographer;
import android.view.DisplayCutout;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;

/**
 * The whole game is this one view: a frame loop driven by the display's vsync, the current
 * screen, and a short fade through black when switching screens.
 */
final class GameView extends View implements Choreographer.FrameCallback {
    private static final float FADE = 0.18f;

    final Art art;
    final Prefs prefs;
    final Sfx sfx;
    final OutlineText text;
    /** The levels, played in this order (the reference designs Levels 1, 3, 6, 8 and 10). */
    static final int[] LEVELS = {1, 3, 6};

    final HomeScreen home;
    final LevelScreen level;                   // Level 1
    private final java.util.HashMap<Integer, LevelScreen> levels = new java.util.HashMap<>();
    /**
     * Screen edges the game must keep its controls away from, in px: display cutouts (camera
     * holes, notches, curved edges) and system bars while they are shown. In immersive mode the
     * bars are hidden, so normally only a top cutout remains.
     */
    final Rect safe = new Rect();

    private Screen screen, next;
    private float fade;
    private int fadeDir;
    private boolean running;
    private long lastFrame;
    private final Paint black = new Paint();

    GameView(Context context, Art.Source source) {
        super(context);
        art = new Art(source);
        prefs = new Prefs(context);
        sfx = new Sfx(context, source, prefs);
        text = new OutlineText(art.font, art.json("level/level.json").optJSONObject("text_style"));
        home = new HomeScreen(this);
        level = new LevelScreen(this, 1, "level");
        levels.put(1, level);
        screen = home;
        screen.onShow();
        black.setColor(0xff000000);
        setFocusable(true);
    }

    /** Fade to {@code target} (ignored while a fade is already running). */
    void show(Screen target) {
        if (fadeDir == 0 && target != screen) {
            next = target;
            fadeDir = 1;
        }
    }

    Screen current() {
        return screen;
    }

    /** The screen of level {@code id} (loaded the first time it is needed). */
    LevelScreen levelScreen(int id) {
        LevelScreen l = levels.get(id);
        if (l == null) {
            l = new LevelScreen(this, id, "level" + id);
            levels.put(id, l);
            if (getWidth() > 0 && getHeight() > 0) {
                l.layout(getWidth(), getHeight());
            }
        }
        return l;
    }

    /** The level after {@code id}, or 0 after the last one. */
    int nextLevel(int id) {
        for (int i = 0; i < LEVELS.length - 1; i++) {
            if (LEVELS[i] == id) {
                return LEVELS[i + 1];
            }
        }
        return 0;
    }

    /** The level PLAY starts: the first one not won yet (the last one once all are). */
    int playLevel() {
        return LEVELS[Math.max(0, Math.min(LEVELS.length - 1, prefs.unlocked()))];
    }

    /** Level {@code id} was won: the next one is unlocked. */
    void levelWon(int id) {
        for (int i = 0; i < LEVELS.length; i++) {
            if (LEVELS[i] == id && i + 1 > prefs.unlocked()) {
                prefs.setUnlocked(Math.min(i + 1, LEVELS.length - 1));
            }
        }
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        relayout();
    }

    private void relayout() {
        if (getWidth() > 0 && getHeight() > 0) {
            home.layout(getWidth(), getHeight());
            for (LevelScreen l : levels.values()) {
                l.layout(getWidth(), getHeight());
            }
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public WindowInsets onApplyWindowInsets(WindowInsets insets) {
        int l, t, r, b;
        if (Build.VERSION.SDK_INT >= 30) {
            Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
            Insets cut = insets.getInsets(WindowInsets.Type.displayCutout());
            l = Math.max(bars.left, cut.left);
            t = Math.max(bars.top, cut.top);
            r = Math.max(bars.right, cut.right);
            b = Math.max(bars.bottom, cut.bottom);
        } else {
            l = insets.getSystemWindowInsetLeft();
            t = insets.getSystemWindowInsetTop();
            r = insets.getSystemWindowInsetRight();
            b = insets.getSystemWindowInsetBottom();
            if (Build.VERSION.SDK_INT >= 28) {
                DisplayCutout cutout = insets.getDisplayCutout();
                if (cutout != null) {
                    l = Math.max(l, cutout.getSafeInsetLeft());
                    t = Math.max(t, cutout.getSafeInsetTop());
                    r = Math.max(r, cutout.getSafeInsetRight());
                    b = Math.max(b, cutout.getSafeInsetBottom());
                }
            }
        }
        setSafeInsets(l, t, r, b);
        return super.onApplyWindowInsets(insets);
    }

    void setSafeInsets(int left, int top, int right, int bottom) {
        if (safe.left != left || safe.top != top || safe.right != right || safe.bottom != bottom) {
            safe.set(left, top, right, bottom);
            relayout();
        }
    }

    /** A small gap kept between a cutout / bar and the controls. */
    float safeMargin() {
        return 6 * getResources().getDisplayMetrics().density;
    }

    void resume() {
        if (!running) {
            running = true;
            lastFrame = 0;
            Choreographer.getInstance().postFrameCallback(this);
        }
    }

    void pause() {
        running = false;
        Choreographer.getInstance().removeFrameCallback(this);
        screen.onPause();
    }

    @Override
    public void doFrame(long frameTimeNanos) {
        if (!running) {
            return;
        }
        float dt = lastFrame == 0 ? 0 : Math.min(0.05f, (frameTimeNanos - lastFrame) / 1e9f);
        lastFrame = frameTimeNanos;
        step(dt);
        invalidate();
        Choreographer.getInstance().postFrameCallback(this);
    }

    /** Advances the game by {@code dt} seconds. */
    void step(float dt) {
        if (fadeDir > 0) {
            fade = Math.min(1, fade + dt / FADE);
            if (fade >= 1) {
                screen = next;
                next = null;
                screen.onShow();
                fadeDir = -1;
                dt = 0;
            }
        } else if (fadeDir < 0) {
            fade = Math.max(0, fade - dt / FADE);
            if (fade <= 0) {
                fadeDir = 0;
            }
        }
        screen.update(dt);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        screen.draw(canvas);
        if (fade > 0) {
            black.setAlpha((int) (255 * fade));
            canvas.drawRect(0, 0, getWidth(), getHeight(), black);
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent e) {
        if (fadeDir == 0) {
            screen.touch(e);
        }
        if (e.getActionMasked() == MotionEvent.ACTION_UP) {
            performClick();
        }
        return true;
    }

    @Override
    public boolean performClick() {
        return super.performClick();
    }

    boolean back() {
        return fadeDir != 0 || screen.back();
    }

    void release() {
        sfx.release();
        art.source.close();
    }
}
