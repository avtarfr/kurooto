package io.github.avtarfr.kurooto;

import java.util.TimeZone;

/** Dock.java on the JVM: bedside mode's brightness and colours by the hour, its "open while charging" hours, and how
 *  a coming call's time is written. */
public class DockTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "ok  " : "FAIL ") + what);
        if (!ok) failed++;
    }

    public static void main(String[] args) {
        check(Dock.brightness(23) == 0.01f && Dock.brightness(0) == 0.01f && Dock.brightness(5) == 0.01f, "night: as dim as it goes");
        check(Dock.brightness(12) == -1f && Dock.brightness(7) == -1f && Dock.brightness(19) == -1f, "day: the phone's own brightness");
        check(Dock.brightness(20) > Dock.brightness(21) && Dock.brightness(21) > Dock.brightness(22), "the evening steps down");
        check(Dock.brightness(6) > Dock.brightness(5) && Dock.brightness(6) < 1, "the morning steps up");
        check(Dock.warm(23) && Dock.warm(6) && Dock.warm(20) && !Dock.warm(7) && !Dock.warm(19), "warm colours from 20:00 to 07:00");
        int night = Dock.ink(2);
        check(((night >> 16) & 0xff) > (night & 0xff) * 3, "night ink is red-orange, no blue to speak of");
        check(Dock.ink(12) != Dock.ink(2) && Dock.dim(2) != Dock.ink(2), "day and night inks differ");

        check(Dock.minutes("22:00") == 1320 && Dock.minutes("7:05") == 425 && Dock.minutes("00:00") == 0, "times read");
        check(Dock.minutes("24:00") == -1 && Dock.minutes("x") == -1 && Dock.minutes(null) == -1 && Dock.minutes("1:2:3") == -1, "nonsense refused");
        check(Dock.hm(425).equals("07:05") && Dock.hm(1320).equals("22:00"), "times written");
        int from = Dock.minutes("22:00"), to = Dock.minutes("07:00");
        check(Dock.within(1380, from, to) && Dock.within(0, from, to) && Dock.within(420 - 1, from, to), "hours across midnight");
        check(!Dock.within(420, from, to) && !Dock.within(720, from, to) && Dock.within(1320, from, to), "its ends: from in, to out");
        check(Dock.within(600, 540, 1020) && !Dock.within(1100, 540, 1020), "daytime hours");
        check(!Dock.within(600, 600, 600) && !Dock.within(600, -1, 700), "equal or unset: never");

        TimeZone tz = TimeZone.getTimeZone("UTC");
        long now = 1_761_210_000_000L; // Thu 23 Oct 2025, 09:00 UTC
        check(Dock.when(now / 1000 + 9 * 3600 + 1800, now, true, tz).equals("18:30"), "today: the time");
        check(Dock.when(now / 1000 + 9 * 3600 + 1800, now, false, tz).equals("6:30 PM"), "a 12-hour clock");
        check(Dock.when(now / 1000 + 22 * 3600, now, true, tz).equals("Fri 07:00"), "tomorrow: with its day");
        check(Dock.when(now / 1000 - 9 * 3600, now, false, tz).equals("12:00 AM"), "midnight on a 12-hour clock");
        check(Dock.toNextMinute(60_000L * 5 + 59_000) <= 1_050 && Dock.toNextMinute(60_000L * 5) > 59_000, "the clock turns on the minute");
        java.util.Calendar c = java.util.Calendar.getInstance(); // (0.9.0) bedside's "due within a day", local time
        c.clear(); c.set(2026, 9, 30, 10, 0);
        long t = c.getTimeInMillis();
        check(Dock.withinDay("2026-10-30T23:59", t) && Dock.withinDay("2026-10-31T09:00", t), "due within a day");
        check(!Dock.withinDay("2026-11-02T09:00", t) && !Dock.withinDay("", t) && !Dock.withinDay(null, t), "later or unreadable: no");
        check(Dock.withinDay("2026-10-30T01:00", t) && !Dock.withinDay("2026-10-29T09:00", t), "overdue under 12 hours only");

        // 0.8.7 (the Compose bedside screen): a tap's brightness, the alarm line, the waiting line
        check(Dock.brightness(23, true) == 0.3f && Dock.brightness(20, true) == 0.35f, "a tap brightens the night to 0.3, never dims");
        check(Dock.brightness(12, true) == -1f && Dock.brightness(23, false) == 0.01f, "daytime keeps the phone's own; no tap, no change");
        long wake = now / 1000 + 22 * 3600, phone = wake + 600;
        check(Dock.alarmLine(wake, phone, true, now, true, tz).equals("Wake-up call  Fri 07:00"), "the wake-up call when it's first");
        check(Dock.alarmLine(wake, wake - 30, true, now, true, tz).startsWith("Wake-up call"), "within a minute of the phone's: still the call");
        check(Dock.alarmLine(wake, wake - 600, true, now, true, tz).equals("Alarm  Fri 06:50"), "the phone's own when it's earlier");
        check(Dock.alarmLine(0, phone, false, now, true, tz).startsWith("Alarm  "), "the phone's own with no wake-up call");
        check(Dock.alarmLine(0, 0, true, now, true, tz).equals("No alarm set") && Dock.alarmLine(0, 0, false, now, true, tz).isEmpty(),
                "none: said once the line has answered");
        check(Dock.waitingLine(0).isEmpty() && Dock.waitingLine(1).equals("1 thing waiting for you")
                && Dock.waitingLine(3).equals("3 things waiting for you"), "the waiting line");

        System.out.println(failed == 0 ? "dock ok" : failed + " failed");
        if (failed > 0) System.exit(1);
    }
}
