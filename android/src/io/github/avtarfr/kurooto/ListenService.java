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
import android.media.AudioManager;
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
 * Keeps this phone's own connection to your call line (Direct, 0.7.0: a WebSocket, no ntfy.sh in between) and,
 * as the fallback, one HTTP stream to your private ntfy topic (no Google services needed either way), and turns
 * your call line's messages into phone-call style rings. Every message is end-to-end encrypted ("k1.") with the
 * key from pairing; anything else on the topic is ignored. A message that comes both ways (a ring does) is taken
 * once, by its id ("mid": deliver).
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
 *   tags "today"  -> your computer's Today list changed: fetch this phone's sealed copy (Today; "stop" too)
 *   anything else -> a normal notification
 * It also rings this phone's own copy of the wake-up alarm (Alarms, 0.6.0): the call for the same alarm and this
 * one ring as one (AlarmPlan), and a reminder's or deadline's notification carries Done and Snooze (Buttons).
 */
public class ListenService extends Service {
    static final String CH_SERVICE = "service", CH_CALL = "calls_v2", CH_MSG = "messages", CH_ASK = "questions", CH_ONCALL = "oncall";
    static final int ID_SERVICE = 1, ID_CALL = 2, ID_SEALED = 8, ID_ONCALL = 3;
    static final String ACTION_ALARM = "io.github.avtarfr.kurooto.LOCAL_ALARM";
    static final int SDK = Build.VERSION.SDK_INT;

    private static ListenService instance;
    private volatile boolean running;
    private Thread thread;
    private Direct direct;
    private MediaPlayer player;
    private Vibrator vibrator;
    private String ringingSince = ""; // "local:<s>" while this phone's own alarm rings without its call
    private boolean ringingAlarm = false;
    private boolean callHeld = false; // a call is on: this service's notification is the call's, and it holds the mic
    private final Handler main = new Handler(Looper.getMainLooper());
    private android.content.BroadcastReceiver dock; // bedside mode opening by itself while charging (BedsideActivity)
    private Object otherCall; // (0.9.1) watching for this phone in another call (OtherCall)

    static void start(Context c) {
        Intent i = new Intent(c, ListenService.class);
        if (SDK >= 26) c.startForegroundService(i); else c.startService(i);
    }

    /** This phone's own copy of the wake-up alarm went off (Alarms.fired): ring it here. If the app was stopped and
     *  Android won't start it again just now, the alarm still shows full screen with the call channel's sound. */
    static void localAlarm(Context c, long at) {
        ListenService s = instance;
        if (s != null) { s.main.post(() -> s.ringLocal(at)); return; }
        Intent i = new Intent(c, ListenService.class).setAction(ACTION_ALARM).putExtra("at", at);
        try {
            if (SDK >= 26) c.startForegroundService(i); else c.startService(i);
        } catch (Exception e) {
            ((NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE))
                    .notify(ID_CALL, ringNotice(c, Alarms.reason(c), null, "local:" + at, true, ALARM_RING_MS, false).build());
        }
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
            NotificationChannel on = new NotificationChannel(CH_ONCALL, "Call in progress", NotificationManager.IMPORTANCE_LOW);
            on.setShowBadge(false);
            on.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            nm.createNotificationChannel(on);
        } catch (Throwable ignored) {
        }
    }

    @Override public void onCreate() {
        super.onCreate();
        instance = this;
        channels(this);
        dock = BedsideActivity.watch(this);
        otherCall = OtherCall.watch(this); // (0.9.1, L87) only told to your computer when it asks
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
        try {
            foreground(callHeld ? callNotice(this) : listening(), callHeld); // started again during a call: still the call's
        } catch (Exception e) {
            callHeld = false;
            foreground(listening(), false);
        }
        if (!Prefs.paired(this)) { stopSelf(); return START_NOT_STICKY; }
        if (intent != null && ACTION_ALARM.equals(intent.getAction())) {
            final long at = intent.getLongExtra("at", 0);
            main.post(() -> ringLocal(at));
        }
        if (!running) {
            running = true;
            thread = new Thread(this::loop, "ntfy-stream");
            thread.start();
            if (Prefs.direct(this)) { // the Phone tab's switch; off: ntfy only
                direct = new Direct(this, this::deliver);
                direct.start();
            }
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        running = false;
        if (thread != null) thread.interrupt();
        if (direct != null) direct.stop();
        stopRing();
        if (dock != null) try { unregisterReceiver(dock); } catch (Exception ignored) { }
        OtherCall.stop(this, otherCall);
        instance = null;
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    /** The wake-up alarm for the line's own connection (ActionReceiver.KEEPALIVE): ping it, and set the next one.
     *  Not running (Android stopped it): started again. Off the main thread. */
    static void keepAlive(Context c) {
        ListenService s = instance;
        if (s != null && s.direct != null) {
            s.direct.keepAlive();
            Direct.arm(c);
        } else if (Prefs.paired(c)) {
            try { start(c); } catch (Exception ignored) { } // Android may refuse a start from the background
        }
    }

    /** A call is on (0.8.17) or over. Back leaves a call running behind other apps, so while it's on an ongoing
     *  notification brings its screen back (a tap) or ends it (Hang up), and this service holds the microphone for it
     *  (Android 11+ silences the microphone of an app in the background without that). The service's own
     *  notification turns into the call's; without the service (not paired, or Android won't have it in the
     *  foreground with the microphone), a separate notification. Over: back to "can call you". */
    static void onCall(Context c, boolean on) {
        NotificationManager nm = (NotificationManager) c.getSystemService(NOTIFICATION_SERVICE);
        ListenService s = instance;
        if (!on) {
            nm.cancel(ID_ONCALL);
            if (s != null && s.callHeld) {
                s.callHeld = false;
                try { s.foreground(s.listening(), false); } catch (Exception ignored) { }
            }
            return;
        }
        Notification n = callNotice(c);
        if (s != null) {
            try { s.foreground(n, true); s.callHeld = true; return; } catch (Exception ignored) { } // not allowed now
        }
        try { nm.notify(ID_ONCALL, n); } catch (Exception ignored) { }
    }

    /** The service in the foreground with `n`; `mic`: with the microphone too (a call is on). */
    private void foreground(Notification n, boolean mic) {
        if (SDK >= 34) {
            startForeground(ID_SERVICE, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING
                    | (mic ? ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE : 0));
        } else if (SDK >= 30 && mic) {
            startForeground(ID_SERVICE, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        } else {
            startForeground(ID_SERVICE, n);
        }
    }

    /** The call's notification: tap to go back to the call, Hang up to end it (both through its screen, which
     *  ends the call as its own Hang up does). */
    static Notification callNotice(Context c) {
        int flags = PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT;
        Intent back = new Intent(c, CallActivity.class).putExtra("back", true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent backPi = PendingIntent.getActivity(c, 5, back, flags);
        PendingIntent endPi = PendingIntent.getActivity(c, 6, new Intent(back).putExtra("hangup", true), flags);
        return builder(c, CH_ONCALL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("On a call with " + Prefs.assistant(c))
                .setContentText("Tap to go back to the call")
                .setCategory(Notification.CATEGORY_CALL)
                .setContentIntent(backPi)
                .addAction(new Notification.Action.Builder(null, "Hang up", endPi).build())
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .build();
    }

    /** Is this phone connected straight to the call line right now (the main screen says so)? */
    static boolean direct() {
        ListenService s = instance;
        return s != null && s.direct != null && s.direct.connected();
    }

    // ---------- the stream ----------
    private void loop() {
        int backoff = 2;
        while (running) {
            String topic = Prefs.topic(this);
            if (topic.isEmpty() || !Prefs.paired(this)) { sleep(30); continue; }
            Line.sendSealKey(this); // so your computer can seal reminders for this phone (once; tried again on reconnects and by Today.fetch)
            if (System.currentTimeMillis() - Today.fetchedAt(this) > 5 * 60_000) Today.fetch(this); // a nudge missed?
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
        if (direct != null) new Thread(direct::keepAlive).start(); // ntfy's keepalive woke the phone: ping the line too
        try {
            JSONObject outer = new JSONObject(line);
            if (!"message".equals(outer.optString("event"))) return;
            Prefs.setSince(this, outer.optString("id"));
            String plain = Crypto.open(Prefs.key(this), outer.optString("message", ""));
            if (plain == null) return; // not from your call line
            JSONObject m = new JSONObject(plain);
            if (!m.has("time")) m.put("time", outer.optLong("time"));
            deliver(m);
        } catch (Exception ignored) { }
    }

    /** One message from your call line, opened: from its own connection (Direct) or from ntfy. A second copy of one
     *  (the same "mid") is dropped. */
    private synchronized void deliver(JSONObject m) {
        try {
            if (!Prefs.firstTime(this, m.optString("mid", ""))) return;
            // every message carries the assistant's current name: a rename on the computer shows up here
            if (Prefs.setAssistant(this, m.optString("assistant", ""))) repostListening();
            long sent = m.optLong("time");
            long ageSec = System.currentTimeMillis() / 1000 - sent;
            JSONArray tags = m.optJSONArray("tags");
            String tagStr = tags == null ? "" : tags.toString();
            String since = tagValue(tags, "since-");
            if (tagStr.contains("\"sealed\"")) {
                sealed(m);
                return;
            }
            if (tagStr.contains("\"chat\"") || tagStr.contains("\"chat-update\"") || tagStr.contains("\"status\"") || tagStr.contains("\"sessions\"")) {
                chat(m); // 0.8.10: a change to a message, a chat's "working", the chat list come the same way
                return;
            }
            if (tagStr.contains("\"outbox\"")) {
                if (m.optString("dev").equals(Prefs.deviceId(this))) outboxDone(Chat.done(this, m.optJSONArray("done")));
                return;
            }
            if (tagStr.contains("\"today\"")) { // the Today list changed: this phone's copy, off the stream's thread
                new Thread(() -> Today.fetch(this)).start();
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
        if (callHeld) return; // the call's notification stands in for it until the call ends
        try { ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify(ID_SERVICE, listening()); } catch (Exception ignored) { }
    }

    private void cancel(int id) {
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(id);
    }

    // ---------- ringing ----------
    static final long RING_MS = 60000, ALARM_RING_MS = 300000;

    /** This phone's own alarm (Alarms), unless the call for the same alarm rings or rang already. */
    private void ringLocal(long at) {
        if (ringingAlarm && !ringingSince.isEmpty()) return; // the call for it rings now
        if (AlarmPlan.same(Alarms.lastCall(this), at)) return; // it rang (and was answered, snoozed or stopped)
        ring(Alarms.reason(this), null, "local:" + at, true);
    }

    /** A ring: a call (url: its link), or this phone's own wake-up alarm (url null, since "local:<s>"). The call for
     *  an alarm that rings here already joins it: one sound, and its notification and screen gain Answer. One that
     *  was stopped or snoozed here already is answered that way at once, without ringing. */
    /** Is the phone in a call already (a phone, WhatsApp or Meet call, or one of Kurooto's own)? The audio mode says so;
     *  it needs no permission. */
    static boolean phoneBusy(Context c) {
        try {
            int m = ((AudioManager) c.getSystemService(AUDIO_SERVICE)).getMode();
            return m == AudioManager.MODE_IN_CALL || m == AudioManager.MODE_IN_COMMUNICATION;
        } catch (Exception e) {
            return false;
        }
    }

    private void ring(String reason, String url, final String since, boolean alarm) {
        boolean local = url == null;
        boolean join = alarm && !local && ringingSince.startsWith("local:");
        if (alarm && !local) {
            long callAt = AlarmPlan.since(since);
            Alarms.callRang(this, callAt);
            final String done = join ? "" : Alarms.answered(this, callAt);
            if (!done.isEmpty()) {
                new Thread(() -> Line.ringReply(this, since, done)).start();
                return;
            }
        }
        long ringMs = alarm ? ALARM_RING_MS : RING_MS;
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (!alarm && !local && phoneBusy(this)) { // you're on another call: no ring over it (0.7.3); a quiet note, and the
            // call line rings again after its usual wait (realert)
            nm.notify(ID_CALL, builder(this, CH_MSG).setSmallIcon(R.drawable.ic_stat).setContentTitle("Kurooto called")
                    .setContentText(reason + " (you were on a call; it rings again soon)").setAutoCancel(true).build());
            return;
        }
        try {
            nm.notify(ID_CALL, ringNotice(this, reason, url, since, alarm, ringMs, true).build());
        } catch (Exception e) { // this phone won't take the incoming-call style: the plain one
            nm.notify(ID_CALL, ringNotice(this, reason, url, since, alarm, ringMs, false).build());
        }
        if (join && CallActivity.showing) { // the alarm's screen is up: it gains the call's Answer
            try { startActivity(fullScreen(this, reason, url, since, alarm)); } catch (Exception ignored) { }
        }
        else if (BedsideActivity.visible) { // bedside mode keeps the screen on, and then Android only shows a heads-up
            try { startActivity(fullScreen(this, reason, url, since, alarm)); } catch (Exception ignored) { }
        }
        if (!join) startRing(alarm);
        ringingSince = since; // after startRing, which stops whatever rang before (and clears this)
        ringingAlarm = alarm;
        main.postDelayed(() -> { if (since.equals(ringingSince)) { stopRing(); cancel(ID_CALL); } }, ringMs);
    }

    static Intent fullScreen(Context c, String reason, String url, String since, boolean alarm) {
        return new Intent(c, CallActivity.class)
                .putExtra("url", url).putExtra("reason", reason).putExtra("ringing", true).putExtra("since", since)
                .putExtra("alarm", alarm).putExtra("local", url == null)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    }

    /** The ringing notification, full screen over the lock screen, ongoing until answered. A call: Decline, Later
     *  (Snooze for the wake-up call) and Answer, in Android 12+'s incoming-call style when the phone takes it. This
     *  phone's own alarm: Stop and Snooze. */
    static Notification.Builder ringNotice(Context c, String reason, String url, String since, boolean alarm, long ringMs,
                                           boolean styled) {
        int flags = PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT;
        Intent full = fullScreen(c, reason, url, since, alarm);
        PendingIntent fullPi = PendingIntent.getActivity(c, 1, full, flags);
        PendingIntent declinePi = PendingIntent.getBroadcast(c, 3, new Intent(c, ActionReceiver.class)
                .setAction(ActionReceiver.DECLINE).putExtra("since", since).putExtra("alarm", alarm), flags);
        PendingIntent laterPi = PendingIntent.getBroadcast(c, 4, new Intent(c, ActionReceiver.class)
                .setAction(ActionReceiver.LATER).putExtra("since", since).putExtra("alarm", alarm), flags);
        Notification.Builder b = builder(c, CH_CALL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentText(reason)
                .setCategory(alarm ? Notification.CATEGORY_ALARM : Notification.CATEGORY_CALL)
                .setFullScreenIntent(fullPi, true)
                .setContentIntent(fullPi)
                .setOngoing(true)
                .setVisibility(Notification.VISIBILITY_PUBLIC);
        if (SDK >= 21) b.setPriority(Notification.PRIORITY_MAX);
        if (SDK >= 26) b.setTimeoutAfter(ringMs);
        if (url == null) { // this phone's own alarm: nothing to answer (yet)
            return b.setContentTitle("Wake-up alarm").setStyle(new Notification.BigTextStyle().bigText(reason))
                    .addAction(new Notification.Action.Builder(null, "Stop", declinePi).build())
                    .addAction(new Notification.Action.Builder(null, "Snooze", laterPi).build());
        }
        PendingIntent answerPi = PendingIntent.getActivity(c, 2, new Intent(full).putExtra("ringing", false), flags);
        if (styled && SDK >= 31) { // Android's own incoming-call look (ring() falls back to the plain one below)
            callStyle(c, b, alarm ? "Wake-up call" : Prefs.assistant(c), declinePi, answerPi);
            return b.addAction(new Notification.Action.Builder(null, alarm ? "Snooze" : "Later", laterPi).build());
        }
        return b.setContentTitle(alarm ? "Wake-up call" : Prefs.assistant(c) + " is calling")
                .setStyle(new Notification.BigTextStyle().bigText(reason))
                .addAction(new Notification.Action.Builder(null, "Decline", declinePi).build())
                .addAction(new Notification.Action.Builder(null, alarm ? "Snooze" : "Later", laterPi).build())
                .addAction(new Notification.Action.Builder(null, "Answer", answerPi).build());
    }

    /** Android 12+: the incoming-call style (who's calling, a red Decline and a green Answer; Later sits between). */
    @TargetApi(31)
    private static void callStyle(Context c, Notification.Builder b, String who, PendingIntent declinePi, PendingIntent answerPi) {
        Person caller = new Person.Builder().setName(who).setImportant(true)
                .setIcon(Icon.createWithResource(c, R.drawable.ic_agent)).build();
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
        ringingAlarm = false;
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
            sealedNote(this, it.optString("id"), it.optString("title", Prefs.assistant(this)), it.optString("text", ""));
        } catch (Exception ignored) { }
    }

    /** A sealed reminder's notification. A reminder (not the morning line) has Done and Telegram's snoozes, +10 min
     *  and +1 h: with your computer asleep they're kept on this phone (it shows the reminder again then; Alarms isn't
     *  needed for that, a plain inexact alarm will do). */
    static void sealedNote(Context c, String id, String title, String text) {
        int flags = PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT;
        String tag = "sealed-" + id;
        Notification.Builder b = builder(c, CH_MSG)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setCategory(Notification.CATEGORY_REMINDER)
                .setContentIntent(PendingIntent.getActivity(c, 0, new Intent(c, MainActivity.class), PendingIntent.FLAG_IMMUTABLE))
                .setAutoCancel(true);
        if (text.startsWith("Reminder")) {
            b.addAction(new Notification.Action.Builder(null, "Done", PendingIntent.getBroadcast(c, (tag + ":done").hashCode(),
                    new Intent(c, ActionReceiver.class).setAction(ActionReceiver.NOTE_DONE).putExtra("tag", tag).putExtra("id", ID_SEALED), flags)).build());
            for (int m : new int[]{10, 60}) {
                Intent i = new Intent(c, ActionReceiver.class).setAction(ActionReceiver.SEALED_SNOOZE).putExtra("sid", id)
                        .putExtra("title", title).putExtra("text", text).putExtra("min", m);
                b.addAction(new Notification.Action.Builder(null, m < 60 ? "+" + m + " min" : "+1 h",
                        PendingIntent.getBroadcast(c, (tag + ":" + m).hashCode(), i, flags)).build());
            }
        }
        ((NotificationManager) c.getSystemService(NOTIFICATION_SERVICE)).notify(tag, ID_SEALED, b.build());
    }

    /** A chat push from Kurooto (Chat.incoming, 0.8.10: a message in a session, a change to one, a session's
     *  "working", the session list): into the chat, and a new message's notification (ChatNotes; none for the chat on
     *  screen, which catches up with the whole text in order instead). */
    private void chat(JSONObject m) {
        try {
            JSONObject msg = Chat.incoming(this, m);
            if (ChatStore.getVisible() != null && msg != null) { new Thread(() -> Chat.sync(this)).start(); }
            if (msg != null) ChatNotes.incoming(this, msg);
        } catch (Exception ignored) { }
    }

    /** The chat's notification again after one of its quick buttons was tapped (ActionReceiver.chatTap), quietly,
     *  saying how it went, with `buttons` offered again (a +1's) or none. */
    static void chatNote(Context c, String id, String text, JSONArray buttons, boolean quiet) {
        ChatNotes.again(c, id, text, buttons);
    }

    /** Answers and files that waited on the call line reached your computer: say so quietly (chat messages just
     *  lose their "Waiting for your computer"). */
    private void outboxDone(JSONArray gone) {
        for (int i = 0; gone != null && i < gone.length(); i++) {
            JSONObject x = gone.optJSONObject(i);
            String k = x == null ? "" : x.optString("kind");
            if (x == null || "chat".equals(k) || "button".equals(k) || "today".equals(k)) continue; // the chat / Today show it
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
