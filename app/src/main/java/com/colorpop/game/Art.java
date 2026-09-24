package com.colorpop.game;

import android.content.res.AssetFileDescriptor;
import android.content.res.AssetManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.media.SoundPool;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;

/**
 * Loads the game's art from the assets folder (bitmaps are decoded once and kept).
 * All positions in the art metadata are reference pixels; see {@link Xf}.
 */
final class Art {

    /** Where the files come from: the APK's assets, or a folder when rendering screens in tests. */
    abstract static class Source {
        abstract InputStream open(String path) throws IOException;

        abstract Typeface font(String path);

        abstract int loadSound(SoundPool pool, String path);

        void close() {
        }

        static Source of(final AssetManager assets) {
            return new Source() {
                private final List<AssetFileDescriptor> open = new ArrayList<>();

                @Override
                InputStream open(String path) throws IOException {
                    return assets.open(path);
                }

                @Override
                Typeface font(String path) {
                    return Typeface.createFromAsset(assets, path);
                }

                @Override
                int loadSound(SoundPool pool, String path) {
                    try {
                        AssetFileDescriptor fd = assets.openFd(path);
                        open.add(fd);
                        return pool.load(fd, 1);
                    } catch (IOException e) {
                        return 0;
                    }
                }

                @Override
                void close() {
                    for (AssetFileDescriptor fd : open) {
                        try {
                            fd.close();
                        } catch (IOException ignored) {
                        }
                    }
                    open.clear();
                }
            };
        }
    }

    final Source source;
    final Typeface font;
    private final HashMap<String, Bitmap> bitmaps = new HashMap<>();

    Art(Source source) {
        this.source = source;
        this.font = source.font("fonts/LilitaOne-Regular.ttf");
    }

    Bitmap bitmap(String path) {
        Bitmap b = bitmaps.get(path);
        if (b == null) {
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inPreferredConfig = Bitmap.Config.ARGB_8888;
            o.inScaled = false;
            try (InputStream in = source.open(path)) {
                b = BitmapFactory.decodeStream(in, null, o);
            } catch (IOException e) {
                throw new IllegalStateException("missing art: " + path, e);
            }
            if (b == null) {
                throw new IllegalStateException("unreadable art: " + path);
            }
            bitmaps.put(path, b);
        }
        return b;
    }

    JSONObject json(String path) {
        try (InputStream in = source.open(path)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
            }
            return new JSONObject(out.toString("UTF-8"));
        } catch (IOException | JSONException e) {
            throw new IllegalStateException("bad art metadata: " + path, e);
        }
    }
}
