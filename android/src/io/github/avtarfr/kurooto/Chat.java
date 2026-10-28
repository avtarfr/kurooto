package io.github.avtarfr.kurooto;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.security.SecureRandom;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * The chat with Kurooto (ChatPane), and the phone outbox: what this phone sent while your computer was off.
 * Kept in the app's private files (chat.json): the chat's messages (yours and Kurooto's, by id, each in a session;
 * the call line keeps the last 50 per session too, and /chat?after=seq catches up), the sessions ("chats": the
 * computer's list, kept so the list shows with the computer off), the slash commands, how far you've read each
 * session, and what still waits on the call line for your computer ("waiting": chat messages, answers, shared files),
 * until the line says each went through (an ntfy "outbox" message, or /chat's own waiting list).
 * What you type is sealed with the ntfy key (as answers are) with a random nonce and the time: single use.
 * 0.8.10: sessions (`session` on every message; "main" is Kurooto's own and the one chats from before were in, so
 * those move there), replies to any message (`reply`, with `quote` back), files (`file`), and the session and message
 * ops (`op` with its `args`: session.new, session.rename, session.delete, session.pin, msg.edit, msg.delete, msg.pin,
 * read, sync; the answer carries the new session list or the changed message, applied here; 0.8.16: the list's read
 * marks, set on the dashboard or another phone, clear the unread counts here too). Pushes tagged "chat"
 * (a new message), "chat-update" (a change), "status" and "sessions" all come through [incoming].
 * Everything that talks to the call line runs in order on one thread ([IO]): a new chat's op before its first message.
 */
final class Chat {
    static final String FILE = "chat.json";
    static final String MAIN = ChatRules.MAIN;
    static final int KEEP = 1500, KEEP_SESSION = 300;
    /** Called (on any thread) when the chat changed: the Chat pane re-reads it (ChatStore). */
    static volatile Runnable listener;
    /** Whether your computer was on at the last look ("online", "offline" or "" unknown). */
    static volatile String computer = "";
    /** Sessions with an AI request running now (kind "status" from your computer): since when (ms). Not stored. */
    static final ConcurrentHashMap<String, Long> working = new ConcurrentHashMap<>();
    /** The chat's talking to the call line, one thing at a time and in order. */
    static final ExecutorService IO = Executors.newSingleThreadExecutor();
    /** Demo (debug and dev builds, `--ez demo true`): the store in memory, made up, and nothing sent anywhere. */
    static volatile JSONObject demo;

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
        JSONObject d;
        if (demo != null) {
            d = demo;
        } else {
            try {
                FileInputStream in = c.openFileInput(FILE);
                try {
                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                    d = new JSONObject(new String(out.toByteArray(), Crypto.UTF8));
                } finally {
                    in.close();
                }
            } catch (Exception e) {
                d = new JSONObject();
            }
        }
        migrate(d);
        return d;
    }

    /** Chats from before sessions (0.8.10) are the "main" session's: each message without one gets it. */
    static void migrate(JSONObject d) {
        if (d.optInt("v", 1) >= 2) return;
        JSONArray all = msgs(d);
        try {
            for (int i = 0; i < all.length(); i++) {
                JSONObject m = all.optJSONObject(i);
                if (m == null) continue;
                if (!ChatRules.isSession(m.optString("session"))) m.put("session", MAIN);
                if (!m.has("ln")) m.put("ln", i + 1);
            }
            d.put("ln", Math.max(d.optLong("ln", 0), all.length()));
            d.put("v", 2);
        } catch (Exception ignored) { }
    }

    static synchronized void save(Context c, JSONObject d) {
        if (demo != null) {
            demo = d;
        } else {
            try {
                FileOutputStream out = c.openFileOutput(FILE, Context.MODE_PRIVATE);
                try { out.write(d.toString().getBytes(Crypto.UTF8)); } finally { out.close(); }
            } catch (Exception ignored) { }
        }
        changed();
    }

    static void changed() {
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

    static JSONArray sessions(JSONObject d) {
        JSONArray a = d.optJSONArray("sessions");
        return a == null ? new JSONArray() : a;
    }

    static String sessionOf(JSONObject m) {
        String s = m == null ? "" : m.optString("session", "");
        return ChatRules.isSession(s) ? s : MAIN;
    }

    /** Add a message or update the one with its id (keeping this phone's own fields, like its state). */
    static void put(Context c, JSONObject m) {
        putAll(c, new JSONArray().put(m));
    }

    /** Add or update several at once (one read and one write of the store). A message deleted on this phone alone
     *  doesn't come back. Each new one gets the next local number ("ln": the order here, and how unread counts). */
    static synchronized void putAll(Context c, JSONArray in) {
        if (in == null || in.length() == 0) return;
        JSONObject d = load(c);
        JSONArray all = msgs(d);
        Map<String, JSONObject> byId = new HashMap<>();
        for (int i = 0; i < all.length(); i++) {
            JSONObject x = all.optJSONObject(i);
            if (x != null) byId.put(x.optString("id"), x);
        }
        Set<String> hidden = strings(d.optJSONArray("hidden"));
        long ln = d.optLong("ln", 0);
        try {
            for (int i = 0; i < in.length(); i++) {
                JSONObject m = in.optJSONObject(i);
                if (m == null || m.optString("id").isEmpty() || hidden.contains(m.optString("id"))) continue;
                JSONObject x = byId.get(m.optString("id"));
                if (x != null) {
                    Iterator<String> k = m.keys();
                    while (k.hasNext()) { String key = k.next(); x.put(key, m.get(key)); }
                    x.put("session", sessionOf(x));
                    continue;
                }
                m.put("session", sessionOf(m)).put("ln", ++ln);
                all.put(m);
                byId.put(m.optString("id"), m);
                touch(d, m);
            }
            d.put("ln", ln);
            d.put("msgs", trim(all));
        } catch (Exception ignored) { }
        Set<String> read = takeReadMarks(d); // a mark from your computer may name a message only now here
        save(c, d);
        clearNotes(c, d, read);
    }

    /** At most KEEP_SESSION per session and KEEP in all, the oldest going first. */
    private static JSONArray trim(JSONArray all) {
        if (all.length() <= KEEP_SESSION) return all;
        Map<String, Integer> left = new HashMap<>();
        boolean[] keep = new boolean[all.length()];
        int kept = 0;
        for (int i = all.length() - 1; i >= 0; i--) {
            JSONObject x = all.optJSONObject(i);
            if (x == null) continue;
            String s = sessionOf(x);
            int n = left.containsKey(s) ? left.get(s) : 0;
            if (n >= KEEP_SESSION || kept >= KEEP) continue;
            left.put(s, n + 1);
            keep[i] = true;
            kept++;
        }
        JSONArray out = new JSONArray();
        for (int i = 0; i < all.length(); i++) if (keep[i]) out.put(all.optJSONObject(i));
        return out;
    }

    /** A new message: its session's last line and time (the list shows them before your computer's own list comes). */
    private static void touch(JSONObject d, JSONObject m) throws Exception {
        String sid = sessionOf(m);
        JSONObject s = sessionIn(d, sid, true);
        String last = m.optBoolean("deleted") ? "" : m.optString("text");
        if (last.isEmpty() && m.optJSONObject("file") != null) last = fileWord(m.optJSONObject("file"));
        if ("you".equals(m.optString("from")) && !last.isEmpty()) last = "You: " + last;
        s.put("last", ChatRules.plain(last).replace('\n', ' '));
        s.put("updated", Math.max(s.optLong("updated", 0), m.optLong("at", System.currentTimeMillis() / 1000)));
    }

    static String fileWord(JSONObject f) {
        String mime = f.optString("mime");
        if (mime.startsWith("image/")) return "Photo";
        if (mime.startsWith("video/")) return "Video";
        if (mime.startsWith("audio/")) return "Voice note";
        return f.optString("name", "File");
    }

    /** The session with this id in the store (made, untitled, when `make` and it isn't there). */
    static JSONObject sessionIn(JSONObject d, String sid, boolean make) throws Exception {
        JSONArray ss = sessions(d);
        for (int i = 0; i < ss.length(); i++) {
            JSONObject s = ss.optJSONObject(i);
            if (s != null && sid.equals(s.optString("id"))) return s;
        }
        if (!make) return null;
        long now = System.currentTimeMillis() / 1000;
        JSONObject s = new JSONObject().put("id", sid).put("title", "").put("created", now).put("updated", now).put("pinned", MAIN.equals(sid)).put("last", "");
        ss.put(s);
        d.put("sessions", ss);
        return s;
    }

    private static Set<String> strings(JSONArray a) {
        Set<String> out = new HashSet<>();
        for (int i = 0; a != null && i < a.length(); i++) out.add(a.optString(i));
        return out;
    }

    static synchronized void setState(Context c, String id, String state, String note) {
        try { put(c, new JSONObject().put("id", id).put("state", state).put("note", note == null ? "" : note)); } catch (Exception ignored) { }
    }

    /** Your computer's list of sessions and the slash commands (kind "sessions"). Its list is the truth for the ones
     *  it knows; one made here a moment ago that it hasn't listed yet stays; one it no longer lists is gone (deleted
     *  on another phone), with its messages. This phone's own marks (archived) stay. */
    static void setSessions(Context c, JSONArray from, JSONArray commands) {
        setSessions(c, from, commands, null);
    }

    static synchronized void setSessions(Context c, JSONArray from, JSONArray commands, JSONObject switches) {
        JSONObject d = load(c);
        try {
            if (commands != null) d.put("commands", commands);
            if (switches != null) d.put("switches", switches);
            if (from != null) {
                Set<String> listed = new HashSet<>();
                JSONArray out = new JSONArray();
                for (int i = 0; i < from.length(); i++) {
                    JSONObject s = from.optJSONObject(i);
                    if (s == null || !ChatRules.isSession(s.optString("id"))) continue;
                    JSONObject had = sessionIn(d, s.optString("id"), false);
                    JSONObject n = new JSONObject(s.toString());
                    if (had != null && had.optLong("updated", 0) > n.optLong("updated", 0)) { // ours is newer: keep its last line
                        n.put("updated", had.optLong("updated")).put("last", had.optString("last"));
                    }
                    out.put(n);
                    listed.add(n.optString("id"));
                }
                long now = System.currentTimeMillis() / 1000;
                Set<String> gone = new HashSet<>();
                JSONArray ss = sessions(d);
                for (int i = 0; i < ss.length(); i++) {
                    JSONObject s = ss.optJSONObject(i);
                    if (s == null || listed.contains(s.optString("id"))) continue;
                    if (MAIN.equals(s.optString("id")) || now - s.optLong("created", 0) < 600) out.put(s);
                    else gone.add(s.optString("id"));
                }
                d.put("sessions", out);
                if (!gone.isEmpty()) dropSessions(d, gone);
            }
        } catch (Exception ignored) { }
        Set<String> read = takeReadMarks(d);
        save(c, d);
        clearNotes(c, d, read);
    }

    /** Your computer's read marks (each listed session's "read": the newest message read there, on the dashboard's
     *  Chat page or another phone) move this phone's own on (ChatRules.readMarks), so reading on either side clears
     *  the unread counts on both (0.8.16; before, the phone kept its own and ignored the computer's). Returns the
     *  sessions whose mark moved. */
    private static Set<String> takeReadMarks(JSONObject d) {
        Set<String> moved = new HashSet<>();
        try {
            Map<String, String> computer = new HashMap<>();
            JSONArray ss = sessions(d);
            for (int i = 0; i < ss.length(); i++) {
                JSONObject s = ss.optJSONObject(i);
                if (s != null && !s.optString("read").isEmpty()) computer.put(s.optString("id"), s.optString("read"));
            }
            if (computer.isEmpty()) return moved;
            JSONObject read = d.optJSONObject("read");
            if (read == null) read = new JSONObject();
            Map<String, Long> phone = new HashMap<>(), lnById = new HashMap<>();
            Map<String, String> sessionById = new HashMap<>();
            for (String sid : computer.keySet()) phone.put(sid, read.optLong(sid, 0));
            JSONArray all = msgs(d);
            for (int i = 0; i < all.length(); i++) {
                JSONObject x = all.optJSONObject(i);
                if (x == null || !computer.containsValue(x.optString("id"))) continue;
                lnById.put(x.optString("id"), x.optLong("ln"));
                sessionById.put(x.optString("id"), sessionOf(x));
            }
            Map<String, Long> next = ChatRules.readMarks(phone, computer, lnById, sessionById);
            if (next.isEmpty()) return moved;
            for (Map.Entry<String, Long> e : next.entrySet()) read.put(e.getKey(), (long) e.getValue());
            d.put("read", read);
            moved.addAll(next.keySet());
        } catch (Exception ignored) { }
        return moved;
    }

    /** A session read elsewhere with nothing of Kurooto's left unread here: its notification goes. */
    private static void clearNotes(Context c, JSONObject d, Set<String> sessions) {
        if (sessions.isEmpty() || demo != null) return;
        JSONObject read = d.optJSONObject("read");
        JSONArray all = msgs(d);
        for (String sid : sessions) {
            long upto = read == null ? 0 : read.optLong(sid, 0);
            boolean left = false;
            for (int i = 0; i < all.length() && !left; i++) {
                JSONObject x = all.optJSONObject(i);
                left = x != null && sid.equals(sessionOf(x)) && !"you".equals(x.optString("from")) && !x.optBoolean("deleted")
                        && x.optLong("ln") > upto;
            }
            if (!left) {
                try { ChatNotes.cancel(c, sid); } catch (Exception ignored) { }
            }
        }
    }

    private static void dropSessions(JSONObject d, Set<String> gone) throws Exception {
        JSONArray all = msgs(d), keep = new JSONArray();
        for (int i = 0; i < all.length(); i++) {
            JSONObject x = all.optJSONObject(i);
            if (x != null && !gone.contains(sessionOf(x))) keep.put(x);
        }
        d.put("msgs", keep);
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

    // ---------- this phone's own marks ----------
    /** How far you've read a session (the newest message's local number then): its unread count starts after it.
     *  Returns that number, or 0 when there was nothing new. */
    static synchronized long markRead(Context c, String sid) {
        JSONObject d = load(c);
        long top = 0, had;
        JSONArray all = msgs(d);
        for (int i = 0; i < all.length(); i++) {
            JSONObject x = all.optJSONObject(i);
            if (x != null && sid.equals(sessionOf(x))) top = Math.max(top, x.optLong("ln"));
        }
        try {
            JSONObject read = d.optJSONObject("read");
            if (read == null) read = new JSONObject();
            had = read.optLong(sid, 0);
            if (top <= had) return 0;
            read.put(sid, top);
            d.put("read", read);
        } catch (Exception e) {
            return 0;
        }
        save(c, d);
        return top;
    }

    /** Archive a session on this phone (the list's Archived; your computer keeps it as it was). */
    static synchronized void setArchived(Context c, String sid, boolean on) {
        JSONObject d = load(c);
        Set<String> a = strings(d.optJSONArray("archived"));
        if (on) a.add(sid); else a.remove(sid);
        try { d.put("archived", new JSONArray(a)); } catch (Exception ignored) { }
        save(c, d);
    }

    /** Change a session here (its title, pin), before your computer says so too. */
    static synchronized void setSession(Context c, String sid, String key, Object value) {
        JSONObject d = load(c);
        try { sessionIn(d, sid, true).put(key, value); } catch (Exception ignored) { }
        save(c, d);
    }

    /** A session goes from this phone, with its messages. */
    static synchronized void forgetSession(Context c, String sid) {
        JSONObject d = load(c);
        try {
            JSONArray ss = sessions(d), keep = new JSONArray();
            for (int i = 0; i < ss.length(); i++) if (!sid.equals(ss.optJSONObject(i).optString("id"))) keep.put(ss.optJSONObject(i));
            d.put("sessions", keep);
            Set<String> one = new HashSet<>();
            one.add(sid);
            dropSessions(d, one);
        } catch (Exception ignored) { }
        save(c, d);
    }

    /** A message goes from this phone only, and stays gone when the call line sends it again. */
    static synchronized void hide(Context c, String mid) {
        JSONObject d = load(c);
        try {
            JSONArray all = msgs(d), keep = new JSONArray();
            for (int i = 0; i < all.length(); i++) if (!mid.equals(all.optJSONObject(i).optString("id"))) keep.put(all.optJSONObject(i));
            d.put("msgs", keep);
            JSONArray h = d.optJSONArray("hidden");
            if (h == null) h = new JSONArray();
            h.put(mid);
            while (h.length() > 500) h.remove(0);
            d.put("hidden", h);
        } catch (Exception ignored) { }
        save(c, d);
    }

    // ---------- from your computer ----------
    /** One chat push from the call line (ntfy or the line's own connection, tag "chat"), opened. kind "status": a
     *  session's AI request started or ended (not stored); kind "sessions": the session list and the commands; else a
     *  message (new, or a change to one: edited, deleted, pinned). Returns the message when it's a new one of Kurooto's
     *  that a notification should show, else null. */
    static JSONObject incoming(Context c, JSONObject p) {
        try {
            String kind = p.optString("kind");
            if ("status".equals(kind)) {
                status(p);
                return null;
            }
            if ("sessions".equals(kind)) {
                // the list inline when it's small; else (and for the commands) fetch it
                if (p.optJSONArray("sessions") != null) setSessions(c, p.optJSONArray("sessions"), p.optJSONArray("commands"), p.optJSONObject("switches"));
                if (p.optJSONArray("sessions") == null || p.optJSONArray("commands") == null) new Thread(() -> sync(c)).start();
                return null;
            }
            String id = p.optString("id");
            if (id.isEmpty()) return null;
            JSONObject m = message(p);
            boolean known = has(c, id);
            put(c, m);
            if (known || !"kurooto".equals(m.optString("from")) || m.optBoolean("deleted")) return null;
            working.remove(sessionOf(m)); // an answer came: that session's request is done, or at least said something
            return m;
        } catch (Exception e) {
            return null;
        }
    }

    /** A push's fields as the store keeps a message (the push says "message" and "time" for "text" and "at"). */
    static JSONObject message(JSONObject p) throws Exception {
        JSONObject m = new JSONObject().put("id", p.optString("id")).put("from", p.optString("from", "kurooto"))
                .put("text", p.has("text") ? p.optString("text") : p.optString("message"))
                .put("at", p.optLong("at", p.optLong("time", System.currentTimeMillis() / 1000)))
                .put("session", sessionOf(p));
        for (String k : new String[] {"re", "reply", "buttons", "quote", "file", "edited", "deleted", "pinned", "title", "seq"}) {
            if (p.has(k)) m.put(k, p.get(k));
        }
        if (!m.has("buttons")) m.put("buttons", new JSONArray());
        if ("you".equals(m.optString("from"))) m.put("state", "").put("note", ""); // it reached your computer
        return m;
    }

    static void status(JSONObject p) {
        String sid = sessionOf(p);
        if ("working".equals(p.optString("state"))) working.put(sid, System.currentTimeMillis());
        else working.remove(sid);
        changed();
    }

    /** Whether a session's AI request runs now (a "working" that never got its "idle" counts for ten minutes). */
    static boolean isWorking(String sid) {
        Long t = working.get(sid);
        return t != null && System.currentTimeMillis() - t < 600_000;
    }

    static synchronized boolean has(Context c, String id) {
        return find(c, id) != null;
    }

    static synchronized JSONObject find(Context c, String id) {
        JSONArray all = msgs(load(c));
        for (int i = all.length() - 1; i >= 0; i--) {
            JSONObject x = all.optJSONObject(i);
            if (x != null && id.equals(x.optString("id"))) return x;
        }
        return null;
    }

    // ---------- talking to the call line ----------
    /** What happened to something sent: delivered now, kept on the call line for your computer, or not sent. */
    static final class Sent {
        final boolean ok, queued;
        final String note;
        final JSONArray said;
        /** The whole answer (an op's: its sessions, its changed message). */
        JSONObject body = new JSONObject();
        Sent(boolean ok, boolean queued, String note, JSONArray said) { this.ok = ok; this.queued = queued; this.note = note; this.said = said; }
    }

    /** Says what an op your computer refused, or anything else the chat should show (ChatPane sets it). */
    interface Say { void say(String text); }
    static volatile Say say;

    private static void tell(String text) {
        Say s = say;
        if (s != null && text != null && !text.isEmpty()) s.say(text);
    }

    private static Sent post(Context c, String id, JSONObject fields) {
        if (demo != null) return new Sent(true, false, "Demo: nothing was sent.", null);
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
            Sent s = new Sent(r.ok() && j.optBoolean("ok", true), queued, note, j.optJSONArray("said"));
            s.body = j;
            return s;
        } catch (Exception e) {
            return new Sent(false, false, "That didn't go through: " + e.getMessage(), null);
        }
    }

    /** The phone's senses, sealed like a chat message (Senses): 0 failed, 1 taken by your computer, 2 kept on the line. */
    static int sendSenses(Context c, String id, JSONArray bins) {
        try {
            Sent s = post(c, id, new JSONObject().put("senses", new JSONObject().put("bins", bins)));
            return s.queued ? 2 : s.ok ? 1 : 0;
        } catch (Exception e) {
            return 0;
        }
    }

    /** The ids of what this phone sent that the call line still holds for your computer, or null if the line can't be
     *  reached (Senses asks whether its last batch went through). Call off the main thread. */
    static java.util.List<String> lineWaiting(Context c) {
        if (demo != null) return new java.util.ArrayList<>();
        Net.Reply r = Net.request("GET", Prefs.url(c) + "/outbox", null, null, Prefs.device(c), 20000);
        if (!r.ok()) return null;
        try {
            JSONObject j = new JSONObject(r.body);
            if (!j.optString("computer").isEmpty()) computer = j.optString("computer");
            JSONArray w = j.optJSONArray("waiting");
            java.util.List<String> out = new java.util.ArrayList<>();
            for (int i = 0; w != null && i < w.length(); i++) out.add(w.getJSONObject(i).optString("oid"));
            return out;
        } catch (Exception e) {
            return null;
        }
    }

    /** Send what you typed in the "main" session (to: the id of Kurooto's message it replies to, or ""). Call off the
     *  main thread. */
    static Sent send(Context c, String id, String text, String to) {
        return send(c, MAIN, id, text, to, null);
    }

    /** Send a message in a session: `reply` the id of any message there it replies to (or ""), `file` the file it
     *  carries ({fid, name, mime, size}: uploaded first, ChatFiles) or null. Kept here first ("sending"), then
     *  "waiting" on the call line, "" once your computer has it, or "failed". Call off the main thread. */
    static Sent send(Context c, String session, String id, String text, String reply, JSONObject file) {
        String sid = ChatRules.isSession(session) ? session : MAIN;
        String said = text == null ? "" : text;
        try {
            JSONObject mine = find(c, id);
            if (mine == null) {
                mine = new JSONObject().put("id", id).put("from", "you").put("text", said).put("session", sid)
                        .put("at", System.currentTimeMillis() / 1000);
                if (reply != null && !reply.isEmpty()) {
                    mine.put("re", reply);
                    JSONObject q = find(c, reply);
                    if (q != null) mine.put("quote", quoteOf(q));
                }
                if (file != null) mine.put("file", file);
            }
            mine.put("state", "sending").put("note", "");
            put(c, mine);
            if (!said.trim().isEmpty() && untitled(c, sid)) setSession(c, sid, "title", ChatRules.title(said));
            JSONObject f = new JSONObject().put("text", said);
            if (!MAIN.equals(sid)) f.put("session", sid);
            if (reply != null && !reply.isEmpty()) {
                f.put("reply", reply);
                JSONObject q = find(c, reply);
                // Kurooto's message that takes a reply: "to" routes it to the feature that asked (as on Telegram, and as
                // computers before 0.8.10 understand it)
                if (q != null && "kurooto".equals(q.optString("from"))) f.put("to", reply);
            }
            if (file != null) {
                f.put("file", new JSONObject().put("fid", file.optString("fid")).put("name", file.optString("name"))
                        .put("mime", file.optString("mime")).put("size", file.optLong("size")));
                if (file.optBoolean("voice")) f.put("voice", true);
            }
            Sent s = post(c, id, f);
            String label = !said.isEmpty() ? said : file != null ? file.optString("name") : "";
            if (s.queued) { setState(c, id, "waiting", ""); waitFor(c, id, "chat", label); }
            else setState(c, id, s.ok ? "" : "failed", s.ok ? "" : s.note);
            if (s.said != null) {
                JSONArray back = new JSONArray();
                for (int i = 0; i < s.said.length(); i++) back.put(message(s.said.getJSONObject(i)));
                putAll(c, back);
            }
            return s;
        } catch (Exception e) {
            setState(c, id, "failed", e.getMessage());
            return new Sent(false, false, "That didn't go through.", null);
        }
    }

    static JSONObject quoteOf(JSONObject q) throws Exception {
        String t = q.optString("text");
        if (t.isEmpty() && q.optJSONObject("file") != null) t = fileWord(q.optJSONObject("file"));
        t = ChatRules.plain(t);
        return new JSONObject().put("id", q.optString("id")).put("from", q.optString("from")).put("text", t.length() > 200 ? t.substring(0, 200) : t);
    }

    private static synchronized boolean untitled(Context c, String sid) {
        if (MAIN.equals(sid)) return false;
        try {
            JSONObject s = sessionIn(load(c), sid, false);
            return s == null || s.optString("title").isEmpty();
        } catch (Exception e) {
            return false;
        }
    }

    /** A session or message op (the protocol's `op`): to your computer, or kept on the call line for it. */
    static Sent op(Context c, String op, JSONObject args) {
        try {
            Sent s = post(c, newId(), new JSONObject().put("op", op).put("args", args));
            JSONObject b = s.body;
            if (s.ok && !s.queued) {
                // the answer carries the result: the session list, or the changed message
                if (b.optJSONArray("sessions") != null) setSessions(c, b.optJSONArray("sessions"), b.optJSONArray("commands"), b.optJSONObject("switches"));
                if (b.optJSONObject("msg") != null) put(c, message(b.optJSONObject("msg")));
            } else if (!s.ok && !"read".equals(op) && !"sync".equals(op)) {
                tell(s.note.isEmpty() ? "Your computer didn't take that." : s.note);
            }
            return s;
        } catch (Exception e) {
            return new Sent(false, false, "That didn't go through.", null);
        }
    }

    /** (0.9.0) A one-way flag for your computer (bedside mode on or off): sealed like a message, never kept on the call
     *  line for later (stale by then), never a toast. True when your computer took it. Call off the main thread. */
    static boolean signal(Context c, String op, boolean on) {
        try {
            Sent s = post(c, newId(), new JSONObject().put("op", op).put("args", new JSONObject().put("on", on)));
            return s.ok && !s.queued;
        } catch (Exception e) {
            return false;
        }
    }

    /** A new chat: here at once (untitled till its first message), and on your computer. Returns its id. */
    static String newSession(Context c, String title) {
        String sid = newId();
        try {
            synchronized (Chat.class) {
                JSONObject d = load(c);
                sessionIn(d, sid, true).put("title", title == null ? "" : title);
                save(c, d);
            }
            JSONObject f = new JSONObject().put("session", sid);
            if (title != null && !title.isEmpty()) f.put("title", title);
            IO.execute(() -> op(c, "session.new", f));
        } catch (Exception ignored) { }
        return sid;
    }

    static void renameSession(Context c, String sid, String title) {
        setSession(c, sid, "title", title);
        IO.execute(() -> { try { op(c, "session.rename", new JSONObject().put("session", sid).put("title", title)); } catch (Exception ignored) { } });
    }

    static void pinSession(Context c, String sid, boolean on) {
        setSession(c, sid, "pinned", on);
        IO.execute(() -> { try { op(c, "session.pin", new JSONObject().put("session", sid).put("on", on)); } catch (Exception ignored) { } });
    }

    /** Delete a chat everywhere ("main", Kurooto's own, can't be). */
    static void deleteSession(Context c, String sid) {
        if (MAIN.equals(sid)) return;
        forgetSession(c, sid);
        IO.execute(() -> { try { op(c, "session.delete", new JSONObject().put("session", sid)); } catch (Exception ignored) { } });
    }

    /** Edit your own message (the last 15 minutes): the text changes and it's marked edited; Kurooto isn't asked again. */
    static void edit(Context c, String mid, String text) {
        try { put(c, new JSONObject().put("id", mid).put("text", text).put("edited", true)); } catch (Exception ignored) { }
        IO.execute(() -> { try { op(c, "msg.edit", new JSONObject().put("target", mid).put("text", text)); } catch (Exception ignored) { } });
    }

    /** Delete a message: from this phone only, or (yours) everywhere. */
    static void deleteMessage(Context c, String mid, boolean everywhere) {
        if (!everywhere) { hide(c, mid); return; }
        try { put(c, new JSONObject().put("id", mid).put("text", "").put("deleted", true).put("file", JSONObject.NULL)); } catch (Exception ignored) { }
        IO.execute(() -> { try { op(c, "msg.delete", new JSONObject().put("target", mid)); } catch (Exception ignored) { } });
    }

    static void pinMessage(Context c, String mid, boolean on) {
        try { put(c, new JSONObject().put("id", mid).put("pinned", on)); } catch (Exception ignored) { }
        IO.execute(() -> { try { op(c, "msg.pin", new JSONObject().put("target", mid).put("on", on)); } catch (Exception ignored) { } });
    }

    /** You've read a session: here, and your computer hears up to which message (when there was something new). */
    static void read(Context c, String sid) {
        new Thread(() -> { // here at once (the unread count goes), then to your computer in order with the rest
            if (markRead(c, sid) == 0) return;
            String upto = "";
            JSONArray all = msgs(load(c));
            for (int i = all.length() - 1; i >= 0; i--) {
                JSONObject x = all.optJSONObject(i);
                if (x != null && sid.equals(sessionOf(x))) { upto = x.optString("id"); break; }
            }
            final String last = upto;
            IO.execute(() -> { try { op(c, "read", new JSONObject().put("session", sid).put("upto", last)); } catch (Exception ignored) { } });
        }).start();
    }

    /** Ask your computer for the session list and the commands (they come as a "sessions" push). */
    static void askSessions(Context c) {
        IO.execute(() -> op(c, "sync", new JSONObject()));
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

    /** Catch up with the call line's copy of the chat (every session's), the session list it keeps, and what still
     *  waits there. False if it can't be reached. */
    static boolean sync(Context c) {
        if (demo != null) return true;
        JSONObject d = load(c);
        Net.Reply r = Net.request("GET", Prefs.url(c) + "/chat?after=" + d.optLong("seq", 0) + "&sessions=1", null, null, Prefs.device(c), 20000);
        if (!r.ok()) return false;
        try {
            JSONObject j = new JSONObject(r.body);
            computer = j.optString("computer", "");
            Prefs.setAssistant(c, j.optString("assistant", ""));
            JSONArray in = j.optJSONArray("msgs"), batch = new JSONArray();
            for (int i = 0; in != null && i < in.length(); i++) {
                JSONObject m = in.getJSONObject(i);
                String kind = m.optString("kind");
                if ("status".equals(kind)) status(m);
                else if ("sessions".equals(kind)) setSessions(c, m.optJSONArray("sessions"), m.optJSONArray("commands"));
                else batch.put(message(m));
            }
            putAll(c, batch);
            if (j.optJSONArray("sessions") != null || j.optJSONArray("commands") != null) {
                setSessions(c, j.optJSONArray("sessions"), j.optJSONArray("commands"), j.optJSONObject("switches"));
            }
            JSONObject st = j.optJSONObject("status"); // the chats with an AI request running now: {session: {state, job}}
            if (st != null) {
                working.clear();
                Iterator<String> k = st.keys();
                while (k.hasNext()) {
                    String sid = k.next();
                    JSONObject x = st.optJSONObject(sid);
                    if (x != null && "working".equals(x.optString("state"))) working.put(ChatRules.isSession(sid) ? sid : MAIN, System.currentTimeMillis());
                }
                changed();
            }
            synchronized (Chat.class) {
                d = load(c);
                d.put("seq", Math.max(d.optLong("seq", 0), j.optLong("seq", 0)));
                save(c, d);
            }
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
