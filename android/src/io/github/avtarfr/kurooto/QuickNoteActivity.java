package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.ByteArrayInputStream;

/**
 * Quick note: a small box to type a note into, from the launcher shortcut (long-press the app's icon, Android 7.1+)
 * or the Quick Settings tile (NoteTile, Android 7+). Save sends it as quick-note.md to your computer's notes inbox
 * the way Share to Kurooto does (Line.upload, this phone's key); with your computer off it waits on your call line
 * (the phone outbox) and goes to the inbox when the computer is back. A note that couldn't be sent stays in the box
 * (and is kept if you close it) until it goes.
 */
public class QuickNoteActivity extends Activity {
    private final Handler h = new Handler(Looper.getMainLooper());
    private EditText typed;
    private Button save;
    private TextView status;
    private boolean sent;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout col = Ui.dialog(this);
        col.addView(Ui.title(this, "Quick note"));
        if (!Prefs.paired(this)) {
            TextView t = Ui.body(this, "Pair this phone with your computer first.");
            Ui.bad(t);
            col.addView(t);
            Button open = Ui.filled(this, "Open Kurooto");
            open.setOnClickListener(v -> { startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); finish(); });
            col.addView(Ui.gap(open, 16, 0));
            return;
        }
        col.addView(Ui.dim(this, "Goes to your notes inbox on your computer. With Chat on, " + Prefs.assistant(this) + " files it."));
        typed = Ui.field(this, "Your note");
        typed.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        typed.setMinLines(3);
        typed.setMaxLines(8);
        typed.setGravity(Gravity.TOP | Gravity.START);
        typed.setText(Prefs.noteDraft(this));
        typed.setSelection(typed.getText().length());
        col.addView(Ui.gap(typed, 16, 0));
        save = Ui.filled(this, "Save to notes");
        save.setOnClickListener(v -> save());
        col.addView(Ui.gap(save, 16, 0));
        Button cancel = Ui.end(Ui.flat(this, "Cancel"));
        cancel.setOnClickListener(v -> finish());
        col.addView(cancel);
        status = Ui.status(this);
        col.addView(status);
        typed.requestFocus();
    }

    @Override protected void onPause() {
        // closed before it went (Cancel, Back, Home): keep it for next time
        if (typed != null && !sent) Prefs.setNoteDraft(this, typed.getText().toString());
        super.onPause();
    }

    private void save() {
        final String text = typed.getText().toString().trim();
        if (text.isEmpty()) return;
        typed.setEnabled(false);
        save.setEnabled(false);
        status.setTextColor(Ui.color(this, R.color.k_dim));
        status.setText("Sending to " + Prefs.assistant(this) + "…");
        final byte[] body = (text + "\n").getBytes(Crypto.UTF8);
        new Thread(() -> {
            int r = Line.upload(this, "quick-note.md", new ByteArrayInputStream(body), "");
            h.post(() -> {
                if (r == Line.NOT_SENT) {
                    status.setText("Not sent: is this phone online? Your call line may also be full while your computer is off. The note stays here.");
                    Ui.bad(status);
                    typed.setEnabled(true);
                    save.setEnabled(true);
                    return;
                }
                sent = true;
                Prefs.setNoteDraft(this, "");
                status.setText(r == Line.WAITING ? "Your computer is off: the note waits on your call line and goes to your notes inbox when it's back."
                        : "Saved to your notes inbox.");
                Ui.ok(status);
                h.postDelayed(this::finish, r == Line.WAITING ? 2500 : 1200);
            });
        }).start();
    }
}
