package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Check-in and quiz cards on the main screen (0.6.0): the evening check-in and quiz questions answered right there,
 * with an answer box and their options (In 30 min, Not tonight; Forgot / Hard / Good / Easy), instead of opening the
 * answer window. They are the same items as the notifications (what's open on your call line, /pending), and an answer
 * goes the same way (Line.answer: sealed, single use), so with your computer asleep it waits in the phone outbox on
 * the call line and is done when it's back. A quiz answer's grading comes back as the next card.
 */
final class Cards {
    /** What you typed and didn't send yet, by item id, so it survives the screen being rebuilt (onResume). */
    private static final Map<String, String> DRAFTS = new HashMap<>();
    private static final Handler H = new Handler(Looper.getMainLooper());

    private Cards() { }

    static String kind(JSONObject it) { return CardRules.kind(it.optString("card"), Inbox.text(it)); }

    static boolean is(JSONObject it) { return !kind(it).isEmpty(); }

    /** The card for one item; `after` runs a moment after an answer went (to fetch what's open again). */
    static LinearLayout view(final Activity a, final JSONObject it, final Runnable after) {
        final String kind = kind(it), id = it.optString("id"), text = Inbox.text(it);
        final List<View> inputs = new ArrayList<>();
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, CardRules.label(kind, text), 14, true, Ui.color(a, R.color.k_primary)));
        card.addView(Ui.body(a, CardRules.body(kind, text)));
        final TextView status = Ui.status(a);

        // the options: a question's choices, then the message's buttons (by number: their data stays on your computer)
        List<String> labels = new ArrayList<>();
        List<JSONObject> sends = new ArrayList<>();
        JSONArray ch = it.optJSONArray("choices");
        for (int i = 0; ch != null && i < ch.length(); i++) { labels.add(ch.optString(i)); sends.add(field("answer", ch.optString(i))); }
        JSONArray bs = it.optJSONArray("buttons");
        for (int i = 0; bs != null && i < bs.length(); i++) {
            JSONObject b = bs.optJSONObject(i);
            if (b == null || b.optString("url").startsWith("https://")) continue; // a link: the answer window has it
            labels.add(b.optString("label"));
            sends.add(field("button", i));
        }
        int per = CardRules.perRow(labels.toArray(new String[0]));
        LinearLayout row = null;
        for (int i = 0; i < labels.size(); i++) {
            if (i % per == 0) { row = Ui.row(a); card.addView(row); }
            final JSONObject f = sends.get(i);
            Button b = Ui.tonal(a, labels.get(i));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
            lp.setMargins(i % per == 0 ? 0 : Ui.dp(a, 4), Ui.dp(a, 8), (i % per == per - 1) ? 0 : Ui.dp(a, 4), 0);
            b.setPadding(Ui.dp(a, 8), b.getPaddingTop(), Ui.dp(a, 8), b.getPaddingBottom());
            row.addView(b, lp);
            inputs.add(b);
            b.setOnClickListener(v -> send(a, id, f, inputs, status, after));
        }

        if (it.optBoolean("reply")) {
            final EditText typed = Ui.field(a, labels.isEmpty() ? CardRules.hint(kind) : "Or type an answer");
            typed.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
            typed.setMinLines(2);
            typed.setGravity(Gravity.TOP | Gravity.START);
            String draft = DRAFTS.get(id);
            if (draft != null) typed.setText(draft);
            typed.addTextChangedListener(new TextWatcher() {
                @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
                @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
                @Override public void afterTextChanged(Editable s) { DRAFTS.put(id, s.toString()); }
            });
            card.addView(typed);
            inputs.add(typed);
            Button go = Ui.end(Ui.filled(a, "Send"));
            inputs.add(go);
            go.setOnClickListener(v -> {
                String t = typed.getText().toString().trim();
                if (t.isEmpty()) { status.setText("Type an answer first."); Ui.bad(status); return; }
                send(a, id, field("answer", t), inputs, status, after);
            });
            card.addView(go);
        }
        card.addView(status);
        return card;
    }

    private static JSONObject field(String k, Object v) {
        try { return new JSONObject().put(k, v); } catch (Exception e) { return new JSONObject(); }
    }

    /** Send the answer or the button off the main thread, then say how it went on the card. */
    private static void send(final Activity a, final String id, final JSONObject fields, final List<View> inputs,
                             final TextView status, final Runnable after) {
        for (View v : inputs) v.setEnabled(false);
        status.setTextColor(Ui.color(a, R.color.k_dim));
        status.setText("Sending…");
        new Thread(() -> {
            final Line.Answered r = Line.answer(a, id, fields);
            H.post(() -> {
                status.setText(r.note);
                if (r.delivered()) Ui.ok(status); else Ui.bad(status);
                if (r.delivered() || r.gone()) {
                    DRAFTS.remove(id);
                    Inbox.cancel(a, id); // its notification too
                    if (after != null) H.postDelayed(() -> { if (!a.isFinishing() && !a.isDestroyed()) after.run(); }, 2500); // a quiz's grading: the next card
                } else {
                    for (View v : inputs) v.setEnabled(true);
                }
            });
        }).start();
    }
}
