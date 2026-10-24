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

    /** The assistant's name, as your computer last said (it can be renamed there). True if it changed. */
    static boolean setAssistant(Context c, String name) {
        if (name == null || name.trim().isEmpty() || name.equals(assistant(c))) return false;
        sp(c).edit().putString("assistant", name.trim()).apply();
        return true;
    }
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
                .putLong("directSeq", 0) // a new line counts its messages from 0
                .putString("sealSent", "") // a new pairing is a new device on the call line: it needs the key again
                .apply();
        TalkWidget.refreshSoon(c);
    }

    static void forget(Context c) {
        sp(c).edit().remove("url").remove("device").remove("topic").remove("ntfyKey").remove("since").remove("sealSent")
                .remove("widgetLine").remove("noteDraft").remove("directSeq").remove("seenIds").apply();
        Chat.forget(c); // the chat and what waited belong to that line
        Today.forget(c); // ... and so do the Today list and the alarms it set here
        Views.forget(c); // ... and the copies of Systems and the Notes map
        Alarms.cancel(c);
        TalkWidget.draw(c);
    }

    /** This phone's id on the call line (the "<id>" in its key "d1.<id>.<secret>"), or "". */
    static String deviceId(Context c) {
        String[] p = device(c).split("\\.");
        return p.length == 3 ? p[1] : "";
    }

    /** This phone's own key pair for sealed reminders (Seal), made the first time it's needed. The private half
     *  stays here; the call line gets the public half (Line.sendSealKey). Null if this phone can't make one. */
    static synchronized java.security.KeyPair sealKeys(Context c) {
        try {
            String priv = sp(c).getString("sealPriv", ""), pub = sp(c).getString("sealPub", "");
            java.security.KeyFactory f = java.security.KeyFactory.getInstance("EC");
            if (!priv.isEmpty() && !pub.isEmpty()) {
                return new java.security.KeyPair(f.generatePublic(new java.security.spec.X509EncodedKeySpec(B64.decode(pub))),
                        f.generatePrivate(new java.security.spec.PKCS8EncodedKeySpec(B64.decode(priv))));
            }
            java.security.KeyPair k = Seal.newKeys();
            sp(c).edit().putString("sealPriv", B64.encode(k.getPrivate().getEncoded(), false))
                    .putString("sealPub", B64.encode(k.getPublic().getEncoded(), false)).putString("sealSent", "").apply();
            return k;
        } catch (Exception e) {
            return null;
        }
    }

    /** The public key the call line has for this phone (base64url, 65 bytes), or "" until it has one. */
    static String sealSent(Context c) { return sp(c).getString("sealSent", ""); }
    static void setSealSent(Context c, String raw) { sp(c).edit().putString("sealSent", raw).apply(); }

    static String since(Context c) { return sp(c).getString("since", ""); }

    /** The last message number this phone had on its own connection to the line (Direct, 0.7.0). */
    static long directSeq(Context c) { return sp(c).getLong("directSeq", 0); }
    static void setDirectSeq(Context c, long seq) { sp(c).edit().putLong("directSeq", seq).apply(); }

    /** True the first time a message id comes (from the line's own connection or from ntfy), false for a second
     *  copy (LinkRules.seen). */
    static synchronized boolean firstTime(Context c, String mid) {
        String now = LinkRules.seen(sp(c).getString("seenIds", ""), mid, LinkRules.SEEN_MAX);
        if (now == null) return false;
        if (mid != null && !mid.isEmpty()) sp(c).edit().putString("seenIds", now).apply();
        return true;
    }
    static void setSince(Context c, String id) { sp(c).edit().putString("since", id).apply(); }

    /** Chosen ringtones (content URIs as strings; empty = the phone's default). */
    static String tone(Context c, boolean alarm) { return sp(c).getString(alarm ? "alarmTone" : "callTone", ""); }
    static void setTone(Context c, boolean alarm, String uri) { sp(c).edit().putString(alarm ? "alarmTone" : "callTone", uri == null ? "" : uri).apply(); }

    /** What the 2x1 widget says is waiting for you ("" until it has looked). */
    static String widgetLine(Context c) { return sp(c).getString("widgetLine", ""); }
    static void setWidgetLine(Context c, String s) { sp(c).edit().putString("widgetLine", s).apply(); }

    /** A quick note that wasn't sent yet (kept until it is). */
    static String noteDraft(Context c) { return sp(c).getString("noteDraft", ""); }
    static void setNoteDraft(Context c, String s) { sp(c).edit().putString("noteDraft", s == null ? "" : s).apply(); }

    /** Bedside mode (0.6.0): open by itself while charging between these hours ("HH:MM"; off by default), and keep
     *  the screen on while it's charging (on by default). */
    static boolean bedsideAuto(Context c) { return sp(c).getBoolean("bedsideAuto", false); }
    static String bedsideFrom(Context c) { return sp(c).getString("bedsideFrom", "22:00"); }
    static String bedsideTo(Context c) { return sp(c).getString("bedsideTo", "07:00"); }
    static boolean bedsideKeepOn(Context c) { return sp(c).getBoolean("bedsideKeepOn", true); }
    static void setBedside(Context c, boolean auto, String from, String to) {
        sp(c).edit().putBoolean("bedsideAuto", auto).putString("bedsideFrom", from).putString("bedsideTo", to).apply();
    }
    static void setBedsideKeepOn(Context c, boolean on) { sp(c).edit().putBoolean("bedsideKeepOn", on).apply(); }

    // Systems or the Notes map: the one the Views tab opens on (ViewsActivity)
    static String viewMode(Context c) { return sp(c).getString("viewMode", "systems"); }
    static void setViewMode(Context c, String mode) { sp(c).edit().putString("viewMode", mode).apply(); }

    static long lastUpdateCheck(Context c) { return sp(c).getLong("updateCheck", 0); }
    static void setUpdate(Context c, String name, String link) {
        sp(c).edit().putLong("updateCheck", System.currentTimeMillis()).putString("updateName", name).putString("updateLink", link).apply();
    }
}
