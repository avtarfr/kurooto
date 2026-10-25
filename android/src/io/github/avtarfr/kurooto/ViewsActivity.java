package io.github.avtarfr.kurooto;

import android.app.Activity;
import android.os.Bundle;

/**
 * Systems or the Notes map as a screen of its own (0.7.0; since 0.8.0 the main screen's Views tab holds the same pane, ViewsPane,
 * so the bar stays). Still here for an intent that names it: extra "mode": "systems" | "notes", "demo" (debug and dev builds).
 */
public class ViewsActivity extends Activity {
    private ViewsPane pane;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        pane = new ViewsPane(this, getIntent().getStringExtra("mode"), getIntent().getBooleanExtra("demo", false), this::finish);
        android.view.View v = pane.build();
        v.setFitsSystemWindows(true);
        setContentView(v);
    }

    @Override protected void onResume() {
        super.onResume();
        pane.resume();
    }

    @Override protected void onPause() {
        super.onPause();
        pane.pause();
    }

    @Override protected void onDestroy() {
        pane.destroy();
        super.onDestroy();
    }
}
