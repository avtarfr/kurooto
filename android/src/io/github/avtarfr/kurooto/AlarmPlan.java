package io.github.avtarfr.kurooto;

/**
 * The rules of the phone's own copy of the wake-up alarm (Alarms does the Android part). Times are in seconds.
 * Your computer sends every alarm still to ring (the Today list); a snooze tapped here adds one. The phone and the
 * call from your call line are one alarm when they're within SAME_S of each other: the first to ring is the one that
 * rings, and the first Stop, Snooze or Answer counts for both.
 * Plain Java, so android/build.sh --test runs it on a JVM.
 */
final class AlarmPlan {
    static final long SAME_S = 300;
    /** a Stop or Snooze here answers the call for the same alarm if that call comes within this long */
    static final long HANDLED_KEEP_S = 1800;

    private AlarmPlan() { }

    static boolean same(long a, long b) { return a > 0 && b > 0 && Math.abs(a - b) <= SAME_S; }

    /** When to ring next: the soonest of your computer's alarms and a snooze set here that's still to come, leaving
     *  out the alarm that last rang here (your computer's copy of a snooze tapped here comes a few seconds after
     *  this phone's own). 0 for none. */
    static long next(long[] alarms, long snooze, long now, long last) {
        long best = 0;
        for (int i = 0; i <= alarms.length; i++) {
            long t = i < alarms.length ? alarms[i] : snooze;
            if (t > now && !same(t, last) && (best == 0 || t < best)) best = t;
        }
        return best;
    }

    /** What a call for the alarm at `callAt` should do, given what was tapped here: "decline", "later" or "" (ring).
     *  handled is "<alarm s>:<action>:<when tapped, s>", or "". */
    static String answered(String handled, long callAt, long now) {
        if (handled == null || handled.isEmpty()) return "";
        String[] p = handled.split(":");
        if (p.length != 3) return "";
        try {
            long at = Long.parseLong(p[0]), when = Long.parseLong(p[2]);
            if (!same(at, callAt) || now - when > HANDLED_KEEP_S || now < when) return "";
            return "decline".equals(p[1]) || "later".equals(p[1]) ? p[1] : "";
        } catch (NumberFormatException e) {
            return "";
        }
    }

    /** The alarm time in a ring's "since": the call line's own ("1761200000"), or this phone's ("local:1761200000"). */
    static long since(String since) {
        if (since == null) return 0;
        try { return Long.parseLong(since.startsWith("local:") ? since.substring(6) : since); } catch (NumberFormatException e) { return 0; }
    }
}
