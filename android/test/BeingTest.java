package io.github.avtarfr.kurooto;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** The being on the phone (0.8.10): its requests to your computer (BeingRules), on a plain JVM (android/build.sh
 *  --test): what's sealed and sent, the answer opened with this phone's own key (s1, the shared vectors) or the chat's
 *  (k1), and the plain words when it can't be (no network, the computer off, an older call line, a stranger's seal). */
public final class BeingTest {
    private static String field(String json, String section, String name) {
        Matcher m = Pattern.compile("\"" + section + "\"\\s*:\\s*\\{(.*?)\\n  \\}", Pattern.DOTALL).matcher(json);
        if (!m.find()) throw new IllegalStateException("no " + section);
        Matcher f = Pattern.compile("\"" + name + "\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"").matcher(m.group(1));
        if (!f.find()) throw new IllegalStateException("no " + section + "." + name);
        return f.group(1).replace("\\\"", "\"").replace("\\\\", "\\");
    }

    private static void check(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
        System.out.println("ok  " + what);
    }

    public static void main(String[] args) throws Exception {
        String json = new String(Files.readAllBytes(Paths.get(args[0])), "UTF-8");

        // what the page may ask, and how its arguments are taken
        check(BeingRules.known("settings.set") && BeingRules.known("module") && BeingRules.known("note.get") && BeingRules.known("voice.mute"),
                "the four requests the being makes");
        check(BeingRules.known("voice.room") && BeingRules.args("{\"mode\":\"night\"}") != null,
                "(0.9.2) the room mode, from Today's Room card and the being's Hearing panel");
        check(!BeingRules.known("session.delete") && !BeingRules.known("") && !BeingRules.known(null) && !BeingRules.known("text"), "nothing else");
        check("{}".equals(BeingRules.args(null)) && "{}".equals(BeingRules.args("  ")), "no arguments: an empty object");
        check(BeingRules.args("[1]") == null && BeingRules.args("{\"a\":1") == null, "arguments that aren't an object aren't sent");
        StringBuilder big = new StringBuilder("{\"k\":\"");
        while (big.length() < BeingRules.ARGS_MAX) big.append('x');
        check(BeingRules.args(big.append("\"}").toString()) == null, "nor a huge one");

        // what's sealed, and what goes in the clear (only the id and "live")
        String f = BeingRules.fields("settings.set", "{\"key\":\"look.being_hints\",\"value\":false}", "0123456789abcdef", 1760000000000L, "nn\"x");
        check(f.startsWith("{\"op\":\"settings.set\",\"args\":{\"key\":\"look.being_hints\",\"value\":false},\"id\":\"0123456789abcdef\",\"ts\":1760000000000,")
                && f.endsWith("\"n\":\"nn\\\"x\"}"), "the sealed fields: op, args, id, time, nonce (quoted safely)");
        String body = BeingRules.body("0123456789abcdef", "k1.abc");
        check(body.equals("{\"id\":\"0123456789abcdef\",\"k1\":\"k1.abc\",\"live\":true}"), "the body: id, sealed fields, live");
        check(BeingRules.quote("a\nb ").equals("\"a\\u000ab\\u2028\""), "control characters are escaped");

        // k1: the fields round-trip with the chat's key (Crypto), as your computer opens them (line.py open_k1)
        byte[] key = B64.decode(field(json, "k1", "key"));
        String sealed = Crypto.seal(key, f);
        check(f.equals(Crypto.open(key, sealed)), "the fields sealed with the chat's key open with it");

        // the answer: sealed for this phone (s1), opened with its key; the shared vector's token goes to the opener
        java.security.KeyPair other = Seal.newKeys();
        java.security.spec.ECParameterSpec params = ((java.security.interfaces.ECPublicKey) other.getPublic()).getParams();
        java.security.PrivateKey phone = java.security.KeyFactory.getInstance("EC").generatePrivate(
                new java.security.spec.ECPrivateKeySpec(new java.math.BigInteger(field(json, "s1", "phone_priv_hex"), 16), params));
        String s1 = field(json, "s1", "sealed"), s1plain = field(json, "s1", "plain");
        final String[] seen = new String[2];
        String opened = BeingRules.reply(200, "{\"ok\":true,\"op\":\"note.get\",\"s1\":\"" + s1 + "\"}", (kind, token) -> {
            seen[0] = kind; seen[1] = Seal.open(phone, params, token);
            return "{\"ok\":true,\"op\":\"note.get\",\"text\":\"A note\"}";
        });
        check("s1".equals(seen[0]) && s1plain.equals(seen[1]), "an s1 answer is opened with this phone's own key");
        check(opened.equals("{\"ok\":true,\"op\":\"note.get\",\"text\":\"A note\"}"), "and the page gets what it says");
        String stranger = BeingRules.reply(200, "{\"ok\":true,\"s1\":\"" + s1 + "\"}", (kind, token) -> Seal.open(other.getPrivate(), params, token));
        check(stranger.contains("\"ok\":false") && stranger.contains("couldn't be opened"), "one sealed for another phone isn't");
        String k1reply = BeingRules.reply(200, "{\"ok\":true,\"op\":\"module\",\"k1\":\"" + Crypto.seal(key, "{\"ok\":true,\"op\":\"module\",\"id\":\"quiz\",\"on\":true}") + "\"}",
                (kind, token) -> "k1".equals(kind) ? Crypto.open(key, token) : null);
        check(k1reply.contains("\"id\":\"quiz\"") && k1reply.contains("\"on\":true"), "a k1 answer (an older computer) opens with the chat's key");

        // no answer: said plainly
        check(BeingRules.reply(-1, "", null).contains("Couldn't reach your call line"), "no network");
        check(BeingRules.reply(503, "{\"ok\":false,\"offline\":true,\"note\":\"x\"}", null).contains("\"offline\":true")
                && BeingRules.reply(503, "", null).contains(BeingRules.OFF), "the computer off: try again when it's on");
        check(BeingRules.reply(200, "{\"ok\":true,\"queued\":true,\"note\":\"waits\"}", null).contains(BeingRules.OFF),
                "an older call line that would keep it for later: still 'off', never queued as done");
        check(BeingRules.reply(404, "", null).contains("too old"), "a call line without the chat");
        String refused = BeingRules.reply(400, "{\"ok\":false,\"op\":\"voice.mute\",\"note\":\"This computer doesn't know that yet. Update Kurooto.\"}", null);
        check(refused.contains("Update Kurooto") && refused.startsWith("{"), "a refusal in words is passed on as it is");
        check(BeingRules.reply(500, "oops", null).contains("(500)"), "anything else: the code");
    }
}
