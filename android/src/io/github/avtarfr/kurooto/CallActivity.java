package io.github.avtarfr.kurooto;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
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
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * One call. Ringing: the reason plus Answer / Later / Decline. In the call: the call page in a WebView, with the
 * phone in call mode (earpiece unless a headset is connected; speaker on request) and the screen switched off by
 * the proximity sensor while it's at your ear. If this phone's WebView is too old for calls, the call opens in
 * your browser instead (it works there, just without the earpiece).
 */
public class CallActivity extends Activity {
    static final int SDK = Build.VERSION.SDK_INT;
    static final int MIN_WEBVIEW = 80; // Chrome version the call page needs (audio worklets, modern JavaScript)

    private WebView web;
    private AudioManager am;
    private PowerManager.WakeLock proximity;
    private boolean speaker = false, inCall = false;
    private final Handler h = new Handler(Looper.getMainLooper());
    private String url;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
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
        if (url == null) { finish(); return; }
        if (i.getBooleanExtra("ringing", false) && !inCall) showRinging(i.getStringExtra("reason"), i.getBooleanExtra("alarm", false));
        else answer();
    }

    // ---------- ringing ----------
    private void showRinging(String reason, boolean alarm) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(48, 48, 48, 96);
        box.setBackgroundColor(Color.parseColor("#14111a"));
        TextView who = text(alarm ? "Good morning: wake-up call" : Prefs.assistant(this) + " is calling", 28, true);
        TextView why = text(reason == null ? "" : reason, 18, false);
        why.setPadding(0, 24, 0, 96);
        final String since = getIntent().getStringExtra("since");
        Button decline = button("Decline", "#c0392b");
        decline.setOnClickListener(v -> reply(since, "decline"));
        Button later = button(alarm ? "Snooze" : "Later", "#3a3150");
        later.setOnClickListener(v -> reply(since, "later"));
        Button ok = button("Answer", "#2e9d6a");
        ok.setOnClickListener(v -> answer());
        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER);
        row.addView(decline, new LinearLayout.LayoutParams(0, 180, 1));
        row.addView(new View(this), new LinearLayout.LayoutParams(24, 1));
        row.addView(later, new LinearLayout.LayoutParams(0, 180, 1));
        row.addView(new View(this), new LinearLayout.LayoutParams(24, 1));
        row.addView(ok, new LinearLayout.LayoutParams(0, 180, 1));
        box.addView(who);
        box.addView(why);
        box.addView(row, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        setContentView(box);
    }

    private void reply(final String since, final String action) {
        ListenService.stopRinging(this);
        if (since != null && !since.isEmpty()) new Thread(() -> Line.ringReply(this, since, action)).start();
        finish();
    }

    private TextView text(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(Color.parseColor("#ece8f2"));
        t.setGravity(Gravity.CENTER);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Button button(String s, String color) {
        Button bt = new Button(this);
        bt.setText(s);
        bt.setTextSize(20);
        bt.setTextColor(Color.WHITE);
        bt.setBackgroundColor(Color.parseColor(color));
        return bt;
    }

    // ---------- the call ----------
    private void answer() {
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
            web.setBackgroundColor(Color.parseColor("#14111a"));
            web.addJavascriptInterface(new Bridge(), "KurootoApp");
            web.setWebViewClient(new WebViewClient());
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
        }
        setContentView(web);
        web.loadUrl(withAuto(url));
    }

    /** The page starts the call by itself when opened from here (you already tapped Answer). */
    static String withAuto(String u) {
        int hash = u.indexOf('#');
        String base = hash < 0 ? u : u.substring(0, hash), frag = hash < 0 ? "" : u.substring(hash);
        return base + (base.contains("?") ? "&" : "?") + "auto=1" + frag;
    }

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
        if (earpiece) holdProximity(); else releaseProximity();
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
            h.post(() -> { endAudio(); h.postDelayed(CallActivity.this::finish, 1500); });
        }
    }

    @Override protected void onDestroy() {
        endAudio();
        if (web != null) { web.loadUrl("about:blank"); web.destroy(); }
        super.onDestroy();
    }
}
