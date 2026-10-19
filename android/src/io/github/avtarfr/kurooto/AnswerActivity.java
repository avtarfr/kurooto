package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** A question, approval or message from Kurooto, with every way to answer it: all the choices, a box to type in,
 *  the message's buttons, Later, Dismiss. Opened by tapping its notification (and by Reply on Android 6). */
public class AnswerActivity extends Activity {
    private final Handler h = new Handler(Looper.getMainLooper());
    private final List<android.view.View> inputs = new ArrayList<>();
    private JSONObject it;
    private TextView status;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        try { it = new JSONObject(getIntent().getStringExtra("item")); } catch (Exception e) { finish(); return; }
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.parseColor("#14111a"));
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(48, 40, 48, 40);
        sv.addView(box);
        box.addView(label(it.optString("title", Prefs.assistant(this)), 20, true));
        box.addView(label(Inbox.text(it), 16, false));

        JSONArray ch = it.optJSONArray("choices");
        for (int i = 0; ch != null && i < ch.length(); i++) {
            final String c = ch.optString(i);
            box.addView(button(c, "#2e9d6a", () -> send(field("answer", c))));
        }
        JSONArray bs = it.optJSONArray("buttons");
        for (int i = 0; bs != null && i < bs.length(); i++) {
            JSONObject x = bs.optJSONObject(i);
            if (x == null) continue;
            final int n = i;
            final String url = x.optString("url");
            box.addView(button(x.optString("label"), "#3a3150", url.startsWith("https://")
                    ? (Runnable) () -> { try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { } }
                    : (Runnable) () -> send(field("button", n))));
        }
        if (it.optBoolean("reply")) {
            final EditText typed = new EditText(this);
            typed.setHint(ch != null && ch.length() > 0 ? "Or type an answer" : "Your answer");
            typed.setTextColor(Color.parseColor("#ece8f2"));
            typed.setHintTextColor(Color.parseColor("#9a93a8"));
            typed.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
            typed.setMinLines(2);
            inputs.add(typed);
            box.addView(typed);
            box.addView(button("Send", "#2e9d6a", () -> {
                String t = typed.getText().toString().trim();
                if (!t.isEmpty()) send(field("answer", t));
            }));
        }
        if (it.optBoolean("later")) box.addView(button("Later", "#3a3150", () -> send(field("answer", "later"))));
        else box.addView(button("Dismiss", "#3a3150", () -> send(field("dismiss", true))));
        status = label("", 14, false);
        box.addView(status);
        setContentView(sv);
    }

    private static JSONObject field(String k, Object v) {
        try { return new JSONObject().put(k, v); } catch (Exception e) { return new JSONObject(); }
    }

    private void send(final JSONObject fields) {
        for (android.view.View v : inputs) v.setEnabled(false);
        status.setTextColor(Color.parseColor("#9a93a8"));
        status.setText("Sending…");
        final String id = it.optString("id");
        new Thread(() -> {
            final Line.Answered r = Line.answer(this, id, fields);
            h.post(() -> {
                status.setText(r.note);
                status.setTextColor(Color.parseColor(r.delivered() ? "#4fbf8a" : "#e85d8a"));
                if (r.delivered() || r.gone()) {
                    Inbox.cancel(this, id);
                    h.postDelayed(this::finish, 1800);
                } else {
                    for (android.view.View v : inputs) v.setEnabled(true);
                }
            });
        }).start();
    }

    private TextView label(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(Color.parseColor(bold ? "#ece8f2" : "#c9c3d4"));
        t.setPadding(0, bold ? 8 : 12, 0, 12);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Button button(String s, String color, final Runnable onClick) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(16);
        b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.parseColor(color));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 16, 0, 0);
        b.setLayoutParams(lp);
        b.setPadding(24, 28, 24, 28);
        b.setOnClickListener(v -> onClick.run());
        inputs.add(b);
        return b;
    }
}
