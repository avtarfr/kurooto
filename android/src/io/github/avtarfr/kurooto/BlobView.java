package io.github.avtarfr.kurooto;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.Settings;
import android.view.View;

/**
 * The main screen's idle background: four soft blobs in the palette (the dashboard's and the site's look: accent,
 * lav, peach, pink; Material You's accents on Android 12+), drifting and changing shape slowly. Each is a closed curve
 * through 24 points whose distance from the centre is a sum of a few slow sines (as the dashboard's cells), filled
 * with a gradient that fades to nothing at its edge.
 * It draws about 20 frames a second only while it's on screen (it stops when the app goes to the background or the
 * view is gone), and stands still (one frame) with the system's "Remove animations" on, or in battery saver.
 * Nothing is allocated per frame.
 */
final class BlobView extends View {
    private static final int N = 24, FRAME_MS = 50;
    private static final double TAU = Math.PI * 2;
    /** Per blob: where it sits (fractions of the width and height), its size (of the width), and a seed. */
    private static final float[][] BLOBS = {
        {0.10f, 0.12f, 0.50f, 1.7f}, {0.92f, 0.36f, 0.42f, 4.1f}, {0.16f, 0.68f, 0.46f, 2.9f}, {0.86f, 0.90f, 0.40f, 5.3f},
    };
    private static final int[] COLOURS = {R.color.k_blob_1, R.color.k_blob_2, R.color.k_blob_3, R.color.k_blob_4};

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final Matrix matrix = new Matrix();
    private final Shader[] shades = new Shader[BLOBS.length];
    private final float[] px = new float[N], py = new float[N];
    private final boolean still;
    private final Runnable tick = this::invalidate;
    private boolean running;

    BlobView(Context c) {
        super(c);
        // fainter on the light background, where the palette's colours are dark
        float a = c.getResources().getBoolean(R.bool.k_light) ? 0.15f : 0.22f;
        for (int i = 0; i < BLOBS.length; i++) {
            int col = Ui.color(c, COLOURS[i]);
            shades[i] = new RadialGradient(0, 0, 1, new int[]{Ui.alpha(col, a), Ui.alpha(col, a * 0.6f), Ui.alpha(col, 0)},
                    new float[]{0, 0.65f, 1}, Shader.TileMode.CLAMP);
        }
        still = calm(c);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }

    /** "Remove animations" (Settings → Accessibility) or battery saver: the blobs stand still. */
    static boolean calm(Context c) {
        try {
            if (Settings.Global.getFloat(c.getContentResolver(), Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f) return true;
        } catch (Exception ignored) { }
        PowerManager pm = (PowerManager) c.getSystemService(Context.POWER_SERVICE);
        return pm != null && pm.isPowerSaveMode();
    }

    @Override protected void onAttachedToWindow() { super.onAttachedToWindow(); update(); }

    @Override protected void onDetachedFromWindow() { super.onDetachedFromWindow(); update(); }

    @Override protected void onWindowVisibilityChanged(int v) { super.onWindowVisibilityChanged(v); update(); }

    @Override protected void onVisibilityChanged(View changed, int v) { super.onVisibilityChanged(changed, v); update(); }

    /** Animate only while attached, shown, and in a visible window. */
    private void update() {
        boolean run = !still && isAttachedToWindow() && getWindowVisibility() == VISIBLE && isShown();
        if (run == running) return;
        running = run;
        removeCallbacks(tick);
        if (run) invalidate();
    }

    @Override protected void onDraw(Canvas canvas) {
        float w = getWidth(), h = getHeight();
        if (w <= 0 || h <= 0) return;
        double t = still ? 0 : SystemClock.uptimeMillis() / 1000.0;
        for (int i = 0; i < BLOBS.length; i++) {
            float[] b = BLOBS[i];
            double seed = b[3];
            float cx = (float) (w * (b[0] + 0.07 * Math.sin(t * 0.05 + seed))), cy = (float) (h * (b[1] + 0.04 * Math.cos(t * 0.043 + seed * 1.3)));
            float r = (float) (w * b[2] * (1 + 0.05 * Math.sin(t * 0.11 + seed)));
            shape(cx, cy, r, t * 0.3, seed);
            matrix.setScale(r * 1.12f, r * 1.12f);
            matrix.postTranslate(cx, cy);
            shades[i].setLocalMatrix(matrix);
            paint.setShader(shades[i]);
            canvas.drawPath(path, paint);
        }
        if (running) {
            removeCallbacks(tick);
            postDelayed(tick, FRAME_MS);
        }
    }

    /** The blob's outline into path: 24 points, joined by curves through their midpoints. */
    private void shape(float cx, float cy, float r, double t, double seed) {
        for (int j = 0; j < N; j++) {
            double a = j * TAU / N;
            double k = 1 + 0.16 * (0.5 * Math.sin(2 * a + t * 0.55 + seed) + 0.38 * Math.sin(3 * a - t * 0.9 + seed * 1.7)
                    + 0.22 * Math.sin(5 * a + t * 1.4 + seed * 2.3));
            px[j] = (float) (cx + Math.cos(a) * r * k);
            py[j] = (float) (cy + Math.sin(a) * r * k);
        }
        path.rewind();
        path.moveTo((px[N - 1] + px[0]) / 2, (py[N - 1] + py[0]) / 2);
        for (int j = 0; j < N; j++) {
            int n = (j + 1) % N;
            path.quadTo(px[j], py[j], (px[j] + px[n]) / 2, (py[j] + py[n]) / 2);
        }
        path.close();
    }
}
