package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Parcelable;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.widget.TextView;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * "Share to Kurooto": files, photos, links and text from any app go to your computer's notes inbox (through your
 * call line). With your computer off, the call line keeps them (up to 20 MB) until it's back. With Chat on, the AI
 * files them and tells you where on Telegram.
 */
public class ShareActivity extends Activity {
    private final Handler h = new Handler(Looper.getMainLooper());
    private TextView status;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        status = new TextView(this);
        status.setTextColor(Color.parseColor("#ece8f2"));
        status.setBackgroundColor(Color.parseColor("#14111a"));
        status.setTextSize(18);
        status.setGravity(Gravity.CENTER);
        status.setPadding(48, 48, 48, 48);
        status.setText("Sending to " + Prefs.assistant(this) + "…");
        setContentView(status);
        if (!Prefs.paired(this)) { done("Pair this phone first: open the Kurooto app."); return; }

        Intent in = getIntent();
        String text = in.getStringExtra(Intent.EXTRA_TEXT);
        String subject = in.getStringExtra(Intent.EXTRA_SUBJECT);
        final List<Uri> uris = streams(in);
        final String note = ((subject == null ? "" : subject + " ") + (text == null ? "" : text)).trim();
        new Thread(() -> {
            int ok = 0, waiting = 0, total = uris.size();
            if (uris.isEmpty()) {
                total = 1;
                int r = note.isEmpty() ? Line.NOT_SENT : Line.upload(this, "shared-text.txt", new ByteArrayInputStream(note.getBytes(Crypto.UTF8)), "");
                if (r != Line.NOT_SENT) ok++;
                if (r == Line.WAITING) waiting++;
            } else {
                for (Uri u : uris) {
                    final String name = nameOf(u);
                    h.post(() -> status.setText("Uploading " + name + "…"));
                    try {
                        InputStream s = getContentResolver().openInputStream(u);
                        int r = s == null ? Line.NOT_SENT : Line.upload(this, name, s, note);
                        if (r != Line.NOT_SENT) ok++;
                        if (r == Line.WAITING) waiting++;
                    } catch (Exception ignored) { }
                }
            }
            done(ok == total && waiting > 0 ? "Your computer is off: it waits on your call line and goes to your notes inbox when the computer is back."
                    : ok == total ? "Sent. It's in your notes inbox; with Chat on, the AI files it and tells you where."
                    : ok == 0 ? "Not sent: is this phone online? Your call line may also be full while your computer is off. (You can send it to your Telegram bot instead.)"
                    : "Sent " + ok + " of " + total + ".");
        }).start();
    }

    @SuppressWarnings("deprecation")
    private static List<Uri> streams(Intent in) {
        List<Uri> out = new ArrayList<>();
        try {
            if (Intent.ACTION_SEND.equals(in.getAction())) {
                Parcelable p = in.getParcelableExtra(Intent.EXTRA_STREAM);
                if (p instanceof Uri) out.add((Uri) p);
            } else if (Intent.ACTION_SEND_MULTIPLE.equals(in.getAction())) {
                ArrayList<Parcelable> list = in.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
                if (list != null) for (Parcelable p : list) if (p instanceof Uri) out.add((Uri) p);
            }
        } catch (Exception ignored) { }
        return out;
    }

    private void done(final String text) {
        h.post(() -> { status.setText(text); h.postDelayed(this::finish, 3000); });
    }

    private String nameOf(Uri u) {
        Cursor c = null;
        try {
            c = getContentResolver().query(u, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null);
            if (c != null && c.moveToFirst()) return c.getString(0);
        } catch (Exception ignored) {
        } finally {
            if (c != null) c.close();
        }
        String last = u.getLastPathSegment();
        return last == null ? "shared" : last;
    }
}
