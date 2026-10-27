package io.github.avtarfr.kurooto;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.media.AudioAttributes;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.EdgeToEdge;
import androidx.activity.SystemBarStyle;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * One call. Ringing: the reason plus Answer / Later / Decline. In the call: the call page in a WebView, with the
 * phone in call mode (earpiece unless a headset is connected; speaker on request) and the screen switched off by
 * the proximity sensor while it's at your ear. If this phone's WebView is too old for calls, the call opens in
 * your browser instead (it works there, just without the earpiece).
 *
 * Turn by turn (Gemini Live is down, or calls.voice_mode is "phone"): the page uses this phone's own speech
 * recognizer (on the phone itself on Android 13+ when its language is downloaded, else the phone's speech service)
 * and its text-to-speech voice, through the bridge below. The screen stays on meanwhile, on the loudspeaker: the
 * recognizer stops when the screen goes off, so the proximity sensor isn't used.
 *
 * This phone's own wake-up alarm (Alarms, 0.6.0) uses the same ringing screen with Stop and Snooze ("local", no call
 * link); when the call for it comes meanwhile, the screen gains its Answer (ListenService.ring).
 *
 * Two screens, one plumbing (0.8.7): with the Phone tab's "New call screen" on (the default), the ringing screen and
 * (0.8.16) the call itself are Compose, Material 3 Expressive (CallScreen.kt): the call page still runs the call, out of
 * sight, and the screen mirrors and presses its buttons (CallScreen.MIRROR, CallUi); off, the framework screen from
 * before 0.8.7 below, with the call page itself. Which one is read as the activity opens. Extra "demo" (debug and dev
 * builds only, Demo.ON): a made-up ring with no call link (the extras "reason", "alarm" and "local" as usual); its
 * buttons send nothing, and Answer shows a stand-in call page (Demo.callPage: no microphone, nothing fetched, no audio
 * changes). With "placed" too it goes straight into that stand-in call, as a call you place from the app does.
 */
public class CallActivity extends ComponentActivity {
    static final int SDK = Build.VERSION.SDK_INT;
    static final int MIN_WEBVIEW = 80; // Chrome version the call page needs (audio worklets, modern JavaScript)
    static volatile boolean showing; // on screen now (a call joining this phone's alarm comes here, not a new ring)

    private WebView web;
    private FrameLayout page; // the WebView, kept clear of the status and navigation bars (Android 15 draws behind them)
    private AudioManager am;
    private PowerManager.WakeLock proximity;
    private boolean speaker = false, inCall = false;
    // turn by turn: the recognizer (on-device when it can), the voice, what waits for the voice to be ready
    private SpeechRecognizer rec;
    private boolean recOnDevice = false, noOnDevice = false, turnMode = false;
    private String listenLang = "";
    private TextToSpeech tts;
    private int ttsState = 0; // 0 not started, 1 starting, 2 ready, -1 failed
    private final List<String[]> ttsWaiting = new ArrayList<>();
    private final Handler h = new Handler(Looper.getMainLooper());
    private String url;
    private boolean fresh, demo; // the Compose screen (Prefs.newCallScreen); made-up, nothing sent (Demo.ON)
    private CallUi ui; // the Compose call screen's state, mirrored from the call page (fresh only)

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        fresh = Prefs.newCallScreen(this);
        demo = Demo.ON && getIntent().getBooleanExtra("demo", false);
        if (fresh) ui = new CallUi(Prefs.assistant(this));
        if (fresh) EdgeToEdge.enable(this, SystemBarStyle.dark(0), SystemBarStyle.dark(0)); // light icons on the dark screen
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        overLockScreen();
        am = (AudioManager) getSystemService(AUDIO_SERVICE);
        setVolumeControlStream(AudioManager.STREAM_VOICE_CALL);
        handle(getIntent());
    }

    @SuppressWarnings("deprecation")
    private void overLockScreen() {
        if (SDK >= 27) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        } else {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                    | WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD);
        }
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        handle(i);
    }

    private void handle(Intent i) {
        url = i.getStringExtra("url");
        boolean local = url == null && i.getBooleanExtra("local", false); // this phone's own alarm (Alarms)
        if (demo && url == null && i.getBooleanExtra("placed", false)) { demoPage(); return; } // made up: a call you placed
        if (demo && url == null && !inCall) { // made up: rings, whatever the extras
            String why = i.getStringExtra("reason");
            showRinging(why != null ? why : "Evening check-in: how did today go?", i.getBooleanExtra("alarm", false), local);
            return;
        }
        switch (CallRules.what(url != null, i.getBooleanExtra("local", false), i.getBooleanExtra("ringing", false), inCall)) {
            case CallRules.FINISH: finish(); return;
            case CallRules.IGNORE: return;
            case CallRules.RING: showRinging(i.getStringExtra("reason"), i.getBooleanExtra("alarm", false), local); return;
            default: answer();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        showing = true;
    }

    @Override protected void onPause() {
        showing = false;
        super.onPause();
    }

    // ---------- ringing ----------
    /** Who's calling and why, then Decline / Later / Answer along the bottom, in the call page's colours (this
     *  phone's own alarm: Stop and Snooze). */
    private void showRinging(String reason, boolean alarm, boolean local) {
        final String since = getIntent().getStringExtra("since");
        if (fresh) {
            CallScreen.ringing(this, CallRules.who(local, alarm, Prefs.assistant(this)), reason == null ? "" : reason,
                    CallRules.declineLabel(local), CallRules.laterLabel(alarm), CallRules.canAnswer(local),
                    () -> reply(since, "decline"), () -> reply(since, "later"), this::answer);
            return;
        }
        showRingingClassic(reason, alarm, local, since);
    }

    /** The ringing screen from before 0.8.7 (framework views), for "New call screen" off. */
    private void showRingingClassic(String reason, boolean alarm, boolean local, final String since) {
        int fg = Ui.color(this, R.color.k_call_fg);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        box.setFitsSystemWindows(true);
        box.setPadding(Ui.dp(this, 24), Ui.dp(this, 48), Ui.dp(this, 24), Ui.dp(this, 32));
        box.setBackgroundColor(Ui.color(this, R.color.k_call_bg));
        box.addView(new View(this), new LinearLayout.LayoutParams(1, 0, 1));
        ImageView badge = Ui.icon(this, R.drawable.ic_stat, fg);
        badge.setBackground(Ui.circle(Ui.color(this, R.color.k_call_go)));
        int pad = Ui.dp(this, 26);
        badge.setPadding(pad, pad, pad, pad);
        box.addView(badge, new LinearLayout.LayoutParams(Ui.dp(this, 96), Ui.dp(this, 96)));
        TextView who = Ui.gap(Ui.text(this, CallRules.who(local, alarm, Prefs.assistant(this)), 28, false, fg), 24, 0);
        who.setGravity(Gravity.CENTER);
        TextView why = Ui.gap(Ui.text(this, reason == null ? "" : reason, 18, false, Ui.color(this, R.color.k_call_dim)), 12, 0);
        why.setGravity(Gravity.CENTER);
        Button decline = button(CallRules.declineLabel(local), R.color.k_call_stop);
        decline.setOnClickListener(v -> reply(since, "decline"));
        Button later = button(CallRules.laterLabel(alarm), R.color.k_call_quiet);
        later.setOnClickListener(v -> reply(since, "later"));
        Button ok = button("Answer", R.color.k_call_go);
        ok.setOnClickListener(v -> answer());
        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER);
        row.addView(decline, new LinearLayout.LayoutParams(0, Ui.dp(this, 64), 1));
        row.addView(new View(this), new LinearLayout.LayoutParams(Ui.dp(this, 12), 1));
        row.addView(later, new LinearLayout.LayoutParams(0, Ui.dp(this, 64), 1));
        if (CallRules.canAnswer(local)) {
            row.addView(new View(this), new LinearLayout.LayoutParams(Ui.dp(this, 12), 1));
            row.addView(ok, new LinearLayout.LayoutParams(0, Ui.dp(this, 64), 1));
        }
        box.addView(who);
        box.addView(why);
        box.addView(new View(this), new LinearLayout.LayoutParams(1, 0, 1));
        box.addView(row, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        setContentView(box);
    }

    private void reply(final String since, final String action) {
        if (demo && url == null) { finish(); return; } // made up: nothing rang, nothing to tell
        ListenService.stopRinging(this);
        Alarms.replied(this, since, action, getIntent().getBooleanExtra("alarm", false)); // this phone's copy hears it
        if (CallRules.tellLine(since)) new Thread(() -> Line.ringReply(this, since, action)).start();
        finish();
    }

    private Button button(String s, int fill) {
        Button bt = Ui.button(this, s, Ui.color(this, fill), Ui.color(this, R.color.k_call_fg), 0);
        bt.setTextSize(18);
        bt.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 8), 0);
        return bt;
    }

    // ---------- the call ----------
    private void answer() {
        if (demo && url == null) { demoPage(); return; }
        ListenService.stopRinging(this);
        if (webViewVersion() < MIN_WEBVIEW) { // too old for the call page: the browser (Chrome) can do it
            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); } catch (Exception ignored) { }
            finish();
            return;
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
            return;
        }
        openPage();
    }

    /** The major Chrome version of this phone's WebView (0 if unknown). */
    private int webViewVersion() {
        String v = null;
        try {
            if (SDK >= 26) {
                PackageInfo p = WebView.getCurrentWebViewPackage();
                v = p == null ? null : p.versionName;
            } else {
                Matcher m = Pattern.compile("Chrome/(\\d+)").matcher(WebSettings.getDefaultUserAgent(this));
                v = m.find() ? m.group(1) : null;
            }
        } catch (Exception ignored) { }
        try { return v == null ? 0 : Integer.parseInt(v.split("\\.")[0]); } catch (Exception e) { return 0; }
    }

    @Override public void onRequestPermissionsResult(int code, String[] p, int[] r) {
        super.onRequestPermissionsResult(code, p, r);
        if (code == 1 && r.length > 0 && r[0] == PackageManager.PERMISSION_GRANTED) openPage();
        else finish();
    }

    private void openPage() {
        if (web == null) {
            web = new WebView(this);
            WebSettings s = web.getSettings();
            s.setJavaScriptEnabled(true);
            s.setDomStorageEnabled(true);
            s.setMediaPlaybackRequiresUserGesture(false);
            web.setBackgroundColor(Ui.color(this, R.color.k_call_bg));
            web.addJavascriptInterface(new Bridge(), "KurootoApp");
            mirrored(web);
            web.setWebChromeClient(new WebChromeClient() {
                @Override public void onPermissionRequest(PermissionRequest req) {
                    for (String res : req.getResources()) {
                        if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res)) {
                            req.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                            return;
                        }
                    }
                    req.deny();
                }
            });
            page = frame(web);
        }
        show(page);
        web.loadUrl(withAuto(url));
    }

    /** The WebView's container: the call page's background; the old screen keeps it clear of the bars itself
     *  (fitsSystemWindows), the new one with Compose's insets. */
    private FrameLayout frame(WebView w) {
        FrameLayout f = new FrameLayout(this);
        f.setFitsSystemWindows(!fresh);
        f.setBackgroundColor(Ui.color(this, R.color.k_call_bg));
        f.addView(w);
        return f;
    }

    private void show(FrameLayout f) {
        if (fresh) CallScreen.call(this, f, ui, actions); else setContentView(f);
    }

    /** The new screen: the page's state comes back through window.KurootoScreen once it has loaded (CallScreen.MIRROR);
     *  a page that never says it's the call page is shown itself. The old screen: a plain client, as before. */
    private void mirrored(WebView w) {
        if (!fresh) { w.setWebViewClient(new WebViewClient()); return; }
        w.addJavascriptInterface(new CallMirror(ui), "KurootoScreen");
        w.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView v, String u) {
                if (isFinishing() || u == null || u.startsWith("about:")) return;
                v.evaluateJavascript(CallScreen.MIRROR, null);
                h.postDelayed(() -> { if (!ui.getReady()) ui.setRaw(true); }, CallScreen.MIRROR_WAIT_MS);
            }
        });
    }

    /** The new screen's buttons: the call page's own (so it tells your computer, routes and mutes as it always has). */
    private final CallActions actions = new CallActions() {
        @Override public void press(String id) { js(CallScreen.press(id)); }
        @Override public void gate(float v) { js(CallScreen.gate(v)); }
        @Override public void hangUp() {
            if (demo && url == null) { finish(); return; } // made up: nothing to tell
            if (ui.getReady() && ui.getInCall()) press("call"); // the page hangs up, tells the line, then callEnded closes
            else finish();
        }
        @Override public void close() { finish(); }
    };

    private void js(String s) {
        if (web != null && s != null && !s.isEmpty()) web.evaluateJavascript(s, null);
    }

    /** Demo: Answer (or a placed call) opens a stand-in for the call page that acts out a call: no microphone, nothing
     *  fetched, no audio changes (it has no KurootoApp bridge). */
    private void demoPage() {
        if (web == null) {
            web = new WebView(this);
            web.getSettings().setJavaScriptEnabled(true);
            web.setBackgroundColor(Ui.color(this, R.color.k_call_bg));
            if (ui != null) ui.setSpeakerFromPage(true);
            mirrored(web);
            page = frame(web);
        }
        show(page);
        web.loadDataWithBaseURL("https://demo.invalid/", Demo.callPage(), "text/html", "utf-8", null);
    }

    /** The page starts the call by itself when opened from here (you already tapped Answer). */
    static String withAuto(String u) { return CallRules.withAuto(u); }

    /** Call mode: earpiece (or a connected headset), or the loudspeaker when asked. */
    @SuppressWarnings("deprecation")
    private void route() {
        am.setMode(AudioManager.MODE_IN_COMMUNICATION);
        boolean earpiece;
        if (SDK >= 31) {
            AudioDeviceInfo pick = null, ear = null, spk = null;
            for (AudioDeviceInfo d : am.getAvailableCommunicationDevices()) {
                switch (d.getType()) {
                    case AudioDeviceInfo.TYPE_BLUETOOTH_SCO:
                    case AudioDeviceInfo.TYPE_BLE_HEADSET:
                    case AudioDeviceInfo.TYPE_WIRED_HEADSET:
                    case AudioDeviceInfo.TYPE_WIRED_HEADPHONES:
                    case AudioDeviceInfo.TYPE_USB_HEADSET:
                        if (pick == null) pick = d;
                        break;
                    case AudioDeviceInfo.TYPE_BUILTIN_EARPIECE: ear = d; break;
                    case AudioDeviceInfo.TYPE_BUILTIN_SPEAKER: spk = d; break;
                    default: break;
                }
            }
            AudioDeviceInfo target = speaker ? spk : (pick != null ? pick : ear);
            if (target != null) am.setCommunicationDevice(target);
            earpiece = !speaker && target == ear;
        } else {
            am.setSpeakerphoneOn(speaker); // a plugged-in headset takes over by itself
            earpiece = !speaker && !am.isWiredHeadsetOn() && !am.isBluetoothScoOn();
        }
        if (earpiece && !turnMode) holdProximity(); else releaseProximity();
        if (ui != null) ui.setSpeaker(speaker);
    }

    private void holdProximity() {
        if (proximity == null) {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            if (pm.isWakeLockLevelSupported(PowerManager.PROXIMITY_SCREEN_OFF_WAKE_LOCK))
                proximity = pm.newWakeLock(PowerManager.PROXIMITY_SCREEN_OFF_WAKE_LOCK, "kurooto:call");
        }
        if (proximity != null && !proximity.isHeld()) proximity.acquire(60 * 60 * 1000L);
    }

    private void releaseProximity() {
        if (proximity != null && proximity.isHeld()) proximity.release();
    }

    @SuppressWarnings("deprecation")
    private void endAudio() {
        inCall = false;
        releaseProximity();
        try {
            if (SDK >= 31) am.clearCommunicationDevice(); else am.setSpeakerphoneOn(false);
        } catch (Exception ignored) { }
        am.setMode(AudioManager.MODE_NORMAL);
    }

    /** What the call page can ask of the app (window.KurootoApp). */
    class Bridge {
        @JavascriptInterface public boolean isEarpiece() { return !speaker; }
        @JavascriptInterface public boolean toggleSpeaker() {
            speaker = !speaker;
            h.post(CallActivity.this::route);
            return speaker;
        }
        @JavascriptInterface public void callStarted() {
            inCall = true;
            // The WebView's own audio setup can override routing a moment later, so set it again.
            h.post(CallActivity.this::route);
            h.postDelayed(() -> { if (inCall) route(); }, 1000);
            h.postDelayed(() -> { if (inCall) route(); }, 3000);
        }
        @JavascriptInterface public void callEnded() {
            h.post(() -> { stopSpeech(); endAudio(); h.postDelayed(CallActivity.this::finish, 1500); });
        }

        // turn by turn: this phone's own speech (answers come back on window.kurootoSpeech, see Speech.java)
        @JavascriptInterface public boolean canListen() {
            return SpeechRecognizer.isRecognitionAvailable(CallActivity.this) || onDeviceAvailable();
        }
        @JavascriptInterface public String speechWhere() { return onDeviceAvailable() && !noOnDevice ? "on-device" : "service"; }
        @JavascriptInterface public void prepareSpeech() { h.post(CallActivity.this::prepareTts); }
        @JavascriptInterface public void listen(final String lang) { h.post(() -> startListening(lang)); }
        @JavascriptInterface public void stopListening() { h.post(() -> { if (rec != null) rec.stopListening(); }); }
        @JavascriptInterface public void speak(final String text, final String id) { h.post(() -> { prepareTts(); say(text, id); }); }
        @JavascriptInterface public void stopSpeaking() { h.post(() -> { if (tts != null) tts.stop(); }); }
        /** The call goes turn by turn: loudspeaker, screen on (returns whether the speaker is on). */
        @JavascriptInterface public boolean turnMode() {
            turnMode = true;
            speaker = true;
            h.post(CallActivity.this::route);
            return speaker;
        }
    }

    // ---------- turn by turn ----------
    private boolean onDeviceAvailable() {
        return SDK >= 33 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this);
    }

    private void startListening(String lang) {
        listenLang = lang == null ? "" : lang;
        if (rec == null) {
            recOnDevice = !noOnDevice && onDeviceAvailable();
            if (recOnDevice && SDK >= 31) {
                rec = SpeechRecognizer.createOnDeviceSpeechRecognizer(this);
            } else {
                rec = SpeechRecognizer.createSpeechRecognizer(this);
            }
            rec.setRecognitionListener(new Heard());
        }
        Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        i.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        i.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true); // the phone's own recognition when it has it
        i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        if (!listenLang.isEmpty()) i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, listenLang);
        try { rec.startListening(i); } catch (Exception e) { toPage("failed", "unavailable"); }
    }

    private class Heard implements RecognitionListener {
        @Override public void onReadyForSpeech(Bundle b) { }
        @Override public void onBeginningOfSpeech() { }
        @Override public void onRmsChanged(float db) { }
        @Override public void onBufferReceived(byte[] b) { }
        @Override public void onEndOfSpeech() { }
        @Override public void onEvent(int type, Bundle b) { }
        @Override public void onError(int code) {
            if (recOnDevice && Speech.tryService(code)) { // its language isn't on the phone: the speech service then
                noOnDevice = true;
                try { rec.destroy(); } catch (Exception ignored) { }
                rec = null;
                startListening(listenLang);
                return;
            }
            toPage("failed", Speech.error(code));
        }
        @Override public void onResults(Bundle b) { toPage("heard", first(b)); }
        @Override public void onPartialResults(Bundle b) { String t = first(b); if (!t.isEmpty()) toPage("partial", t); }
    }

    static String first(Bundle b) {
        ArrayList<String> r = b == null ? null : b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        return r == null || r.isEmpty() || r.get(0) == null ? "" : r.get(0);
    }

    private void prepareTts() {
        if (tts != null) return;
        ttsState = 1;
        tts = new TextToSpeech(this, status -> h.post(() -> {
            ttsState = status == TextToSpeech.SUCCESS ? 2 : -1;
            if (ttsState == 2) {
                // a call's voice: the earpiece or the speaker, as route() set them
                tts.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String id) { }
                    @Override public void onDone(String id) { toPage("spoken", id); }
                    @Override public void onError(String id) { toPage("spoken", id); }
                    @Override public void onStop(String id, boolean interrupted) { toPage("spoken", id); }
                });
            }
            for (String[] w : ttsWaiting) say(w[0], w[1]);
            ttsWaiting.clear();
        }));
    }

    private void say(String text, String id) {
        if (ttsState == 2) tts.speak(text == null ? "" : text, TextToSpeech.QUEUE_ADD, new Bundle(), id);
        else if (ttsState == 1) ttsWaiting.add(new String[]{text, id});
        else toPage("spoken", id); // no voice on this phone: the page shows the answer and goes on
    }

    private void toPage(final String fn, final String arg) {
        h.post(() -> { if (web != null) web.evaluateJavascript(Speech.js(fn, arg), null); });
    }

    private void stopSpeech() {
        if (rec != null) { try { rec.destroy(); } catch (Exception ignored) { } rec = null; }
        if (tts != null) { try { tts.stop(); tts.shutdown(); } catch (Exception ignored) { } tts = null; ttsState = 0; }
        ttsWaiting.clear();
        turnMode = false;
    }

    @Override protected void onDestroy() {
        stopSpeech();
        endAudio();
        if (web != null) { web.loadUrl("about:blank"); web.destroy(); }
        super.onDestroy();
    }
}
