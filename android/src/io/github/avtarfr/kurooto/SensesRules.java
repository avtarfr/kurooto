package io.github.avtarfr.kurooto;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** The plain rules behind the phone's senses (0.8.0), kept free of Android so the JVM tests can run them: what a
 *  reading becomes (a bin: sensor, time, fields), the motion state from steps and shaking, the light band, and the
 *  salted hash of a Wi-Fi name. Nothing here reads a sensor; Senses does, and hands numbers to these. */
final class SensesRules {
    static final String[] SENSORS = {"screen", "charging", "motion", "steps", "light", "places", "headphones", "dnd", "alarm", "wifi", "usage"};
    static final long BIN_MS = 5 * 60_000L;
    static final double SHAKE_WALK = 1.2;   // accelerometer standard deviation (m/s2) that, with steps, means walking
    static final double SHAKE_VEHICLE = 0.25; // a steady low shake with no steps: in a vehicle
    static final double SHAKE_STILL = 0.08;
    static final float DARK_LUX = 10, DIM_LUX = 100;

    private SensesRules() { }

    static boolean known(String sensor) {
        for (String s : SENSORS) if (s.equals(sensor)) return true;
        return false;
    }

    /** The start of the 5-minute bin a time falls in. */
    static long bin(long ms) { return ms - (ms % BIN_MS); }

    /** still, walking or vehicle, from the steps counted in the sample window and the accelerometer's spread. */
    static String motion(int steps, double shake) {
        if (steps >= 3 && shake >= SHAKE_STILL) return "walking";
        if (steps < 3 && shake >= SHAKE_VEHICLE && shake < SHAKE_WALK) return "vehicle";
        return "still";
    }

    /** dark, dim or bright from the ambient light in lux. */
    static String light(float lux) { return lux < DARK_LUX ? "dark" : lux < DIM_LUX ? "dim" : "bright"; }

    /** The standard deviation of a window of accelerometer magnitudes. */
    static double spread(double[] mags) {
        if (mags == null || mags.length < 2) return 0;
        double m = 0;
        for (double v : mags) m += v;
        m /= mags.length;
        double s = 0;
        for (double v : mags) s += (v - m) * (v - m);
        return Math.sqrt(s / mags.length);
    }

    /** A hash of the Wi-Fi name made with this phone's own random salt: it recognises a network, never names it. */
    static String wifiId(String salt, String ssid) {
        if (ssid == null || ssid.isEmpty() || ssid.equals("<unknown ssid>")) return "";
        try {
            MessageDigest d = MessageDigest.getInstance("SHA-256");
            byte[] h = d.digest((salt + "\u001f" + ssid).getBytes(StandardCharsets.UTF_8));
            StringBuilder b = new StringBuilder();
            for (int i = 0; i < 6; i++) b.append(String.format(Locale.ROOT, "%02x", h[i]));
            return b.toString();
        } catch (Exception e) {
            return "";
        }
    }

    /** One reading as the bin the computer takes: {"s": sensor, "t": ms, ...fields}, as JSON text. Fields are numbers or
     *  short words; a label is cut to 30 characters. Returns "" for an unknown sensor. */
    static String bin(String sensor, long ms, String[] keys, Object[] values) {
        if (!known(sensor) || keys.length != values.length) return "";
        StringBuilder b = new StringBuilder("{\"s\":\"").append(sensor).append("\",\"t\":").append(bin(ms));
        for (int i = 0; i < keys.length; i++) {
            b.append(",\"").append(keys[i]).append("\":");
            Object v = values[i];
            if (v instanceof Number) b.append(v);
            else b.append('"').append(String.valueOf(v).replaceAll("[\"\\\\\\p{Cntrl}]", " ").trim()).append('"');
        }
        return b.append('}').toString();
    }

    /** Readings kept until they're sent: the oldest are dropped past `max`, and a bin already there for the same sensor and
     *  time is replaced (a later reading of the same five minutes wins). */
    static List<String> keep(List<String> held, String bin, int max) {
        List<String> out = new ArrayList<>();
        String key = bin.replaceAll("^(\\{\"s\":\"[a-z]+\",\"t\":\\d+).*$", "$1");
        for (String x : held) if (!(x.startsWith(key + ",") || x.equals(key + "}"))) out.add(x);
        out.add(bin);
        while (out.size() > max) out.remove(0);
        return out;
    }
}
