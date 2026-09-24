package com.colorpop.game;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.MotionEvent;

import org.json.JSONObject;

/**
 * Welcome / Home. The background is the reference with its controls removed; every control is
 * its own sprite at its reference position.
 *
 * Layout (art = reference pixels, 628 x 1157, one uniform scale, see {@link Fit}): the art is
 * anchored to the safe bottom, so title, beaver, tagline, PLAY and the nav bar keep their exact
 * arrangement; the coin counter and the gear stay pinned to the top (below a camera cutout). A
 * taller screen shows more sky between them (painted into bg_full.png); a shorter or wider one
 * scales everything down together and shows a little of the side padding. Must-see: from the
 * coin counter (art y 51) to the bottom of the nav bar.
 */
final class HomeScreen extends Screen {
    private static final int SETTINGS_SOUND = 1, SETTINGS_VIBRATION = 2, SETTINGS_DONE = 3;

    private static final float CONTENT_TOP = 51;   // top of the coin counter
    private final Fit.Backdrop bg;
    private final int artW, artH;
    private final Xf main = new Xf(), top = new Xf();
    private final SpriteButton coin, plus, gear, play;
    private final SpriteButton[] nav;
    private final SpriteButton[] buttons;
    private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
    private final Paint ui = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Ui.Toast toast = new Ui.Toast();
    private Ui.Dialog settings;
    private SpriteButton pressed;

    HomeScreen(GameView game) {
        super(game);
        Art art = game.art;
        JSONObject meta = art.json("home/_meta.json");
        JSONObject b = meta.optJSONObject("_bg");
        artW = b.optInt("art_w");
        artH = b.optInt("art_h");
        bg = new Fit.Backdrop(art.bitmap("home/bg_full.png"), b.optInt("pad_side"), b.optInt("pad_top"));
        coin = SpriteButton.fromMeta(art, "home", "coin_pill", meta, false, top);
        plus = SpriteButton.fromMeta(art, "home", "plus", meta, false, top);
        gear = SpriteButton.fromMeta(art, "home", "gear", meta, true, top);
        play = SpriteButton.fromMeta(art, "home", "play", meta, false, main);
        nav = new SpriteButton[]{
                SpriteButton.fromMeta(art, "home", "nav_missions", meta, false, main),
                SpriteButton.fromMeta(art, "home", "nav_shop", meta, false, main),
                SpriteButton.fromMeta(art, "home", "nav_rewards", meta, false, main),
                SpriteButton.fromMeta(art, "home", "nav_profile", meta, false, main)};
        // touch order: the + sits on top of the coin counter (which is display only)
        buttons = new SpriteButton[]{plus, gear, play, nav[0], nav[1], nav[2], nav[3]};
    }

    @Override
    void layout(int width, int height) {
        super.layout(width, height);
        android.graphics.Rect safe = game.safe;
        float topNeed = Fit.topNeed(game);
        float s = Fit.scale(artW, CONTENT_TOP, artH, w - safe.left - safe.right, h - safe.bottom, topNeed);
        float ox = Fit.left(safe, w, artW, s);
        main.set(s, ox, h - safe.bottom - artH * s);
        top.set(s, ox, Math.max(0, topNeed - CONTENT_TOP * s));
        if (settings != null) {
            settings.layout(w, h, s, safe);
        }
    }

    @Override
    void onShow() {
        settings = null;
        pressed = null;
        for (SpriteButton b : buttons) {
            b.pressed = false;
        }
    }

    @Override
    void update(float dt) {
        for (SpriteButton b : buttons) {
            b.update(dt);
        }
        toast.update(dt);
        if (settings != null) {
            settings.update(dt);
        }
    }

    @Override
    void draw(Canvas c) {
        bg.draw(c, main, w, h);
        play.draw(c, paint);
        for (SpriteButton n : nav) {
            n.draw(c, paint);
        }
        coin.draw(c, paint);
        plus.draw(c, paint);
        gear.draw(c, paint);
        toast.draw(c, w / 2f, main.y(700), main.s, game.text, ui);
        if (settings != null) {
            settings.draw(c, w, h, game.text, ui);
        }
    }

    @Override
    void touch(MotionEvent e) {
        if (settings != null) {
            onSettings(settings.touch(e, game.sfx));
            return;
        }
        float x = e.getX(), y = e.getY();
        switch (e.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                pressed = null;
                for (SpriteButton b : buttons) {
                    if (b.contains(x, y)) {
                        pressed = b;
                        b.pressed = true;
                        break;
                    }
                }
                break;
            case MotionEvent.ACTION_MOVE:
                if (pressed != null) {
                    pressed.pressed = pressed.contains(x, y);
                }
                break;
            case MotionEvent.ACTION_UP:
                if (pressed != null) {
                    SpriteButton b = pressed;
                    pressed = null;
                    b.pressed = false;
                    if (b.contains(x, y)) {
                        activate(b);
                    }
                }
                break;
            case MotionEvent.ACTION_CANCEL:
                if (pressed != null) {
                    pressed.pressed = false;
                    pressed = null;
                }
                break;
            default:
                break;
        }
    }

    private void activate(SpriteButton b) {
        game.sfx.click();
        if (b == play) {
            game.show(game.level);
        } else if (b == gear) {
            openSettings();
        } else {
            toast.show("COMING SOON!");  // + and the nav tabs: those screens don't exist yet
        }
    }

    void openSettings() {
        settings = new Ui.Dialog("SETTINGS")
                .toggle(SETTINGS_SOUND, "SOUND", game.prefs.sound())
                .toggle(SETTINGS_VIBRATION, "VIBRATION", game.prefs.vibration())
                .button(SETTINGS_DONE, "DONE", true);
        settings.layout(w, h, main.s, game.safe);
    }

    private void onSettings(int id) {
        if (id == SETTINGS_SOUND) {
            game.prefs.setSound(settings.toggles.get(0).on);
        } else if (id == SETTINGS_VIBRATION) {
            game.prefs.setVibration(settings.toggles.get(1).on);
            game.sfx.buzz(30);
        } else if (id == SETTINGS_DONE) {
            settings = null;
        }
    }

    @Override
    boolean back() {
        if (settings != null) {
            settings = null;
            return true;
        }
        return false;
    }

    // ------------------------------------------------------------------ for tests
    Ui.Toast toast() {
        return toast;
    }

    boolean settingsOpen() {
        return settings != null;
    }

    Xf mainXf() {
        return main;
    }

    Xf topXf() {
        return top;
    }

    SpriteButton[] controls() {
        return new SpriteButton[]{coin, plus, gear, play, nav[0], nav[1], nav[2], nav[3]};
    }
}
