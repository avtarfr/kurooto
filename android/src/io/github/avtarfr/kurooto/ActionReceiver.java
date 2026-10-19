package io.github.avtarfr.kurooto;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Buttons on Kurooto's notifications. A ringing call's Decline / Later: stop ringing and tell your computer. A
 *  question's Reply, choices, Approve / Deny, Later, or a message's buttons: send the answer (Inbox.send). */
public class ActionReceiver extends BroadcastReceiver {
    static final String DECLINE = "io.github.avtarfr.kurooto.DECLINE", LATER = "io.github.avtarfr.kurooto.LATER";
    static final String ANSWER = "io.github.avtarfr.kurooto.ANSWER", REPLY = "io.github.avtarfr.kurooto.REPLY",
            BUTTON = "io.github.avtarfr.kurooto.BUTTON";

    @Override public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (ANSWER.equals(a) || REPLY.equals(a) || BUTTON.equals(a)) {
            Inbox.send(c.getApplicationContext(), i, goAsync());
            return;
        }
        ListenService.stopRinging(c);
        final String since = i.getStringExtra("since");
        final String action = LATER.equals(a) ? "later" : "decline";
        if (since == null || since.isEmpty()) return;
        final PendingResult pr = goAsync();
        new Thread(() -> { Line.ringReply(c, since, action); pr.finish(); }).start();
    }
}
