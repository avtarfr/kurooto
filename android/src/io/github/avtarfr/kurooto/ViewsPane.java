package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.net.Uri;
import android.os.Build;
import android.view.View;
import android.os.Handler;
import android.os.Looper;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.view.Gravity;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Systems or the Notes map (0.7.0): the dashboard's own drawing code (src/kurooto/web/static/views/, copied into the
 * app's assets at build time, build.gradle.kts) in a WebView, with this phone's copy (Views) handed in through
 * KurootoView.take, and the app's colours, light or dark. Read-only: tap for a card, drag, pinch. The main screen's
 * Views tab opens it; Systems and Notes map at its top switch between the two, and it opens on the one you looked at
 * last (extra "mode": "systems" | "notes" picks one). Extra "demo" (debug and dev builds only, Demo.ON): made-up
 * copies of both, nothing fetched.
 * While Systems shows, the app tells your computer every WATCH_MS that it's watching and fetches a fresh copy every
 * POLL_MS (every WATCH_MS while the computer is asleep); the Notes map is fetched when it opens. With no network or the
 * computer asleep the last copy shows, "as of" its time.
 * The WebView is shut in: it can load only the files below, which this activity serves from the app itself (no file
 * or content access, nothing from the network, no new windows), and the page can't call into the app at all (no
 * JavaScript interface: data goes in only, with evaluateJavascript).
 */
public class ViewsPane {
    static final int SDK = Build.VERSION.SDK_INT;
    static final String HOST = "appassets.androidplatform.net"; // Android's own name for an app's local files
    static final String PAGE = "https://" + HOST + "/views/phone.html";
    private static final Pattern ASSET = Pattern.compile("/(views/[a-z0-9_-]+\\.(html|js|css)|fonts/[a-z0-9_-]+\\.woff2)");
    static final int MIN_CHROME = 58; // the views' JavaScript needs this much (tests/unit/test_views.py)
    static final long WATCH_MS = 20000, POLL_MS = 4000;

    private final Activity a;
    private final Runnable onGone;
    private final String asked;
    private final Handler h = new Handler(Looper.getMainLooper());
    private WebView web;
    private String mode = "systems";
    private boolean loaded, shown, busy, demo;
    private Button sysTab, notesTab;
    private long lastWatch;
    private JSONObject last; // what was kept or fetched last
    private String sent = ""; // the last thing handed to the page

    /** a: the screen it's in; asked: "systems" or "notes" (null: the one you looked at last); onGone: the page's process
     *  ended (leave rather than take the app down). */
    public ViewsPane(Activity a, String asked, boolean demo, Runnable onGone) {
        this.a = a;
        this.asked = asked;
        this.demo = Demo.ON && demo;
        this.onGone = onGone;
    }

    /** The pane's view: the Systems | Notes map switch over the page. Call once. */
    public View build() {
        mode = "notes".equals(asked != null ? asked : Prefs.viewMode(a)) ? "notes" : "systems";
        int v = chromeVersion();
        if (v > 0 && v < MIN_CHROME) { // too old to draw them: say what to update
            LinearLayout box = Ui.page(a);
            box.addView(Ui.headline(a, "notes".equals(mode) ? "Notes map" : "Systems"));
            box.addView(Ui.body(a, "This phone's web view (Android System WebView, version " + v + ") is too old to draw this. "
                    + "Update Android System WebView (or Chrome) from the Play Store, then open it again."));
            return box;
        }
        web = new WebView(a);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setAllowFileAccessFromFileURLs(false);
        s.setAllowUniversalAccessFromFileURLs(false);
        s.setDomStorageEnabled(false);
        s.setDatabaseEnabled(false);
        s.setGeolocationEnabled(false);
        s.setSupportMultipleWindows(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setSupportZoom(false); // pinching is the drawing's own
        if (SDK >= 26) s.setSafeBrowsingEnabled(false); // nothing to look up: the page is the app's own
        web.setBackgroundColor(Ui.color(a, R.color.k_bg));
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                return serve(req.getUrl());
            }

            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) { return true; }

            @SuppressWarnings("deprecation")
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) { return true; }

            @Override public void onPageFinished(WebView view, String url) {
                loaded = true;
                hand(true);
            }

            @Override public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail d) {
                web = null; // the drawing's process ended: leave rather than take the app down with it
                if (onGone != null) onGone.run();
                return true;
            }
        });
        LinearLayout page = Ui.column(a);
        page.setBackgroundColor(Ui.color(a, R.color.k_bg));
        page.addView(tabs());
        FrameLayout box = new FrameLayout(a);
        box.addView(web);
        page.addView(box, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        last = kept();
        web.loadUrl(PAGE);
        return page;
    }

    /** Systems | Notes map: the two drawings, one tap apart. */
    private LinearLayout tabs() {
        LinearLayout row = Ui.row(a);
        row.setGravity(Gravity.CENTER);
        row.setPadding(Ui.dp(a, 16), Ui.dp(a, 8), Ui.dp(a, 16), 0);
        sysTab = Ui.button(a, "Systems", 0, 0, 0);
        notesTab = Ui.button(a, "Notes map", 0, 0, 0);
        sysTab.setOnClickListener(v -> show("systems"));
        notesTab.setOnClickListener(v -> show("notes"));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        lp.setMargins(Ui.dp(a, 4), 0, Ui.dp(a, 4), 0);
        row.addView(sysTab, lp);
        row.addView(notesTab, new LinearLayout.LayoutParams(lp));
        paintTabs();
        return row;
    }

    private void paintTabs() {
        for (Button b : new Button[] {sysTab, notesTab}) {
            boolean on = (b == notesTab) == "notes".equals(mode);
            Button look = on ? Ui.tonal(a, "") : Ui.outlined(a, "");
            b.setBackground(look.getBackground());
            b.setTextColor(look.getTextColors());
            b.setSelected(on);
            b.setContentDescription((on ? "Showing " : "Show ") + b.getText());
        }
    }

    /** The other drawing: the page starts afresh (it draws one kind), with what's kept of that one. */
    private void show(String m) {
        if (m.equals(mode) || web == null) return;
        mode = m;
        Prefs.setViewMode(a, m);
        paintTabs();
        loaded = false;
        sent = "";
        last = kept();
        web.loadUrl(PAGE);
        h.removeCallbacks(tick);
        lastWatch = 0;
        if (shown) h.post(tick);
    }

    /** This phone's copy of the drawing shown (Demo's made-up one in demo). */
    private JSONObject kept() {
        if (demo) {
            JSONObject d = Demo.INSTANCE.view(mode);
            if (d != null) return d;
        }
        return Views.load(a, mode);
    }

    /** Only the views' own files, from the app's assets; anything else is refused, so nothing leaves the phone. */
    private WebResourceResponse serve(Uri u) {
        Map<String, String> head = new HashMap<>();
        head.put("Cache-Control", "no-store");
        String path = u == null ? null : u.getPath();
        if (u != null && "https".equals(u.getScheme()) && HOST.equals(u.getHost()) && path != null && ASSET.matcher(path).matches()) {
            try {
                InputStream in = a.getAssets().open(path.substring(1));
                String type = path.endsWith(".html") ? "text/html" : path.endsWith(".js") ? "text/javascript"
                        : path.endsWith(".css") ? "text/css" : "font/woff2";
                return new WebResourceResponse(type, path.endsWith(".woff2") ? null : "utf-8", 200, "OK", head, in);
            } catch (Exception ignored) { /* not in this app */ }
        }
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not here", head, new ByteArrayInputStream(new byte[0]));
    }

    /** The screen came to the front (or the tab was opened): fetch and keep fresh. */
    public void resume() {
        shown = true;
        lastWatch = 0;
        h.post(tick);
    }

    /** The screen left the front (or another tab was opened): stop fetching. */
    public void pause() {
        shown = false;
        h.removeCallbacks(tick);
    }

    public void destroy() {
        h.removeCallbacksAndMessages(null);
        if (web != null) {
            web.destroy();
            web = null;
        }
    }

    // Systems: say we're watching (every WATCH_MS) and fetch (every POLL_MS, or WATCH_MS with the computer asleep).
    // The Notes map: fetched once each time it's opened.
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (!shown || web == null || demo) return; // demo: nothing to fetch
            final boolean systems = "systems".equals(mode);
            final boolean ping = systems && System.currentTimeMillis() - lastWatch >= WATCH_MS;
            if (!busy) {
                busy = true;
                if (ping) lastWatch = System.currentTimeMillis();
                new Thread(() -> {
                    if (ping) Views.watch(a);
                    if (ping) try { Thread.sleep(1500); } catch (InterruptedException ignored) { } // its first copy
                    final JSONObject d = Views.fetch(a, mode);
                    h.post(() -> {
                        busy = false;
                        last = d;
                        hand(false);
                    });
                }).start();
            }
            if (systems) h.postDelayed(this, last != null && "offline".equals(last.optString("computer")) ? WATCH_MS : POLL_MS);
        }
    };

    /** Hand what's kept to the page (once it has loaded): the copy, how fresh it is, and the app's colours. */
    private void hand(boolean force) {
        if (!loaded || web == null) return;
        JSONObject d = last == null ? new JSONObject() : last;
        String snap = d.optString("snap", "");
        StringBuilder j = new StringBuilder(snap.length() + 600);
        j.append("{\"mode\":").append(JSONObject.quote(mode))
                .append(",\"snap\":").append(snap.isEmpty() ? "null" : snap)
                .append(",\"computer\":").append(JSONObject.quote(d.optString("computer", "")))
                .append(",\"reach\":").append(d.optBoolean("reach", true) && !d.optBoolean("old"))
                .append(",\"off\":").append(d.optBoolean("off"))
                .append(",\"palette\":").append(palette()).append('}');
        String text = j.toString();
        if (!force && text.equals(sent)) return;
        sent = text;
        web.evaluateJavascript("window.KurootoView && KurootoView.take(" + JSONObject.quote(text) + ")", null);
    }

    /** The app's colours (light or dark, Material You's on Android 12+) under the names the drawing uses. */
    private String palette() {
        int[] res = {R.color.k_bg, R.color.k_fg, R.color.k_primary, R.color.k_view_lav, R.color.k_view_pink, R.color.k_view_peach,
                R.color.k_sand, R.color.k_rose, R.color.k_bad, R.color.k_card};
        String[] names = {"bg", "fg", "accent", "lav", "pink", "peach", "sand", "rose", "bad", "panel"};
        StringBuilder s = new StringBuilder("{");
        for (int i = 0; i < res.length; i++) {
            if (i > 0) s.append(',');
            s.append('"').append(names[i]).append("\":\"").append(String.format("#%06x", Ui.color(a, res[i]) & 0xffffff)).append('"');
        }
        return s.append('}').toString();
    }

    /** The major version of this phone's WebView (0 if unknown), from its user agent. */
    private int chromeVersion() {
        try {
            Matcher m = Pattern.compile("Chrome/(\\d+)").matcher(WebSettings.getDefaultUserAgent(a));
            return m.find() ? Integer.parseInt(m.group(1)) : 0;
        } catch (Exception e) {
            return 0;
        }
    }
}
