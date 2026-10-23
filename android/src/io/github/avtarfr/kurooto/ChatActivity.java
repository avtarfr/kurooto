package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.app.NotificationManager;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
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
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#14111a"));
        root.setPadding(32, 48, 32, 24);
        root.addView(label("Chat with " + Prefs.assistant(this), 22, true));
        status = label("", 13, false);
        root.addView(status);
        scroll = new ScrollView(this);
        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(list);
        root.addView(scroll, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        replying = label("", 13, false);
        replying.setOnClickListener(v -> setReply("", ""));
        root.addView(replying);
        LinearLayout row = new LinearLayout(this);
        typed = new EditText(this);
        typed.setHint("Message " + Prefs.assistant(this));
        typed.setTextColor(Color.parseColor("#ece8f2"));
        typed.setHintTextColor(Color.parseColor("#9a93a8"));
        typed.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        typed.setMaxLines(5);
        row.addView(typed, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        Button send = new Button(this);
        send.setText("Send");
        send.setAllCaps(false);
        send.setTextColor(Color.WHITE);
        send.setBackgroundColor(Color.parseColor("#2e9d6a"));
        send.setOnClickListener(v -> send());
        row.addView(send);
        root.addView(row);
        setContentView(root);
    }

    @Override protected void onResume() {
        super.onResume();
        visible = true;
        Chat.listener = () -> h.post(this::render);
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel("chat", ID_NOTE);
        render();
        new Thread(() -> {
            boolean ok = Chat.sync(this);
            h.post(() -> { if (!ok) status.setText("Couldn't reach your call line. Is this phone online?"); else render(); });
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
    }

    /** Draw the chat again from what's stored, newest at the bottom. */
    private void render() {
        if (list == null) return;
        String c = Chat.computer;
        status.setText("offline".equals(c) ? "Your computer is off: what you send waits on your call line and goes to it when it's back." : "");
        list.removeAllViews();
        JSONArray all = Chat.msgs(Chat.load(this));
        for (int i = 0; i < all.length(); i++) {
            JSONObject m = all.optJSONObject(i);
            if (m != null) list.addView(bubble(m));
        }
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private View bubble(final JSONObject m) {
        boolean mine = "you".equals(m.optString("from"));
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.gravity = mine ? Gravity.END : Gravity.START;
        lp.setMargins(mine ? 96 : 0, 12, mine ? 0 : 96, 12);
        box.setLayoutParams(lp);
        box.setPadding(28, 20, 28, 20);
        box.setBackgroundColor(Color.parseColor(mine ? "#235c43" : "#2a2438"));
        TextView t = label(m.optString("text"), 16, false);
        t.setTextColor(Color.parseColor("#ece8f2"));
        t.setTextIsSelectable(true);
        box.addView(t);
        String state = m.optString("state");
        if (mine && !state.isEmpty()) {
            TextView s = label("sending".equals(state) ? "Sending…" : "waiting".equals(state) ? "Waiting for your computer"
                    : "Not sent: tap to try again" + (m.optString("note").isEmpty() ? "" : " (" + m.optString("note") + ")"), 12, false);
            s.setTextColor(Color.parseColor("failed".equals(state) ? "#e85d8a" : "#9a93a8"));
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
                        if (!s.ok || s.queued) status.setText(s.queued ? "Tapped. It waits on your call line for your computer." : s.note);
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

    private TextView label(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(Color.parseColor(bold ? "#ece8f2" : "#9a93a8"));
        t.setPadding(0, 4, 0, 4);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Button small(String s) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(14);
        b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.parseColor("#3a3150"));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 10, 0, 0);
        b.setLayoutParams(lp);
        return b;
    }
}
