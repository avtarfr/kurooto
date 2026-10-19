package io.github.avtarfr.kurooto;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
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
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Pairing (first run), then: call Kurooto, what's waiting for you (questions, approvals, messages), ringtones, a
 *  checklist of what the phone must allow, and updates. */
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
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#14111a"));
        box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(48, 72, 48, 48);
        sv.addView(box);
        if (Prefs.paired(this)) paired(); else unpaired();
        setContentView(sv);
    }

    // ---------- first run ----------
    private void unpaired() {
        box.addView(label("Kurooto", 28, true));
        box.addView(label("Pair this phone with Kurooto on your computer, so it can call you and you can call it.", 16, false));
        box.addView(label("On your computer: open Kurooto's dashboard → Phone → Pair a phone. Scan the QR code with this phone's camera "
                + "and tap Pair the app. Or send /phone to your Telegram bot and open the link here.", 15, false));
        box.addView(label("Or paste the pairing link", 20, true));
        final EditText link = new EditText(this);
        link.setHint("https://…/pair#c=…");
        link.setTextColor(Color.parseColor("#ece8f2"));
        link.setHintTextColor(Color.parseColor("#9a93a8"));
        link.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        box.addView(link);
        Button pair = big("Pair", "#2e9d6a");
        status = label("", 14, false);
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
        box.addView(label(name, 28, true));
        box.addView(label("Its calls ring here like phone calls (earpiece, screen off at your ear); wake-up calls ring like an alarm.", 15, false));
        Button call = big("Call " + name, "#2e9d6a");
        call.setOnClickListener(v -> requestCall());
        box.addView(call);
        status = label(getIntent().getBooleanExtra("justPaired", false) ? "Paired. You're all set." : "", 14, false);
        box.addView(status);
        waiting = new LinearLayout(this);
        waiting.setOrientation(LinearLayout.VERTICAL);
        box.addView(waiting);
        loadWaiting();

        String upd = Prefs.sp(this).getString("updateLink", "");
        if (!upd.isEmpty()) {
            Button u = big("Update available: " + Prefs.sp(this).getString("updateName", ""), "#e85d8a");
            u.setOnClickListener(v -> open(Uri.parse(upd)));
            box.addView(u);
        }

        box.addView(label("Checklist", 20, true));
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        Intent appInfo = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()));
        check("Notifications", SDK < 24 || nm.areNotificationsEnabled(),
                SDK >= 26 ? new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName()) : appInfo);
        check("Microphone", checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED, appInfo);
        if (SDK >= 34) check("Full-screen calls (ring on the lock screen)", nm.canUseFullScreenIntent(),
                new Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:" + getPackageName())));
        check("Battery: unrestricted (keeps listening)", pm.isIgnoringBatteryOptimizations(getPackageName()),
                new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + getPackageName())));
        if (Build.MANUFACTURER.toLowerCase(java.util.Locale.ROOT).matches(".*(samsung|xiaomi|redmi|poco|oppo|realme|vivo|oneplus|huawei|honor).*")) {
            box.addView(label(Build.MANUFACTURER + " phones also put apps to sleep on their own: in Settings → Battery, set Kurooto to "
                    + "\"Unrestricted\" or \"No restrictions\" and take it off any \"sleeping apps\" list, or calls may not ring.", 13, false));
        }

        box.addView(label("Ringtones", 20, true));
        Button callTone = big("Call ringtone: " + toneName(false), "#3a3150");
        callTone.setOnClickListener(v -> pickTone(false));
        box.addView(callTone);
        Button alarmTone = big("Wake-up alarm tone: " + toneName(true), "#3a3150");
        alarmTone.setOnClickListener(v -> pickTone(true));
        box.addView(alarmTone);
        box.addView(label("The alarm tone plays on the alarm stream, so wake-up calls ring even on silent.", 13, false));

        box.addView(label("This phone", 20, true));
        box.addView(label("Paired with " + Prefs.url(this) + " · app " + versionName(), 13, false));
        Button forget = big("Unpair this phone", "#3a3150");
        forget.setOnClickListener(v -> {
            Prefs.forget(this);
            stopService(new Intent(this, ListenService.class));
            build();
            status.setText("Unpaired here. Also remove it on your computer (Phone tab, or /phones on Telegram).");
        });
        box.addView(forget);
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
                into.addView(label("Waiting for you", 20, true));
                for (int i = items.length() - 1; i >= 0; i--) {
                    final JSONObject it = items.optJSONObject(i);
                    if (it == null) continue;
                    String text = Inbox.text(it);
                    Button b = big(it.optString("title", "Kurooto") + ": " + (text.length() > 80 ? text.substring(0, 79) + "…" : text), "#3a3150");
                    b.setTextSize(15);
                    b.setAllCaps(false);
                    b.getLayoutParams().height = LinearLayout.LayoutParams.WRAP_CONTENT;
                    b.setPadding(32, 24, 32, 24);
                    b.setOnClickListener(v -> startActivity(new Intent(this, AnswerActivity.class).putExtra("item", it.toString())));
                    into.addView(b);
                }
            });
        }).start();
    }

    private void check(String what, boolean ok, final Intent fix) {
        LinearLayout row = new LinearLayout(this);
        row.setPadding(0, 12, 0, 12);
        TextView t = label((ok ? "✓  " : "✗  ") + what, 15, false);
        t.setTextColor(Color.parseColor(ok ? "#4fbf8a" : "#e85d8a"));
        row.addView(t, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        if (!ok) {
            Button fixB = new Button(this);
            fixB.setText("Fix");
            fixB.setOnClickListener(v -> {
                try { startActivity(fix); }
                catch (Exception e) { startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()))); }
            });
            row.addView(fixB);
        }
        box.addView(row);
    }

    private TextView label(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(Color.parseColor(bold ? "#ece8f2" : "#9a93a8"));
        t.setPadding(0, bold ? 36 : 8, 0, 8);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Button big(String s, String color) {
        Button b = new Button(this);
        b.setText(s);
        b.setTextSize(18);
        b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.parseColor(color));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 160);
        lp.setMargins(0, 24, 0, 8);
        b.setLayoutParams(lp);
        return b;
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
                .putExtra(RingtoneManager.EXTRA_RINGTONE_TYPE, type | RingtoneManager.TYPE_NOTIFICATION)
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

    /** At most once a day: is there a newer app on Kurooto's release page? If so, show a button to get it. */
    private void checkForUpdate() {
        if (System.currentTimeMillis() - Prefs.lastUpdateCheck(this) < 24 * 3600e3) return;
        new Thread(() -> {
            Net.Reply r = Net.request("GET", UPDATES, null, null, null, 20000);
            try {
                JSONObject j = new JSONObject(r.ok() ? r.body : "{}");
                boolean newer = j.optLong("versionCode", 0) > versionCode() && j.optString("url", "").startsWith("https://");
                Prefs.setUpdate(this, newer ? j.optString("versionName") : "", newer ? j.optString("url") : "");
                if (newer) h.post(this::build);
            } catch (Exception ignored) {
                Prefs.setUpdate(this, "", "");
            }
        }).start();
    }
}
