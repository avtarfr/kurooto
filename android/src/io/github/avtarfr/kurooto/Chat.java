package io.github.avtarfr.kurooto;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.security.SecureRandom;

/**
 * The chat with Kurooto (ChatActivity), and the phone outbox: what this phone sent while your computer was off.
 * Kept in the app's private files (chat.json): the chat's messages (yours and Kurooto's, by id; the call line keeps
 * the last 50 too, and /chat?after=seq catches up), and what still waits on the call line for your computer
 * ("waiting": chat messages, answers, shared files), until the line says each went through (an ntfy "outbox"
 * message, or /chat's own waiting list).
 * What you type is sealed with the ntfy key (as answers are) with a random nonce and the time: single use.
 */
final class Chat {
    static final String FILE = "chat.json";
    static final int KEEP = 200;
    /** Called (on any thread) when the chat changed: ChatActivity re-draws. */
    static volatile Runnable listener;
    /** Whether your computer was on at the last look ("online", "offline" or "" unknown). */
    static volatile String computer = "";

    private Chat() { }

    static String newId() {
        byte[] b = new byte[8];
        new SecureRandom().nextBytes(b);
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format(java.util.Locale.ROOT, "%02x", x & 0xff));
        return s.toString();
    }

    // ---------- the store ----------
    static synchronized JSONObject load(Context c) {
        try {
            FileInputStream in = c.openFileInput(FILE);
            try {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                return new JSONObject(new String(out.toByteArray(), Crypto.UTF8));
            } finally {
                in.close();
            }
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    static synchronized void save(Context c, JSONObject d) {
        try {
            FileOutputStream out = c.openFileOutput(FILE, Context.MODE_PRIVATE);
            try { out.write(d.toString().getBytes(Crypto.UTF8)); } finally { out.close(); }
        } catch (Exception ignored) { }
        Runnable l = listener;
        if (l != null) l.run();
    }

    static JSONArray msgs(JSONObject d) {
        JSONArray a = d.optJSONArray("msgs");
        return a == null ? new JSONArray() : a;
    }

    static JSONArray waiting(JSONObject d) {
        JSONArray a = d.optJSONArray("waiting");
        return a == null ? new JSONArray() : a;
    }

    /** Add a message or update the one with its id (keeping this phone's own fields, like its state). */
    static synchronized void put(Context c, JSONObject m) {
        JSONObject d = load(c);
        JSONArray all = msgs(d), out = new JSONArray();
        boolean found = false;
        try {
            for (int i = 0; i < all.length(); i++) {
                JSONObject x = all.optJSONObject(i);
                if (x == null) continue;
                if (x.optString("id").equals(m.optString("id"))) {
                    java.util.Iterator<String> k = m.keys();
                    while (k.hasNext()) { String key = k.next(); x.put(key, m.get(key)); }
                    found = true;
                }
                out.put(x);
            }
            if (!found) out.put(m);
            while (out.length() > KEEP) out.remove(0);
            d.put("msgs", out);
        } catch (Exception ignored) { }
        save(c, d);
    }

    static synchronized void setState(Context c, String id, String state, String note) {
        try { put(c, new JSONObject().put("id", id).put("state", state).put("note", note == null ? "" : note)); } catch (Exception ignored) { }
    }

    /** Something this phone sent now waits on the call line (oid: the chat message's id, the question's item id,
     *  or the shared file's id). */
    static synchronized void waitFor(Context c, String oid, String kind, String label) {
        JSONObject d = load(c);
        JSONArray w = waiting(d);
        for (int i = 0; i < w.length(); i++) if (oid.equals(w.optJSONObject(i).optString("oid"))) return;
        try {
            w.put(new JSONObject().put("oid", oid).put("kind", kind).put("label", label).put("at", System.currentTimeMillis()));
            d.put("waiting", w);
        } catch (Exception ignored) { }
        save(c, d);
    }

    /** The call line says these went through to your computer: {oid, kind, ok, note}. Returns the ones that were
     *  waiting here, with their labels. */
    static synchronized JSONArray done(Context c, JSONArray done) {
        JSONObject d = load(c);
        JSONArray w = waiting(d), left = new JSONArray(), gone = new JSONArray();
        for (int i = 0; i < w.length(); i++) {
            JSONObject x = w.optJSONObject(i);
            if (x == null) continue;
            JSONObject hit = null;
            for (int j = 0; done != null && j < done.length(); j++) {
                JSONObject y = done.optJSONObject(j);
                if (y != null && x.optString("oid").equals(y.optString("oid"))) hit = y;
            }
            if (hit == null) { left.put(x); continue; }
            try { gone.put(new JSONObject(x.toString()).put("ok", hit.optBoolean("ok", true)).put("note", hit.optString("note"))); } catch (Exception ignored) { }
        }
        try { d.put("waiting", left); } catch (Exception ignored) { }
        save(c, d);
        for (int i = 0; i < gone.length(); i++) {
            JSONObject x = gone.optJSONObject(i);
            if ("chat".equals(x.optString("kind"))) setState(c, x.optString("oid"), "", "");
        }
        return gone;
    }

    // ---------- talking to the call line ----------
    /** What happened to something sent: delivered now, kept on the call line for your computer, or not sent. */
    static final class Sent {
        final boolean ok, queued;
        final String note;
        final JSONArray said;
        Sent(boolean ok, boolean queued, String note, JSONArray said) { this.ok = ok; this.queued = queued; this.note = note; this.said = said; }
    }

    private static Sent post(Context c, String id, JSONObject fields) {
        try {
            fields.put("id", id).put("ts", System.currentTimeMillis()).put("n", newId() + newId());
            String sealed = Crypto.seal(Prefs.key(c), fields.toString());
            if (sealed == null || Prefs.key(c).length == 0) return new Sent(false, false, "This phone has no key: pair it again.", null);
            String body = new JSONObject().put("id", id).put("k1", sealed).toString();
            Net.Reply r = Net.postJson(Prefs.url(c) + "/chat", body, Prefs.device(c));
            if (r.code == -1) return new Sent(false, false, "Couldn't reach your call line. Is this phone online?", null);
            if (r.code == 404) return new Sent(false, false, "Your call line doesn't have the chat yet: update Kurooto on your computer.", null);
            JSONObject j = new JSONObject(r.body.isEmpty() ? "{}" : r.body);
            boolean queued = j.optBoolean("queued");
            if (queued) computer = "offline";
            else if (r.ok()) computer = "online";
            String note = j.optString("note", j.optString("error", r.ok() ? "" : "That didn't go through (" + r.code + ")."));
            return new Sent(r.ok() && j.optBoolean("ok", true), queued, note, j.optJSONArray("said"));
        } catch (Exception e) {
            return new Sent(false, false, "That didn't go through: " + e.getMessage(), null);
        }
    }

    /** Send what you typed (to: the id of Kurooto's message it replies to, or ""). Call off the main thread. */
    static Sent send(Context c, String id, String text, String to) {
        try {
            JSONObject mine = new JSONObject().put("id", id).put("from", "you").put("text", text)
                    .put("at", System.currentTimeMillis() / 1000).put("state", "sending").put("note", "");
            if (to != null && !to.isEmpty()) mine.put("re", to);
            put(c, mine);
            JSONObject f = new JSONObject().put("text", text);
            if (to != null && !to.isEmpty()) f.put("to", to);
            Sent s = post(c, id, f);
            if (s.queued) { setState(c, id, "waiting", ""); waitFor(c, id, "chat", text); }
            else setState(c, id, s.ok ? "" : "failed", s.ok ? "" : s.note);
            for (int i = 0; s.said != null && i < s.said.length(); i++) put(c, s.said.getJSONObject(i));
            return s;
        } catch (Exception e) {
            setState(c, id, "failed", e.getMessage());
            return new Sent(false, false, "That didn't go through.", null);
        }
    }

    /** A button under one of Kurooto's messages (by its number: the data stays on your computer). */
    static Sent tap(Context c, String msgId, int n, String label) {
        try {
            String id = newId();
            Sent s = post(c, id, new JSONObject().put("button", n).put("msg", msgId));
            if (s.queued) waitFor(c, id, "button", label);
            return s;
        } catch (Exception e) {
            return new Sent(false, false, "That didn't go through.", null);
        }
    }

    /** Done or +1 on a deadline on the Today screen (Today): to your computer like a chat button (it does what that
     *  button on the deadline's Telegram message does), or kept on the call line till it's back. */
    static Sent today(Context c, String deadline, String act, String label) {
        try {
            String id = newId();
            Sent s = post(c, id, new JSONObject().put("today", new JSONObject().put("id", deadline).put("do", act)));
            if (s.queued) waitFor(c, id, "today", label);
            return s;
        } catch (Exception e) {
            return new Sent(false, false, "That didn't go through.", null);
        }
    }

    /** Catch up with the call line's copy of the chat, and what still waits there. False if it can't be reached. */
    static boolean sync(Context c) {
        JSONObject d = load(c);
        Net.Reply r = Net.request("GET", Prefs.url(c) + "/chat?after=" + d.optLong("seq", 0), null, null, Prefs.device(c), 20000);
        if (!r.ok()) return false;
        try {
            JSONObject j = new JSONObject(r.body);
            computer = j.optString("computer", "");
            Prefs.setAssistant(c, j.optString("assistant", ""));
            JSONArray in = j.optJSONArray("msgs");
            for (int i = 0; in != null && i < in.length(); i++) {
                JSONObject m = in.getJSONObject(i);
                if ("you".equals(m.optString("from"))) m.put("state", "").put("note", ""); // it reached your computer
                put(c, m);
            }
            d = load(c);
            d.put("seq", Math.max(d.optLong("seq", 0), j.optLong("seq", 0)));
            save(c, d);
            // anything this phone thinks is waiting that the line no longer holds went through
            JSONArray still = j.optJSONArray("waiting"), gone = new JSONArray(), w = waiting(d);
            for (int i = 0; still != null && i < w.length(); i++) {
                String oid = w.getJSONObject(i).optString("oid");
                boolean there = false;
                for (int k = 0; k < still.length(); k++) if (oid.equals(still.getJSONObject(k).optString("oid"))) there = true;
                if (!there) gone.put(new JSONObject().put("oid", oid).put("ok", true));
            }
            if (gone.length() > 0) done(c, gone);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    static void forget(Context c) {
        c.deleteFile(FILE);
    }
}
