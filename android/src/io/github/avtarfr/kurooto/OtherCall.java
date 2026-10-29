package io.github.avtarfr.kurooto;

import android.content.Context;
import android.media.AudioManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

/**
 * (0.9.1, L87) This phone in another call: a WhatsApp or Meet call, or a phone call. Only when your computer asks for
 * it (calls.phone_busy or voice.listen.phone_call, the "sessions" message's switch phone_busy): "busy until" goes to it
 * sealed, a time and nothing else (never who, never which app), and 0 when the call ends. Kurooto's own call on this
 * phone doesn't count. Read from AudioManager's mode: a listener on Android 12 and newer, a look once a minute before.
 */
final class OtherCall {
    static final int SDK = Build.VERSION.SDK_INT;
    private static volatile boolean last; // what your computer was last told
    private static final Handler H = new Handler(Looper.getMainLooper());

    private OtherCall() { }

    /** Start watching (ListenService.onCreate). Returns what stop() takes. */
    static Object watch(final Context c) {
        final AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
        if (am == null) return null;
        try { changed(c, am.getMode()); } catch (Exception ignored) { } // already in one when the app starts
        if (SDK >= 31) {
            try {
                AudioManager.OnModeChangedListener l = mode -> changed(c, mode);
                am.addOnModeChangedListener(Chat.IO, l);
                return l;
            } catch (Exception e) {
                return null;
            }
        }
        final Runnable[] tick = new Runnable[1];
        tick[0] = () -> {
            try { changed(c, am.getMode()); } catch (Exception ignored) { }
            H.postDelayed(tick[0], 60_000);
        };
        H.postDelayed(tick[0], 60_000);
        return tick[0];
    }

    static void stop(Context c, Object w) {
        if (w == null) return;
        try {
            if (SDK >= 31 && w instanceof AudioManager.OnModeChangedListener) {
                AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
                if (am != null) am.removeOnModeChangedListener((AudioManager.OnModeChangedListener) w);
            } else if (w instanceof Runnable) {
                H.removeCallbacks((Runnable) w);
            }
        } catch (Exception ignored) { }
    }

    private static void changed(final Context c, int mode) {
        final boolean busy = CallRules.otherCall(mode, CallActivity.live || CallActivity.showing);
        if (busy == last) return;
        Chat.IO.execute(() -> {
            if (Chat.demo != null || !Chat.computerSwitch(c, "phone_busy")) return;
            if (Chat.busy(c, CallRules.busyUntil(busy, System.currentTimeMillis()))) last = busy;
        });
    }
}
