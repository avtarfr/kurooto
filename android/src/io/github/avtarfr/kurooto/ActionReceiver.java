package io.github.avtarfr.kurooto;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Decline or Later on a ringing call's notification: stop ringing and tell your computer (through the line). */
public class ActionReceiver extends BroadcastReceiver {
    static final String DECLINE = "io.github.avtarfr.kurooto.DECLINE", LATER = "io.github.avtarfr.kurooto.LATER";

    @Override public void onReceive(Context c, Intent i) {
        ListenService.stopRinging(c);
        final String since = i.getStringExtra("since");
        final String action = LATER.equals(i.getAction()) ? "later" : "decline";
        if (since == null || since.isEmpty()) return;
        final PendingResult pr = goAsync();
        new Thread(() -> { Line.ringReply(c, since, action); pr.finish(); }).start();
    }
}
