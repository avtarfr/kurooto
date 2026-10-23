package io.github.avtarfr.kurooto;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Start listening after a reboot or an app update, and set the wake-up alarm on this phone again (Android forgets
 *  alarms when it restarts). */
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        try { Alarms.schedule(c); } catch (Exception ignored) { }
        try { if (Prefs.paired(c)) ListenService.start(c); } catch (Exception ignored) { }
    }
}
