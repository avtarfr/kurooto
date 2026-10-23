package io.github.avtarfr.kurooto;

import android.annotation.SuppressLint;
import android.annotation.TargetApi;
import android.app.PendingIntent;
import android.content.Intent;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/** The Quick Settings tile "Quick note" (Android 7+; add it by editing the Quick Settings panel): opens the Quick
 *  note box (QuickNoteActivity), after unlocking if the phone is locked. */
@TargetApi(24)
public class NoteTile extends TileService {
    @Override public void onStartListening() {
        Tile t = getQsTile();
        if (t == null) return;
        t.setState(Tile.STATE_INACTIVE); // a button, not a switch
        t.updateTile();
    }

    @Override public void onClick() {
        if (isLocked()) unlockAndRun(this::open); else open();
    }

    @SuppressWarnings("deprecation")
    @SuppressLint("StartActivityAndCollapseDeprecated") // only below Android 14, where it's the only way
    private void open() {
        Intent i = new Intent(this, QuickNoteActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (Build.VERSION.SDK_INT >= 34) { // Android 14 takes only a PendingIntent here
            startActivityAndCollapse(PendingIntent.getActivity(this, 3, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
        } else {
            startActivityAndCollapse(i);
        }
    }
}
