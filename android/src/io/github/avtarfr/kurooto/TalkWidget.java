package io.github.avtarfr.kurooto;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * The home screen widgets. Talk (1x1, this class): one round button that opens the chat ready to type. Talk, and
 * what's waiting (2x1, TalkWideWidget): the same button, and the newest question or message waiting for you (what the
 * app's main screen lists under "Waiting for you"); tapping that side opens the app.
 * The 2x1 looks up what's waiting on the call line (GET /pending, as the main screen does) every 30 minutes, when a
 * question arrives or is dealt with (Inbox), when the app's main screen has just looked (no second request), and after
 * pairing. With no 2x1 widget placed nothing is looked up. The text shown is kept in Prefs ("widgetLine").
 */
public class TalkWidget extends AppWidgetProvider {
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static Runnable pending;

    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        draw(c);
        if (!(this instanceof TalkWideWidget)) return;
        final Context app = c.getApplicationContext();
        final PendingResult pr = goAsync(); // the look-up runs past onUpdate (it has under a minute)
        new Thread(() -> {
            try { fetch(app); } finally { pr.finish(); }
        }).start();
    }

    /** Redraw every placed widget from what's stored (no network). Any thread. */
    static void draw(Context c) {
        try {
            AppWidgetManager m = AppWidgetManager.getInstance(c);
            if (m == null) return;
            int[] small = m.getAppWidgetIds(new ComponentName(c, TalkWidget.class));
            if (small.length > 0) m.updateAppWidget(small, views(c, R.layout.widget_talk));
            int[] wide = wideIds(c);
            if (wide.length > 0) {
                RemoteViews v = views(c, R.layout.widget_talk_wide);
                v.setTextViewText(R.id.name, Prefs.assistant(c));
                v.setTextViewText(R.id.line, line(c));
                Intent open = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                v.setOnClickPendingIntent(R.id.info, PendingIntent.getActivity(c, 2, open, flags()));
                m.updateAppWidget(wide, v);
            }
        } catch (Exception ignored) { } // a launcher that went away mid-update: the next update draws it
    }

    /** Look again soon (a few seconds, so a burst of questions or answers is one request). Any thread. */
    static void refreshSoon(Context c) {
        final Context app = c.getApplicationContext();
        MAIN.post(() -> {
            if (pending != null) MAIN.removeCallbacks(pending);
            pending = () -> {
                pending = null;
                new Thread(() -> fetch(app)).start();
            };
            MAIN.postDelayed(pending, 3000);
        });
    }

    /** The main screen just fetched what's waiting: show it without asking the call line again. */
    static void waiting(Context c, JSONArray items) {
        String s;
        if (items == null || items.length() == 0) {
            s = c.getString(R.string.widget_nothing);
        } else {
            JSONObject newest = items.optJSONObject(items.length() - 1);
            String text = newest == null ? "" : Inbox.text(newest).replaceAll("\\s+", " ").trim();
            s = items.length() == 1 ? text : items.length() + " waiting: " + text;
        }
        Prefs.setWidgetLine(c, s);
        draw(c);
    }

    private static void fetch(Context c) {
        if (wideIds(c).length == 0) return;
        if (!Prefs.paired(c)) { draw(c); return; }
        JSONArray items = Line.waiting(c); // null: unreachable; keep what it said before
        if (items != null) waiting(c, items); else draw(c);
    }

    private static String line(Context c) {
        if (!Prefs.paired(c)) return "Open the app to pair this phone";
        String s = Prefs.widgetLine(c);
        return s.isEmpty() ? c.getString(R.string.widget_nothing) : s;
    }

    /** A widget's views with the Talk button wired to the chat (keyboard up). */
    private static RemoteViews views(Context c, int layout) {
        RemoteViews v = new RemoteViews(c.getPackageName(), layout);
        Intent chat = new Intent(c, ChatActivity.class).putExtra("type", true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        v.setOnClickPendingIntent(R.id.talk, PendingIntent.getActivity(c, 1, chat, flags()));
        v.setContentDescription(R.id.talk, "Chat with " + Prefs.assistant(c));
        return v;
    }

    private static int[] wideIds(Context c) {
        try {
            return AppWidgetManager.getInstance(c).getAppWidgetIds(new ComponentName(c, TalkWideWidget.class));
        } catch (Exception e) {
            return new int[0];
        }
    }

    private static int flags() { return PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT; }
}
