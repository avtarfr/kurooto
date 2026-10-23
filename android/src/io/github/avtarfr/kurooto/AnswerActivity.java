package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
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
        LinearLayout box = Ui.dialog(this);
        box.addView(Ui.title(this, it.optString("title", Prefs.assistant(this))));
        box.addView(Ui.gap(Ui.body(this, Inbox.text(it)), 0, 8));

        JSONArray ch = it.optJSONArray("choices");
        for (int i = 0; ch != null && i < ch.length(); i++) {
            final String c = ch.optString(i);
            box.addView(button(Ui.filled(this, c), () -> send(field("answer", c))));
        }
        JSONArray bs = it.optJSONArray("buttons");
        for (int i = 0; bs != null && i < bs.length(); i++) {
            JSONObject x = bs.optJSONObject(i);
            if (x == null) continue;
            final int n = i;
            final String url = x.optString("url");
            box.addView(button(Ui.tonal(this, x.optString("label")), url.startsWith("https://")
                    ? (Runnable) () -> { try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { } }
                    : (Runnable) () -> send(field("button", n))));
        }
        if (it.optBoolean("reply")) {
            final EditText typed = Ui.gap(Ui.field(this, ch != null && ch.length() > 0 ? "Or type an answer" : "Your answer"), 16, 0);
            typed.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
            typed.setMinLines(2);
            typed.setGravity(Gravity.TOP | Gravity.START);
            inputs.add(typed);
            box.addView(typed);
            box.addView(button(Ui.filled(this, "Send"), () -> {
                String t = typed.getText().toString().trim();
                if (!t.isEmpty()) send(field("answer", t));
            }));
        }
        if (it.optBoolean("later")) box.addView(button(Ui.end(Ui.flat(this, "Later")), () -> send(field("answer", "later"))));
        else box.addView(button(Ui.end(Ui.flat(this, "Dismiss")), () -> send(field("dismiss", true))));
        status = Ui.status(this);
        box.addView(status);
    }

    private static JSONObject field(String k, Object v) {
        try { return new JSONObject().put(k, v); } catch (Exception e) { return new JSONObject(); }
    }

    private void send(final JSONObject fields) {
        for (android.view.View v : inputs) v.setEnabled(false);
        status.setTextColor(Ui.color(this, R.color.k_dim));
        status.setText("Sending…");
        final String id = it.optString("id");
        new Thread(() -> {
            final Line.Answered r = Line.answer(this, id, fields);
            h.post(() -> {
                status.setText(r.note);
                if (r.delivered()) Ui.ok(status); else Ui.bad(status);
                if (r.delivered() || r.gone()) {
                    Inbox.cancel(this, id);
                    h.postDelayed(this::finish, 1800);
                } else {
                    for (android.view.View v : inputs) v.setEnabled(true);
                }
            });
        }).start();
    }

    /** A button that sends (or opens) something, greyed out while an answer is on its way. */
    private Button button(Button b, final Runnable onClick) {
        b.setOnClickListener(v -> onClick.run());
        inputs.add(b);
        return b;
    }
}
