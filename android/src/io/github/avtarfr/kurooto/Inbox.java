package io.github.avtarfr.kurooto;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.RemoteInput;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Questions, approvals and messages from Kurooto (everything that isn't a call). An item is what your computer sent:
 * id, kind, title, message, and how to answer it: reply (a Reply box), choices, buttons, later. Its notification is
 * tagged with the item's id, so the call line can take it down once it's dealt with somewhere else.
 *   Android 7 and newer: Reply types the answer right in the notification (the choices are offered there too).
 *   Android 6: Reply opens a small answer window (AnswerActivity), as tapping the notification does everywhere.
 * A counting button ("+1": one more part of a problem set done) leaves the notification up after a tap, showing what
 * your computer said (or that the tap waits on the call line for it), so the next tap counts too.
 * A reminder or a deadline (0.6.0) puts its quick buttons on the notification instead (Buttons): +1, Done, Snooze 3 h
 * for a deadline; Done, +10 min, +1 h for a reminder, whose Done only takes it down (on every phone: "dismiss").
 */
final class Inbox {
    static final int ID = 7; // one number for all of them; the tag (the item id) tells them apart
    static final String KEY_REPLY = "reply";
    static final int SDK = Build.VERSION.SDK_INT;

    private Inbox() { }

    static boolean asks(JSONObject it) {
        String k = it.optString("kind");
        return "question".equals(k) || "approval".equals(k);
    }

    static String text(JSONObject it) { return it.optString("message", it.optString("text", "")); }

    /** A counting button: labelled "+1" (or "+2"...). Your computer keeps its message open for the next tap. */
    static boolean counts(JSONObject button) { return button != null && Buttons.counts(button.optString("label")); }

    /** The buttons' labels (null for a link, which never goes on as a quick button). */
    static String[] labels(JSONArray bs) {
        String[] out = new String[bs == null ? 0 : bs.length()];
        for (int i = 0; i < out.length; i++) {
            JSONObject x = bs.optJSONObject(i);
            out[i] = x == null || x.has("url") ? null : x.optString("label");
        }
        return out;
    }

    static boolean quickKind(JSONObject it) {
        String k = it.optString("kind");
        return "reminder".equals(k) || "deadline".equals(k);
    }

    private static int code(String id, String what) { return (id + ":" + what).hashCode(); }

    private static int immutable() { return PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT; }

    /** Opens the answer window for this item (tapping the notification, or Reply on Android 6). */
    static PendingIntent open(Context c, JSONObject it, String what) {
        Intent i = new Intent(c, AnswerActivity.class).putExtra("item", it.toString())
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(c, code(it.optString("id"), what), i, immutable());
    }

    private static PendingIntent act(Context c, JSONObject it, String action, String what, String extraKey, String extra) {
        Intent i = new Intent(c, ActionReceiver.class).setAction(action).putExtra("item", it.toString()).putExtra(extraKey, extra);
        return PendingIntent.getBroadcast(c, code(it.optString("id"), what), i, immutable());
    }

    static void show(Context c, JSONObject it) {
        String id = it.optString("id");
        if (id.isEmpty()) return;
        String body = text(it);
        Notification.Builder b = ListenService.builder(c, asks(it) ? ListenService.CH_ASK : ListenService.CH_MSG)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(it.optString("title", Prefs.assistant(c)))
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setOnlyAlertOnce(true) // shown again after a +1: quietly
                .setContentIntent(open(c, it, "open"))
                .setAutoCancel(!asks(it));
        JSONArray bs = it.optJSONArray("buttons");
        String[] labels = labels(bs);
        int[] quick = quickKind(it) ? Buttons.pick(labels, Buttons.MAX) : new int[0];
        if (quick.length > 0) { // a reminder or a deadline: Done and Snooze first (Reply is in the answer window)
            int n = 0;
            if (Buttons.addDone(labels)) {
                b.addAction(new Notification.Action.Builder(null, "Done", act(c, it, ActionReceiver.DISMISS, "dismiss", "dismiss", "1")).build());
                n++;
            }
            for (int i = 0; i < quick.length && n < Buttons.MAX; i++, n++) {
                b.addAction(new Notification.Action.Builder(null, labels[quick[i]],
                        act(c, it, ActionReceiver.BUTTON, "b" + quick[i], "button", String.valueOf(quick[i]))).build());
            }
            if (it.optBoolean("reply") && n < Buttons.MAX) b.addAction(reply(c, it));
            nm(c).notify(id, ID, b.build());
            return;
        }
        int n = 0;
        if (it.optBoolean("reply")) { b.addAction(reply(c, it)); n++; }
        JSONArray ch = it.optJSONArray("choices");
        for (int i = 0; ch != null && i < ch.length() && n < 3; i++, n++) {
            b.addAction(new Notification.Action.Builder(null, ch.optString(i), act(c, it, ActionReceiver.ANSWER, "c" + i, "answer", ch.optString(i))).build());
        }
        for (int i = 0; bs != null && i < bs.length() && n < 3; i++, n++) {
            JSONObject x = bs.optJSONObject(i);
            if (x == null) continue;
            PendingIntent pi = x.optString("url").startsWith("https://")
                    ? PendingIntent.getActivity(c, code(id, "u" + i), new Intent(Intent.ACTION_VIEW, Uri.parse(x.optString("url"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), immutable())
                    : act(c, it, ActionReceiver.BUTTON, "b" + i, "button", String.valueOf(i));
            b.addAction(new Notification.Action.Builder(null, x.optString("label"), pi).build());
        }
        if (it.optBoolean("later") && n < 3) b.addAction(new Notification.Action.Builder(null, "Later", act(c, it, ActionReceiver.ANSWER, "later", "answer", "later")).build());
        nm(c).notify(id, ID, b.build());
    }

    /** Reply: typed in the notification (Android 7+, with the choices offered), else the answer window. */
    private static Notification.Action reply(Context c, JSONObject it) {
        if (SDK >= 24) {
            RemoteInput.Builder ri = new RemoteInput.Builder(KEY_REPLY).setLabel("Your answer");
            JSONArray ch = it.optJSONArray("choices");
            if (ch != null && ch.length() > 0) {
                CharSequence[] opts = new CharSequence[Math.min(ch.length(), 5)];
                for (int i = 0; i < opts.length; i++) opts[i] = ch.optString(i);
                ri.setChoices(opts);
            }
            int flags = PendingIntent.FLAG_UPDATE_CURRENT | (SDK >= 31 ? PendingIntent.FLAG_MUTABLE : 0); // the answer is filled in
            Intent i = new Intent(c, ActionReceiver.class).setAction(ActionReceiver.REPLY).putExtra("item", it.toString());
            PendingIntent pi = PendingIntent.getBroadcast(c, code(it.optString("id"), "reply"), i, flags);
            return new Notification.Action.Builder(null, "Reply", pi).addRemoteInput(ri.build()).build();
        }
        return new Notification.Action.Builder(null, "Reply", open(c, it, "reply")).build();
    }

    static void cancel(Context c, String id) { nm(c).cancel(id, ID); }

    static void cancel(Context c, JSONArray ids) {
        for (int i = 0; ids != null && i < ids.length(); i++) cancel(c, ids.optString(i));
    }

    /** After an answer from a notification: say how it went (and stop the Reply spinner on Android 7+). */
    static void done(Context c, JSONObject it, Line.Answered r) {
        String id = it.optString("id");
        Notification.Builder b = ListenService.builder(c, ListenService.CH_ASK)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(r.delivered() ? "Sent" : r.gone() ? "No longer open" : "Not sent: tap to try again")
                .setContentText(r.note)
                .setStyle(new Notification.BigTextStyle().bigText(r.note))
                .setOnlyAlertOnce(true)
                .setAutoCancel(true);
        if (!r.delivered() && !r.gone()) b.setContentIntent(open(c, it, "retry"));
        else if (SDK >= 26) b.setTimeoutAfter(8000);
        nm(c).notify(id, ID, b.build());
    }

    /** A notification button or Reply: send it from a background thread, then show the outcome. */
    static void send(final Context c, Intent i, final BroadcastReceiver.PendingResult pr) {
        final JSONObject it, fields = new JSONObject();
        try {
            it = new JSONObject(i.getStringExtra("item"));
            if (ActionReceiver.REPLY.equals(i.getAction())) {
                Bundle in = RemoteInput.getResultsFromIntent(i);
                CharSequence typed = in == null ? null : in.getCharSequence(KEY_REPLY);
                if (typed == null || typed.toString().trim().isEmpty()) { pr.finish(); return; }
                fields.put("answer", typed.toString().trim());
            } else if (ActionReceiver.BUTTON.equals(i.getAction())) {
                fields.put("button", Integer.parseInt(i.getStringExtra("button")));
            } else if (ActionReceiver.DISMISS.equals(i.getAction())) {
                fields.put("dismiss", true);
            } else {
                fields.put("answer", i.getStringExtra("answer"));
            }
        } catch (Exception e) {
            pr.finish();
            return;
        }
        JSONArray bs = it.optJSONArray("buttons");
        final boolean again = fields.has("button") && bs != null && counts(bs.optJSONObject(fields.optInt("button")));
        // a receiver may only hold on for a few seconds; the listening service keeps the app alive after that
        final AtomicBoolean finished = new AtomicBoolean(false);
        final Runnable release = () -> { if (finished.compareAndSet(false, true)) pr.finish(); };
        new Handler(Looper.getMainLooper()).postDelayed(release, 8000);
        new Thread(() -> {
            try {
                Line.Answered r = Line.answer(c, it.optString("id"), fields);
                if (again && r.delivered()) {
                    try { it.put("message", r.note); } catch (Exception ignored) { }
                    show(c, it); // still there, for the next +1
                } else if (fields.has("dismiss") && (r.delivered() || r.gone())) {
                    cancel(c, it.optString("id")); // Done on a reminder: gone here, and from your other phones
                } else {
                    done(c, it, r);
                }
            } finally { release.run(); }
        }).start();
    }

    private static NotificationManager nm(Context c) {
        return (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
    }
}
