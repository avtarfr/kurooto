package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.content.SharedPreferences;
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
 * Views (0.7.0; the being and the Brain, 0.8.10): the dashboard's own drawing code (src/kurooto/web/static, copied into
 * the app's assets at build time, build.gradle.kts) in a WebView, with this phone's copies (Views) handed in, and the
 * app's colours, light or dark. Four drawings:
 *   being    the dashboard's board, static/being.js on views/being.html (being-phone.js sets it for touch): the Systems
 *            copy's "being" block and the Notes map's graph. Needs WebGL 2 and Chrome BEING_MIN_CHROME; without them
 *            the page says so (/state?gl=0) and ViewsTab shows Systems.
 *   brain    the Brain console: the brain-console part's views/brain.html and brainconsole.js, its copy "brain"
 *            handed in with KurootoView.take as for Systems; watched like Systems (/view/watch?kind=brain)
 *   systems  SYSTEMS on views/phone.html          notes  the Notes map on views/phone.html
 * The main screen's Views tab (ViewsTab, a button group) picks one: page(). ViewsActivity, the screen of its own from
 * before, still opens Systems or the Notes map with its two buttons: build(). It opens on the one you looked at last
 * (extra "mode" picks one). Extra "demo" (debug and dev builds only, Demo.ON): made-up copies, nothing fetched.
 * While Systems or the being shows, the app tells your computer every WATCH_MS that it's watching and fetches a fresh
 * copy every POLL_MS (every WATCH_MS while the computer is asleep); the Notes map is fetched when it opens (the being
 * too: it draws the notes); the Brain every BRAIN_MS. With no network or the computer asleep the last copy shows.
 * The WebView is shut in: it loads only the files below, which this class serves from the app itself (no file or
 * content access, nothing from the network, no new windows), and the page has no JavaScript interface: data goes in
 * with evaluateJavascript. The being's page asks for two things by address, answered here and nowhere else: /ask (a
 * setting, a feature on or off, a note's preview, mute: sealed requests to your computer, BeingRules) and /state
 * (how deep you are in the being, for the back button; whether it can draw).
 * Organ pages (0.8.10, Prefs.viewsOrgans, on by default): the being is four pages, Brain, Heart, Senses and Memory, each
 * that organ alone (being.js opts.only), switched on the same page with KurootoBeing.only (never loaded again); the page
 * says on /state when what it lists changed (rev) and the app reads it (KurootoBeing.organState) for OrganViews' list.
 */
public class ViewsPane {
    static final int SDK = Build.VERSION.SDK_INT;
    static final String HOST = "appassets.androidplatform.net"; // Android's own name for an app's local files
    static final String BASE = "https://" + HOST + "/views/";
    private static final Pattern ASSET = Pattern.compile("/(views/[a-z0-9_-]+\\.(html|js|css)|fonts/[a-z0-9_-]+\\.woff2"
            + "|static/(being|being-layout|being-phone)\\.js|static/vendor/three/[A-Za-z]+(\\.min)?\\.js|static/body/(anatomy\\.bin|cerebrum\\.vol))");
    static final int MIN_CHROME = 58; // the views' JavaScript needs this much (tests/unit/test_views.py)
    static final int BEING_MIN_CHROME = 80; // being.js uses ?? (tests/unit/test_being.py)
    static final long WATCH_MS = 20000, POLL_MS = 4000, BRAIN_MS = 8000;
    static final String[] MODES = {"being", "brain", "systems", "notes"};
    static final String[] ORGANS = {"brain", "heart", "senses", "memory"}; // the being's organ pages

    /** Told when the being's state changes: whether it can draw here, and how deep you are in it (0: the whole body). */
    public interface Watcher { void changed(); }

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
    private JSONObject notes; // the being: the Notes map's copy it draws
    private boolean notesFetched;
    private String sent = "", notesSent = ""; // the last things handed to the page
    private volatile int depth;
    private Watcher watcher;
    private String organ; // the organ page shown (one of ORGANS), or null: the whole being (organs off, or ViewsActivity)
    private boolean still; // Remove animations: the organ pages' camera jumps instead of flying
    private String organRev = "";
    private JSONObject organState = new JSONObject();
    private float insetTop, insetBottom; // CSS pixels of the page under the app's bars (OrganViews)

    /** a: the screen it's in; asked: one of MODES (null: the one you looked at last); onGone: the page's process
     *  ended (leave rather than take the app down). */
    public ViewsPane(Activity a, String asked, boolean demo, Runnable onGone) {
        this.a = a;
        this.asked = asked;
        this.demo = Demo.ON && demo;
        this.onGone = onGone;
    }

    private SharedPreferences sp() { return a.getSharedPreferences("kurooto-views", Activity.MODE_PRIVATE); }

    /** The drawing to show first: the one asked for, else the one you looked at last (Systems the first time). */
    public String startMode() {
        if (asked == null && !sp().getBoolean("beingShown", false)) { // 0.8.10: the first time, the being (it's new)
            sp().edit().putBoolean("beingShown", true).apply();
            if (beingOk()) { Prefs.setViewMode(a, "being"); return "being"; }
        }
        String m = asked != null ? asked : Prefs.viewMode(a);
        for (String x : MODES) if (x.equals(m)) return m;
        return "systems";
    }

    public String mode() { return mode; }

    /** The being can draw here: this WebView is new enough and had WebGL 2 (once it said so). */
    public boolean beingOk() {
        int v = chromeVersion();
        return (v == 0 || v >= BEING_MIN_CHROME) && sp().getBoolean("beingGl", true);
    }

    /** How deep you are in the being: 0 the whole body, 1 an organ (or its panel), 2 a part of it. */
    public int depth() { return "being".equals(mode) ? depth : 0; }

    public void setWatcher(Watcher w) { watcher = w; }

    /** The being as organ pages (OrganViews): on the one you looked at last. Call before page(). */
    public ViewsPane organs(boolean reduced) {
        String o = Prefs.viewOrgan(a);
        organ = "brain";
        for (String x : ORGANS) if (x.equals(o)) organ = o;
        still = reduced;
        return this;
    }

    /** The organ page shown, or null (the whole being). */
    public String organ() { return organ; }

    /** What the organ page lists (being.js describe(), with how fresh the copy is); {} until it has said. */
    public JSONObject organState() { return organState; }

    /** Another organ page: switched on the page as it is when the being is showing, else the being opens on it. */
    public void showOrgan(String o) {
        boolean known = false;
        for (String x : ORGANS) known |= x.equals(o);
        if (!known || organ == null) return;
        organ = o;
        Prefs.setViewOrgan(a, o);
        if (!"being".equals(mode)) { show("being"); return; }
        js("KurootoBeing.only(" + JSONObject.quote(o) + ")");
    }

    /** A part picked in the list (kind and key as the page named them; "" goes back to the whole organ). */
    public void pick(String kind, String key) { js("KurootoBeing.pick(" + JSONObject.quote(kind) + "," + JSONObject.quote(key) + ")"); }

    /** A switch in the list: a setting (key, true or false) or a feature on or off; sealed to your computer as before. */
    public void setting(String key, boolean on) { js("KurootoBeing.setting(" + JSONObject.quote(key) + "," + on + ")"); }

    public void feature(String id, boolean on) { js("KurootoBeing.feature(" + JSONObject.quote(id) + "," + on + ")"); }

    /** The brain seen solid, cut away or in X-ray ("solid", "cut", "xray"). */
    public void brainMode(String m) { js("KurootoBeing.mode(" + JSONObject.quote(m) + ")"); }

    /** How much of the page the app's bars cover, in CSS pixels (dp): the organ is centred between them. */
    public void inset(float top, float bottom) {
        insetTop = top;
        insetBottom = bottom;
        js("KurootoBeing.inset(" + Math.round(top) + "," + Math.round(bottom) + ")");
    }

    /** Call into the being's page (organ pages only, once it has loaded). */
    private void js(String call) {
        if (web != null && loaded && "being".equals(mode) && organ != null) web.evaluateJavascript("window.KurootoBeing && " + call, null);
    }

    /** The page said what it lists changed: read it (on the main thread). */
    private void pullOrgan() {
        if (web == null || !"being".equals(mode) || organ == null) return;
        web.evaluateJavascript("window.KurootoBeing && KurootoBeing.organState ? KurootoBeing.organState() : '{}'", v -> {
            try {
                Object o = new org.json.JSONTokener(v == null ? "" : v).nextValue();
                if (o instanceof String) organState = new JSONObject((String) o);
            } catch (Exception ignored) { return; }
            if (watcher != null) watcher.changed();
        });
    }

    /** The back button in the being: one level up (the page does it, as Esc on the dashboard). */
    public void back() {
        if (web != null && "being".equals(mode)) web.evaluateJavascript("window.KurootoBeing && KurootoBeing.back()", null);
    }

    /** ViewsActivity's view: the Systems | Notes map switch over the page. Call once. */
    public View build() {
        mode = "notes".equals(asked != null ? asked : Prefs.viewMode(a)) ? "notes" : "systems";
        View tooOld = tooOld();
        if (tooOld != null) return tooOld;
        LinearLayout page = Ui.column(a);
        page.setBackgroundColor(Ui.color(a, R.color.k_bg));
        page.addView(tabs());
        FrameLayout box = new FrameLayout(a);
        box.addView(makeWeb());
        page.addView(box, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        last = kept();
        web.loadUrl(pageOf(mode));
        return page;
    }

    /** The Views tab's view (ViewsTab picks the drawing with show()): the page alone. Call once. */
    public View page() {
        mode = startMode();
        if ("being".equals(mode) && !beingOk()) mode = "systems";
        View tooOld = tooOld();
        if (tooOld != null) return tooOld;
        FrameLayout box = new FrameLayout(a);
        box.setBackgroundColor(Ui.color(a, R.color.k_bg));
        box.addView(makeWeb());
        last = kept();
        notes = "being".equals(mode) ? keptNotes() : null;
        web.loadUrl(pageOf(mode));
        return box;
    }

    private View tooOld() {
        int v = chromeVersion();
        if (v <= 0 || v >= MIN_CHROME) return null;
        LinearLayout box = Ui.page(a); // too old to draw them: say what to update
        box.addView(Ui.headline(a, "Views"));
        box.addView(Ui.body(a, "This phone's web view (Android System WebView, version " + v + ") is too old to draw this. "
                + "Update Android System WebView (or Chrome) from the Play Store, then open it again."));
        return box;
    }

    private static String pageOf(String m) {
        return BASE + ("being".equals(m) ? "being.html" : "brain".equals(m) ? "brain.html" : "phone.html");
    }

    private WebView makeWeb() {
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
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
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
        return web;
    }

    /** Systems | Notes map: the two drawings, one tap apart (ViewsActivity). */
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
        if (sysTab == null) return;
        for (Button b : new Button[] {sysTab, notesTab}) {
            boolean on = (b == notesTab) == "notes".equals(mode);
            Button look = on ? Ui.tonal(a, "") : Ui.outlined(a, "");
            b.setBackground(look.getBackground());
            b.setTextColor(look.getTextColors());
            b.setSelected(on);
            b.setContentDescription((on ? "Showing " : "Show ") + b.getText());
        }
    }

    /** Another drawing: the page starts afresh (it draws one kind), with what's kept of that one. The being where it
     *  can't draw shows Systems (ViewsTab says why). */
    public void show(String m) {
        boolean known = false;
        for (String x : MODES) known |= x.equals(m);
        if (!known || web == null) return;
        Prefs.setViewMode(a, m);
        if ("being".equals(m) && !beingOk()) m = "systems";
        if (m.equals(mode)) return;
        mode = m;
        paintTabs();
        loaded = false;
        sent = "";
        notesSent = "";
        depth = 0;
        notesFetched = false;
        organRev = "";
        organState = new JSONObject();
        last = kept();
        notes = "being".equals(mode) ? keptNotes() : null;
        web.loadUrl(pageOf(mode));
        h.removeCallbacks(tick);
        lastWatch = 0;
        if (shown) h.post(tick);
    }

    /** The kind of copy the drawing shown reads: the being reads Systems' (and the Notes map's, keptNotes). */
    private String kind() { return "being".equals(mode) ? "systems" : mode; }

    /** This phone's copy of the drawing shown (Demo's made-up one in demo; Demo has none of the Brain: its page says so). */
    private JSONObject kept() {
        if (demo && "brain".equals(mode)) return new JSONObject();
        if (demo) {
            JSONObject d = Demo.INSTANCE.view(kind());
            if (d != null) return d;
        }
        return Views.load(a, kind());
    }

    private JSONObject keptNotes() {
        if (demo) {
            JSONObject d = Demo.INSTANCE.view("notes");
            if (d != null) return d;
        }
        return Views.load(a, "notes");
    }

    /** Only the views' own files, from the app's assets, and the being page's two addresses; anything else is refused,
     *  so nothing leaves the phone except what BeingRules sends. Called on the WebView's own threads, never the main one. */
    private WebResourceResponse serve(Uri u) {
        Map<String, String> head = new HashMap<>();
        head.put("Cache-Control", "no-store");
        String path = u == null ? null : u.getPath();
        boolean ours = u != null && "https".equals(u.getScheme()) && HOST.equals(u.getHost()) && path != null;
        if (ours && "/ask".equals(path) && "being".equals(mode)) return text(head, ask(u.getQueryParameter("op"), u.getQueryParameter("a")));
        if (ours && "/state".equals(path)) {
            state(u.getQueryParameter("depth"), u.getQueryParameter("gl"), u.getQueryParameter("rev"));
            return text(head, "{}");
        }
        if (ours && ASSET.matcher(path).matches()) {
            try {
                InputStream in = a.getAssets().open(path.substring(1));
                boolean bin = path.endsWith(".bin") || path.endsWith(".vol") || path.endsWith(".woff2");
                String type = path.endsWith(".html") ? "text/html" : path.endsWith(".js") ? "text/javascript"
                        : path.endsWith(".css") ? "text/css" : path.endsWith(".woff2") ? "font/woff2" : "application/octet-stream";
                return new WebResourceResponse(type, bin ? null : "utf-8", 200, "OK", head, in);
            } catch (Exception ignored) { /* not in this app */ }
        }
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not here", head, new ByteArrayInputStream(new byte[0]));
    }

    private static WebResourceResponse text(Map<String, String> head, String json) {
        return new WebResourceResponse("application/json", "utf-8", 200, "OK", head, new ByteArrayInputStream(json.getBytes(Crypto.UTF8)));
    }

    /** The being's page said how deep you are, or that it can't draw (no WebGL 2): remembered, and ViewsTab told. */
    private void state(String d, String gl, String rev) {
        if ("0".equals(gl)) sp().edit().putBoolean("beingGl", false).apply();
        try { if (d != null) depth = Integer.parseInt(d); } catch (NumberFormatException ignored) { }
        h.post(() -> {
            if ("0".equals(gl) && "being".equals(mode)) show("being"); // shows Systems now
            if (rev != null && !rev.equals(organRev)) { organRev = rev; pullOrgan(); } // an organ page's list changed
            if (watcher != null) watcher.changed();
        });
    }

    /** A request from the being's page to your computer (BeingRules): sealed with this phone's chat key, marked live,
     *  over the call line; its answer opened with this phone's own key. On a WebView thread (it waits). */
    private String ask(String op, String argsText) {
        if (!BeingRules.known(op)) return BeingRules.fail("Not something the phone asks.");
        String args = BeingRules.args(argsText);
        if (args == null) return BeingRules.fail("That request was too big.");
        if (!Prefs.paired(a)) return BeingRules.fail("This phone isn't paired with your computer.");
        byte[] key = Prefs.key(a);
        if (key.length == 0) return BeingRules.fail("This phone has no key: pair it again.");
        String id = Chat.newId();
        String sealed = Crypto.seal(key, BeingRules.fields(op, args, id, System.currentTimeMillis(), Chat.newId() + Chat.newId()));
        if (sealed == null) return BeingRules.fail("This phone has no key: pair it again.");
        Net.Reply r = Net.request("POST", Prefs.url(a) + "/chat", BeingRules.body(id, sealed).getBytes(Crypto.UTF8), "application/json", Prefs.device(a), 25000);
        return BeingRules.reply(r.code, r.body, (kind, token) -> {
            if ("k1".equals(kind)) return Crypto.open(Prefs.key(a), token);
            java.security.KeyPair k = Prefs.sealKeys(a);
            if (k == null) return null;
            return Seal.open(k.getPrivate(), ((java.security.interfaces.ECPublicKey) k.getPublic()).getParams(), token);
        });
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
        watcher = null;
        if (web != null) {
            web.destroy();
            web = null;
        }
    }

    // Systems and the being: say we're watching (every WATCH_MS) and fetch (every POLL_MS, or WATCH_MS with the computer
    // asleep). The Notes map: fetched once each time it's opened (the being fetches it once too). The Brain: BRAIN_MS.
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (!shown || web == null || demo) return; // demo: nothing to fetch
            final String m = mode, k = kind();
            final boolean live = "systems".equals(k), being = "being".equals(m);
            final boolean brain = "brain".equals(m); // the Brain is sent only while watched, as Systems is
            final boolean ping = (live || brain) && System.currentTimeMillis() - lastWatch >= WATCH_MS;
            final boolean withNotes = being && !notesFetched;
            if (!busy) {
                busy = true;
                if (ping) lastWatch = System.currentTimeMillis();
                if (withNotes) notesFetched = true;
                final JSONObject before = last;
                new Thread(() -> {
                    if (ping) Views.watch(a, brain ? "brain" : "systems");
                    if (ping) try { Thread.sleep(1500); } catch (InterruptedException ignored) { } // its first copy
                    JSONObject d = Views.fetch(a, k);
                    if (being) d = carry(before, d);
                    final JSONObject got = d, n = withNotes ? Views.fetch(a, "notes") : null;
                    h.post(() -> {
                        busy = false;
                        if (!m.equals(mode)) return; // another drawing since
                        last = got;
                        if (n != null) notes = n;
                        hand(false);
                    });
                }).start();
            }
            if (live) h.postDelayed(this, last != null && "offline".equals(last.optString("computer")) ? WATCH_MS : POLL_MS);
            else if (brain) h.postDelayed(this, BRAIN_MS);
        }
    };

    /** The being's settings and Brain parts come only when they changed (calls/views.py being_snapshot): a copy
     *  without them keeps the last ones, so the panels have them after the app was closed. Off the main thread. */
    private JSONObject carry(JSONObject before, JSONObject d) {
        try {
            String was = before == null ? "" : before.optString("snap", ""), now = d.optString("snap", "");
            if (was.isEmpty() || now.isEmpty() || was.equals(now)) return d;
            JSONObject ns = new JSONObject(now), nb = ns.optJSONObject("being");
            JSONObject ob = new JSONObject(was).optJSONObject("being");
            if (nb == null || ob == null || nb.has("settings") || !ob.has("settings")) return d;
            nb.put("settings", ob.get("settings"));
            if (ob.has("brain")) nb.put("brain", ob.get("brain"));
            d.put("snap", ns.toString());
            Views.save(a, "systems", d);
        } catch (Exception ignored) { /* the copy as it came */ }
        return d;
    }

    /** Hand what's kept to the page (once it has loaded): the copy, how fresh it is, and the app's colours; the being
     *  also gets the Notes map's copy, when it's new to the page. */
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
                .append(",\"demo\":").append(demo)
                .append(",\"palette\":").append(palette());
        if ("being".equals(mode) && organ != null) j.append(",\"only\":").append(JSONObject.quote(organ)).append(",\"still\":").append(still);
        String text = j.toString() + "}";
        String noteSnap = notes == null ? "" : notes.optString("snap", "");
        boolean newNotes = "being".equals(mode) && !noteSnap.isEmpty() && (force || !noteSnap.equals(notesSent));
        if (!force && !newNotes && text.equals(sent)) return;
        sent = text;
        if (newNotes) notesSent = noteSnap;
        String all = newNotes ? text.substring(0, text.length() - 1) + ",\"notes\":" + noteSnap + "}" : text;
        String fn = "being".equals(mode) ? "KurootoBeing" : "KurootoView"; // the Brain's page takes it as Systems' does
        web.evaluateJavascript("window." + fn + " && " + fn + ".take(" + JSONObject.quote(all) + ")", null);
        if (force && organ != null && "being".equals(mode)) inset(insetTop, insetBottom); // the page is new: where the bars are
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
