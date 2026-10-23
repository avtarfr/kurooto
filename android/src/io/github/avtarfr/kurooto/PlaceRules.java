package io.github.avtarfr.kurooto;

import java.util.Locale;

/** The plain rules behind location reminders (Places), kept free of Android so the JVM tests can run them. */
final class PlaceRules {
    static final float RADIUS_M = 150;           // how near counts as "there"
    static final long QUIET_MS = 20 * 60_000L;    // a place's reminders come at most once in this long (GPS drift)
    static final String BATTERY = "Battery: Android checks where you are a few times an hour while the app is in the "
            + "background, mostly from Wi-Fi and the phone network (the GPS isn't kept on), and more often when you're near "
            + "a saved place. The cost is small, about what a weather widget uses. A reminder can come a few minutes after "
            + "you arrive.";

    private PlaceRules() { }

    /** A place's name as it's matched: "The Library " and "library" are the same place. */
    static String key(String name) {
        String s = name == null ? "" : name.trim().toLowerCase(Locale.ROOT).replaceAll("\\s+", " ");
        s = s.replaceFirst("^(the|my|our) ", "");
        return s.replaceAll("[.!?,;:]+$", "").trim();
    }

    /** A name to save a place under: trimmed, at most 40 characters, or "" if there's nothing. */
    static String name(String typed) {
        String s = typed == null ? "" : typed.trim().replaceAll("\\s+", " ");
        return s.length() > 40 ? s.substring(0, 40).trim() : s;
    }

    /** Metres between two points (haversine). */
    static double distance(double lat1, double lon1, double lat2, double lon2) {
        double r = 6371008.8, p1 = Math.toRadians(lat1), p2 = Math.toRadians(lat2);
        double dp = p2 - p1, dl = Math.toRadians(lon2 - lon1);
        double a = Math.sin(dp / 2) * Math.sin(dp / 2) + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
        return 2 * r * Math.asin(Math.min(1, Math.sqrt(a)));
    }

    /** Whether arriving now says the place's reminders: you came in from outside (Android also says "entering" when
     *  an alert is set while you're already there, or after a restart there), and not again within QUIET_MS. */
    static boolean fire(boolean entering, boolean wasInside, long now, long lastFired) {
        return entering && !wasInside && (lastFired <= 0 || now - lastFired >= QUIET_MS);
    }

    /** A fix good enough to save a place with: accurate to 50 m, or the best one after waiting. */
    static boolean goodFix(float accuracyM, boolean waitedLongEnough) {
        return accuracyM > 0 && (accuracyM <= 50 || (waitedLongEnough && accuracyM <= 500));
    }
}
