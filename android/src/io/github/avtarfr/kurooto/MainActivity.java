package io.github.avtarfr.kurooto;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Pairing (first run), then: call Kurooto, chat with it (ChatActivity), what's waiting for you (questions,
 *  approvals, messages) and for your computer (the phone outbox), ringtones, a checklist of what the phone must
 *  allow, and updates. */
public class MainActivity extends Activity {
    static final int SDK = Build.VERSION.SDK_INT;
    static final String UPDATES = "https://avtarfr.github.io/kurooto/android.json";
    private final Handler h = new Handler(Looper.getMainLooper());
    private LinearLayout box, waiting;
    private TextView status;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        ListenService.channels(this);
        askPermissions();
        if (Prefs.paired(this)) ListenService.start(this);
        build();
    }

    @Override protected void onResume() {
        super.onResume();
        build();
        checkForUpdate();
    }

    private void askPermissions() {
        List<String> want = new ArrayList<>();
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) want.add(Manifest.permission.RECORD_AUDIO);
        if (SDK >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) want.add(Manifest.permission.POST_NOTIFICATIONS);
        if (!want.isEmpty()) requestPermissions(want.toArray(new String[0]), 1);
    }

    private void build() {
        box = Ui.page(this);
        if (Prefs.paired(this)) paired(); else unpaired();
    }

    // ---------- first run ----------
    private void unpaired() {
        box.addView(Ui.headline(this, "Kurooto"));
        box.addView(Ui.body(this, "Pair this phone with Kurooto on your computer, so it can call you and you can call it."));
        LinearLayout how = Ui.card(this);
        how.addView(Ui.dim(this, "On your computer: open Kurooto's dashboard → Phone → Pair a phone. Scan the QR code with this phone's camera "
                + "and tap Pair the app. Or send /phone to your Telegram bot and open the link here."));
        box.addView(how);
        box.addView(Ui.heading(this, "Or paste the pairing link"));
        final EditText link = Ui.field(this, "https://…/pair#c=…");
        link.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        box.addView(link);
        Button pair = Ui.large(Ui.filled(this, "Pair"));
        status = Ui.status(this);
        pair.setOnClickListener(v -> {
            final Line.Pairing p = Line.parse(link.getText().toString());
            if (p == null) { status.setText("That isn't a pairing link. It looks like https://…/pair#c=ABCD2345."); return; }
            status.setText("Pairing…");
            new Thread(() -> {
                String err = Line.claim(this, p);
                h.post(() -> {
                    if (err != null) { status.setText(err); return; }
                    ListenService.start(this);
                    build();
                });
            }).start();
        });
        box.addView(pair);
        box.addView(status);
    }

    // ---------- paired ----------
    private void paired() {
        String name = Prefs.assistant(this);
        box.addView(Ui.headline(this, name));
        box.addView(Ui.dim(this, "Its calls ring here like phone calls (earpiece, screen off at your ear); wake-up calls ring like an alarm."));
        Button call = Ui.large(Ui.filled(this, "Call " + name));
        Ui.gap(call, 16, 0);
        call.setOnClickListener(v -> requestCall());
        box.addView(call);
        Button chat = Ui.tonal(this, "Chat with " + name);
        Ui.gap(chat, 8, 0);
        chat.setOnClickListener(v -> startActivity(new Intent(this, ChatActivity.class)));
        box.addView(chat);
        TodayView.add(this, box); // the day, from your computer's last copy (0.6.0)
        JSONArray queued = Chat.waiting(Chat.load(this));
        if (queued.length() > 0) {
            StringBuilder s = new StringBuilder("Waiting for your computer (on your call line):");
            for (int i = 0; i < queued.length(); i++) s.append("\n· ").append(queued.optJSONObject(i).optString("label"));
            box.addView(Ui.dim(this, s.toString()));
        }
        status = Ui.status(this);
        if (getIntent().getBooleanExtra("justPaired", false)) { status.setText("Paired. You're all set."); Ui.ok(status); }
        box.addView(status);
        waiting = new LinearLayout(this);
        waiting.setOrientation(LinearLayout.VERTICAL);
        box.addView(waiting);
        loadWaiting();

        String upd = Prefs.sp(this).getString("updateLink", "");
        String updName = Prefs.sp(this).getString("updateName", "");
        if (!upd.isEmpty() && !versionName().equals(updName)) {
            Button u = Ui.button(this, "Update available: " + updName, Ui.color(this, R.color.k_primary_container),
                    Ui.color(this, R.color.k_on_primary_container), 0);
            u.setOnClickListener(v -> open(Uri.parse(upd)));
            box.addView(u);
        }

        box.addView(Ui.heading(this, "Checklist"));
        LinearLayout list = Ui.list(this);
        box.addView(list);
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        Intent appInfo = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()));
        check(list, "Notifications", SDK < 24 || nm.areNotificationsEnabled(),
                SDK >= 26 ? new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName()) : appInfo);
        check(list, "Microphone", checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED, appInfo);
        if (SDK >= 34) check(list, "Full-screen calls (ring on the lock screen)", nm.canUseFullScreenIntent(),
                new Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:" + getPackageName())));
        if (SDK >= 31) check(list, "Alarms at the exact time (the wake-up alarm on this phone)", Alarms.exact(this), Alarms.allowExact(this));
        check(list, "Battery: unrestricted (keeps listening)", pm.isIgnoringBatteryOptimizations(getPackageName()),
                new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + getPackageName())));
        if (Build.MANUFACTURER.toLowerCase(java.util.Locale.ROOT).matches(".*(samsung|xiaomi|redmi|poco|oppo|realme|vivo|oneplus|huawei|honor).*")) {
            box.addView(Ui.small(this, Build.MANUFACTURER + " phones also put apps to sleep on their own: in Settings → Battery, set Kurooto to "
                    + "\"Unrestricted\" or \"No restrictions\" and take it off any \"sleeping apps\" list, or calls may not ring."));
        }

        box.addView(Ui.heading(this, "Location reminders"));
        LinearLayout places = Ui.list(this);
        places.addView(Ui.item(this, "Places", Places.on(this) ? "On: " + Places.places(this).length() + " saved" : "Off",
                v -> startActivity(new Intent(this, PlacesActivity.class))));
        box.addView(places);

        box.addView(Ui.heading(this, "Ringtones"));
        LinearLayout tones = Ui.list(this);
        tones.addView(Ui.item(this, "Call ringtone", toneName(false), v -> pickTone(false)));
        tones.addView(Ui.item(this, "Wake-up alarm tone", toneName(true), v -> pickTone(true)));
        box.addView(tones);
        box.addView(Ui.small(this, "The alarm tone plays on the alarm stream, so wake-up calls ring even on silent."));

        box.addView(Ui.heading(this, "This phone"));
        LinearLayout phone = Ui.card(this);
        phone.addView(Ui.body(this, "Paired with " + Prefs.url(this)));
        phone.addView(Ui.dim(this, "App " + versionName()));
        int bad = Ui.color(this, R.color.k_bad);
        Button forget = Ui.button(this, "Unpair this phone", 0, bad, bad);
        phone.addView(forget);
        box.addView(phone);
        forget.setOnClickListener(v -> {
            Prefs.forget(this);
            stopService(new Intent(this, ListenService.class));
            build();
            status.setText("Unpaired here. Also remove it on your computer (the dashboard's Phone tab).");
        });
    }

    /** Open questions, approvals and messages, newest first; tap one to answer it. */
    private void loadWaiting() {
        final LinearLayout into = waiting;
        final String name = Prefs.assistant(this);
        new Thread(() -> {
            final JSONArray items = Line.waiting(this);
            h.post(() -> {
                if (into != waiting) return;
                if (!name.equals(Prefs.assistant(this))) { build(); return; } // renamed on the computer
                if (items == null || items.length() == 0) return;
                into.addView(Ui.heading(this, "Waiting for you"));
                for (int i = items.length() - 1; i >= 0; i--) {
                    final JSONObject it = items.optJSONObject(i);
                    if (it == null) continue;
                    if (Places.adopt(this, it)) continue; // a place reminder the notification missed
                    if (Cards.is(it)) { into.addView(Cards.view(this, it, this::build)); continue; } // check-in, quiz: answered here
                    LinearLayout card = Ui.tapCard(this, v -> startActivity(new Intent(this, AnswerActivity.class).putExtra("item", it.toString())));
                    card.addView(Ui.text(this, it.optString("title", "Kurooto"), 14, true, Ui.color(this, R.color.k_primary)));
                    card.addView(Ui.lines(Ui.body(this, Inbox.text(it)), 3));
                    into.addView(card);
                }
                if (into.getChildCount() == 1) into.removeAllViews(); // only place reminders: nothing to show
            });
        }).start();
    }

    /** One checklist row: a tick or a warning, what it is, and Fix (to the setting) when it isn't done. */
    private void check(LinearLayout into, String what, boolean ok, final Intent fix) {
        LinearLayout row = Ui.row(this);
        row.setMinimumHeight(Ui.dp(this, 56));
        row.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 8), Ui.dp(this, 4));
        row.addView(Ui.icon(this, ok ? R.drawable.ic_ok : R.drawable.ic_fix, Ui.color(this, ok ? R.color.k_ok : R.color.k_bad)),
                new LinearLayout.LayoutParams(Ui.dp(this, 24), Ui.dp(this, 24)));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        lp.setMargins(Ui.dp(this, 16), 0, Ui.dp(this, 8), 0);
        row.addView(Ui.text(this, what, 16, false, Ui.color(this, R.color.k_fg)), lp);
        if (!ok) {
            Button fixB = Ui.flat(this, "Fix");
            fixB.setOnClickListener(v -> {
                try { startActivity(fix); }
                catch (Exception e) { startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()))); }
            });
            row.addView(fixB, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        }
        into.addView(row);
    }

    private void open(Uri u) {
        try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
    }

    private String toneName(boolean alarm) {
        String u = Prefs.tone(this, alarm);
        if (u.isEmpty()) return "phone default";
        try {
            android.media.Ringtone r = RingtoneManager.getRingtone(this, Uri.parse(u));
            return r == null ? "custom" : r.getTitle(this);
        } catch (Exception e) {
            return "custom";
        }
    }

    private void pickTone(boolean alarm) {
        int type = alarm ? RingtoneManager.TYPE_ALARM : RingtoneManager.TYPE_RINGTONE;
        Intent i = new Intent(RingtoneManager.ACTION_RINGTONE_PICKER)
                .putExtra(RingtoneManager.EXTRA_RINGTONE_TYPE, type)
                .putExtra(RingtoneManager.EXTRA_RINGTONE_TITLE, alarm ? "Wake-up alarm tone" : "Call ringtone")
                .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_SILENT, false)
                .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_DEFAULT, true);
        String cur = Prefs.tone(this, alarm);
        if (!cur.isEmpty()) i.putExtra(RingtoneManager.EXTRA_RINGTONE_EXISTING_URI, Uri.parse(cur));
        startActivityForResult(i, alarm ? 11 : 10);
    }

    @SuppressWarnings("deprecation")
    @Override protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        if ((code == 10 || code == 11) && result == RESULT_OK && data != null) {
            Uri u = data.getParcelableExtra(RingtoneManager.EXTRA_RINGTONE_PICKED_URI);
            Prefs.setTone(this, code == 11, u == null ? "" : u.toString());
            build();
        }
    }

    /** A call line link (works with your computer on or off), then the call. */
    private void requestCall() {
        status.setText("Opening a call line…");
        new Thread(() -> {
            String link = Line.callLink(this);
            h.post(() -> {
                if (link == null) { status.setText("Couldn't reach your call line. Is this phone online?"); return; }
                status.setText("");
                startActivity(new Intent(this, CallActivity.class).putExtra("url", link));
            });
        }).start();
    }

    // ---------- updates ----------
    @SuppressWarnings("deprecation")
    private long versionCode() {
        try {
            PackageInfo p = getPackageManager().getPackageInfo(getPackageName(), 0);
            return SDK >= 28 ? p.getLongVersionCode() : p.versionCode;
        } catch (Exception e) {
            return 0;
        }
    }

    private String versionName() {
        try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception e) { return "?"; }
    }

    /** Check if there is a newer app on Kurooto's release page. */
    private void checkForUpdate() {
        if (System.currentTimeMillis() - Prefs.lastUpdateCheck(this) < 120_000) return;
        new Thread(() -> {
            Net.Reply r = Net.request("GET", UPDATES, null, null, null, 20000);
            try {
                JSONObject j = new JSONObject(r.ok() ? r.body : "{}");
                boolean newer = j.optLong("versionCode", 0) > versionCode() && j.optString("url", "").startsWith("https://");
                Prefs.setUpdate(this, newer ? j.optString("versionName") : "", newer ? j.optString("url") : "");
                h.post(this::build);
            } catch (Exception ignored) {
                Prefs.setUpdate(this, "", "");
            }
        }).start();
    }
}
