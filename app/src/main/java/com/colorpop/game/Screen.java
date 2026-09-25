package com.colorpop.game;

import android.graphics.Canvas;
import android.view.MotionEvent;

/** One full-screen state of the game (Home, a level). */
abstract class Screen {
    final GameView game;
    int w, h;

    Screen(GameView game) {
        this.game = game;
    }

    /** Screen size (px) or display-cutout inset changed. */
    void layout(int width, int height) {
        w = width;
        h = height;
    }

    /** Called when the screen becomes the current one (after the fade out of the previous one). */
    void onShow() {
    }

    /** The app went to the background. */
    void onPause() {
    }

    abstract void update(float dt);

    abstract void draw(Canvas c);

    abstract void touch(MotionEvent e);

    /** System back; return false to let the app close. */
    boolean back() {
        return false;
    }
}
