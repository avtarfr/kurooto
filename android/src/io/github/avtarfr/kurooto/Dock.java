package io.github.avtarfr.kurooto;

import java.util.Calendar;
import java.util.Locale;
import java.util.TimeZone;

/** Bedside mode's rules, kept free of Android so test/DockTest.java checks them on a plain JVM: how bright the screen
 *  is at each hour (night: very dim and warm), whether a time falls in the "open by itself while charging" hours, and
 *  how a coming call's time is written. BedsideActivity uses them. */
final class Dock {
    private Dock() { }

    /** Window brightness for this hour (0..1), or -1 for the phone's own setting (daytime). Night is as dim as the
     *  screen goes; the evening steps down, the morning steps up. */
    static float brightness(int hour) {
        if (hour >= 22 || hour < 6) return 0.01f;
        if (hour == 6) return 0.15f;
        if (hour == 21) return 0.12f;
        if (hour == 20) return 0.35f;
        return -1f;
    }

    /** The same, after a tap on the screen (brightened for a while): at least 0.3, except in the daytime, which keeps
     *  the phone's own setting. */
    static float brightness(int hour, boolean tapped) {
        float want = brightness(hour);
        return tapped && want >= 0 ? Math.max(want, 0.3f) : want;
    }

    /** The alarm line: Kurooto's wake-up call (`wake`, 0 if none) if it comes no later than a minute after the phone's
     *  own next alarm (`phone`, 0 if none), else the phone's; before the call line has answered once (`loaded` false),
     *  nothing rather than "No alarm set". Times are seconds. */
    static String alarmLine(long wake, long phone, boolean loaded, long nowMs, boolean h24, TimeZone tz) {
        if (wake > 0 && (phone == 0 || wake <= phone + 60)) return "Wake-up call  " + when(wake, nowMs, h24, tz);
        if (phone > 0) return "Alarm  " + when(phone, nowMs, h24, tz);
        return loaded ? "No alarm set" : "";
    }

    /** How many things wait for you in Inbox ("" for none). */
    static String waitingLine(int n) {
        return n <= 0 ? "" : n == 1 ? "1 thing waiting for you" : n + " things waiting for you";
    }

    /** True from 20:00 to 06:59: warm colours, no blue. */
    static boolean warm(int hour) { return hour >= 20 || hour < 7; }

    /** The clock's colour (ARGB): a dim amber-red at night, a warm white in the evening and early morning, else the
     *  call screen's white. */
    static int ink(int hour) {
        if (hour >= 22 || hour < 6) return 0xFF9C3B12;
        if (warm(hour)) return 0xFFE8B98A;
        return 0xFFF2EEE8;
    }

    /** Supporting text: the same hue, quieter. */
    static int dim(int hour) {
        if (hour >= 22 || hour < 6) return 0xFF6E2A0D;
        if (warm(hour)) return 0xFFA88566;
        return 0xFF95A682;
    }

    /** "22:00" -> minutes after midnight; -1 if it isn't a time. */
    static int minutes(String hm) {
        if (hm == null) return -1;
        String[] p = hm.trim().split(":");
        try {
            int h = Integer.parseInt(p[0]), m = p.length > 1 ? Integer.parseInt(p[1]) : 0;
            return h >= 0 && h < 24 && m >= 0 && m < 60 && p.length <= 2 ? h * 60 + m : -1;
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    static String hm(int minutes) { return String.format(Locale.ROOT, "%02d:%02d", minutes / 60 % 24, minutes % 60); }

    /** Is `now` (minutes after midnight) within [from, to)? The hours may cross midnight (22:00 to 07:00). Equal or
     *  unset ends: never. */
    static boolean within(int now, int from, int to) {
        if (from < 0 || to < 0 || from == to) return false;
        return from < to ? now >= from && now < to : now >= from || now < to;
    }

    /** A coming call's time: "18:30" today, "Tue 07:00" another day ("6:30 PM" with a 12-hour clock). */
    static String when(long atSec, long nowMs, boolean h24, TimeZone tz) {
        Calendar at = Calendar.getInstance(tz, Locale.ROOT), now = Calendar.getInstance(tz, Locale.ROOT);
        at.setTimeInMillis(atSec * 1000);
        now.setTimeInMillis(nowMs);
        int h = at.get(Calendar.HOUR_OF_DAY), m = at.get(Calendar.MINUTE);
        String t = h24 ? String.format(Locale.ROOT, "%02d:%02d", h, m)
                : String.format(Locale.ROOT, "%d:%02d %s", h % 12 == 0 ? 12 : h % 12, m, h < 12 ? "AM" : "PM");
        boolean today = at.get(Calendar.YEAR) == now.get(Calendar.YEAR) && at.get(Calendar.DAY_OF_YEAR) == now.get(Calendar.DAY_OF_YEAR);
        if (today) return t;
        String[] days = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
        return days[at.get(Calendar.DAY_OF_WEEK) - 1] + " " + t;
    }

    /** Milliseconds to the next whole minute, so the clock turns over on time. */
    static long toNextMinute(long nowMs) { return 60000 - nowMs % 60000 + 50; }
}
