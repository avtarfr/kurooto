package io.github.avtarfr.kurooto;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;

import org.json.JSONObject;

import java.net.Socket;
import java.net.SocketTimeoutException;
import java.util.Collections;
import java.util.Random;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLSocket;

/** This phone's own connection to your call line (0.7.0): one WebSocket to <line>/phone with this phone's key, so
 *  rings, messages, chat and Today nudges come straight from the line, not through ntfy.sh (which limits each
 *  internet address; on a campus that address is shared). Each message is sealed exactly as on ntfy ("k1", the key
 *  from pairing) and carries an id ("mid"): ListenService.deliver drops a second copy, so a ring that comes both
 *  ways rings once. The ntfy stream stays on as the fallback (ListenService).
 *
 *  Staying connected: it says "ping" about every PING_S while the phone is awake, and a wake-up alarm (KEEP_MS,
 *  allowed in Doze, a few times an hour at most there) pings while it sleeps; the line answers "pong" without
 *  waking (so an idle connection costs nothing on Cloudflare's free plan). No answer within DEAD_MS: it connects
 *  again. Lost: again after 2 s doubling to 60 s, with jitter (LinkRules.backoffMs). A line from before 0.7.0
 *  answers 404 (and an unpaired phone 401/403): it waits OLD_MS before asking again, and ntfy carries everything. On
 *  each connection the line first sends what this phone missed since the last message number it had. */
final class Direct {
    static final long PING_MS = 60_000, DEAD_MS = 30_000, KEEP_MS = 4 * 60_000, OLD_MS = 30 * 60_000;
    static final int READ_MS = 20_000;

    interface Sink { void deliver(JSONObject m); }

    private final Context c;
    private final Sink sink;
    private final Random jitter = new Random();
    private volatile boolean running;
    private volatile WebSock ws;
    private volatile long pingAt, lastPing; // elapsedRealtime (counts sleep too): an unanswered ping, the last one
    private volatile boolean up;
    private Thread thread;

    Direct(Context c, Sink sink) {
        this.c = c.getApplicationContext();
        this.sink = sink;
    }

    boolean connected() { return up; }

    synchronized void start() {
        if (running) return;
        running = true;
        thread = new Thread(this::loop, "line-direct");
        thread.start();
        arm(c);
    }

    synchronized void stop() {
        running = false;
        WebSock w = ws;
        if (w != null) w.close();
        if (thread != null) thread.interrupt();
        disarm(c);
    }

    /** Called often (the reader's timeouts, every line on the ntfy stream, the wake-up alarm): ping when it's time,
     *  and give up on a connection whose ping went unanswered. Off the main thread. */
    void keepAlive() {
        WebSock w = ws;
        if (w == null) return;
        long now = SystemClock.elapsedRealtime();
        if (pingAt > 0 && now - pingAt > DEAD_MS) { w.close(); return; } // the reader sees it and connects again
        if (now - lastPing < PING_MS) return;
        try {
            lastPing = now;
            if (pingAt == 0) pingAt = now;
            w.sendText("ping");
        } catch (Exception e) {
            w.close();
        }
    }

    private void loop() {
        int fails = 0;
        while (running) {
            if (!Prefs.paired(c)) { pause(30_000); continue; }
            String[] t = LinkRules.target(Prefs.url(c), Prefs.directSeq(c));
            if (t == null) { pause(OLD_MS); continue; }
            WebSock w = null;
            try {
                w = connect(t);
                ws = w;
                up = true;
                fails = 0;
                pingAt = 0;
                lastPing = SystemClock.elapsedRealtime();
                new Thread(() -> { Line.sendSealKey(c); if (System.currentTimeMillis() - Today.fetchedAt(c) > 5 * 60_000) Today.fetch(c); }).start();
                w.timeout(READ_MS);
                while (running) {
                    String m;
                    try {
                        m = w.read();
                    } catch (SocketTimeoutException e) {
                        keepAlive();
                        continue;
                    }
                    pingAt = 0; // anything heard: it's alive
                    if (!m.isEmpty() && !"pong".equals(m)) take(m);
                    keepAlive();
                }
            } catch (WebSock.Refused e) {
                if (e.code == 404 || e.code == 401 || e.code == 403 || e.code == 426) { up = false; pause(OLD_MS); continue; }
                fails++;
            } catch (Exception e) {
                fails++; // network change, sleep, the line redeployed: below, then again
            } finally {
                up = false;
                ws = null;
                if (w != null) w.close();
            }
            if (running) pause(LinkRules.backoffMs(fails, jitter.nextDouble()));
        }
    }

    private WebSock connect(String[] t) throws Exception {
        String host = t[0];
        int port = Integer.parseInt(t[1]);
        Socket s;
        if ("tls".equals(t[3])) {
            // the app's own trust (Tls: ISRG Root X1 on Android before 7.1.1), and the name checked as HTTPS does
            SSLSocket ss = (SSLSocket) HttpsURLConnection.getDefaultSSLSocketFactory().createSocket(host, port);
            ss.setSoTimeout(20_000);
            ss.startHandshake();
            if (!HttpsURLConnection.getDefaultHostnameVerifier().verify(host, ss.getSession())) {
                ss.close();
                throw new java.io.IOException("the call line's certificate doesn't match");
            }
            s = ss;
        } else {
            s = new Socket(host, port);
        }
        s.setSoTimeout(20_000);
        String hostHeader = ("tls".equals(t[3]) ? port == 443 : port == 80) ? host : host + ":" + port;
        return WebSock.open(s, hostHeader, t[2], Collections.singletonMap("x-call-secret", Prefs.device(c)));
    }

    /** {"type": "hello", seq} first, then {seq, k1} for each message. */
    private void take(String text) {
        try {
            JSONObject j = new JSONObject(text);
            if ("hello".equals(j.optString("type"))) {
                if (j.optLong("seq") < Prefs.directSeq(c)) Prefs.setDirectSeq(c, j.optLong("seq")); // the line counts again
                return;
            }
            String plain = Crypto.open(Prefs.key(c), j.optString("k1", ""));
            if (plain != null) sink.deliver(new JSONObject(plain));
            long seq = j.optLong("seq");
            if (seq > Prefs.directSeq(c)) Prefs.setDirectSeq(c, seq);
        } catch (Exception ignored) { }
    }

    private void pause(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) { }
    }

    // ---------- the wake-up alarm that keeps it alive while the phone sleeps ----------
    private static PendingIntent keepIntent(Context c) {
        return PendingIntent.getBroadcast(c, 41, new Intent(c, ActionReceiver.class).setAction(ActionReceiver.KEEPALIVE),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    /** Inexact, allowed while idle: no exact-alarm permission needed, and Android spaces them out in Doze. */
    static void arm(Context c) {
        try {
            AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
            am.setAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + KEEP_MS, keepIntent(c));
        } catch (Exception ignored) { }
    }

    static void disarm(Context c) {
        try { ((AlarmManager) c.getSystemService(Context.ALARM_SERVICE)).cancel(keepIntent(c)); } catch (Exception ignored) { }
    }
}
