package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/**
 * The Today screen (0.6.0), on the app's first screen under Call and Chat: the dashboard's Today from your computer's
 * last copy (Today), "as of" when your call line got it, so it shows with the computer asleep. The alarm (and whether
 * it's also set on this phone, Alarms), classes and events, what's due (parts done, "4/7"; tap one for Done and +1,
 * which go through the phone outbox), reminders, open threads. Built from Ui's pieces into its own column, which it
 * re-draws by itself when a fresh copy comes.
 */
final class TodayView {
    private final Activity a;
    private final LinearLayout col;
    private final Handler h = new Handler(Looper.getMainLooper());
    private String open = ""; // the deadline whose Done / +1 show
    private String said = "";
    private boolean saidOk = true;

    private TodayView(Activity a) {
        this.a = a;
        col = Ui.column(a);
        Ui.gap(col, 0, 0);
    }

    /** Add the Today screen to a page (MainActivity), and fetch a fresh copy if the last is over 30 seconds old. */
    static void add(Activity a, LinearLayout page) {
        final TodayView v = new TodayView(a);
        page.addView(v.col);
        v.draw();
        Today.listener = () -> v.h.post(() -> { if (v.col.isAttachedToWindow()) v.draw(); });
        if (System.currentTimeMillis() - Today.fetchedAt(a) > 30_000) new Thread(() -> Today.fetch(a.getApplicationContext())).start();
    }

    private void draw() {
        col.removeAllViews();
        JSONObject d = Today.load(a), t = d.optJSONObject("list");
        String day = t == null ? "" : t.optString("day", "");
        col.addView(Ui.heading(a, day.isEmpty() ? "Today" : "Today · " + day));
        String asOf = asOf(d.optString("at", ""));
        String off = "offline".equals(d.optString("computer")) ? "your computer is off" : "";
        if (!asOf.isEmpty() || !off.isEmpty()) {
            col.addView(Ui.dim(a, (asOf.isEmpty() ? "" : "As of " + asOf) + (asOf.isEmpty() || off.isEmpty() ? "" : " · ") + off));
        }
        if (d.optBoolean("old")) {
            col.addView(Ui.dim(a, "Your call line doesn't have Today yet: your computer updates it by itself (at 05:10)."));
        }
        if (t == null) {
            LinearLayout k = Ui.card(a);
            k.addView(Ui.dim(a, d.optBoolean("off")
                    ? "Turned off on your computer (Settings → calls → today)."
                    : "Nothing here yet. Your computer sends today's classes, what's due and your alarm to your call line, "
                    + "sealed for this phone; they show here once it has."));
            col.addView(k);
            return;
        }
        alarm(t.optJSONObject("alarm"));
        LinearLayout day1 = Ui.list(a);
        JSONArray cl = t.optJSONArray("classes"), ev = t.optJSONArray("events");
        for (int i = 0; cl != null && i < cl.length(); i++) {
            JSONObject x = cl.optJSONObject(i);
            if (x == null) continue;
            day1.addView(Ui.item(a, x.optString("name"), x.optString("time") + (x.optBoolean("skipping") ? " · skipping" : ""), null));
        }
        for (int i = 0; ev != null && i < ev.length(); i++) day1.addView(Ui.item(a, ev.optString(i), null, null));
        section("Classes and events", day1);
        due(t.optJSONArray("due"));
        LinearLayout rem = Ui.list(a);
        JSONArray rs = t.optJSONArray("reminders");
        for (int i = 0; rs != null && i < rs.length(); i++) {
            JSONObject x = rs.optJSONObject(i);
            if (x != null) rem.addView(Ui.item(a, x.optString("what"), x.optString("when"), null));
        }
        section("Reminders", rem);
        LinearLayout th = Ui.list(a);
        JSONArray ts = t.optJSONArray("threads");
        for (int i = 0; ts != null && i < ts.length(); i++) {
            JSONObject x = ts.optJSONObject(i);
            if (x != null) th.addView(Ui.item(a, x.optString("text"), null, null));
        }
        section("Open threads", th);
        int q = t.optInt("questions");
        if (q > 0) col.addView(Ui.dim(a, q == 1 ? "1 question waits for you (below)." : q + " questions wait for you (below)."));
        if (!said.isEmpty()) {
            TextView s = Ui.status(a);
            s.setText(said);
            if (saidOk) Ui.ok(s); else Ui.bad(s);
            col.addView(s);
        }
    }

    /** A section: its name, then its list card; left out when the list is empty. */
    private void section(String name, LinearLayout list) {
        if (list.getChildCount() == 0) return;
        col.addView(Ui.gap(Ui.text(a, name, 14, true, Ui.color(a, R.color.k_dim)), 16, 0));
        col.addView(list);
    }

    /** The next alarm, and whether this phone rings it too (tap to switch); Android 12+ without exact alarms: why
     *  that matters, and Allow. */
    private void alarm(JSONObject al) {
        if (al == null || al.length() == 0) return;
        JSONArray at = al.optJSONArray("at");
        String next = al.optString("next", "");
        LinearLayout list = Ui.list(a);
        String daily = al.optString("daily", "");
        list.addView(Ui.item(a, next.isEmpty() ? "No alarm set" : next, daily.isEmpty() ? null : "Daily alarm " + daily, null));
        if (at == null || at.length() == 0) { section("Alarm", list); return; }
        boolean on = Alarms.on(a);
        String sub = !on ? "Off: only the call from your call line rings."
                : Alarms.set(a) == 0 ? "On: rings here too, even with your computer and call line out of reach."
                : Alarms.exact(a) ? "On: set on this phone too, so it rings even with your computer and call line out of reach."
                : "On, but Android doesn't allow exact alarms for Kurooto yet: it may ring a few minutes late.";
        list.addView(Ui.item(a, "Ring on this phone too", sub, v -> { Alarms.setOn(a, !Alarms.on(a)); draw(); }));
        section("Alarm", list);
        if (on && !Alarms.exact(a)) {
            Button allow = Ui.end(Ui.flat(a, "Allow exact alarms"));
            allow.setOnClickListener(v -> { try { a.startActivity(Alarms.allowExact(a)); } catch (Exception ignored) { } });
            col.addView(allow);
        }
    }

    /** What's due: title, parts done and when. Tap one for +1 and Done (quizzes and exams have none). */
    private void due(JSONArray ds) {
        LinearLayout list = Ui.list(a);
        for (int i = 0; ds != null && i < ds.length(); i++) {
            final JSONObject x = ds.optJSONObject(i);
            if (x == null) continue;
            final String id = x.optString("id");
            String parts = x.has("parts") ? x.optInt("done") + "/" + x.optInt("parts") + " · " : "";
            final JSONArray acts = x.optJSONArray("acts");
            boolean can = acts != null && acts.length() > 0;
            list.addView(Ui.item(a, x.optString("title"), parts + "due " + x.optString("when") + (x.optBoolean("exam") ? " · quiz or exam" : ""),
                    can ? v -> { open = id.equals(open) ? "" : id; draw(); } : null));
            if (!can || !id.equals(open)) continue;
            LinearLayout row = Ui.row(a);
            row.setPadding(Ui.dp(a, 16), 0, Ui.dp(a, 16), Ui.dp(a, 8));
            for (int k = 0; k < acts.length(); k++) {
                final String act = acts.optString(k);
                Button b = "done".equals(act) ? Ui.filled(a, "Done") : Ui.tonal(a, act);
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
                lp.setMargins(k == 0 ? 0 : Ui.dp(a, 8), 0, 0, 0);
                b.setOnClickListener(v -> tap(id, act, x.optString("title")));
                row.addView(b, lp);
            }
            list.addView(row);
        }
        section("Due", list);
    }

    /** Done or +1: to your computer through the call line (kept there while it's off). */
    private void tap(final String id, final String act, final String title) {
        final String label = ("done".equals(act) ? "Done" : act) + ": " + title;
        said = "Sending…";
        saidOk = true;
        open = "";
        draw();
        new Thread(() -> {
            Chat.Sent s = Today.act(a.getApplicationContext(), id, act, label);
            h.post(() -> {
                said = s.queued ? "Saved on your call line: it goes to your computer when it's back." : s.note;
                saidOk = s.ok;
                if (said.isEmpty()) said = "Sent.";
                draw();
            });
            if (s.ok && !s.queued) Today.fetch(a.getApplicationContext()); // your computer sends the new list at once
        }).start();
    }

    /** "14:05" for an ISO time today, "Thu 14:05" another day; "" if there's none. */
    static String asOf(String iso) {
        if (iso == null || iso.length() < 19) return "";
        try {
            SimpleDateFormat in = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.ROOT);
            in.setTimeZone(TimeZone.getTimeZone("UTC"));
            Date t = in.parse(iso.substring(0, 19));
            SimpleDateFormat day = new SimpleDateFormat("yyyyMMdd", Locale.ROOT);
            boolean today = day.format(t).equals(day.format(new Date()));
            return new SimpleDateFormat(today ? "HH:mm" : "EEE HH:mm", Locale.getDefault()).format(t);
        } catch (Exception e) {
            return "";
        }
    }
}
