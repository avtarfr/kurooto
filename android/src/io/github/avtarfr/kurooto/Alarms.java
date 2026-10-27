package io.github.avtarfr.kurooto;

import android.annotation.TargetApi;
import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * The wake-up alarm, also set on this phone (0.6.0). Your computer sends every alarm still to ring with the Today list
 * (Today); the soonest is set with AlarmManager.setAlarmClock, so it shows in the status bar, survives Doze and rings
 * with this phone alone: no computer, no call line, no internet needed. It rings like the wake-up call (ListenService,
 * the ringing screen in CallActivity) with Stop and Snooze. Only alarms you set yourself come here; the app never sets
 * one of its own, except the snooze you tap.
 * The call from your call line and this are one alarm (AlarmPlan): whichever rings first rings, the other joins it,
 * and the first Stop, Snooze or Answer counts for both (a Stop here turns the call down, a Snooze snoozes it).
 * Android 12 and newer: exact alarms need a permission (USE_EXACT_ALARM on 13+, granted with the app; on 12 the
 * phone may ask: SCHEDULE_EXACT_ALARM). Without it the alarm is set inexactly (it can come a few minutes late in
 * deep sleep) and the app says so.
 */
final class Alarms {
    static final int SDK = Build.VERSION.SDK_INT;
    static final int CODE = 40; // the PendingIntent for the alarm that's set

    private Alarms() { }

    static boolean on(Context c) { return Prefs.sp(c).getBoolean("alarmOn", true); }

    static void setOn(Context c, boolean on) {
        Prefs.sp(c).edit().putBoolean("alarmOn", on).apply();
        schedule(c);
    }

    /** Can this phone ring at the exact minute? (Before Android 12 always.) */
    static boolean exact(Context c) {
        if (SDK < 31) return true;
        try { return am(c).canScheduleExactAlarms(); } catch (Throwable e) { return false; }
    }

    /** Where Android 12+ lets you allow exact alarms for the app (only asked for there: exact() is true before). */
    @TargetApi(31)
    static Intent allowExact(Context c) {
        return new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:" + c.getPackageName()));
    }

    /** From the Today list: {"at": [s, ...], "snooze_min", "reason"} (empty or null: no alarm set there). */
    static void update(Context c, JSONObject alarm) {
        JSONArray at = alarm == null ? null : alarm.optJSONArray("at");
        Prefs.sp(c).edit()
                .putString("alarms", at == null ? "[]" : at.toString())
                .putInt("alarmSnoozeMin", alarm == null ? 10 : Math.max(1, alarm.optInt("snooze_min", 10)))
                .putString("alarmReason", alarm == null ? "Wake-up call" : alarm.optString("reason", "Wake-up call"))
                .apply();
        schedule(c);
    }

    static long[] fromComputer(Context c) {
        try {
            JSONArray a = new JSONArray(Prefs.sp(c).getString("alarms", "[]"));
            long[] out = new long[a.length()];
            for (int i = 0; i < out.length; i++) out[i] = a.optLong(i);
            return out;
        } catch (Exception e) {
            return new long[0];
        }
    }

    static String reason(Context c) { return Prefs.sp(c).getString("alarmReason", "Wake-up call"); }

    /** The alarm set on this phone now (s), or 0. */
    static long set(Context c) { return Prefs.sp(c).getLong("alarmSet", 0); }

    /** Whether the one that's set is exact (false: set inexactly, exact alarms aren't allowed). */
    static boolean setExact(Context c) { return Prefs.sp(c).getBoolean("alarmExact", true); }

    private static AlarmManager am(Context c) { return (AlarmManager) c.getSystemService(Context.ALARM_SERVICE); }

    private static PendingIntent fire(Context c, long at) {
        Intent i = new Intent(c, ActionReceiver.class).setAction(ActionReceiver.ALARM).putExtra("at", at);
        return PendingIntent.getBroadcast(c, CODE, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    /** Set the next one (or nothing). Called whenever the list, the snooze or the switch changes, after one rang,
     *  and after the phone restarts (alarms don't survive that). */
    static synchronized void schedule(Context c) {
        long now = System.currentTimeMillis() / 1000;
        long next = Prefs.paired(c) && on(c)
                ? AlarmPlan.next(fromComputer(c), Prefs.sp(c).getLong("alarmSnooze", 0), now, Prefs.sp(c).getLong("alarmLast", 0))
                : 0;
        AlarmManager am = am(c);
        if (next == 0) {
            am.cancel(fire(c, 0));
            Prefs.sp(c).edit().putLong("alarmSet", 0).apply();
            return;
        }
        PendingIntent pi = fire(c, next);
        boolean exact = true;
        try {
            if (!exact(c)) throw new SecurityException("no exact alarms");
            // the status bar's alarm opens the Alarms pane (0.8.10)
            PendingIntent show = PendingIntent.getActivity(c, CODE + 1, new Intent(c, MainActivity.class).putExtra("tab", "alarms"), PendingIntent.FLAG_IMMUTABLE);
            am.setAlarmClock(new AlarmManager.AlarmClockInfo(next * 1000, show), pi);
        } catch (SecurityException e) { // Android 12+ without the permission: as close as it allows
            exact = false;
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next * 1000, pi);
        }
        Prefs.sp(c).edit().putLong("alarmSet", next).putBoolean("alarmExact", exact).apply();
    }

    static void cancel(Context c) {
        am(c).cancel(fire(c, 0));
        Prefs.sp(c).edit().putLong("alarmSet", 0).remove("alarms").remove("alarmSnooze").remove("alarmLast")
                .remove("alarmDone").remove("alarmCall").apply();
    }

    /** It's time (ActionReceiver): ring, unless the call for it rings or rang already; then set the next. */
    static void fired(Context c, long at) {
        Prefs.sp(c).edit().putLong("alarmLast", at).apply();
        if (Prefs.sp(c).getLong("alarmSnooze", 0) <= at) Prefs.sp(c).edit().remove("alarmSnooze").apply();
        schedule(c);
        if (!Prefs.paired(c) || !on(c)) return;
        ListenService.localAlarm(c, at);
    }

    /** Stop, Snooze or Answer on the wake-up alarm (this phone's, or the call for it). since: the ring's ("local:<s>"
     *  for this phone's own). A Snooze also sets one here, so it rings again even if nothing else can; a Stop or
     *  Snooze here answers the call for the same alarm when it comes. */
    static void replied(Context c, String since, String action, boolean alarm) {
        if (!alarm && (since == null || !since.startsWith("local:"))) return;
        long now = System.currentTimeMillis() / 1000, at = AlarmPlan.since(since);
        String act = "later".equals(action) ? "later" : "decline";
        android.content.SharedPreferences.Editor e = Prefs.sp(c).edit();
        if (at > 0) e.putString("alarmDone", at + ":" + act + ":" + now);
        if ("later".equals(act)) {
            long snooze = now + 60L * Prefs.sp(c).getInt("alarmSnoozeMin", 10);
            e.putLong("alarmSnooze", snooze);
        }
        e.apply();
        schedule(c);
    }

    /** What to do with the call for the alarm at callAt: "decline" / "later" (it was stopped or snoozed here), or ""
     *  (ring). */
    static String answered(Context c, long callAt) {
        return AlarmPlan.answered(Prefs.sp(c).getString("alarmDone", ""), callAt, System.currentTimeMillis() / 1000);
    }

    /** A call for an alarm rang (the phone's own for the same alarm then stays quiet). */
    static void callRang(Context c, long callAt) { Prefs.sp(c).edit().putLong("alarmCall", callAt).apply(); }

    static long lastCall(Context c) { return Prefs.sp(c).getLong("alarmCall", 0); }
}
