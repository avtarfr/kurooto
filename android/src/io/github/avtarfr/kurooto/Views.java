package io.github.avtarfr.kurooto;

import android.content.Context;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;

/**
 * Systems and the Notes map (0.7.0): this phone's copies of the dashboard's two drawings, from your computer through
 * your call line, sealed for this phone alone (ViewSeal, "v1"). Fetched from /view while ViewsActivity shows them and
 * kept in the app's private files (view-systems.json, view-notes.json), so the last copy shows with the computer
 * asleep or no network. While Systems is open the app says it's watching (/view/watch, every ~20 s), and your
 * computer sends a fresh copy every few seconds until it stops hearing that.
 * Stored: {"snap": the snapshot's JSON text, "rev", "at": when the call line got it, "computer": online/offline,
 * "off": turned off on your computer, "fetched": when this phone last asked (ms), "old": the call line is too old}.
 */
final class Views {
    private Views() { }

    static String file(String kind) { return "view-" + ("notes".equals(kind) || "brain".equals(kind) ? kind : "systems") + ".json"; } // brain: the Brain console (0.8.10)

    static synchronized JSONObject load(Context c, String kind) {
        try {
            FileInputStream in = c.openFileInput(file(kind));
            try {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buf = new byte[16384];
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

    static synchronized void save(Context c, String kind, JSONObject d) {
        try {
            FileOutputStream out = c.openFileOutput(file(kind), Context.MODE_PRIVATE);
            try { out.write(d.toString().getBytes(Crypto.UTF8)); } finally { out.close(); }
        } catch (Exception ignored) { }
    }

    /** Ask the call line for this phone's copy, open it and keep it. Returns what's kept now, with "reach": whether the
     *  call line answered. Call off the main thread. */
    static JSONObject fetch(Context c, String kind) {
        JSONObject d = load(c, kind);
        boolean reach = false;
        try {
            if (!Prefs.paired(c)) return d.put("reach", false);
            Line.sendSealKey(c); // the key the copies are sealed with (sent once per pairing; a failed send is retried)
            Net.Reply r = Net.request("GET", Prefs.url(c) + "/view?kind=" + kind, null, null, Prefs.device(c), 30000);
            d.put("fetched", System.currentTimeMillis());
            reach = r.code > 0;
            if (r.code == 404) { // a call line from before 0.7.0: your computer updates it at 05:10
                d.put("old", true);
            } else if (r.ok()) {
                JSONObject j = new JSONObject(r.body);
                d.remove("old");
                d.put("computer", j.optString("computer", ""));
                d.put("off", j.optBoolean("off"));
                JSONObject v = j.optJSONObject("view");
                if (v != null && v.optLong("rev") != d.optLong("rev", -1)) {
                    ViewSeal.Opened o = open(c, v.optString("key", ""), v.optString("data", ""));
                    if (o != null && kind.equals(o.kind)) {
                        new JSONObject(o.text); // it is what it says it is
                        d.put("snap", o.text).put("rev", o.rev).put("at", v.optString("at", ""));
                    }
                } else if (v == null && j.optBoolean("off")) { // turned off on your computer: nothing kept
                    d.remove("snap");
                    d.remove("rev");
                    d.remove("at");
                }
            }
            save(c, kind, d);
        } catch (Exception e) {
            save(c, kind, d);
        }
        try { d.put("reach", reach); } catch (Exception ignored) { }
        return d;
    }

    private static ViewSeal.Opened open(Context c, String head, String data) {
        java.security.KeyPair k = Prefs.sealKeys(c);
        if (k == null || head.isEmpty() || data.isEmpty()) return null;
        return ViewSeal.open(k.getPrivate(), ((java.security.interfaces.ECPublicKey) k.getPublic()).getParams(), head, B64.decode(data));
    }

    /** Systems is on screen: tell your computer (through the call line) to send it live. The call line's answer, or
     *  null if it couldn't be reached. Call off the main thread. */
    static JSONObject watch(Context c) {
        if (!Prefs.paired(c)) return null;
        Net.Reply r = Net.request("POST", Prefs.url(c) + "/view/watch", "{}".getBytes(Crypto.UTF8), "application/json", Prefs.device(c), 20000);
        if (r.code <= 0) return null;
        try { return new JSONObject(r.body); } catch (Exception e) { return new JSONObject(); }
    }

    static void forget(Context c) {
        c.deleteFile(file("systems"));
        c.deleteFile(file("notes"));
        c.deleteFile(file("brain"));
    }
}
