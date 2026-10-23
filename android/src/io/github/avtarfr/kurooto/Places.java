package io.github.avtarfr.kurooto;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Location reminders (0.5.22), off by default: "remind me when I reach the library". You save places on this phone
 * (where you are now, with a name: no map), and each gets an Android proximity alert (LocationManager
 * .addProximityAlert: Android 6 and newer, no Google Play services). Arriving shows that place's reminders.
 *
 * Reminders come from Kurooto ("remind me when I reach the library to return the book" on Telegram or in the chat:
 * your computer sends the place's name and the text, a "place" message, and this phone keeps it) or are typed here.
 * They're kept by the place's name, so one for a place you haven't saved yet waits until you save it.
 * Where your places are never leaves this phone: your computer and the call line only ever see the names.
 *
 * Proximity alerts don't survive a restart or an app update, so App sets them again whenever the app starts.
 */
final class Places {
    static final String FILE = "places";
    static final String ACTION = "io.github.avtarfr.kurooto.PLACE";
    static final int NOTE_ID = 9;
    static final int SDK = Build.VERSION.SDK_INT;
    private static final Handler H = new Handler(Looper.getMainLooper());

    private Places() { }

    // ---------- the store (the app's private preferences) ----------
    private static SharedPreferences sp(Context c) { return c.getSharedPreferences(FILE, Context.MODE_PRIVATE); }

    static boolean on(Context c) { return sp(c).getBoolean("on", false); }

    static synchronized JSONArray places(Context c) { return arr(sp(c).getString("places", "[]")); }

    static synchronized JSONArray reminders(Context c) { return arr(sp(c).getString("reminders", "[]")); }

    private static JSONArray arr(String s) {
        try { return new JSONArray(s); } catch (Exception e) { return new JSONArray(); }
    }

    private static synchronized void put(Context c, String key, JSONArray a) { sp(c).edit().putString(key, a.toString()).apply(); }

    static JSONObject place(Context c, String id) {
        JSONArray ps = places(c);
        for (int i = 0; i < ps.length(); i++) if (id.equals(ps.optJSONObject(i).optString("id"))) return ps.optJSONObject(i);
        return null;
    }

    static JSONObject placeNamed(Context c, String name) {
        String k = PlaceRules.key(name);
        JSONArray ps = places(c);
        for (int i = 0; i < ps.length(); i++) if (k.equals(PlaceRules.key(ps.optJSONObject(i).optString("name")))) return ps.optJSONObject(i);
        return null;
    }

    /** The reminders for a place's name. */
    static JSONArray remindersFor(Context c, String name) {
        String k = PlaceRules.key(name);
        JSONArray all = reminders(c), out = new JSONArray();
        for (int i = 0; i < all.length(); i++) if (k.equals(all.optJSONObject(i).optString("place"))) out.put(all.optJSONObject(i));
        return out;
    }

    /** Reminders whose place isn't saved on this phone yet: {name: [reminder...]} in the order they came. */
    static JSONObject waiting(Context c) {
        JSONObject out = new JSONObject();
        JSONArray all = reminders(c);
        try {
            for (int i = 0; i < all.length(); i++) {
                JSONObject r = all.optJSONObject(i);
                if (placeNamed(c, r.optString("name", r.optString("place"))) != null) continue;
                String n = r.optString("name", r.optString("place"));
                if (!out.has(n)) out.put(n, new JSONArray());
                out.getJSONArray(n).put(r);
            }
        } catch (Exception ignored) { }
        return out;
    }

    static synchronized JSONObject addPlace(Context c, String name, double lat, double lon) {
        JSONObject p = placeNamed(c, name);
        JSONArray ps = places(c), out = new JSONArray();
        try {
            for (int i = 0; i < ps.length(); i++) if (p == null || !p.optString("id").equals(ps.optJSONObject(i).optString("id"))) out.put(ps.optJSONObject(i));
            JSONObject n = new JSONObject().put("id", p != null ? p.optString("id") : Chat.newId()).put("name", PlaceRules.name(name))
                    .put("lat", lat).put("lon", lon).put("r", PlaceRules.RADIUS_M).put("inside", true).put("last", 0);
            out.put(n); // saved where you stand: you're inside it, so it says its reminders the next time you arrive
            put(c, "places", out);
            if (on(c)) register(c, n);
            return n;
        } catch (Exception e) {
            return null;
        }
    }

    static synchronized void removePlace(Context c, String id) {
        JSONObject p = place(c, id);
        if (p == null) return;
        unregister(c, p);
        JSONArray ps = places(c), out = new JSONArray();
        for (int i = 0; i < ps.length(); i++) if (!id.equals(ps.optJSONObject(i).optString("id"))) out.put(ps.optJSONObject(i));
        put(c, "places", out);
        String k = PlaceRules.key(p.optString("name"));
        JSONArray rs = reminders(c), keep = new JSONArray();
        for (int i = 0; i < rs.length(); i++) if (!k.equals(rs.optJSONObject(i).optString("place"))) keep.put(rs.optJSONObject(i));
        put(c, "reminders", keep);
    }

    /** A reminder for a place (by name, saved or not): once (gone after it's said) or every time you arrive. */
    static synchronized JSONObject addReminder(Context c, String place, String text, boolean every, String from) {
        String t = text == null ? "" : text.trim();
        if (t.isEmpty() || PlaceRules.key(place).isEmpty()) return null;
        JSONArray rs = reminders(c);
        for (int i = 0; i < rs.length(); i++) { // the same one twice (a message seen again): kept once
            JSONObject r = rs.optJSONObject(i);
            if (r.optString("place").equals(PlaceRules.key(place)) && r.optString("text").equalsIgnoreCase(t)) return r;
        }
        try {
            JSONObject r = new JSONObject().put("id", Chat.newId()).put("place", PlaceRules.key(place)).put("name", PlaceRules.name(place))
                    .put("text", t.length() > 300 ? t.substring(0, 300) : t).put("every", every).put("from", from).put("at", System.currentTimeMillis());
            rs.put(r);
            put(c, "reminders", rs);
            return r;
        } catch (Exception e) {
            return null;
        }
    }

    static synchronized void removeReminder(Context c, String id) {
        JSONArray rs = reminders(c), out = new JSONArray();
        for (int i = 0; i < rs.length(); i++) if (!id.equals(rs.optJSONObject(i).optString("id"))) out.put(rs.optJSONObject(i));
        put(c, "reminders", out);
    }

    // ---------- permissions ----------
    static boolean permitted(Context c) {
        return c.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    /** Android 10+: location while the app is closed ("Allow all the time"); before that it comes with the above. */
    static boolean background(Context c) {
        return SDK < 29 || c.checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    // ---------- on and off ----------
    static void setOn(Context c, boolean on) {
        sp(c).edit().putBoolean("on", on).apply();
        JSONArray ps = places(c);
        for (int i = 0; i < ps.length(); i++) {
            if (on) register(c, ps.optJSONObject(i)); else unregister(c, ps.optJSONObject(i));
        }
    }

    /** Set every place's alert again (the app started: after a restart, an update, or the system stopped it). */
    static void restore(Context c) {
        try { if (on(c)) setOn(c, true); } catch (Exception ignored) { }
    }

    private static PendingIntent intent(Context c, JSONObject p, boolean create) {
        Intent i = new Intent(c, PlaceReceiver.class).setAction(ACTION)
                .setData(Uri.parse("kurooto-place:" + p.optString("id"))) // one alert per place
                .putExtra("place", p.optString("id"));
        int flags = (create ? PendingIntent.FLAG_UPDATE_CURRENT : PendingIntent.FLAG_NO_CREATE)
                | (SDK >= 31 ? PendingIntent.FLAG_MUTABLE : 0); // Android adds "entering" to it
        return PendingIntent.getBroadcast(c, p.optString("id").hashCode(), i, flags);
    }

    private static LocationManager lm(Context c) { return (LocationManager) c.getSystemService(Context.LOCATION_SERVICE); }

    @SuppressWarnings("MissingPermission")
    static boolean register(Context c, JSONObject p) {
        if (p == null || !permitted(c)) return false;
        try {
            lm(c).addProximityAlert(p.optDouble("lat"), p.optDouble("lon"), (float) p.optDouble("r", PlaceRules.RADIUS_M), -1, intent(c, p, true));
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @SuppressWarnings("MissingPermission")
    static void unregister(Context c, JSONObject p) {
        try {
            PendingIntent pi = intent(c, p, false);
            if (pi == null) return;
            if (permitted(c)) lm(c).removeProximityAlert(pi);
            pi.cancel();
        } catch (Exception ignored) { }
    }

    // ---------- arriving ----------
    /** Android says you came near a place (or left it). Says its reminders when you arrived from outside. */
    static synchronized void entered(Context c, String id, boolean entering) {
        if (!on(c)) return;
        JSONArray ps = places(c), out = new JSONArray();
        JSONObject hit = null;
        boolean fire = false;
        long now = System.currentTimeMillis();
        try {
            for (int i = 0; i < ps.length(); i++) {
                JSONObject p = ps.optJSONObject(i);
                if (id.equals(p.optString("id"))) {
                    fire = PlaceRules.fire(entering, p.optBoolean("inside"), now, p.optLong("last"));
                    p.put("inside", entering);
                    if (fire) p.put("last", now);
                    hit = p;
                }
                out.put(p);
            }
        } catch (Exception ignored) { }
        put(c, "places", out);
        if (!fire || hit == null) return;
        JSONArray rs = remindersFor(c, hit.optString("name"));
        if (rs.length() == 0) return;
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < rs.length(); i++) {
            JSONObject r = rs.optJSONObject(i);
            s.append(i > 0 ? "\n" : "").append(rs.length() > 1 ? "· " : "").append(r.optString("text"));
            if (!r.optBoolean("every")) removeReminder(c, r.optString("id")); // once: said, so gone
        }
        show(c, "At " + hit.optString("name"), s.toString(), "arrived:" + id);
    }

    // ---------- reminders from your computer ----------
    /** A "place" message from your computer (title: the place's name, message: what to remind you of; "place_every":
     *  every time you arrive). Kept here and
     *  taken off the call line's list; true when it was one. */
    static boolean adopt(final Context c, final JSONObject it) {
        String kind = it.optString("kind");
        if (!"place".equals(kind) && !"place_every".equals(kind)) return false;
        final String name = it.optString("title"), text = Inbox.text(it), id = it.optString("id");
        boolean seen = false;
        JSONArray have = remindersFor(c, name);
        for (int i = 0; i < have.length(); i++) seen |= have.optJSONObject(i).optString("text").equalsIgnoreCase(text.trim());
        JSONObject r = seen ? null : addReminder(c, name, text, "place_every".equals(kind), "kurooto");
        if (r != null) {
            boolean ready = on(c) && permitted(c) && placeNamed(c, name) != null;
            show(c, "When you reach " + PlaceRules.name(name), text + (ready ? "" : on(c)
                    ? "\n\n" + PlaceRules.name(name) + " isn't saved on this phone yet: open Kurooto → Places and save it when you're there."
                    : "\n\nLocation reminders are off on this phone: open Kurooto → Places to turn them on."), "kept:" + r.optString("id"));
        }
        if (!id.isEmpty()) new Thread(() -> {
            try { Line.answer(c, id, new JSONObject().put("dismiss", true)); } catch (Exception ignored) { }
        }).start();
        return true;
    }

    private static void show(Context c, String title, String body, String tag) {
        Intent open = new Intent(c, PlacesActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent pi = PendingIntent.getActivity(c, tag.hashCode(), open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = ListenService.builder(c, ListenService.CH_MSG)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setCategory(Notification.CATEGORY_REMINDER)
                .setContentIntent(pi)
                .setAutoCancel(true);
        ((NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE)).notify(tag, NOTE_ID, b.build());
    }

    // ---------- where you are now ----------
    interface Fix { void got(Location l, String why); }

    /** Where this phone is now, for saving a place: a fix accurate to 50 m, or the best within 30 seconds. On the
     *  main thread; `done` gets null and why when there's none. */
    @SuppressWarnings({"MissingPermission", "deprecation"})
    static void here(Context c, final Fix done) {
        if (!permitted(c)) { done.got(null, "Kurooto may not use this phone's location: turn location reminders on first."); return; }
        final LocationManager lm = lm(c);
        final Location[] best = {null};
        final boolean[] over = {false};
        for (String p : new String[]{LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
            try {
                Location l = lm.getLastKnownLocation(p);
                if (l != null && System.currentTimeMillis() - l.getTime() < 60_000 && better(l, best[0])) best[0] = l;
            } catch (Exception ignored) { }
        }
        if (best[0] != null && PlaceRules.goodFix(best[0].getAccuracy(), false)) { done.got(best[0], ""); return; }
        final LocationListener[] ll = new LocationListener[1];
        final Runnable finish = () -> {
            if (over[0]) return;
            over[0] = true;
            try { lm.removeUpdates(ll[0]); } catch (Exception ignored) { }
            if (best[0] != null && PlaceRules.goodFix(best[0].getAccuracy(), true)) done.got(best[0], "");
            else done.got(null, "Couldn't tell where this phone is. Is location on in the phone's settings? Outdoors or near a window works best.");
        };
        ll[0] = new LocationListener() {
            @Override public void onLocationChanged(Location l) {
                if (better(l, best[0])) best[0] = l;
                if (PlaceRules.goodFix(l.getAccuracy(), false)) finish.run();
            }
            @Override public void onStatusChanged(String p, int s, Bundle b) { }
            @Override public void onProviderEnabled(String p) { }
            @Override public void onProviderDisabled(String p) { }
        };
        boolean any = false;
        for (String p : new String[]{LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
            try {
                if (lm.isProviderEnabled(p)) { lm.requestLocationUpdates(p, 1000, 0, ll[0], Looper.getMainLooper()); any = true; }
            } catch (Exception ignored) { }
        }
        if (!any) { over[0] = true; done.got(null, "Location is off in the phone's settings: turn it on, then try again."); return; }
        H.postDelayed(finish, 30_000);
    }

    private static boolean better(Location l, Location than) {
        return l != null && (than == null || (l.hasAccuracy() && (!than.hasAccuracy() || l.getAccuracy() < than.getAccuracy())));
    }
}
