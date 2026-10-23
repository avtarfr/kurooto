package io.github.avtarfr.kurooto;

import android.content.Context;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;

/**
 * The Today list (0.6.0): what your computer last sent for the day (classes and events, what's due, reminders, the
 * alarm, open threads), sealed for this phone alone with its own key (Seal, "s1": your call line keeps it but can't
 * read it). Fetched from the call line's /today when the app opens, when the call line nudges ("today" on ntfy), and
 * when the listening stream reconnects; kept in the app's private files (today.json) so it shows with no network. The
 * alarms in it go to this phone's own alarm (Alarms). What you tap on it goes through Chat.today.
 * Stored: {"list": the list or absent, "at": when the call line got it (ISO, UTC), "computer": online/offline,
 * "off": turned off on your computer, "fetched": when this phone last asked (ms), "old": the call line is too old}.
 */
final class Today {
    static final String FILE = "today.json";
    /** Called (on any thread) after a fetch: the screen re-draws. */
    static volatile Runnable listener;

    private Today() { }

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
    }

    static long fetchedAt(Context c) { return load(c).optLong("fetched", 0); }

    /** Ask the call line for this phone's copy, open it, keep it and set the alarms in it. False if the call line
     *  can't be reached (what was kept stays). Call off the main thread. */
    static boolean fetch(Context c) {
        if (!Prefs.paired(c)) return false;
        Net.Reply r = Net.request("GET", Prefs.url(c) + "/today", null, null, Prefs.device(c), 20000);
        JSONObject d = load(c);
        try {
            d.put("fetched", System.currentTimeMillis());
            if (r.code == 404) { // a call line from before 0.6.0: your computer updates it at 05:10
                d.put("old", true);
                save(c, d);
                return false;
            }
            if (!r.ok()) { save(c, d); return false; }
            JSONObject j = new JSONObject(r.body);
            d.remove("old");
            d.put("computer", j.optString("computer", ""));
            d.put("off", j.optBoolean("off"));
            String tok = j.isNull("today") ? "" : j.optString("today", "");
            JSONObject list = tok.isEmpty() ? null : open(c, tok);
            if (list != null) {
                d.put("list", list).put("at", j.optString("at", ""));
                Alarms.update(c, list.optJSONObject("alarm"));
            } else if (j.optBoolean("off")) { // turned off on your computer: nothing kept, no alarm set from it
                d.remove("list");
                d.remove("at");
                Alarms.update(c, null);
            }
            save(c, d);
        } catch (Exception e) {
            save(c, d);
            return false;
        } finally {
            Runnable l = listener;
            if (l != null) l.run();
        }
        return true;
    }

    private static JSONObject open(Context c, String token) {
        java.security.KeyPair k = Prefs.sealKeys(c);
        if (k == null) return null;
        String plain = Seal.open(k.getPrivate(), ((java.security.interfaces.ECPublicKey) k.getPublic()).getParams(), token);
        try { return plain == null ? null : new JSONObject(plain); } catch (Exception e) { return null; }
    }

    /** Done or +1 on a deadline (act "done" or "+1"). */
    static Chat.Sent act(Context c, String deadline, String act, String label) {
        return Chat.today(c, deadline, act, label);
    }

    static void forget(Context c) { c.deleteFile(FILE); }
}
