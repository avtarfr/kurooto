package io.github.avtarfr.kurooto;

/** The rules of the app's own connection to the call line (Direct, 0.7.0), in plain Java for the JVM tests
 *  (LinkTest): where it connects, how long it waits before trying again, and which messages it has had already
 *  (each one comes with an id, "mid": a ring comes both on this connection and through ntfy, and a phone that
 *  reconnects is sent what it may have missed). */
final class LinkRules {
    private LinkRules() { }

    static final int SEEN_MAX = 200; // message ids remembered (a few days of messages)

    /** Where to connect for a call line at `base` ("https://host[:port]"): {host, port, path, "tls" or ""}; null if
     *  it isn't an address. `after`: the last message number this phone had. */
    static String[] target(String base, long after) {
        java.net.URI u;
        try { u = new java.net.URI(base); } catch (Exception e) { return null; }
        String scheme = u.getScheme(), host = u.getHost();
        if (host == null || !("https".equals(scheme) || "http".equals(scheme))) return null;
        boolean tls = "https".equals(scheme);
        int port = u.getPort() > 0 ? u.getPort() : (tls ? 443 : 80);
        return new String[]{host, String.valueOf(port), "/phone?after=" + Math.max(0, after), tls ? "tls" : ""};
    }

    /** How long to wait before the next try, after `fails` failures in a row: 2 s doubling to 60 s, and a random
     *  part (rnd in [0, 1)) of up to a third more, so phones that lost the network together don't all come back in
     *  the same second. */
    static long backoffMs(int fails, double rnd) {
        long base = 2000L << Math.min(Math.max(fails, 0), 5);
        base = Math.min(base, 60_000L);
        return base + (long) (base * Math.max(0, Math.min(rnd, 1)) / 3);
    }

    /** The ids seen (comma separated, newest last) with `mid` added, or null when it was there already: a second
     *  copy, dropped. An empty mid (a line from before 0.7.0) is never a copy. */
    static String seen(String csv, String mid, int max) {
        if (mid == null || mid.isEmpty()) return csv == null ? "" : csv;
        String all = csv == null ? "" : csv;
        if (("," + all + ",").contains("," + mid + ",")) return null;
        String[] ids = all.isEmpty() ? new String[0] : all.split(",");
        StringBuilder b = new StringBuilder();
        for (int i = Math.max(0, ids.length - max + 1); i < ids.length; i++) b.append(ids[i]).append(',');
        return b.append(mid).toString();
    }
}
