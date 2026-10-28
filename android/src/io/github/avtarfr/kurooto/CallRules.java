package io.github.avtarfr.kurooto;

/** The call screen's rules (0.8.7), kept free of Android so test/CallRulesTest.java checks them on a plain JVM: what an
 *  intent to CallActivity does, the ringing screen's words, whether a reply goes to the call line, and the call page's
 *  link. CallActivity uses them on both of its screens (the Compose one and the one from before 0.8.7). */
final class CallRules {
    private CallRules() { }

    static final int FINISH = 0, IGNORE = 1, RING = 2, ANSWER = 3, HANG_UP = 4;

    /** An intent's job: no call link and not this phone's own alarm, close; the alarm while a call is on, nothing;
     *  the alarm, or a ringing call while none is on, ring; else (a call link to open) straight into the call. */
    static int what(boolean hasUrl, boolean localExtra, boolean ringing, boolean inCall) {
        boolean local = !hasUrl && localExtra;
        if (!hasUrl && !local) return FINISH;
        if (local && inCall) return IGNORE;
        if (local || (ringing && !inCall)) return RING;
        return ANSWER;
    }

    /** The ongoing call's notification (0.8.17: Back leaves a call running): a tap only brings the call back, its
     *  Hang up ends the call through the call page; with the call already over, the screen just closes. */
    static int fromNotice(boolean inCall, boolean hangup) {
        if (!inCall) return FINISH;
        return hangup ? HANG_UP : IGNORE;
    }

    /** Who's calling: this phone's own alarm, the wake-up call, or the assistant. */
    static String who(boolean local, boolean alarm, String assistant) {
        return local ? "Good morning: wake-up alarm" : alarm ? "Good morning: wake-up call" : assistant + " is calling";
    }

    static String declineLabel(boolean local) { return local ? "Stop" : "Decline"; }

    static String laterLabel(boolean alarm) { return alarm ? "Snooze" : "Later"; }

    /** This phone's own alarm has no Answer (until the call for it comes and joins it). */
    static boolean canAnswer(boolean local) { return !local; }

    /** Decline or Later reaches the call line only for a call that came from it (not this phone's own alarm). */
    static boolean tellLine(String since) { return since != null && !since.isEmpty() && !since.startsWith("local:"); }

    /** The page starts the call by itself when opened from here (you already tapped Answer). */
    static String withAuto(String u) {
        int hash = u.indexOf('#');
        String base = hash < 0 ? u : u.substring(0, hash), frag = hash < 0 ? "" : u.substring(hash);
        return base + (base.contains("?") ? "&" : "?") + "auto=1" + frag;
    }
}
