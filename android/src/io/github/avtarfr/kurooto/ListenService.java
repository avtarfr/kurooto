package io.github.avtarfr.kurooto;

import android.annotation.TargetApi;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Person;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.drawable.Icon;
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
 *   + "clear"    -> questions or messages dealt with elsewhere: take their notifications down
 *   tags "msg"   -> a question, approval or message, with ways to answer it (Inbox)
 *   tags "sealed" -> a reminder your call line sent while your computer was asleep, sealed for this phone alone
 *                   (Seal; the line can't read it): a normal notification. It also carries "stop", so an older
 *                   app ignores it.
 *   tags "chat"   -> a chat message from Kurooto (Chat): kept, and a notification unless the chat is open ("stop" too)
 *   tags "outbox" -> things this phone sent while your computer was off went through to it (Chat; "stop" too)
 *   anything else -> a normal notification
 */
public class ListenService extends Service {
    static final String CH_SERVICE = "service", CH_CALL = "calls_v2", CH_MSG = "messages", CH_ASK = "questions";
    static final int ID_SERVICE = 1, ID_CALL = 2, ID_SEALED = 8;
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

    /** A notification builder on every Android version (channels exist from 8.0), in Kurooto's colour. */
    @SuppressWarnings("deprecation")
    static Notification.Builder builder(Context c, String channel) {
        if (SDK >= 26) return Ui.tint(c, new Notification.Builder(c, channel));
        Notification.Builder b = new Notification.Builder(c);
        b.setPriority(CH_SERVICE.equals(channel) ? Notification.PRIORITY_MIN : Notification.PRIORITY_MAX);
        return Ui.tint(c, b);
    }

    static void channels(Context c) {
        if (SDK < 26) return;
        try {
            NotificationManager nm = c.getSystemService(NotificationManager.class);
            if (nm == null) return;
            try { nm.deleteNotificationChannel("calls"); } catch (Throwable ignored) {}
            NotificationChannel svc = new NotificationChannel(CH_SERVICE, "Listening for calls", NotificationManager.IMPORTANCE_MIN);
            svc.setShowBadge(false);
            NotificationChannel call = new NotificationChannel(CH_CALL, "Calls from Kurooto", NotificationManager.IMPORTANCE_HIGH);
            Uri ringtoneUri = android.provider.Settings.System.DEFAULT_RINGTONE_URI;
            try {
                Uri u = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
                if (u != null) ringtoneUri = u;
            } catch (Throwable ignored) {}
            AudioAttributes audioAttributes = new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build();
            call.setSound(ringtoneUri, audioAttributes);
            call.enableVibration(true);
            call.setVibrationPattern(new long[]{0, 800, 600, 800, 1600});
            call.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            NotificationChannel msg = new NotificationChannel(CH_MSG, "Messages", NotificationManager.IMPORTANCE_HIGH);
            NotificationChannel ask = new NotificationChannel(CH_ASK, "Questions and approvals", NotificationManager.IMPORTANCE_HIGH);
            ask.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
            nm.createNotificationChannel(svc);
            nm.createNotificationChannel(call);
            nm.createNotificationChannel(msg);
            nm.createNotificationChannel(ask);
        } catch (Throwable ignored) {
        }
    }

    @Override public void onCreate() {
        super.onCreate();
        instance = this;
        channels(this);
    }

    /** The quiet "listening" notification (it names your assistant). */
    private Notification listening() {
        return builder(this, CH_SERVICE)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(Prefs.assistant(this) + " can call you")
                .setContentText("Calls, questions and wake-up alarms come here")
                .setContentIntent(PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE))
                .setOngoing(true)
                .build();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        Notification n = listening();
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
            Line.sendSealKey(this); // so your computer can seal reminders for this phone (once; tried again on reconnects)
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
            // every message carries the assistant's current name: a rename on the computer shows up here
            if (Prefs.setAssistant(this, m.optString("assistant", ""))) repostListening();
            long sent = m.optLong("time", outer.optLong("time"));
            long ageSec = System.currentTimeMillis() / 1000 - sent;
            JSONArray tags = m.optJSONArray("tags");
            String tagStr = tags == null ? "" : tags.toString();
            String since = tagValue(tags, "since-");
            if (tagStr.contains("\"sealed\"")) {
                sealed(m);
                return;
            }
            if (tagStr.contains("\"chat\"")) {
                chat(m);
                return;
            }
            if (tagStr.contains("\"outbox\"")) {
                if (m.optString("dev").equals(Prefs.deviceId(this))) outboxDone(Chat.done(this, m.optJSONArray("done")));
                return;
            }
            if (tagStr.contains("\"clear\"")) {
                Inbox.cancel(this, m.optJSONArray("ids"));
                return;
            }
            if (tagStr.contains("\"stop\"")) {
                if (since.equals(ringingSince)) main.post(() -> { stopRing(); cancel(ID_CALL); });
                return;
            }
            String text = m.optString("message", ""), click = m.optString("click", "");
            if (tagStr.contains("\"call\"")) {
                boolean alarm = tagStr.contains("\"alarm\"");
                if (ageSec < (alarm ? 300 : 120) && !click.isEmpty()) main.post(() -> ring(text, click, since, alarm));
                else notifyPlain("Missed call", text, click);
            } else if (tagStr.contains("\"msg\"")) {
                Inbox.show(this, m);
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

    private void repostListening() {
        try { ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify(ID_SERVICE, listening()); } catch (Exception ignored) { }
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
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        boolean shown = false;
        if (SDK >= 31) { // Android's own incoming-call look; if this phone won't take it, the plain one below
            try {
                Notification.Builder b = ringNotice(reason, alarm, fullPi, ringMs);
                callStyle(b, alarm ? "Wake-up call" : Prefs.assistant(this), declinePi, answerPi);
                nm.notify(ID_CALL, b.addAction(new Notification.Action.Builder(null, alarm ? "Snooze" : "Later", laterPi).build()).build());
                shown = true;
            } catch (Exception ignored) { }
        }
        if (!shown) {
            Notification.Builder b = ringNotice(reason, alarm, fullPi, ringMs)
                    .setContentTitle(alarm ? "Wake-up call" : Prefs.assistant(this) + " is calling")
                    .setStyle(new Notification.BigTextStyle().bigText(reason));
            b.addAction(new Notification.Action.Builder(null, "Decline", declinePi).build())
                    .addAction(new Notification.Action.Builder(null, alarm ? "Snooze" : "Later", laterPi).build())
                    .addAction(new Notification.Action.Builder(null, "Answer", answerPi).build());
            nm.notify(ID_CALL, b.build());
        }
        ringingSince = since;
        startRing(alarm);
        main.postDelayed(() -> { if (since.equals(ringingSince)) { stopRing(); cancel(ID_CALL); } }, ringMs);
    }

    /** What every ringing notification has: the reason, full screen over the lock screen, ongoing until answered. */
    private Notification.Builder ringNotice(String reason, boolean alarm, PendingIntent fullPi, long ringMs) {
        Notification.Builder b = builder(this, CH_CALL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentText(reason)
                .setCategory(alarm ? Notification.CATEGORY_ALARM : Notification.CATEGORY_CALL)
                .setFullScreenIntent(fullPi, true)
                .setContentIntent(fullPi)
                .setOngoing(true)
                .setVisibility(Notification.VISIBILITY_PUBLIC);
        if (SDK >= 21) b.setPriority(Notification.PRIORITY_MAX);
        if (SDK >= 26) b.setTimeoutAfter(ringMs);
        return b;
    }

    /** Android 12+: the incoming-call style (who's calling, a red Decline and a green Answer; Later sits between). */
    @TargetApi(31)
    private void callStyle(Notification.Builder b, String who, PendingIntent declinePi, PendingIntent answerPi) {
        Person caller = new Person.Builder().setName(who).setImportant(true)
                .setIcon(Icon.createWithResource(this, R.drawable.ic_agent)).build();
        b.setStyle(Notification.CallStyle.forIncomingCall(caller, declinePi, answerPi));
    }

    /** Calls use your call ringtone; wake-up calls use the alarm tone on the alarm stream, so they ring on silent. */
    @SuppressWarnings("deprecation")
    private void startRing(boolean alarm) {
        stopRing();
        try {
            String chosen = Prefs.tone(this, alarm);
            int type = alarm ? RingtoneManager.TYPE_ALARM : RingtoneManager.TYPE_RINGTONE;
            Uri uri = null;
            try {
                uri = chosen.isEmpty() ? RingtoneManager.getActualDefaultRingtoneUri(this, type) : Uri.parse(chosen);
            } catch (Throwable ignored) {}
            if (uri == null) {
                try { uri = RingtoneManager.getDefaultUri(type); } catch (Throwable ignored) {}
            }
            if (uri == null) {
                uri = alarm ? android.provider.Settings.System.DEFAULT_ALARM_ALERT_URI : android.provider.Settings.System.DEFAULT_RINGTONE_URI;
            }
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
    /** A sealed reminder: only the copy for this phone opens (each paired phone gets its own). Shown once per id. */
    private void sealed(JSONObject m) {
        if (!m.optString("dev").equals(Prefs.deviceId(this))) return;
        java.security.KeyPair k = Prefs.sealKeys(this);
        if (k == null) return;
        String plain = Seal.open(k.getPrivate(), ((java.security.interfaces.ECPublicKey) k.getPublic()).getParams(), m.optString("sealed"));
        if (plain == null) return;
        try {
            JSONObject it = new JSONObject(plain);
            String text = it.optString("text", "");
            Notification n = builder(this, CH_MSG)
                    .setSmallIcon(R.drawable.ic_stat)
                    .setContentTitle(it.optString("title", Prefs.assistant(this)))
                    .setContentText(text)
                    .setStyle(new Notification.BigTextStyle().bigText(text))
                    .setCategory(Notification.CATEGORY_REMINDER)
                    .setContentIntent(PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE))
                    .setAutoCancel(true)
                    .build();
            ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify("sealed-" + it.optString("id"), ID_SEALED, n);
        } catch (Exception ignored) { }
    }

    /** A chat message from Kurooto: into the chat, and a notification that opens it (unless it's open already). */
    private void chat(JSONObject m) {
        try {
            JSONObject msg = new JSONObject().put("id", m.optString("id")).put("from", "kurooto").put("text", m.optString("message"))
                    .put("at", m.optLong("time")).put("re", m.optString("re")).put("reply", m.optBoolean("reply"))
                    .put("buttons", m.optJSONArray("buttons") == null ? new JSONArray() : m.optJSONArray("buttons"));
            if (m.optString("id").isEmpty()) return;
            Chat.put(this, msg);
            if (ChatActivity.visible) { new Thread(() -> Chat.sync(this)).start(); return; } // the whole text, in order
            chatNote(this, m.optString("id"), m.optString("message"), m.optJSONArray("buttons"), false);
        } catch (Exception ignored) { }
    }

    /** The chat's notification: Kurooto's newest message. A counting button under it ("+1") is an action there too,
     *  tapped like the chat's own button (Chat.tap: through the outbox while your computer is off). quiet: shown
     *  again after such a tap, without a sound. */
    static void chatNote(Context c, String id, String text, JSONArray buttons, boolean quiet) {
        int flags = PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT;
        Notification.Builder b = builder(c, CH_MSG)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(Prefs.assistant(c))
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setOnlyAlertOnce(quiet)
                .setContentIntent(PendingIntent.getActivity(c, 5, new Intent(c, ChatActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), flags))
                .setAutoCancel(true);
        for (int i = 0, n = 0; buttons != null && i < buttons.length() && n < 2; i++) {
            JSONObject x = buttons.optJSONObject(i);
            if (!Inbox.counts(x)) continue;
            Intent tap = new Intent(c, ActionReceiver.class).setAction(ActionReceiver.CHAT_TAP).putExtra("msg", id)
                    .putExtra("n", i).putExtra("label", x.optString("label")).putExtra("buttons", buttons.toString());
            b.addAction(new Notification.Action.Builder(null, x.optString("label"), PendingIntent.getBroadcast(c, (id + ":t" + i).hashCode(), tap, flags)).build());
            n++;
        }
        ((NotificationManager) c.getSystemService(NOTIFICATION_SERVICE)).notify("chat", ChatActivity.ID_NOTE, b.build());
    }

    /** Answers and files that waited on the call line reached your computer: say so quietly (chat messages just
     *  lose their "Waiting for your computer"). */
    private void outboxDone(JSONArray gone) {
        for (int i = 0; gone != null && i < gone.length(); i++) {
            JSONObject x = gone.optJSONObject(i);
            if (x == null || "chat".equals(x.optString("kind")) || "button".equals(x.optString("kind"))) continue;
            String what = ("file".equals(x.optString("kind")) ? "File: " : "Answer: ") + x.optString("label");
            String note = x.optString("note");
            Notification n = builder(this, CH_MSG)
                    .setSmallIcon(R.drawable.ic_stat)
                    .setContentTitle(x.optBoolean("ok", true) ? "Reached your computer" : "Your computer couldn't take it")
                    .setContentText(what)
                    .setStyle(new Notification.BigTextStyle().bigText(what + (note.isEmpty() ? "" : "\n" + note)))
                    .setOnlyAlertOnce(true)
                    .setAutoCancel(true)
                    .build();
            ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify("outbox-" + x.optString("oid"), ID_SEALED + 2, n);
        }
    }

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
