package io.github.avtarfr.kurooto;

import java.util.Locale;

/**
 * Which of a message's buttons go on its notification (Android shows three). A reminder's or a deadline's (0.6.0):
 * the counting button first (+1), then Done, then the snoozes (Snooze 3 h, +10 min, +1 h), in the order they came;
 * the rest (Not mine, Reply...) stay a tap away, in the answer window or the chat. They're the message's own buttons,
 * the ones Telegram shows, so a tap does what it does there. A message that snoozes but has no Done (a reminder) gets
 * a Done of the app's own, which only takes it down.
 * Plain Java, so android/build.sh --test runs it on a JVM.
 */
final class Buttons {
    static final int MAX = 3;

    private Buttons() { }

    /** "+1" (or "+2"...): one more part of a problem set done; its message stays for the next tap. */
    static boolean counts(String label) { return label != null && label.matches("\\+\\d+"); }

    static boolean done(String label) { return label != null && label.trim().equalsIgnoreCase("done"); }

    /** "Snooze 3 h", "Snooze", "+10 min", "+1 h". */
    static boolean snoozes(String label) {
        if (label == null) return false;
        String l = label.trim().toLowerCase(Locale.ROOT);
        return l.startsWith("snooze") || l.matches("\\+\\d+\\s*(m|min|mins|minutes?|h|hours?)");
    }

    /** The buttons that go on the notification, by index: counting, Done, snoozes, at most max (null labels, e.g.
     *  links, never). */
    static int[] pick(String[] labels, int max) {
        int[] out = new int[Math.min(max, labels.length)];
        int n = 0;
        for (int pass = 0; pass < 3; pass++) {
            for (int i = 0; i < labels.length && n < out.length; i++) {
                String l = labels[i];
                boolean hit = pass == 0 ? counts(l) : pass == 1 ? done(l) : snoozes(l);
                if (hit) out[n++] = i;
            }
        }
        int[] got = new int[n];
        System.arraycopy(out, 0, got, 0, n);
        return got;
    }

    /** It snoozes but has no Done of its own: the notification adds one that only takes it down. */
    static boolean addDone(String[] labels) {
        boolean snooze = false;
        for (String l : labels) {
            if (done(l)) return false;
            snooze |= snoozes(l);
        }
        return snooze;
    }
}
