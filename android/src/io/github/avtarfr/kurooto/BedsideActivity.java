package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.app.AlarmManager;
import android.app.AlertDialog;
import android.app.KeyguardManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.TimePickerDialog;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.format.DateFormat;
import android.view.View;
import android.view.WindowManager;

import androidx.activity.ComponentActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.TimeZone;

/**
 * Bedside mode (0.6.0): an old phone as a dock. A big clock, the date, the next alarm, the calls due next, and one big
 * Talk button that starts a voice call with Kurooto (the same call screen as the app's Call button). The screen dims
 * by the hour (Dock: at night as dim as it goes, in warm colours; a tap brightens it for 15 s), stays on while
 * charging (optional), and shows over the lock screen, so Talk works on a locked phone; Chat and "waiting for you"
 * ask you to unlock first, and with a secure lock the calls' reasons are hidden until you do. A wake-up call or any
 * call rings here full screen. Opened from the app's main screen, or by itself while charging between chosen hours
 * (ListenService keeps Watcher registered for that). What's coming is read from the call line (/upcoming: the
 * schedule your computer pushed) every 5 minutes; the next alarm is Kurooto's wake-up call or the phone's own.
 * The screen itself (0.8.7) is Compose, Material 3 Expressive (BedsideScreen.kt): this activity keeps every rule and
 * lifecycle hook and writes what to show into a BedsideState. Extra "auto": opened by itself while charging; "demo" (debug
 * and dev builds only, Demo.ON): made-up calls, nothing fetched or sent, and "hour" (an int) to look at any hour's colours.
 */
public class BedsideActivity extends ComponentActivity {
    static final int SDK = Build.VERSION.SDK_INT;
    static final String CH_BEDSIDE = "bedside";
    static final int ID_BEDSIDE = 9;
    static final long RELOAD_MS = 5 * 60_000, BRIGHT_MS = 15_000;
    static volatile boolean visible;

    private final Handler h = new Handler(Looper.getMainLooper());
    private BedsideState st; // what the screen shows (BedsideScreen draws it)
    private boolean charging, auto, busy, demo;
    private int demoHour = -1;
    private long brightUntil, loadedAt;
    private JSONObject upcoming;
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            paint();
            if (System.currentTimeMillis() - loadedAt > RELOAD_MS) load();
            h.postDelayed(this, Dock.toNextMinute(System.currentTimeMillis()));
        }
    };
    private final BroadcastReceiver battery = new BroadcastReceiver() {
        @Override public void onReceive(Context c, Intent i) { power(i); }
    };

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        auto = getIntent().getBooleanExtra("auto", false);
        demo = Demo.ON && getIntent().getBooleanExtra("demo", false);
        if (demo) {
            upcoming = Demo.INSTANCE.upcoming();
            loadedAt = System.currentTimeMillis();
            demoHour = getIntent().getIntExtra("hour", -1);
        }
        overLockScreen();
        build();
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(ID_BEDSIDE);
        signal(true);
    }

    @Override protected void onDestroy() {
        if (isFinishing()) signal(false);
        super.onDestroy();
    }

    /** (0.9.0) Tell your computer bedside mode opened or closed (a flag, no sensor; phone.bedside.signal there).
     *  Quiet: an older computer, or none reachable, just doesn't hear it. */
    private void signal(boolean on) {
        if (demo || !Prefs.paired(this)) return;
        final Context c = getApplicationContext();
        new Thread(() -> Chat.signal(c, "bedside", on)).start();
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        if (i.getBooleanExtra("auto", false)) auto = true;
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(ID_BEDSIDE);
    }

    @Override protected void onResume() {
        super.onResume();
        visible = true;
        immersive();
        power(registerReceiver(battery, new IntentFilter(Intent.ACTION_BATTERY_CHANGED)));
        h.removeCallbacks(tick);
        h.post(tick);
        if (System.currentTimeMillis() - loadedAt > 30_000) load();
    }

    @Override protected void onPause() {
        visible = false;
        try { unregisterReceiver(battery); } catch (Exception ignored) { }
        h.removeCallbacksAndMessages(null);
        super.onPause();
    }

    @Override public void onWindowFocusChanged(boolean has) {
        super.onWindowFocusChanged(has);
        if (has) immersive();
    }

    @SuppressWarnings("deprecation")
    private void overLockScreen() {
        if (SDK >= 27) {
            setShowWhenLocked(true);
            if (auto) setTurnScreenOn(true);
        } else {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED | (auto ? WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON : 0));
        }
    }

    @SuppressWarnings("deprecation")
    private void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    /** Charging or not: keep the screen on while it charges (if chosen); opened by itself, close when unplugged. */
    private void power(Intent i) {
        boolean was = charging;
        charging = i != null && i.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0;
        if (charging && Prefs.bedsideKeepOn(this)) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (auto && was && !charging) finish();
    }

    // ---------- the screen ----------
    private void build() {
        st = new BedsideState();
        BedsideScreen.show(this, st);
        paint();
    }

    /** A tap on the screen: brighter for 15 s. */
    void tapped() {
        brightUntil = System.currentTimeMillis() + BRIGHT_MS;
        paint();
        h.postDelayed(this::paint, BRIGHT_MS + 100);
    }

    /** "N things waiting for you": Inbox on the main screen, once unlocked. */
    void openInbox() {
        unlocked(new Intent(this, MainActivity.class).putExtra("tab", "inbox").putExtra("demo", demo));
    }

    void openChat() {
        if (demo) { st.setStatus("Demo: the chat needs a paired phone."); return; }
        unlocked(new Intent(this, ChatActivity.class));
    }

    /** The clock, colours and brightness for this minute, and what's coming. */
    private void paint() {
        if (st == null) return;
        long now = System.currentTimeMillis();
        Calendar c = Calendar.getInstance();
        if (demoHour >= 0 && demoHour < 24) c.set(Calendar.HOUR_OF_DAY, demoHour);
        int hour = c.get(Calendar.HOUR_OF_DAY);
        boolean h24 = DateFormat.is24HourFormat(this);
        st.setClock(DateFormat.format(h24 ? "HH:mm" : "h:mm", c).toString());
        st.setDate(DateFormat.format("EEEE d MMMM", c).toString());
        int ink = Dock.ink(hour), dim = Dock.dim(hour);
        st.setInk(ink);
        st.setDim(dim);
        st.setNight(Dock.warm(hour)); // the Talk pill and the cards turn warm when day turns to night
        st.setTalk("Talk to " + Prefs.assistant(this));

        WindowManager.LayoutParams lp = getWindow().getAttributes();
        float want = Dock.brightness(hour, now < brightUntil);
        if (lp.screenBrightness != want) {
            lp.screenBrightness = want;
            getWindow().setAttributes(lp);
        }
        showUpcoming(now, h24);
    }

    private void showUpcoming(long now, boolean h24) {
        List<String> next = new ArrayList<>();
        TimeZone tz = TimeZone.getDefault();
        long nowSec = now / 1000, wake = 0;
        JSONArray calls = upcoming == null ? null : upcoming.optJSONArray("calls");
        KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        boolean hide = km != null && km.isKeyguardLocked() && km.isKeyguardSecure();
        int shown = 0;
        for (int i = 0; calls != null && i < calls.length(); i++) {
            JSONObject it = calls.optJSONObject(i);
            if (it == null || it.optLong("at") < nowSec - 60) continue;
            if (it.optBoolean("alarm")) { if (wake == 0) wake = it.optLong("at"); continue; }
            if (shown >= 3) continue;
            String what = hide ? "a call (unlock to see)" : it.optString("reason", "a call");
            next.add(Dock.when(it.optLong("at"), now, h24, tz) + "   " + what);
            shown++;
        }
        long phone = 0;
        try {
            AlarmManager am = (AlarmManager) getSystemService(ALARM_SERVICE);
            AlarmManager.AlarmClockInfo a = am == null ? null : am.getNextAlarmClock();
            if (a != null) phone = a.getTriggerTime() / 1000;
        } catch (Exception ignored) { }
        st.setCalls(next);
        showToday(hide);
        st.setAlarm(Dock.alarmLine(wake, phone, upcoming != null, now, h24, tz));
        st.setWaiting(Dock.waitingLine(upcoming == null ? 0 : upcoming.optInt("waiting", 0))); // none: hidden
        if (upcoming != null && "offline".equals(upcoming.optString("computer")) && !busy) st.setStatus("Your computer is off: calls still work.");
    }

    /** (0.9.0, Prefs.bedsideToday) Today's reminders and what's due within a day, from the Today list your computer
     *  sealed for this phone (Today.java), and whether your assistant is asleep. Locked with a secure lock: counts
     *  only, as for the calls. */
    private void showToday(boolean hide) {
        if (!Prefs.bedsideToday(this) || demo) { st.setToday(new ArrayList<>()); st.setAsleep(""); return; }
        JSONObject list = Today.load(this).optJSONObject("list");
        List<String> rows = new ArrayList<>();
        int n = 0;
        JSONArray rem = list == null ? null : list.optJSONArray("reminders");
        for (int i = 0; rem != null && i < rem.length(); i++) {
            JSONObject r = rem.optJSONObject(i);
            if (r == null) continue;
            n++;
            if (rows.size() < 3) rows.add(r.optString("when") + "   " + r.optString("what"));
        }
        JSONArray due = list == null ? null : list.optJSONArray("due");
        int dues = 0;
        for (int i = 0; due != null && i < due.length(); i++) {
            JSONObject d = due.optJSONObject(i);
            if (d == null || !Dock.withinDay(d.optString("due"), System.currentTimeMillis())) continue;
            n++;
            if (dues++ < 2) rows.add("due " + d.optString("when") + "   " + d.optString("title"));
        }
        if (hide && n > 0) { rows.clear(); rows.add(n + (n == 1 ? " reminder or deadline" : " reminders and deadlines") + " (unlock to see)"); }
        st.setToday(rows);
        st.setAsleep(list != null && list.optBoolean("asleep") ? Prefs.assistant(this) + " is asleep" : "");
    }

    /** What's coming, from the call line (off the main thread). */
    private void load() {
        loadedAt = System.currentTimeMillis();
        if (demo) return; // the made-up calls stay
        if (!Prefs.paired(this)) { st.setStatus("Pair this phone first (the app's main screen)."); return; }
        new Thread(() -> {
            final JSONObject j = Line.upcoming(this);
            h.post(() -> {
                if (j != null) upcoming = j;
                else if (upcoming == null) st.setStatus("Couldn't reach your call line just now.");
                if (j != null && !busy) st.setStatus("");
                paint();
            });
        }).start();
    }

    // ---------- talking ----------
    /** The big button: a call with Kurooto, on the app's own call screen (it works over the lock screen). */
    void talk() {
        if (demo) { st.setStatus("Demo: there's no call line to call."); return; }
        if (!Prefs.paired(this)) { st.setStatus("Pair this phone first (the app's main screen)."); return; }
        st.setTalkEnabled(false);
        busy = true;
        st.setStatus("Calling…");
        new Thread(() -> {
            final String link = Line.callLink(this);
            h.post(() -> {
                st.setTalkEnabled(true);
                busy = false;
                if (link == null) { st.setStatus("Couldn't reach your call line. Is this phone online?"); return; }
                st.setStatus("");
                startActivity(new Intent(this, CallActivity.class).putExtra("url", link));
            });
        }).start();
    }

    /** Chat and the main screen need the phone unlocked: ask for that first (Android 8+), then open it. */
    private void unlocked(final Intent i) {
        KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        if (SDK >= 26 && km != null && km.isKeyguardLocked()) {
            km.requestDismissKeyguard(this, new KeyguardManager.KeyguardDismissCallback() {
                @Override public void onDismissSucceeded() { startActivity(i); }
            });
        } else {
            startActivity(i); // Android 6 and 7: the phone asks you to unlock before it shows
        }
    }

    // ---------- opening by itself while charging ----------
    static boolean charging(Context c) {
        Intent i = c.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        return i != null && i.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0;
    }

    static boolean inHours(Context c) {
        Calendar now = Calendar.getInstance();
        return Dock.within(now.get(Calendar.HOUR_OF_DAY) * 60 + now.get(Calendar.MINUTE),
                Dock.minutes(Prefs.bedsideFrom(c)), Dock.minutes(Prefs.bedsideTo(c)));
    }

    /** Registered by ListenService while it runs: plugging in during the chosen hours, or those hours starting while
     *  it charges, opens bedside mode (once; close it and it stays closed until the next time). */
    static final class Watcher extends BroadcastReceiver {
        private boolean wasIn;

        @Override public void onReceive(Context c, Intent i) {
            boolean in = inHours(c);
            boolean open = Prefs.bedsideAuto(c) && Prefs.paired(c) && !visible && in
                    && (Intent.ACTION_POWER_CONNECTED.equals(i.getAction()) || (!wasIn && charging(c)));
            wasIn = in;
            if (open) open(c);
        }
    }

    static BroadcastReceiver watch(Context c) {
        Watcher w = new Watcher();
        w.wasIn = inHours(c); // a restart in the middle of the hours doesn't open it
        IntentFilter f = new IntentFilter(Intent.ACTION_POWER_CONNECTED);
        f.addAction(Intent.ACTION_TIME_TICK);
        try {
            if (SDK >= 33) c.registerReceiver(w, f, Context.RECEIVER_NOT_EXPORTED); else c.registerReceiver(w, f);
        } catch (Exception e) {
            return null;
        }
        return w;
    }

    /** Android 9 and older: straight to the screen. Android 10+ won't let a service open a screen, so a full-screen
     *  notification does it (it opens by itself with the screen off; with the phone in use it's a tap away). */
    static void open(Context c) {
        Intent i = new Intent(c, BedsideActivity.class).putExtra("auto", true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (SDK < 29) {
            try { c.startActivity(i); } catch (Exception ignored) { }
            return;
        }
        NotificationManager nm = (NotificationManager) c.getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) return;
        try {
            NotificationChannel ch = new NotificationChannel(CH_BEDSIDE, "Bedside mode", NotificationManager.IMPORTANCE_HIGH);
            ch.setSound(null, null);
            ch.enableVibration(false);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        } catch (Exception ignored) { }
        PendingIntent pi = PendingIntent.getActivity(c, 9, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = ListenService.builder(c, CH_BEDSIDE)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("Bedside mode")
                .setContentText("Charging: tap to open the bedside clock")
                .setCategory(Notification.CATEGORY_REMINDER)
                .setFullScreenIntent(pi, true)
                .setContentIntent(pi)
                .setAutoCancel(true)
                .setTimeoutAfter(10 * 60_000);
        try { nm.notify(ID_BEDSIDE, b.build()); } catch (Exception ignored) { }
    }

    // ---------- its settings, on the main screen's Phone tab ----------
    /** The "Bedside mode" section: open it, open by itself while charging (and when), keep the screen on. */
    /** "Open by itself while charging" on the main screen's Phone tab: pick the hours, or turn it off. */
    static void hours(final Activity a, final Runnable rebuild) {
        if (!Prefs.bedsideAuto(a)) { pick(a, rebuild); return; }
        new AlertDialog.Builder(a).setTitle("Open by itself while charging")
                .setItems(new String[]{"Change the hours", "Turn it off"}, (d, which) -> {
                    if (which == 0) pick(a, rebuild);
                    else { Prefs.setBedside(a, false, Prefs.bedsideFrom(a), Prefs.bedsideTo(a)); rebuild.run(); }
                }).show();
    }

    private static void pick(final Activity a, final Runnable rebuild) {
        final boolean h24 = DateFormat.is24HourFormat(a);
        final int from = Math.max(0, Dock.minutes(Prefs.bedsideFrom(a))), to = Math.max(0, Dock.minutes(Prefs.bedsideTo(a)));
        TimePickerDialog first = new TimePickerDialog(a, (v1, h1, m1) -> {
            TimePickerDialog second = new TimePickerDialog(a, (v2, h2, m2) -> {
                Prefs.setBedside(a, true, Dock.hm(h1 * 60 + m1), Dock.hm(h2 * 60 + m2));
                rebuild.run();
            }, to / 60, to % 60, h24);
            second.setTitle("Until");
            second.show();
        }, from / 60, from % 60, h24);
        first.setTitle("From (while charging)");
        first.show();
    }
}
