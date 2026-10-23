package io.github.avtarfr.kurooto;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;

import java.util.concurrent.atomic.AtomicBoolean;

/** Buttons on Kurooto's notifications. A ringing call's Decline / Later: stop ringing and tell your computer. A
 *  question's Reply, choices, Approve / Deny, Later, or a message's buttons: send the answer (Inbox.send). A +1 on
 *  the chat's notification: tapped as in the chat (Chat.tap). */
public class ActionReceiver extends BroadcastReceiver {
    static final String DECLINE = "io.github.avtarfr.kurooto.DECLINE", LATER = "io.github.avtarfr.kurooto.LATER";
    static final String ANSWER = "io.github.avtarfr.kurooto.ANSWER", REPLY = "io.github.avtarfr.kurooto.REPLY",
            BUTTON = "io.github.avtarfr.kurooto.BUTTON", CHAT_TAP = "io.github.avtarfr.kurooto.CHAT_TAP";

    @Override public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (ANSWER.equals(a) || REPLY.equals(a) || BUTTON.equals(a)) {
            Inbox.send(c.getApplicationContext(), i, goAsync());
            return;
        }
        if (CHAT_TAP.equals(a)) {
            chatTap(c.getApplicationContext(), i, goAsync());
            return;
        }
        ListenService.stopRinging(c);
        final String since = i.getStringExtra("since");
        final String action = LATER.equals(a) ? "later" : "decline";
        if (since == null || since.isEmpty()) return;
        final PendingResult pr = goAsync();
        new Thread(() -> { Line.ringReply(c, since, action); pr.finish(); }).start();
    }

    /** Your computer answers a +1 that went through in the chat (a new message, with the +1 again); one that waits on
     *  the call line, or didn't go, is said on the notification, which keeps the +1. */
    private static void chatTap(final Context c, final Intent i, final PendingResult pr) {
        final AtomicBoolean finished = new AtomicBoolean(false);
        final Runnable release = () -> { if (finished.compareAndSet(false, true)) pr.finish(); };
        new Handler(Looper.getMainLooper()).postDelayed(release, 8000);
        new Thread(() -> {
            try {
                String msg = i.getStringExtra("msg"), label = i.getStringExtra("label");
                Chat.Sent s = Chat.tap(c, msg, i.getIntExtra("n", -1), label);
                if (s.queued || !s.ok) {
                    JSONArray bs = null;
                    try { bs = new JSONArray(i.getStringExtra("buttons")); } catch (Exception ignored) { }
                    ListenService.chatNote(c, msg, s.queued ? "Tapped " + label + ". It waits on your call line for your computer." : s.note, bs, true);
                }
            } finally { release.run(); }
        }).start();
    }
}
