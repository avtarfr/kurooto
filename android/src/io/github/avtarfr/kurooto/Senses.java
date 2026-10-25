package io.github.avtarfr.kurooto;

import android.Manifest;
import android.app.Activity;
import android.app.AlarmManager;
import android.app.AppOpsManager;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.usage.UsageStats;
import android.app.usage.UsageStatsManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.Settings;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.UUID;

/** The phone's senses (0.8.0): each one off until you switch it on in the Phone tab. Every 15 minutes (Android batches
 *  the alarm, so it's cheap) it takes one reading of each sensor that's on, keeps it as a 5-minute bin on this phone, and
 *  sends what it holds, sealed with this phone's key, to your computer through the call line (the line can't read it; if
 *  your computer is off it waits there). Motion is worked out here from steps and the accelerometer's spread; the
 *  accelerometer's readings never leave the phone. The microphone isn't a sense. Rules: SensesRules. */
public class Senses extends BroadcastReceiver {
    static final String ACTION = "io.github.avtarfr.kurooto.SENSES";
    static final long EVERY_MS = 15 * 60_000L;
    static final int HOLD_MAX = 300;
    private static final String P = "senses";
    private static boolean unlockReceiverOn = false;

    @Override public void onReceive(Context c, Intent i) {
        final PendingResult pr = goAsync();
        new Thread(() -> {
            try { sample(c.getApplicationContext()); } catch (Exception ignored) { } finally { pr.finish(); }
        }).start();
    }

    // ------------------------------------------------------------------------------------------------ switches
    static SharedPreferences sp(Context c) { return c.getSharedPreferences(P, Context.MODE_PRIVATE); }
    static boolean on(Context c, String sensor) { return sp(c).getBoolean("on." + sensor, false); }
    static boolean any(Context c) {
        for (String s : SensesRules.SENSORS) if (on(c, s)) return true;
        return false;
    }

    static String label(String s) {
        switch (s) {
            case "screen": return "Screen on and unlocks";
            case "charging": return "Charging";
            case "motion": return "Moving (still, walking, in a vehicle)";
            case "steps": return "Steps a day";
            case "light": return "Room light (dark, dim, bright)";
            case "places": return "Arriving at and leaving your saved places";
            case "headphones": return "Headphones connected";
            case "dnd": return "Do Not Disturb";
            case "alarm": return "Your next alarm";
            case "wifi": return "Which Wi-Fi (a code, never the name)";
            default: return "Total screen time a day";
        }
    }

    static String note(String s) {
        switch (s) {
            case "motion": case "steps": return "Needs the physical activity permission.";
            case "wifi": return "Android asks for location to read the Wi-Fi name; only a code made on this phone is sent.";
            case "usage": return "Needs Usage access in Android's settings; only the day's total, never per app.";
            default: return "";
        }
    }

    /** Switch one on or off. Turning on may ask for the permission it needs; it takes effect once that's allowed. */
    static void set(Activity a, String sensor, boolean value) {
        sp(a).edit().putBoolean("on." + sensor, value).apply();
        if (value) {
            if ((sensor.equals("motion") || sensor.equals("steps")) && Build.VERSION.SDK_INT >= 29
                    && a.checkSelfPermission(Manifest.permission.ACTIVITY_RECOGNITION) != PackageManager.PERMISSION_GRANTED) {
                a.requestPermissions(new String[]{Manifest.permission.ACTIVITY_RECOGNITION}, 71);
            }
            if (sensor.equals("wifi") && Build.VERSION.SDK_INT >= 23
                    && a.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
                a.requestPermissions(new String[]{Manifest.permission.ACCESS_COARSE_LOCATION}, 72);
            }
            if (sensor.equals("usage") && !usageAllowed(a)) {
                try { a.startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)); } catch (Exception ignored) { }
            }
        } else {
            clearHeld(a, sensor);
        }
        schedule(a);
        if (sensor.equals("screen")) watchUnlocks(a);
    }

    static boolean usageAllowed(Context c) {
        try {
            AppOpsManager ops = (AppOpsManager) c.getSystemService(Context.APP_OPS_SERVICE);
            int m = ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, android.os.Process.myUid(), c.getPackageName());
            return m == AppOpsManager.MODE_ALLOWED;
        } catch (Exception e) {
            return false;
        }
    }

    // ------------------------------------------------------------------------------------------------ schedule
    /** Set (or cancel) the repeating alarm; call at app start, after boot and whenever a switch changes. */
    static void schedule(Context c) {
        try {
            AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
            PendingIntent pi = PendingIntent.getBroadcast(c, 710, new Intent(c, Senses.class).setAction(ACTION),
                    PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0));
            if (!Prefs.paired(c) || !any(c)) { am.cancel(pi); return; }
            am.setInexactRepeating(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + 60_000L, EVERY_MS, pi);
        } catch (Exception ignored) { }
    }

    /** Unlocks are counted by a receiver that lives while the app's process does (Android won't start one for us). */
    static synchronized void watchUnlocks(Context c) {
        if (unlockReceiverOn || !on(c, "screen")) return;
        unlockReceiverOn = true;
        final Context app = c.getApplicationContext();
        app.registerReceiver(new BroadcastReceiver() {
            @Override public void onReceive(Context x, Intent i) {
                if (Intent.ACTION_USER_PRESENT.equals(i.getAction())) sp(x).edit().putInt("unlocks", sp(x).getInt("unlocks", 0) + 1).apply();
            }
        }, new IntentFilter(Intent.ACTION_USER_PRESENT));
    }

    // ------------------------------------------------------------------------------------------------ readings
    static void sample(Context c) {
        if (!Prefs.paired(c) || !any(c)) return;
        long now = System.currentTimeMillis();
        List<String> held = held(c);
        try {
            if (on(c, "screen")) {
                PowerManager pm = (PowerManager) c.getSystemService(Context.POWER_SERVICE);
                int unlocks = sp(c).getInt("unlocks", 0);
                sp(c).edit().putInt("unlocks", 0).apply();
                held = SensesRules.keep(held, SensesRules.bin("screen", now, new String[]{"unlocks", "on_min"},
                        new Object[]{unlocks, pm.isInteractive() ? 15 : 0}), HOLD_MAX);
            }
            if (on(c, "charging")) {
                Intent b = c.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
                int st = b == null ? 0 : b.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
                held = SensesRules.keep(held, SensesRules.bin("charging", now, new String[]{"on"}, new Object[]{st != 0 ? 1 : 0}), HOLD_MAX);
            }
            if (on(c, "steps") || on(c, "motion") || on(c, "light")) held = motionLightSteps(c, now, held);
            if (on(c, "headphones")) {
                AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
                boolean any = false;
                if (Build.VERSION.SDK_INT >= 23) {
                    for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
                        int t = d.getType();
                        if (t == AudioDeviceInfo.TYPE_WIRED_HEADPHONES || t == AudioDeviceInfo.TYPE_WIRED_HEADSET
                                || t == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP || t == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) any = true;
                    }
                }
                held = SensesRules.keep(held, SensesRules.bin("headphones", now, new String[]{"on"}, new Object[]{any ? 1 : 0}), HOLD_MAX);
            }
            if (on(c, "dnd") && Build.VERSION.SDK_INT >= 23) {
                NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
                boolean dnd = nm.getCurrentInterruptionFilter() > NotificationManager.INTERRUPTION_FILTER_ALL;
                held = SensesRules.keep(held, SensesRules.bin("dnd", now, new String[]{"on"}, new Object[]{dnd ? 1 : 0}), HOLD_MAX);
            }
            if (on(c, "alarm")) {
                AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
                AlarmManager.AlarmClockInfo next = am.getNextAlarmClock();
                held = SensesRules.keep(held, SensesRules.bin("alarm", now, new String[]{"at"}, new Object[]{next == null ? 0 : next.getTriggerTime()}), HOLD_MAX);
            }
            if (on(c, "wifi") && Build.VERSION.SDK_INT >= 23
                    && c.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                WifiManager wm = (WifiManager) c.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                WifiInfo wi = wm == null ? null : wm.getConnectionInfo();
                String id = wi == null ? "" : SensesRules.wifiId(salt(c), wi.getSSID() == null ? "" : wi.getSSID().replace("\"", ""));
                if (!id.isEmpty()) held = SensesRules.keep(held, SensesRules.bin("wifi", now, new String[]{"id"}, new Object[]{id}), HOLD_MAX);
            }
            if (on(c, "usage") && usageAllowed(c)) {
                Calendar d = Calendar.getInstance();
                d.set(Calendar.HOUR_OF_DAY, 0); d.set(Calendar.MINUTE, 0); d.set(Calendar.SECOND, 0); d.set(Calendar.MILLISECOND, 0);
                UsageStatsManager um = (UsageStatsManager) c.getSystemService(Context.USAGE_STATS_SERVICE);
                long total = 0;
                for (UsageStats u : um.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, d.getTimeInMillis(), now)) total += u.getTotalTimeInForeground();
                held = SensesRules.keep(held, SensesRules.bin("usage", now, new String[]{"min"}, new Object[]{total / 60_000L}), HOLD_MAX);
            }
        } catch (Exception ignored) { }
        saveHeld(c, held);
        send(c);
    }

    /** Steps (the day's counter), motion (steps since the last reading plus the accelerometer's spread over two seconds)
     *  and light (one reading), taken together with one short listener. The raw readings stay here. */
    private static List<String> motionLightSteps(Context c, long now, List<String> held) {
        final SensorManager sm = (SensorManager) c.getSystemService(Context.SENSOR_SERVICE);
        if (sm == null) return held;
        final double[] mags = new double[200];
        final int[] n = {0};
        final float[] steps = {-1};
        final float[] lux = {-1};
        SensorEventListener l = new SensorEventListener() {
            @Override public void onSensorChanged(SensorEvent e) {
                switch (e.sensor.getType()) {
                    case Sensor.TYPE_ACCELEROMETER:
                        if (n[0] < mags.length) mags[n[0]++] = Math.sqrt(e.values[0] * e.values[0] + e.values[1] * e.values[1] + e.values[2] * e.values[2]);
                        break;
                    case Sensor.TYPE_STEP_COUNTER: steps[0] = e.values[0]; break;
                    case Sensor.TYPE_LIGHT: lux[0] = e.values[0]; break;
                    default: break;
                }
            }
            @Override public void onAccuracyChanged(Sensor s, int a) { }
        };
        boolean walk = on(c, "steps") || on(c, "motion");
        if (walk) {
            Sensor acc = sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER), st = sm.getDefaultSensor(Sensor.TYPE_STEP_COUNTER);
            if (acc != null && on(c, "motion")) sm.registerListener(l, acc, SensorManager.SENSOR_DELAY_GAME);
            if (st != null) sm.registerListener(l, st, SensorManager.SENSOR_DELAY_NORMAL);
        }
        if (on(c, "light")) { Sensor li = sm.getDefaultSensor(Sensor.TYPE_LIGHT); if (li != null) sm.registerListener(l, li, SensorManager.SENSOR_DELAY_NORMAL); }
        try { Thread.sleep(2500); } catch (InterruptedException ignored) { }
        sm.unregisterListener(l);
        if (steps[0] >= 0) {
            SharedPreferences s = sp(c);
            long day = now / 86_400_000L;
            float base = s.getLong("stepsDay", -1) == day ? s.getFloat("stepsBase", steps[0]) : steps[0];
            float last = s.getFloat("stepsLast", steps[0]);
            int since = (int) Math.max(0, steps[0] - last);
            s.edit().putLong("stepsDay", day).putFloat("stepsBase", base).putFloat("stepsLast", steps[0]).apply();
            if (on(c, "steps")) held = SensesRules.keep(held, SensesRules.bin("steps", now, new String[]{"total"}, new Object[]{(int) (steps[0] - base)}), HOLD_MAX);
            if (on(c, "motion")) {
                double[] w = java.util.Arrays.copyOf(mags, n[0]);
                held = SensesRules.keep(held, SensesRules.bin("motion", now, new String[]{"state", "min"},
                        new Object[]{SensesRules.motion(since, SensesRules.spread(w)), 15}), HOLD_MAX);
            }
        }
        if (lux[0] >= 0 && on(c, "light")) held = SensesRules.keep(held, SensesRules.bin("light", now, new String[]{"band"}, new Object[]{SensesRules.light(lux[0])}), HOLD_MAX);
        return held;
    }

    /** Arriving at or leaving a saved place (Places calls this): the label the computer already knows. */
    static void place(Context c, String name, boolean arrive) {
        if (!on(c, "places")) return;
        List<String> held = held(c);
        held = SensesRules.keep(held, SensesRules.bin("places", System.currentTimeMillis(), new String[]{"event", "label"}, new Object[]{arrive ? "arrive" : "leave", name}), HOLD_MAX);
        saveHeld(c, held);
        send(c);
    }

    // ------------------------------------------------------------------------------------------------ held and sent
    static String salt(Context c) {
        String s = sp(c).getString("salt", "");
        if (s.isEmpty()) { s = UUID.randomUUID().toString(); sp(c).edit().putString("salt", s).apply(); }
        return s;
    }

    static synchronized List<String> held(Context c) {
        List<String> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(sp(c).getString("held", "[]"));
            for (int i = 0; i < a.length(); i++) out.add(a.getString(i));
        } catch (Exception ignored) { }
        return out;
    }

    static synchronized void saveHeld(Context c, List<String> held) { sp(c).edit().putString("held", new JSONArray(held).toString()).apply(); }

    static synchronized void clearHeld(Context c, String sensor) {
        List<String> keep = new ArrayList<>();
        for (String b : held(c)) if (!b.startsWith("{\"s\":\"" + sensor + "\"")) keep.add(b);
        saveHeld(c, keep);
    }

    /** Send what's held, 40 bins at a time; kept for next time if the line can't be reached. When your computer is off the
     *  line keeps one sealed batch for it, and nothing more is sent for 12 hours (what waits stays here, up to HOLD_MAX),
     *  so the senses never crowd the line's room for chat and answers. Call off the main thread. */
    static synchronized void send(Context c) {
        List<String> held = held(c);
        if (held.isEmpty()) return;
        long now = System.currentTimeMillis();
        if (now - sp(c).getLong("queuedAt", 0) < 12 * 3_600_000L) return;
        try {
            while (!held.isEmpty()) {
                int n = Math.min(40, held.size());
                JSONArray bins = new JSONArray();
                for (String b : held.subList(0, n)) bins.put(new JSONObject(b));
                int r = Chat.sendSenses(c, bins);
                if (r == 0) break;
                held = new ArrayList<>(held.subList(n, held.size()));
                if (r == 2) { sp(c).edit().putLong("queuedAt", now).apply(); break; }
            }
        } catch (Exception ignored) { }
        saveHeld(c, held);
    }
}
