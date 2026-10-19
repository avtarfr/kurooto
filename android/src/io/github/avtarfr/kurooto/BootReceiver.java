package io.github.avtarfr.kurooto;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Start listening after a reboot or an app update. */
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        try { if (Prefs.paired(c)) ListenService.start(c); } catch (Exception ignored) { }
    }
}
