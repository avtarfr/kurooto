package io.github.avtarfr.kurooto;

/** The plain rules behind the check-in and quiz cards (Cards), kept free of Android so the JVM tests can run them. */
final class CardRules {
    private CardRules() { }

    /** "checkin", "quiz" or "" (no card): from the item's "card" field (your computer, 0.5.22), else from its text,
     *  for a computer on an older version ("Evening check-in: ...", "Quiz (topology, Must know): ..."). */
    static String kind(String card, String text) {
        if ("checkin".equals(card) || "quiz".equals(card)) return card;
        String t = text == null ? "" : text.trim();
        if (t.matches("(?s)(Evening|Midday|Night) check-in: .*")) return "checkin";
        if (t.matches("(?s)(Quiz \\(|Link card[ :(]).*")) return "quiz";
        return "";
    }

    /** The card's label: what it is, at a glance. */
    static String label(String kind, String text) {
        String t = text == null ? "" : text.trim();
        if ("checkin".equals(kind)) {
            int c = t.indexOf(" check-in:");
            return c > 0 && c < 12 ? t.substring(0, c) + " check-in" : "Check-in";
        }
        if (t.startsWith("Link card")) return "Link card";
        return t.startsWith("The note says") ? "Quiz: how did you do?" : "Quiz";
    }

    /** The question without what the card already shows: the "Evening check-in: " start and the "(Reply to this
     *  message.)" / "Reply with your answer." ends meant for Telegram. */
    static String body(String kind, String text) {
        String t = text == null ? "" : text.trim();
        if ("checkin".equals(kind)) t = t.replaceFirst("^(Evening|Midday|Night) check-in: ", "");
        t = t.replaceAll("\\s*\\((Reply to this message\\.)\\)\\s*$", "")
                .replaceAll("\\s*(Reply with your answer\\.|Reply in your own words\\.)\\s*$", "");
        return t.trim();
    }

    /** How many buttons go side by side: four short ones (Forgot, Hard, Good, Easy) fit a row, longer ones two. */
    static int perRow(String[] labels) {
        int longest = 0;
        for (String s : labels) longest = Math.max(longest, s == null ? 0 : s.length());
        if (labels.length <= 1) return 1;
        if (longest <= 7) return Math.min(4, labels.length);
        return longest <= 16 ? 2 : 1;
    }

    /** The hint in the answer box. */
    static String hint(String kind) {
        return "checkin".equals(kind) ? "How it went" : "Your answer";
    }
}
