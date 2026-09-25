package com.colorpop.game;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.SoundPool;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;

/** Sound effects and vibration, both switchable in Settings. */
final class Sfx {
    private final Prefs prefs;
    private final SoundPool pool;
    private final Vibrator vibrator;
    private final int pop, bonk, click, end, shoot;

    Sfx(Context context, Art.Source source, Prefs prefs) {
        this.prefs = prefs;
        pool = new SoundPool.Builder()
                .setMaxStreams(6)
                .setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_GAME)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build())
                .build();
        pop = source.loadSound(pool, "sfx/pop.wav");
        bonk = source.loadSound(pool, "sfx/bonk.wav");
        click = source.loadSound(pool, "sfx/click.wav");
        end = source.loadSound(pool, "sfx/end.wav");
        shoot = source.loadSound(pool, "sfx/shoot.wav");
        vibrator = findVibrator(context);
    }

    @SuppressWarnings("deprecation")
    private static Vibrator findVibrator(Context context) {
        if (Build.VERSION.SDK_INT >= 31) {
            VibratorManager vm = (VibratorManager) context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
            return vm == null ? null : vm.getDefaultVibrator();
        }
        return (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
    }

    void pop() {
        play(pop, 1f);
        buzz(18);
    }

    void bonk() {
        play(bonk, 0.8f);
        buzz(40);
    }

    /** Level 3: a shot leaves. */
    void shoot() {
        play(shoot, 0.55f);
    }

    void click() {
        play(click, 0.7f);
    }

    void end() {
        play(end, 0.9f);
    }

    private void play(int id, float volume) {
        if (id != 0 && prefs.sound()) {
            pool.play(id, volume, volume, 1, 0, 1f);
        }
    }

    @SuppressWarnings("deprecation")
    void buzz(long ms) {
        if (vibrator == null || !prefs.vibration() || !vibrator.hasVibrator()) {
            return;
        }
        if (Build.VERSION.SDK_INT >= 26) {
            vibrator.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
        } else {
            vibrator.vibrate(ms);
        }
    }

    void release() {
        pool.release();
    }
}
