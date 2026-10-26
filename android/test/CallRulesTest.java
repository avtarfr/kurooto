package io.github.avtarfr.kurooto;

/** CallRules.java on the JVM: what an intent to the call screen does, the ringing screen's words, which replies reach
 *  the call line, and the call page's link. */
public class CallRulesTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "ok  " : "FAIL ") + what);
        if (!ok) failed++;
    }

    public static void main(String[] args) {
        check(CallRules.what(false, false, false, false) == CallRules.FINISH, "no link, not the alarm: close");
        check(CallRules.what(false, false, true, false) == CallRules.FINISH, "ringing without a link: close");
        check(CallRules.what(false, true, false, false) == CallRules.RING, "this phone's alarm rings");
        check(CallRules.what(false, true, false, true) == CallRules.IGNORE, "the alarm during a call: nothing");
        check(CallRules.what(true, true, true, false) == CallRules.RING, "a link with the local extra is a call, ringing");
        check(CallRules.what(true, false, true, false) == CallRules.RING, "a call rings");
        check(CallRules.what(true, false, true, true) == CallRules.ANSWER, "a ring during the call: stays in the call");
        check(CallRules.what(true, false, false, false) == CallRules.ANSWER, "a link alone: straight into the call");

        check(CallRules.who(true, true, "Kuro").equals("Good morning: wake-up alarm"), "the phone's own alarm");
        check(CallRules.who(false, true, "Kuro").equals("Good morning: wake-up call"), "the wake-up call");
        check(CallRules.who(false, false, "Kuro").equals("Kuro is calling"), "a call");
        check(CallRules.declineLabel(true).equals("Stop") && CallRules.declineLabel(false).equals("Decline"), "Stop or Decline");
        check(CallRules.laterLabel(true).equals("Snooze") && CallRules.laterLabel(false).equals("Later"), "Snooze or Later");
        check(!CallRules.canAnswer(true) && CallRules.canAnswer(false), "the alarm alone has no Answer");

        check(CallRules.tellLine("1700000000") && !CallRules.tellLine("local:7") && !CallRules.tellLine("") && !CallRules.tellLine(null),
                "only the line's own calls hear a reply");

        check(CallRules.withAuto("https://line.example/call").equals("https://line.example/call?auto=1"), "auto added");
        check(CallRules.withAuto("https://line.example/call?t=1").equals("https://line.example/call?t=1&auto=1"), "after a query");
        check(CallRules.withAuto("https://line.example/call?t=1#k=abc").equals("https://line.example/call?t=1&auto=1#k=abc"),
                "before the fragment, which stays");
        check(CallRules.withAuto("https://line.example/c#x?y").equals("https://line.example/c?auto=1#x?y"), "a ? in the fragment isn't a query");

        System.out.println(failed == 0 ? "call rules ok" : failed + " failed");
        if (failed > 0) System.exit(1);
    }
}
