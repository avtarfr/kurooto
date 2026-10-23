package io.github.avtarfr.kurooto;

/** The check-in and quiz cards' rules (CardRules) and location reminders' rules (PlaceRules), on the JVM. */
public class CardsPlacesTest {
    static int failed = 0;

    static void check(boolean ok, String what) {
        if (!ok) { failed++; System.out.println("FAIL: " + what); }
    }

    public static void main(String[] a) {
        // cards: the computer's "card" field first, else the text (an older computer)
        check(CardRules.kind("checkin", "anything").equals("checkin"), "card field checkin");
        check(CardRules.kind("quiz", "").equals("quiz"), "card field quiz");
        check(CardRules.kind("", "Evening check-in: How did today go?\n\n(Reply to this message.)").equals("checkin"), "check-in by text");
        check(CardRules.kind(null, "Quiz (topology, Must know):\nA compact space...").equals("quiz"), "quiz by text");
        check(CardRules.kind("", "Link card (Topology):\nhow does...").equals("quiz"), "link card by text");
        check(CardRules.kind("", "How was the lecture?").isEmpty(), "other questions: no card");
        check(CardRules.label("checkin", "Night check-in: Before bed").equals("Night check-in"), "label check-in");
        check(CardRules.label("checkin", "I missed your evening check-in").equals("Check-in"), "label missed check-in");
        check(CardRules.label("quiz", "The note says: x\nHow did you do?").equals("Quiz: how did you do?"), "label grading");
        check(CardRules.body("checkin", "Evening check-in: How did today go?\n\n(Reply to this message.)").equals("How did today go?"), "body check-in");
        check(CardRules.body("quiz", "Quiz (t, Must know):\nX\n\nReply with your answer.").equals("Quiz (t, Must know):\nX"), "body quiz");
        check(CardRules.perRow(new String[]{"Forgot", "Hard", "Good", "Easy"}) == 4, "four short buttons in a row");
        check(CardRules.perRow(new String[]{"In 30 min", "Tomorrow morning", "Skip today"}) == 2, "longer ones two a row");
        check(CardRules.perRow(new String[]{"One"}) == 1, "one");
        check(CardRules.perRow(new String[]{"A very long label for a button", "B"}) == 1, "very long: one a row");

        // places
        check(PlaceRules.key(" The  Library. ").equals("library") && PlaceRules.key("my gym").equals("gym"), "names match loosely");
        check(PlaceRules.name("  a   place  ").equals("a place") && PlaceRules.name("x".repeat(60)).length() == 40, "names tidied");
        double d = PlaceRules.distance(18.5204, 73.8567, 18.5204, 73.8577); // 0.001 degrees of longitude at 18.5 N
        check(Math.abs(d - 105.5) < 1.5, "distance " + d);
        check(PlaceRules.distance(0, 0, 0, 0) == 0, "no distance");
        long now = 10_000_000L;
        check(PlaceRules.fire(true, false, now, 0), "arriving from outside says it");
        check(!PlaceRules.fire(true, true, now, 0), "already there (alert set while inside): quiet");
        check(!PlaceRules.fire(false, false, now, 0), "leaving: quiet");
        check(!PlaceRules.fire(true, false, now, now - 60_000), "back within 20 minutes: quiet");
        check(PlaceRules.fire(true, false, now, now - PlaceRules.QUIET_MS), "after 20 minutes: again");
        check(PlaceRules.goodFix(30, false) && !PlaceRules.goodFix(120, false) && PlaceRules.goodFix(120, true), "fixes");
        check(!PlaceRules.goodFix(0, true) && !PlaceRules.goodFix(900, true), "no accuracy or too rough: not saved");
        check(PlaceRules.BATTERY.startsWith("Battery:"), "battery said");

        if (failed > 0) { System.out.println(failed + " failed"); System.exit(1); }
        System.out.println("CardsPlacesTest: ok");
    }
}
