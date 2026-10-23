package io.github.avtarfr.kurooto;

import android.app.AlarmManager;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;

import java.util.concurrent.atomic.AtomicBoolean;

/** Buttons on Kurooto's notifications. A ringing call's Decline / Later: stop ringing and tell your computer (this
 *  phone's own wake-up alarm: Stop / Snooze, kept here, Alarms). A question's Reply, choices, Approve / Deny, Later, or
 *  a message's buttons: send the answer (Inbox.send); a reminder's Done takes it off every phone ("dismiss"). A quick
 *  button on the chat's notification (+1, Done, Snooze): tapped as in the chat (Chat.tap). A Done of the app's own:
 *  the notification goes. A sealed reminder's +10 min / +1 h: shown again then (kept on this phone). And the alarm
 *  going off (Alarms.fired). */
public class ActionReceiver extends BroadcastReceiver {
    static final String DECLINE = "io.github.avtarfr.kurooto.DECLINE", LATER = "io.github.avtarfr.kurooto.LATER";
    static final String ANSWER = "io.github.avtarfr.kurooto.ANSWER", REPLY = "io.github.avtarfr.kurooto.REPLY",
            BUTTON = "io.github.avtarfr.kurooto.BUTTON", CHAT_TAP = "io.github.avtarfr.kurooto.CHAT_TAP";
    static final String DISMISS = "io.github.avtarfr.kurooto.DISMISS", ALARM = "io.github.avtarfr.kurooto.ALARM",
            NOTE_DONE = "io.github.avtarfr.kurooto.NOTE_DONE", SEALED_SNOOZE = "io.github.avtarfr.kurooto.SEALED_SNOOZE",
            SEALED_SHOW = "io.github.avtarfr.kurooto.SEALED_SHOW";

    @Override public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (ALARM.equals(a)) {
            Alarms.fired(c.getApplicationContext(), i.getLongExtra("at", 0));
            return;
        }
        if (NOTE_DONE.equals(a)) {
            nm(c).cancel(i.getStringExtra("tag"), i.getIntExtra("id", 0));
            return;
        }
        if (SEALED_SNOOZE.equals(a)) {
            sealedSnooze(c.getApplicationContext(), i);
            return;
        }
        if (SEALED_SHOW.equals(a)) {
            ListenService.sealedNote(c, i.getStringExtra("sid"), i.getStringExtra("title"), i.getStringExtra("text"));
            return;
        }
        if (ANSWER.equals(a) || REPLY.equals(a) || BUTTON.equals(a) || DISMISS.equals(a)) {
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
        Alarms.replied(c, since, action, i.getBooleanExtra("alarm", false)); // the wake-up alarm: this phone's copy hears it
        if (since == null || since.isEmpty() || since.startsWith("local:")) return;
        final PendingResult pr = goAsync();
        new Thread(() -> { Line.ringReply(c, since, action); pr.finish(); }).start();
    }

    /** A sealed reminder's +10 min / +1 h: it goes now and comes back then (an inexact alarm is enough). */
    private static void sealedSnooze(Context c, Intent i) {
        String sid = i.getStringExtra("sid");
        nm(c).cancel("sealed-" + sid, ListenService.ID_SEALED);
        Intent show = new Intent(c, ActionReceiver.class).setAction(SEALED_SHOW).putExtra("sid", sid)
                .putExtra("title", i.getStringExtra("title")).putExtra("text", i.getStringExtra("text"));
        PendingIntent pi = PendingIntent.getBroadcast(c, ("sealed-" + sid + ":show").hashCode(), show,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        long at = System.currentTimeMillis() + 60_000L * i.getIntExtra("min", 10);
        ((AlarmManager) c.getSystemService(Context.ALARM_SERVICE)).setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
    }

    private static NotificationManager nm(Context c) {
        return (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
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
                JSONArray bs = null;
                try { bs = new JSONArray(i.getStringExtra("buttons")); } catch (Exception ignored) { }
                boolean counting = Buttons.counts(label); // a +1 stays for the next tap; Done or Snooze is done with
                if (s.queued) {
                    ListenService.chatNote(c, msg, "Tapped " + label + ". It waits on your call line for your computer.", counting ? bs : null, true);
                } else if (!s.ok) {
                    ListenService.chatNote(c, msg, s.note, bs, true);
                } else if (!counting) {
                    ListenService.chatNote(c, msg, s.note.isEmpty() ? "Tapped " + label + "." : s.note, null, true);
                }
            } finally { release.run(); }
        }).start();
    }
}
