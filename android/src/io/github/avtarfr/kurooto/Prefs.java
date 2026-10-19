package io.github.avtarfr.kurooto;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

/** What pairing gave this phone (the call line's address, this device's key, the ntfy topic and key), plus the
 *  stream position and your ringtones. Kept in the app's private storage only. */
final class Prefs {
    private Prefs() { }

    static SharedPreferences sp(Context c) {
        return c.getSharedPreferences("kurooto", Context.MODE_PRIVATE);
    }

    static boolean paired(Context c) { return !device(c).isEmpty() && !url(c).isEmpty(); }
    static String url(Context c) { return sp(c).getString("url", ""); }
    static String device(Context c) { return sp(c).getString("device", ""); }
    static String assistant(Context c) { return sp(c).getString("assistant", "Kurooto"); }
    static String ntfyServer(Context c) { return sp(c).getString("ntfyServer", "https://ntfy.sh"); }
    static String topic(Context c) { return sp(c).getString("topic", ""); }

    static byte[] key(Context c) {
        String k = sp(c).getString("ntfyKey", "");
        try { return k.isEmpty() ? new byte[0] : B64.decode(k); } catch (Exception e) { return new byte[0]; }
    }

    /** The call line's answer to /pair/claim. */
    static void savePairing(Context c, JSONObject r) {
        JSONObject n = r.optJSONObject("ntfy");
        sp(c).edit()
                .putString("url", r.optString("url", "").replaceAll("/+$", ""))
                .putString("device", r.optString("device", ""))
                .putString("assistant", r.optString("assistant", "Kurooto"))
                .putString("ntfyServer", n == null ? "https://ntfy.sh" : n.optString("server", "https://ntfy.sh").replaceAll("/+$", ""))
                .putString("topic", n == null ? "" : n.optString("topic", ""))
                .putString("ntfyKey", n == null ? "" : n.optString("key", ""))
                .putString("since", "")
                .apply();
    }

    static void forget(Context c) {
        sp(c).edit().remove("url").remove("device").remove("topic").remove("ntfyKey").remove("since").apply();
    }

    static String since(Context c) { return sp(c).getString("since", ""); }
    static void setSince(Context c, String id) { sp(c).edit().putString("since", id).apply(); }

    /** Chosen ringtones (content URIs as strings; empty = the phone's default). */
    static String tone(Context c, boolean alarm) { return sp(c).getString(alarm ? "alarmTone" : "callTone", ""); }
    static void setTone(Context c, boolean alarm, String uri) { sp(c).edit().putString(alarm ? "alarmTone" : "callTone", uri == null ? "" : uri).apply(); }

    static long lastUpdateCheck(Context c) { return sp(c).getLong("updateCheck", 0); }
    static void setUpdate(Context c, String name, String link) {
        sp(c).edit().putLong("updateCheck", System.currentTimeMillis()).putString("updateName", name).putString("updateLink", link).apply();
    }
}
