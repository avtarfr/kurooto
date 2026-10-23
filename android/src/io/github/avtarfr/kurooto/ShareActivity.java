package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Parcelable;
import android.provider.OpenableColumns;
import android.widget.TextView;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * "Share to Kurooto": files, photos, links and text from any app go to your computer's notes inbox (through your
 * call line, so the computer must be on). With Chat on, the AI files them and tells you where on Telegram.
 */
public class ShareActivity extends Activity {
    private final Handler h = new Handler(Looper.getMainLooper());
    private TextView status;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        status = Ui.busy(this, "Share to " + Prefs.assistant(this), "Sending to " + Prefs.assistant(this) + "…");
        if (!Prefs.paired(this)) { done("Pair this phone first: open the Kurooto app.", false); return; }

        Intent in = getIntent();
        String text = in.getStringExtra(Intent.EXTRA_TEXT);
        String subject = in.getStringExtra(Intent.EXTRA_SUBJECT);
        final List<Uri> uris = streams(in);
        final String note = ((subject == null ? "" : subject + " ") + (text == null ? "" : text)).trim();
        new Thread(() -> {
            h.post(() -> status.setText("Opening a line to your computer…"));
            String link = Line.callLink(this);
            if (link == null) { done("Couldn't reach your call line. Is this phone online?", false); return; }
            int ok = 0, total = uris.size();
            if (uris.isEmpty()) {
                total = 1;
                if (!note.isEmpty() && Line.upload(link, "shared-text.txt", new ByteArrayInputStream(note.getBytes(Crypto.UTF8)), "")) ok++;
            } else {
                for (Uri u : uris) {
                    final String name = nameOf(u);
                    h.post(() -> status.setText("Uploading " + name + "…"));
                    try {
                        InputStream s = getContentResolver().openInputStream(u);
                        if (s != null && Line.upload(link, name, s, note)) ok++;
                    } catch (Exception ignored) { }
                }
            }
            done(ok == total ? "Sent. It's in your notes inbox; with Chat on, the AI files it and tells you where."
                    : ok == 0 ? "Not sent: is your computer on and connected? (You can send it to your Telegram bot instead.)"
                    : "Sent " + ok + " of " + total + ".", ok == total);
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

    private void done(final String text, final boolean worked) {
        h.post(() -> { status.setText(text); Ui.done(status, worked); h.postDelayed(this::finish, 3000); });
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
