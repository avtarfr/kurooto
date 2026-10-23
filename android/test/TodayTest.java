package io.github.avtarfr.kurooto;

import java.util.Arrays;

/** The 0.6.0 phone rules on the JVM: which buttons a reminder's or deadline's notification shows (Buttons), and the
 *  phone's own wake-up alarm against the call for it (AlarmPlan). */
public class TodayTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "ok  " : "FAIL ") + what);
        if (!ok) failed++;
    }

    public static void main(String[] args) {
        // a deadline's message on Telegram: +1, Done, Not mine, Snooze 3 h
        String[] dl = {"+1", "Done", "Not mine", "Snooze 3 h"};
        check(Arrays.equals(Buttons.pick(dl, 3), new int[]{0, 1, 3}), "a deadline: +1, Done, Snooze (Not mine a tap away)");
        check(!Buttons.addDone(dl), "a deadline has its own Done");
        String[] dl2 = {"Done", "Not mine", "Snooze 3 h"};
        check(Arrays.equals(Buttons.pick(dl2, 3), new int[]{0, 2}), "all parts done: Done, Snooze");
        // a reminder: +10 min, +1 h (snoozes; no Done)
        String[] rem = {"+10 min", "+1 h"};
        check(Arrays.equals(Buttons.pick(rem, 3), new int[]{0, 1}), "a reminder's snoozes");
        check(Buttons.addDone(rem), "a reminder gets the app's own Done");
        check(!Buttons.counts("+10 min") && Buttons.counts("+1") && Buttons.counts("+12"), "+10 min isn't a count");
        check(Buttons.snoozes("Snooze 3 h") && Buttons.snoozes("+1 h") && Buttons.snoozes("+15 minutes") && !Buttons.snoozes("+1"),
                "what snoozes");
        check(Buttons.pick(new String[]{"Why?", "Less of this", null}, 3).length == 0, "nothing quick: none");
        check(!Buttons.addDone(new String[]{"Why?", null}), "nothing to snooze: no Done added");
        check(Buttons.pick(new String[]{"+1", "+2", "Done", "Snooze"}, 3).length == 3, "at most three");

        // the phone's own alarm
        long now = 1_800_000_000L;
        check(AlarmPlan.next(new long[]{now + 3600, now + 600}, 0, now, 0) == now + 600, "the soonest alarm");
        check(AlarmPlan.next(new long[]{now - 60}, 0, now, 0) == 0, "past ones don't ring");
        check(AlarmPlan.next(new long[]{now + 3600}, now + 600, now, 0) == now + 600, "a snooze set here first");
        check(AlarmPlan.next(new long[]{now + 620, now + 3600}, now + 600, now, now + 600) == now + 3600,
                "your computer's copy of the snooze that rang here doesn't ring again");
        check(AlarmPlan.next(new long[0], 0, now, 0) == 0, "no alarm, nothing set");
        check(AlarmPlan.same(now, now + 120) && !AlarmPlan.same(now, now + 900) && !AlarmPlan.same(0, now), "one alarm or two");
        String stopped = (now - 30) + ":decline:" + now;
        check(AlarmPlan.answered(stopped, now + 10, now + 20).equals("decline"), "stopped here: the call is turned down");
        check(AlarmPlan.answered((now - 30) + ":later:" + now, now, now + 5).equals("later"), "snoozed here: the call snoozes");
        check(AlarmPlan.answered(stopped, now + 3600, now + 3600).isEmpty(), "another alarm still rings");
        check(AlarmPlan.answered(stopped, now, now + 7200).isEmpty(), "an old tap doesn't count");
        check(AlarmPlan.answered("junk", now, now).isEmpty() && AlarmPlan.answered("", now, now).isEmpty(), "nothing tapped");
        check(AlarmPlan.since("local:1761200000") == 1761200000L && AlarmPlan.since("1761200000") == 1761200000L
                && AlarmPlan.since("x") == 0, "a ring's alarm time");
        if (failed > 0) System.exit(1);
    }
}
