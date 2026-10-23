package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.TextView;

/** Opened by the pairing page's "Pair the app" button (kurooto://pair?c=…&u=…): pairs, then starts listening. */
public class PairActivity extends Activity {
    private final Handler h = new Handler(Looper.getMainLooper());

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        final TextView t = Ui.busy(this, "Pair this phone", "Pairing with your computer…");
        final Line.Pairing p = Line.parse(getIntent().getDataString());
        if (p == null) {
            t.setText("That pairing link isn't complete. Make a new one on your computer (Phone → Pair a phone).");
            Ui.done(t, false);
            return;
        }
        new Thread(() -> {
            String err = Line.claim(this, p);
            h.post(() -> {
                if (err != null) { t.setText(err); Ui.done(t, false); return; }
                ListenService.start(this);
                startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP).putExtra("justPaired", true));
                finish();
            });
        }).start();
    }
}
