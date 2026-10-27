package io.github.avtarfr.kurooto;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The being's requests to your computer (0.8.10, Views → Being): a setting, a feature on or off, a note's preview,
 * mute. The page asks the app (ViewsPane answers /ask), the app sends it like a chat message, sealed with this phone's
 * chat key (Crypto, k1) and marked live (the call line passes it on now or says your computer is off; it never waits
 * there), and your computer answers sealed for this phone alone (Seal, s1; or k1 from an older line), through chat.py's
 * "op". These are the rules, with no Android classes and no JSON library, so android/build.sh --test runs them on a
 * plain JVM (BeingTest). ViewsPane.ask does the sending.
 */
final class BeingRules {
    static final String[] OPS = {"settings.set", "module", "note.get", "voice.mute"};
    static final int ARGS_MAX = 4000;
    static final String OFF = "Your computer is off: try again when it's on.";
    private static final Pattern TOKEN = Pattern.compile("\"(s1|k1)\"\\s*:\\s*\"([A-Za-z0-9_.-]{8,200000})\"");

    /** Opens what your computer sealed: kind "s1" (for this phone's own key) or "k1" (the chat's key); null if it can't. */
    interface Opener { String open(String kind, String token); }

    private BeingRules() { }

    static boolean known(String op) {
        for (String o : OPS) if (o.equals(op)) return true;
        return false;
    }

    /** The arguments the page sent, if they're a JSON object of a sane size (else null: nothing is sent). */
    static String args(String a) {
        if (a == null) return "{}";
        String t = a.trim();
        if (t.isEmpty()) return "{}";
        if (t.length() > ARGS_MAX || !t.startsWith("{") || !t.endsWith("}")) return null;
        return t;
    }

    /** What's sealed: the op, its arguments, and the chat's own once-only fields (id, the time, a random nonce). */
    static String fields(String op, String args, String id, long ts, String n) {
        return "{\"op\":" + quote(op) + ",\"args\":" + args + ",\"id\":" + quote(id) + ",\"ts\":" + ts + ",\"n\":" + quote(n) + "}";
    }

    /** The body POSTed to /chat: only the id, the sealed fields, and "live" (now or not at all). */
    static String body(String id, String k1) {
        return "{\"id\":" + quote(id) + ",\"k1\":" + quote(k1) + ",\"live\":true}";
    }

    /** The answer the page gets, a JSON object with "ok" and "note" at least: what your computer said, opened, or why
     *  there's no answer (code -1: the call line wasn't reached). */
    static String reply(int code, String body, Opener o) {
        String b = body == null ? "" : body;
        if (code == -1) return fail("Couldn't reach your call line. Is this phone online?");
        if (code == 404) return fail("Your call line is too old for this: update Kurooto on your computer.");
        if (flag(b, "offline") || flag(b, "queued") || code == 503) return "{\"ok\":false,\"offline\":true,\"note\":" + quote(OFF) + "}";
        Matcher m = TOKEN.matcher(b);
        if (m.find()) {
            String plain = o == null ? null : o.open(m.group(1), m.group(2));
            if (plain != null && plain.trim().startsWith("{") && plain.trim().endsWith("}")) return plain.trim();
            return fail("Your computer's answer couldn't be opened here. Pair the phone again.");
        }
        String t = b.trim();
        if (t.startsWith("{") && t.endsWith("}") && t.contains("\"note\"")) return t; // a refusal, in words (not sealed: nothing in it)
        return fail(code >= 200 && code < 300 ? "Your computer didn't say." : "That didn't work (" + code + ").");
    }

    private static boolean flag(String b, String name) {
        return Pattern.compile("\"" + name + "\"\\s*:\\s*true").matcher(b).find();
    }

    static String fail(String note) { return "{\"ok\":false,\"note\":" + quote(note) + "}"; }

    /** A JSON string. */
    static String quote(String s) {
        StringBuilder q = new StringBuilder(s.length() + 2).append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') q.append('\\').append(c);
            else if (c < 0x20 || c == 0x2028 || c == 0x2029) q.append(String.format("\\u%04x", (int) c));
            else q.append(c);
        }
        return q.append('"').toString();
    }
}
