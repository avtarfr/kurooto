package io.github.avtarfr.kurooto;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.location.LocationManager;

/** Android's proximity alert for one saved place: you came near it (or left). Places decides what to say. */
public class PlaceReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        if (!Places.ACTION.equals(i.getAction()) || !i.hasExtra(LocationManager.KEY_PROXIMITY_ENTERING)) return;
        String id = i.getStringExtra("place");
        if (id == null || id.isEmpty()) return;
        try { Places.entered(c.getApplicationContext(), id, i.getBooleanExtra(LocationManager.KEY_PROXIMITY_ENTERING, false)); }
        catch (Exception ignored) { }
    }
}
