package com.colorpop.game;

import android.content.Context;
import android.content.SharedPreferences;

/** Player settings (Settings panel on Home). */
final class Prefs {
    private final SharedPreferences sp;

    Prefs(Context context) {
        sp = context.getSharedPreferences("colorpop", Context.MODE_PRIVATE);
    }

    boolean sound() {
        return sp.getBoolean("sound", true);
    }

    boolean vibration() {
        return sp.getBoolean("vibration", true);
    }

    void setSound(boolean on) {
        sp.edit().putBoolean("sound", on).apply();
    }

    void setVibration(boolean on) {
        sp.edit().putBoolean("vibration", on).apply();
    }
}
