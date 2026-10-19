package io.github.avtarfr.kurooto;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Keeps one HTTP stream open to your private ntfy topic (instant delivery, no Google services needed) and turns
 * your call line's messages into phone-call style rings. Every message is end-to-end encrypted ("k1.") with the
 * key from pairing; anything else on the topic is ignored.
 *   tags "call"  -> ringing full-screen call (Answer / Later / Decline), your ringtone + vibration
 *   + "alarm"    -> the wake-up call: alarm sound on the alarm stream (rings on silent), rings longer
 *   tags "stop"  -> the call was answered elsewhere (or ended): stop ringing
 *   anything else -> a normal notification
 */
public class ListenService extends Service {
    static final String CH_SERVICE = "service", CH_CALL = "calls", CH_MSG = "messages";
    static final int ID_SERVICE = 1, ID_CALL = 2;
    static final int SDK = Build.VERSION.SDK_INT;

    private static ListenService instance;
    private volatile boolean running;
    private Thread thread;
    private MediaPlayer player;
    private Vibrator vibrator;
    private String ringingSince = "";
    private final Handler main = new Handler(Looper.getMainLooper());

    static void start(Context c) {
        Intent i = new Intent(c, ListenService.class);
        if (SDK >= 26) c.startForegroundService(i); else c.startService(i);
    }

    static void stopRinging(Context c) {
        ListenService s = instance;
        if (s != null) s.main.post(s::stopRing);
        ((NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE)).cancel(ID_CALL);
    }

    /** A notification builder on every Android version (channels exist from 8.0). */
    @SuppressWarnings("deprecation")
    static Notification.Builder builder(Context c, String channel) {
        if (SDK >= 26) return new Notification.Builder(c, channel);
        Notification.Builder b = new Notification.Builder(c);
        b.setPriority(CH_SERVICE.equals(channel) ? Notification.PRIORITY_MIN : Notification.PRIORITY_MAX);
        return b;
    }

    static void channels(Context c) {
        if (SDK < 26) return;
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        NotificationChannel svc = new NotificationChannel(CH_SERVICE, "Listening for calls", NotificationManager.IMPORTANCE_MIN);
        svc.setShowBadge(false);
        NotificationChannel call = new NotificationChannel(CH_CALL, "Calls from Kurooto", NotificationManager.IMPORTANCE_HIGH);
        call.setSound(null, null); // the app plays the ringtone itself, looping
        call.enableVibration(false);
        call.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        call.setBypassDnd(true);
        NotificationChannel msg = new NotificationChannel(CH_MSG, "Messages", NotificationManager.IMPORTANCE_HIGH);
        nm.createNotificationChannel(svc);
        nm.createNotificationChannel(call);
        nm.createNotificationChannel(msg);
    }

    @Override public void onCreate() {
        super.onCreate();
        instance = this;
        channels(this);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        Notification n = builder(this, CH_SERVICE)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(Prefs.assistant(this) + " can call you")
                .setContentText("Calls and wake-up alarms ring here")
                .setContentIntent(PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE))
                .setOngoing(true)
                .build();
        if (SDK >= 34) startForeground(ID_SERVICE, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING);
        else startForeground(ID_SERVICE, n);
        if (!Prefs.paired(this)) { stopSelf(); return START_NOT_STICKY; }
        if (!running) {
            running = true;
            thread = new Thread(this::loop, "ntfy-stream");
            thread.start();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        running = false;
        if (thread != null) thread.interrupt();
        stopRing();
        instance = null;
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    // ---------- the stream ----------
    private void loop() {
        int backoff = 2;
        while (running) {
            String topic = Prefs.topic(this);
            if (topic.isEmpty() || !Prefs.paired(this)) { sleep(30); continue; }
            HttpURLConnection c = null;
            try {
                String since = Prefs.since(this);
                URL url = new URL(Prefs.ntfyServer(this) + "/" + topic + "/json" + (since.isEmpty() ? "?since=10m" : "?since=" + since));
                c = (HttpURLConnection) url.openConnection();
                c.setConnectTimeout(20000);
                c.setReadTimeout(120000); // ntfy sends a keepalive every ~45 s
                BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), Crypto.UTF8));
                try {
                    backoff = 2;
                    String line;
                    while (running && (line = r.readLine()) != null) handle(line);
                } finally {
                    r.close();
                }
            } catch (Exception e) {
                // network change, sleep, server restart: reconnect below
            } finally {
                if (c != null) c.disconnect();
            }
            sleep(backoff);
            backoff = Math.min(60, backoff * 2);
        }
    }

    private void handle(String line) {
        try {
            JSONObject outer = new JSONObject(line);
            if (!"message".equals(outer.optString("event"))) return;
            Prefs.setSince(this, outer.optString("id"));
            String plain = Crypto.open(Prefs.key(this), outer.optString("message", ""));
            if (plain == null) return; // not from your call line
            JSONObject m = new JSONObject(plain);
            long sent = m.optLong("time", outer.optLong("time"));
            long ageSec = System.currentTimeMillis() / 1000 - sent;
            JSONArray tags = m.optJSONArray("tags");
            String tagStr = tags == null ? "" : tags.toString();
            String since = tagValue(tags, "since-");
            if (tagStr.contains("\"stop\"")) {
                if (since.equals(ringingSince)) main.post(() -> { stopRing(); cancel(ID_CALL); });
                return;
            }
            String text = m.optString("message", ""), click = m.optString("click", "");
            if (tagStr.contains("\"call\"")) {
                boolean alarm = tagStr.contains("\"alarm\"");
                if (ageSec < (alarm ? 300 : 120) && !click.isEmpty()) main.post(() -> ring(text, click, since, alarm));
                else notifyPlain("Missed call", text, click);
            } else {
                notifyPlain(m.optString("title", Prefs.assistant(this)), text, click);
            }
        } catch (Exception ignored) { }
    }

    static String tagValue(JSONArray tags, String prefix) {
        if (tags == null) return "";
        for (int i = 0; i < tags.length(); i++) {
            String t = tags.optString(i);
            if (t.startsWith(prefix)) return t.substring(prefix.length());
        }
        return "";
    }

    private void cancel(int id) {
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(id);
    }

    // ---------- ringing ----------
    private void ring(String reason, String url, String since, boolean alarm) {
        int flags = PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT;
        Intent full = new Intent(this, CallActivity.class)
                .putExtra("url", url).putExtra("reason", reason).putExtra("ringing", true).putExtra("since", since).putExtra("alarm", alarm)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent fullPi = PendingIntent.getActivity(this, 1, full, flags);
        Intent answer = new Intent(full).putExtra("ringing", false);
        PendingIntent answerPi = PendingIntent.getActivity(this, 2, answer, flags);
        PendingIntent declinePi = PendingIntent.getBroadcast(this, 3,
                new Intent(this, ActionReceiver.class).setAction(ActionReceiver.DECLINE).putExtra("since", since), flags);
        PendingIntent laterPi = PendingIntent.getBroadcast(this, 4,
                new Intent(this, ActionReceiver.class).setAction(ActionReceiver.LATER).putExtra("since", since), flags);
        long ringMs = alarm ? 300000 : 60000;
        Notification.Builder b = builder(this, CH_CALL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(alarm ? "Wake-up call" : Prefs.assistant(this) + " is calling")
                .setContentText(reason)
                .setStyle(new Notification.BigTextStyle().bigText(reason))
                .setCategory(alarm ? Notification.CATEGORY_ALARM : Notification.CATEGORY_CALL)
                .setFullScreenIntent(fullPi, true)
                .setContentIntent(fullPi)
                .setOngoing(true)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .addAction(new Notification.Action.Builder(null, "Decline", declinePi).build())
                .addAction(new Notification.Action.Builder(null, alarm ? "Snooze" : "Later", laterPi).build())
                .addAction(new Notification.Action.Builder(null, "Answer", answerPi).build());
        if (SDK >= 26) b.setTimeoutAfter(ringMs);
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify(ID_CALL, b.build());
        ringingSince = since;
        startRing(alarm);
        main.postDelayed(() -> { if (since.equals(ringingSince)) { stopRing(); cancel(ID_CALL); } }, ringMs);
    }

    /** Calls use your call ringtone; wake-up calls use the alarm tone on the alarm stream, so they ring on silent. */
    @SuppressWarnings("deprecation")
    private void startRing(boolean alarm) {
        stopRing();
        try {
            String chosen = Prefs.tone(this, alarm);
            int type = alarm ? RingtoneManager.TYPE_ALARM : RingtoneManager.TYPE_RINGTONE;
            Uri uri = chosen.isEmpty() ? RingtoneManager.getActualDefaultRingtoneUri(this, type) : Uri.parse(chosen);
            if (uri == null) uri = RingtoneManager.getDefaultUri(type);
            player = new MediaPlayer();
            player.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(alarm ? AudioAttributes.USAGE_ALARM : AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
            player.setDataSource(this, uri);
            player.setLooping(true);
            player.prepare();
            player.start();
        } catch (Exception e) {
            player = null;
        }
        try {
            long[] pattern = {0, 800, 600, 800, 1600};
            if (SDK >= 31) vibrator = ((VibratorManager) getSystemService(VIBRATOR_MANAGER_SERVICE)).getDefaultVibrator();
            else vibrator = (Vibrator) getSystemService(VIBRATOR_SERVICE);
            if (SDK >= 26) vibrator.vibrate(VibrationEffect.createWaveform(pattern, 0));
            else vibrator.vibrate(pattern, 0);
        } catch (Exception ignored) { }
        try { // light up the screen if the full-screen intent is held back
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            PowerManager.WakeLock wl = pm.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP, "kurooto:ring");
            wl.acquire(10000);
        } catch (Exception ignored) { }
    }

    void stopRing() {
        ringingSince = "";
        if (player != null) { try { player.stop(); player.release(); } catch (Exception ignored) { } player = null; }
        if (vibrator != null) { try { vibrator.cancel(); } catch (Exception ignored) { } vibrator = null; }
    }

    // ---------- other messages ----------
    private void notifyPlain(String title, String text, String click) {
        Notification.Builder b = builder(this, CH_MSG)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setAutoCancel(true);
        if (!click.isEmpty()) {
            b.setContentIntent(PendingIntent.getActivity(this, (int) (System.nanoTime() & 0xffff),
                    new Intent(this, CallActivity.class).putExtra("url", click).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
        }
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify((int) (System.currentTimeMillis() & 0x7fffffff), b.build());
    }

    private static void sleep(int s) {
        try { Thread.sleep(s * 1000L); } catch (InterruptedException ignored) { }
    }
}
