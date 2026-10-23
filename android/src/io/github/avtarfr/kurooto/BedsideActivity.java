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
import android.graphics.Typeface;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.format.DateFormat;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Calendar;
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
 */
public class BedsideActivity extends Activity {
    static final int SDK = Build.VERSION.SDK_INT;
    static final String CH_BEDSIDE = "bedside";
    static final int ID_BEDSIDE = 9;
    static final long RELOAD_MS = 5 * 60_000, BRIGHT_MS = 15_000;
    static volatile boolean visible;

    private final Handler h = new Handler(Looper.getMainLooper());
    private LinearLayout col, next;
    private TextView clock, date, alarm, waiting, status;
    private Button talk, chat, close;
    private boolean charging, auto;
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
        overLockScreen();
        build();
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(ID_BEDSIDE);
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
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF000000);
        root.setOnClickListener(v -> { brightUntil = System.currentTimeMillis() + BRIGHT_MS; paint(); h.postDelayed(this::paint, BRIGHT_MS + 100); });
        col = Ui.column(this);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        col.setPadding(Ui.dp(this, 24), Ui.dp(this, 24), Ui.dp(this, 24), Ui.dp(this, 24));
        root.addView(col, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        col.addView(new View(this), new LinearLayout.LayoutParams(1, 0, 1));
        float wdp = getResources().getConfiguration().screenWidthDp, hdp = getResources().getConfiguration().screenHeightDp;
        clock = centred(Math.max(56, Math.min(160, Math.min(wdp / 3.3f, hdp / 2.6f))));
        clock.setTypeface(Typeface.create("sans-serif-light", Typeface.NORMAL));
        clock.setIncludeFontPadding(false);
        col.addView(clock);
        date = centred(18);
        col.addView(date);
        alarm = centred(20);
        Ui.gap(alarm, 16, 0);
        col.addView(alarm);
        next = Ui.column(this);
        next.setGravity(Gravity.CENTER_HORIZONTAL);
        col.addView(Ui.gap(next, 12, 0));
        waiting = centred(16);
        waiting.setOnClickListener(v -> unlocked(new Intent(this, MainActivity.class)));
        col.addView(Ui.gap(waiting, 8, 0));
        col.addView(new View(this), new LinearLayout.LayoutParams(1, 0, 1));

        talk = Ui.large(Ui.button(this, "Talk to " + Prefs.assistant(this), 0, 0, 0));
        talk.setTextSize(22);
        talk.setMinHeight(Ui.dp(this, 80));
        talk.setMinimumHeight(Ui.dp(this, 80));
        talk.setOnClickListener(v -> call());
        LinearLayout.LayoutParams tl = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        tl.setMargins(0, Ui.dp(this, 16), 0, 0);
        col.addView(talk, tl);
        status = centred(14);
        col.addView(Ui.gap(status, 8, 0));
        LinearLayout row = Ui.row(this);
        row.setGravity(Gravity.CENTER);
        chat = Ui.button(this, "Chat", 0, 0, 0);
        chat.setOnClickListener(v -> unlocked(new Intent(this, ChatActivity.class)));
        close = Ui.button(this, "Close", 0, 0, 0);
        close.setOnClickListener(v -> finish());
        row.addView(chat, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        row.addView(close, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        col.addView(row);
        setContentView(root);
        paint();
    }

    private TextView centred(float sp) {
        TextView t = Ui.text(this, "", sp, false, 0xFFF2EEE8);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    /** The clock, colours and brightness for this minute, and what's coming. */
    private void paint() {
        if (clock == null) return;
        long now = System.currentTimeMillis();
        Calendar c = Calendar.getInstance();
        int hour = c.get(Calendar.HOUR_OF_DAY);
        boolean h24 = DateFormat.is24HourFormat(this);
        clock.setText(DateFormat.format(h24 ? "HH:mm" : "h:mm", c));
        date.setText(DateFormat.format("EEEE d MMMM", c));
        int ink = Dock.ink(hour), dim = Dock.dim(hour);
        clock.setTextColor(ink);
        date.setTextColor(dim);
        alarm.setTextColor(ink);
        waiting.setTextColor(dim);
        status.setTextColor(dim);
        boolean night = Dock.warm(hour);
        int fill = night ? 0xFF2A1408 : Ui.color(this, R.color.k_call_go);
        if (talk.getTag() == null || (Boolean) talk.getTag() != night) { // the pill's colour, set when day turns to night
            talk.setBackground(Ui.ripple(ink, Ui.shape(fill, 0, Ui.PILL), Ui.PILL));
            talk.setTag(night);
        }
        talk.setTextColor(night ? ink : 0xFFFFFFFF);
        talk.setText("Talk to " + Prefs.assistant(this));
        chat.setTextColor(dim);
        close.setTextColor(dim);

        WindowManager.LayoutParams lp = getWindow().getAttributes();
        float want = Dock.brightness(hour);
        if (now < brightUntil && want >= 0) want = Math.max(want, 0.3f);
        if (lp.screenBrightness != want) {
            lp.screenBrightness = want;
            getWindow().setAttributes(lp);
        }
        showUpcoming(now, h24, ink, dim);
    }

    private void showUpcoming(long now, boolean h24, int ink, int dim) {
        next.removeAllViews();
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
            TextView t = Ui.lines(Ui.text(this, Dock.when(it.optLong("at"), now, h24, tz) + "   " + what, 17, false, dim), 1);
            t.setGravity(Gravity.CENTER);
            next.addView(t);
            shown++;
        }
        long phone = 0;
        try {
            AlarmManager am = (AlarmManager) getSystemService(ALARM_SERVICE);
            AlarmManager.AlarmClockInfo a = am == null ? null : am.getNextAlarmClock();
            if (a != null) phone = a.getTriggerTime() / 1000;
        } catch (Exception ignored) { }
        if (wake > 0 && (phone == 0 || wake <= phone + 60)) alarm.setText("Wake-up call  " + Dock.when(wake, now, h24, tz));
        else if (phone > 0) alarm.setText("Alarm  " + Dock.when(phone, now, h24, tz));
        else alarm.setText(upcoming == null ? "" : "No alarm set");
        int n = upcoming == null ? 0 : upcoming.optInt("waiting", 0);
        waiting.setText(n == 0 ? "" : n == 1 ? "1 thing waiting for you" : n + " things waiting for you");
        waiting.setVisibility(n == 0 ? View.GONE : View.VISIBLE);
        if (upcoming != null && "offline".equals(upcoming.optString("computer")) && status.getTag() == null) status.setText("Your computer is off: calls still work.");
    }

    /** What's coming, from the call line (off the main thread). */
    private void load() {
        loadedAt = System.currentTimeMillis();
        if (!Prefs.paired(this)) { status.setText("Pair this phone first (the app's main screen)."); return; }
        new Thread(() -> {
            final JSONObject j = Line.upcoming(this);
            h.post(() -> {
                if (j != null) upcoming = j;
                else if (upcoming == null) status.setText("Couldn't reach your call line just now.");
                if (j != null && status.getTag() == null) status.setText("");
                paint();
            });
        }).start();
    }

    // ---------- talking ----------
    /** The big button: a call with Kurooto, on the app's own call screen (it works over the lock screen). */
    private void call() {
        if (!Prefs.paired(this)) { status.setText("Pair this phone first (the app's main screen)."); return; }
        talk.setEnabled(false);
        status.setTag("busy");
        status.setText("Calling…");
        new Thread(() -> {
            final String link = Line.callLink(this);
            h.post(() -> {
                talk.setEnabled(true);
                status.setTag(null);
                if (link == null) { status.setText("Couldn't reach your call line. Is this phone online?"); return; }
                status.setText("");
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

    // ---------- its settings, on the app's main screen ----------
    /** The "Bedside mode" section: open it, open by itself while charging (and when), keep the screen on. */
    static void settings(final Activity a, LinearLayout box, final Runnable rebuild) {
        box.addView(Ui.heading(a, "Bedside mode"));
        LinearLayout list = Ui.list(a);
        list.addView(Ui.item(a, "Open bedside mode", "A big clock, the next alarm and calls, and one button to talk. Dims at night.",
                v -> a.startActivity(new Intent(a, BedsideActivity.class))));
        list.addView(Ui.item(a, "Open by itself while charging",
                Prefs.bedsideAuto(a) ? Prefs.bedsideFrom(a) + " to " + Prefs.bedsideTo(a) : "Off", v -> hours(a, rebuild)));
        list.addView(Ui.item(a, "Keep the screen on while charging", Prefs.bedsideKeepOn(a) ? "On" : "Off", v -> {
            Prefs.setBedsideKeepOn(a, !Prefs.bedsideKeepOn(a));
            rebuild.run();
        }));
        box.addView(list);
        box.addView(Ui.small(a, "An old phone on a charger by your bed works well. Talk works with the phone locked; leave the app "
                + "listening (the checklist above) so wake-up calls ring there."));
    }

    private static void hours(final Activity a, final Runnable rebuild) {
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
