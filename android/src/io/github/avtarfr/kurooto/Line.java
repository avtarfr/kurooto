package io.github.avtarfr.kurooto;

import android.content.Context;
import android.net.Uri;
import android.os.Build;

import org.json.JSONObject;

import java.io.InputStream;
import java.net.URLEncoder;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.UUID;

/** Talking to your call line (the Cloudflare Worker Kurooto made for you), with this phone's own key. */
final class Line {
    private Line() { }

    /** What a pairing link carries: the line's address and the one-time code. */
    static final class Pairing {
        final String url, code;
        Pairing(String url, String code) { this.url = url; this.code = code; }
    }

    /** kurooto://pair?c=CODE&u=https://line, or https://line/pair#c=CODE (pasted), or null. */
    static Pairing parse(String text) {
        if (text == null) return null;
        text = text.trim();
        try {
            Uri u = Uri.parse(text);
            if ("kurooto".equals(u.getScheme())) {
                String c = u.getQueryParameter("c"), url = u.getQueryParameter("u");
                return c != null && url != null && url.startsWith("https://") ? new Pairing(url, c) : null;
            }
            if ("https".equals(u.getScheme()) && u.getPath() != null && u.getPath().startsWith("/pair")) {
                String frag = u.getEncodedFragment() == null ? "" : u.getEncodedFragment();
                String c = u.getQueryParameter("c");
                for (String part : frag.split("&")) if (part.startsWith("c=")) c = part.substring(2);
                return c == null ? null : new Pairing("https://" + u.getHost(), c);
            }
        } catch (Exception ignored) { }
        return null;
    }

    /** Trade the one-time code for this phone's key. Returns null on success, else what went wrong. */
    static String claim(Context c, Pairing p) {
        try {
            JSONObject body = new JSONObject().put("code", p.code).put("kind", "android").put("name", Build.MANUFACTURER + " " + Build.MODEL);
            Net.Reply r = Net.postJson(p.url + "/pair/claim", body.toString(), null);
            if (r.code == -1) return "Couldn't reach your call line. Is this phone online?";
            JSONObject j = new JSONObject(r.body.isEmpty() ? "{}" : r.body);
            if (!r.ok()) return j.optString("error", "Pairing failed (" + r.code + ").");
            if (j.optJSONObject("ntfy") == null) return "The call line didn't send the ringing details.";
            if (!j.has("url")) j.put("url", p.url);
            Prefs.savePairing(c, j);
            return null;
        } catch (Exception e) {
            return "Pairing failed: " + e.getMessage();
        }
    }

    /** A fresh call link (2 hours), with this computer on or off. Null if the line can't be reached. */
    static String callLink(Context c) {
        Net.Reply r = Net.postJson(Prefs.url(c) + "/app-call", "{}", Prefs.device(c));
        try { return r.ok() ? new JSONObject(r.body).optString("link", null) : null; } catch (Exception e) { return null; }
    }

    /** Give the call line this phone's public key for sealed reminders (once per pairing, and again if it changes).
     *  True when the line has it; an older line that doesn't know it answers 404, and this is tried again later. */
    static boolean sendSealKey(Context c) {
        java.security.KeyPair k = Prefs.sealKeys(c);
        if (k == null || !Prefs.paired(c)) return false;
        String raw = B64.encode(Seal.raw((java.security.interfaces.ECPublicKey) k.getPublic()), true);
        if (raw.equals(Prefs.sealSent(c))) return true;
        try {
            Net.Reply r = Net.postJson(Prefs.url(c) + "/device/key", new JSONObject().put("pub", raw).toString(), Prefs.device(c));
            if (!r.ok()) return false;
            Prefs.setSealSent(c, raw);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /** Decline / Later on a ringing call. */
    static boolean ringReply(Context c, String since, String action) {
        try {
            String body = new JSONObject().put("since", since).put("action", action).toString();
            return Net.postJson(Prefs.url(c) + "/ring-reply", body, Prefs.device(c)).ok();
        } catch (Exception e) {
            return false;
        }
    }

    /** What happened to an answer: sent (or kept by the line until the computer is back), or why not. */
    static final class Answered {
        final int code;
        final boolean ok;
        final String note;
        Answered(int code, boolean ok, String note) { this.code = code; this.ok = ok; this.note = note; }
        boolean delivered() { return code >= 200 && code < 300; }
        boolean gone() { return code == 410; }
    }

    /** Answer a question, approval or message (fields: "answer", "button" or "dismiss"). The answer is sealed with
     *  this phone's ntfy key, so the call line only passes it on; a random nonce and the time make it single use. */
    static Answered answer(Context c, String item, JSONObject fields) {
        try {
            byte[] n = new byte[16];
            new SecureRandom().nextBytes(n);
            StringBuilder hex = new StringBuilder();
            for (byte x : n) hex.append(String.format(java.util.Locale.ROOT, "%02x", x & 0xff));
            fields.put("item", item).put("ts", System.currentTimeMillis()).put("n", hex.toString());
            String sealed = Crypto.seal(Prefs.key(c), fields.toString());
            if (sealed == null || Prefs.key(c).length == 0) return new Answered(0, false, "This phone has no key: pair it again.");
            String body = new JSONObject().put("item", item).put("k1", sealed).toString();
            Net.Reply r = Net.postJson(Prefs.url(c) + "/answer", body, Prefs.device(c));
            if (r.code == -1) return new Answered(-1, false, "Couldn't reach your call line. Is this phone online?");
            JSONObject j = new JSONObject(r.body.isEmpty() ? "{}" : r.body);
            String note = j.optString("note", j.optString("error", r.ok() ? "Sent." : "That didn't go through (" + r.code + ")."));
            if (j.optBoolean("queued")) Chat.waitFor(c, item, "answer", fields.optString("answer", fields.has("button") ? "a button" : "dismissed"));
            return new Answered(r.code, r.ok() && j.optBoolean("ok", true), note);
        } catch (Exception e) {
            return new Answered(0, false, "That didn't go through: " + e.getMessage());
        }
    }

    /** What's waiting for you (open questions, approvals, messages), from the call line; null if unreachable. */
    static org.json.JSONArray waiting(Context c) {
        Net.Reply r = Net.request("GET", Prefs.url(c) + "/pending", null, null, Prefs.device(c), 20000);
        try {
            if (!r.ok()) return null;
            JSONObject j = new JSONObject(r.body);
            Prefs.setAssistant(c, j.optString("assistant", "")); // renamed on the computer since pairing?
            return j.optJSONArray("items");
        } catch (Exception e) {
            return null;
        }
    }

    static final int NOT_SENT = 0, WAITING = 1, SENT = 2;

    /** Upload one file to your computer's notes inbox, in 512 KB parts, with this phone's key. With your computer
     *  off, the call line keeps it (the phone outbox, up to 20 MB) and the answer is WAITING. */
    static int upload(Context c, String name, InputStream in, String note) {
        try {
            byte[] all = Net.readAll(in);
            int size = 512 * 1024, parts = Math.max(1, (all.length + size - 1) / size);
            String id = UUID.randomUUID().toString().replace("-", "");
            boolean queued = false;
            for (int p = 0; p < parts; p++) {
                byte[] chunk = Arrays.copyOfRange(all, p * size, Math.min(all.length, (p + 1) * size));
                String url = Prefs.url(c) + "/upload?name=" + URLEncoder.encode(name, "UTF-8") + "&note=" + URLEncoder.encode(note == null ? "" : note, "UTF-8")
                        + "&id=" + id + "&part=" + p + "&parts=" + parts;
                Net.Reply r = Net.request("POST", url, chunk, "application/octet-stream", Prefs.device(c), 120000);
                if (!r.ok()) return NOT_SENT;
                queued |= r.body.contains("\"queued\":true");
            }
            if (queued) Chat.waitFor(c, id, "file", name);
            return queued ? WAITING : SENT;
        } catch (Exception e) {
            return NOT_SENT;
        } finally {
            try { in.close(); } catch (Exception ignored) { }
        }
    }
}
