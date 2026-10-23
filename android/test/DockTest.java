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

        System.out.println(failed == 0 ? "dock ok" : failed + " failed");
        if (failed > 0) System.exit(1);
    }
}
