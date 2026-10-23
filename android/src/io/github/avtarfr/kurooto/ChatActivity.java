package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.app.NotificationManager;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.text.method.LinkMovementMethod;
import android.text.util.Linkify;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Chat with Kurooto here, like on Telegram: what you type goes through your call line to your computer and is
 * handled like a Telegram message; the answers come back here (and as a notification when this screen isn't open).
 * Buttons under an answer work as on Telegram; Reply under a message that takes one answers it. With your computer
 * off, what you send waits on your call line ("Waiting for your computer") and goes to it when it's back.
 * Without Telegram (0.5.18), this chat is where everything Kurooto says comes; a file comes as a button that opens a
 * link (Google Drive, or a sealed copy on your call line for a day) in the browser.
 */
public class ChatActivity extends Activity {
    static final int ID_NOTE = 9; // chat notifications (tag "chat")
    static volatile boolean visible;
    private final Handler h = new Handler(Looper.getMainLooper());
    private LinearLayout list;
    private ScrollView scroll;
    private TextView status, replying;
    private EditText typed;
    private String replyTo = "";

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (!Prefs.paired(this)) { startActivity(new Intent(this, MainActivity.class)); finish(); return; }
        LinearLayout root = Ui.column(this);
        root.setFitsSystemWindows(true); // Android 15 draws apps under the bars (and the keyboard): keep clear of them
        root.setBackgroundColor(Ui.color(this, R.color.k_bg)); // the look comes from Ui's palette (light/dark, Material You)
        root.addView(Ui.appBar(this, "Chat with " + Prefs.assistant(this), v -> up()));
        status = pad(Ui.dim(this, ""));
        status.setVisibility(View.GONE);
        root.addView(status);
        scroll = new ScrollView(this);
        scroll.setClipToPadding(false);
        list = Ui.column(this);
        list.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 8));
        scroll.addView(list);
        root.addView(scroll, new LinearLayout.LayoutParams(Ui.MATCH, 0, 1));
        replying = pad(Ui.text(this, "", 13, false, Ui.color(this, R.color.k_primary)));
        replying.setVisibility(View.GONE);
        replying.setOnClickListener(v -> setReply("", ""));
        root.addView(replying);
        LinearLayout row = Ui.row(this);
        row.setGravity(Gravity.BOTTOM);
        row.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), Ui.dp(this, 12));
        typed = Ui.field(this, "Message " + Prefs.assistant(this));
        typed.setBackground(Ui.shape(Ui.color(this, R.color.k_card), 0, Ui.dp(this, 28)));
        typed.setPadding(Ui.dp(this, 20), Ui.dp(this, 14), Ui.dp(this, 20), Ui.dp(this, 14));
        typed.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        typed.setMaxLines(5);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.WRAP, 1);
        lp.setMargins(0, Ui.dp(this, 8), Ui.dp(this, 8), 0);
        row.addView(typed, lp);
        Button send = Ui.filled(this, "Send");
        send.setMinHeight(Ui.dp(this, 56));
        send.setMinimumHeight(Ui.dp(this, 56));
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(Ui.WRAP, Ui.WRAP);
        sp.setMargins(0, Ui.dp(this, 8), 0, 0);
        send.setOnClickListener(v -> send());
        row.addView(send, sp);
        root.addView(row);
        setContentView(root);
        // opened from the Talk widget: straight to typing
        if (getIntent().getBooleanExtra("type", false)) {
            typed.requestFocus();
            getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE | WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        }
    }

    /** The app bar's back arrow: back to the main screen (opened from the widget, there's nothing under the chat). */
    private void up() {
        if (isTaskRoot()) startActivity(new Intent(this, MainActivity.class));
        finish();
    }

    /** A line of the screen's own (status, "Replying to"), inset like the messages. */
    private TextView pad(TextView t) {
        t.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 4));
        return t;
    }

    @Override protected void onResume() {
        super.onResume();
        visible = true;
        Chat.listener = () -> h.post(this::render);
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel("chat", ID_NOTE);
        render();
        new Thread(() -> {
            boolean ok = Chat.sync(this);
            h.post(() -> { if (!ok) say("Couldn't reach your call line. Is this phone online?"); else render(); });
        }).start();
    }

    @Override protected void onPause() {
        visible = false;
        Chat.listener = null;
        super.onPause();
    }

    private void send() {
        final String text = typed.getText().toString().trim();
        if (text.isEmpty()) return;
        typed.setText("");
        final String to = replyTo;
        setReply("", "");
        final String id = Chat.newId();
        new Thread(() -> Chat.send(this, id, text, to)).start();
    }

    private void resend(final JSONObject m) {
        new Thread(() -> Chat.send(this, m.optString("id"), m.optString("text"), m.optString("re"))).start();
    }

    private void setReply(String id, String text) {
        replyTo = id;
        replying.setText(id.isEmpty() ? "" : "Replying to: " + (text.length() > 60 ? text.substring(0, 59) + "…" : text) + "  (tap to cancel)");
        replying.setVisibility(id.isEmpty() ? View.GONE : View.VISIBLE);
    }

    /** Draw the chat again from what's stored, newest at the bottom. */
    private void render() {
        if (list == null) return;
        String c = Chat.computer;
        say("offline".equals(c) ? "Your computer is off: what you send waits on your call line and goes to it when it's back." : "");
        list.removeAllViews();
        JSONArray all = Chat.msgs(Chat.load(this));
        for (int i = 0; i < all.length(); i++) {
            JSONObject m = all.optJSONObject(i);
            if (m != null) list.addView(bubble(m));
        }
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    /** The status line under the app bar; hidden when there's nothing to say. */
    private void say(String text) {
        status.setText(text);
        status.setVisibility(text.isEmpty() ? View.GONE : View.VISIBLE);
    }

    /** One message: yours on the right in the accent's container colour, Kurooto's on the left on a card. */
    private View bubble(final JSONObject m) {
        boolean mine = "you".equals(m.optString("from"));
        LinearLayout box = Ui.column(this);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(Ui.WRAP, Ui.WRAP);
        lp.gravity = mine ? Gravity.END : Gravity.START;
        lp.setMargins(Ui.dp(this, mine ? 48 : 0), Ui.dp(this, 4), Ui.dp(this, mine ? 0 : 48), Ui.dp(this, 4));
        box.setLayoutParams(lp);
        box.setPadding(Ui.dp(this, 16), Ui.dp(this, 10), Ui.dp(this, 16), Ui.dp(this, 12));
        box.setBackground(Ui.shape(Ui.color(this, mine ? R.color.k_primary_container : R.color.k_card), 0, Ui.dp(this, 20)));
        TextView t = Ui.text(this, m.optString("text"), 16, false, Ui.color(this, mine ? R.color.k_on_primary_container : R.color.k_fg));
        t.setLayoutParams(new LinearLayout.LayoutParams(Ui.WRAP, Ui.WRAP));
        t.setTextIsSelectable(true);
        if (Linkify.addLinks(t, Linkify.WEB_URLS)) t.setMovementMethod(LinkMovementMethod.getInstance());  // /help's wiki links open
        box.addView(t);
        String state = m.optString("state");
        if (mine && !state.isEmpty()) {
            TextView s = Ui.text(this, "sending".equals(state) ? "Sending…" : "waiting".equals(state) ? "Waiting for your computer"
                    : "Not sent: tap to try again" + (m.optString("note").isEmpty() ? "" : " (" + m.optString("note") + ")"), 12, false,
                    Ui.color(this, "failed".equals(state) ? R.color.k_bad : R.color.k_on_primary_container));
            Ui.gap(s, 4, 0);
            if ("failed".equals(state)) box.setOnClickListener(v -> resend(m));
            box.addView(s);
        }
        JSONArray bs = m.optJSONArray("buttons");
        for (int i = 0; !mine && bs != null && i < bs.length(); i++) {
            final JSONObject x = bs.optJSONObject(i);
            if (x == null) continue;
            final int n = i;
            Button b = small(x.optString("label"));
            final String url = x.optString("url");
            b.setOnClickListener(v -> {
                if (url.startsWith("https://")) { try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { } return; }
                b.setEnabled(false);
                new Thread(() -> {
                    Chat.Sent s = Chat.tap(this, m.optString("id"), n, x.optString("label"));
                    h.post(() -> {
                        b.setEnabled(true);
                        if (!s.ok || s.queued) say(s.queued ? "Tapped. It waits on your call line for your computer." : s.note);
                    });
                }).start();
            });
            box.addView(b);
        }
        if (!mine && m.optBoolean("reply")) {
            Button r = small("Reply");
            r.setOnClickListener(v -> { setReply(m.optString("id"), m.optString("text")); typed.requestFocus(); });
            box.addView(r);
        }
        return box;
    }

    /** A button under one of Kurooto's messages: tonal, a little smaller than the screen's own. */
    private Button small(String s) {
        Button b = Ui.tonal(this, s);
        b.setTextSize(14);
        b.setMinHeight(Ui.dp(this, 40));
        b.setMinimumHeight(Ui.dp(this, 40));
        b.setPadding(Ui.dp(this, 16), Ui.dp(this, 6), Ui.dp(this, 16), Ui.dp(this, 6));
        return b;
    }
}
