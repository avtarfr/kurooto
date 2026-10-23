package io.github.avtarfr.kurooto;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/** Places: turn location reminders on or off (the battery cost said first; location asked for only then), save where
 *  you are as a named place, and see or add each place's reminders. See Places for how it works. */
public class PlacesActivity extends Activity {
    private static final int ASK_FINE = 21, ASK_BACKGROUND = 22;
    private LinearLayout box;
    private TextView status;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        build();
    }

    @Override protected void onResume() {
        super.onResume();
        build();
    }

    private void build() {
        box = Ui.page(this);
        box.addView(Ui.headline(this, "Places"));
        box.addView(Ui.dim(this, "Reminders for when you reach a place. Say \"remind me when I reach the library to return the book\" "
                + "on Telegram or in the chat, or add one here. Your places stay on this phone: your computer only knows their names."));
        LinearLayout battery = Ui.card(this);
        battery.addView(Ui.body(this, PlaceRules.BATTERY));
        box.addView(battery);
        status = Ui.status(this);
        boolean on = Places.on(this);
        if (on && !Places.permitted(this)) { Places.setOn(this, false); on = false; } // location taken away in Settings

        if (!on) {
            Button turn = Ui.large(Ui.filled(this, "Turn on location reminders"));
            Ui.gap(turn, 16, 0);
            turn.setOnClickListener(v -> turnOn());
            box.addView(turn);
            box.addView(Ui.small(this, "Android then asks to let Kurooto use this phone's location."));
            box.addView(status);
            listWaiting();
            return;
        }
        if (!Places.background(this)) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.body(this, "Reminders only come while the app is open: let Kurooto use location \"All the time\"."));
            Button allow = Ui.tonal(this, "Allow all the time");
            allow.setOnClickListener(v -> askBackground());
            warn.addView(allow);
            box.addView(warn);
        }

        box.addView(Ui.heading(this, "Save where you are now"));
        final EditText name = Ui.field(this, "A name, e.g. library");
        name.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        box.addView(name);
        Button save = Ui.filled(this, "Save this place");
        save.setOnClickListener(v -> saveHere(PlaceRules.name(name.getText().toString()), save));
        box.addView(save);
        box.addView(status);

        JSONArray ps = Places.places(this);
        if (ps.length() > 0) box.addView(Ui.heading(this, "Your places"));
        for (int i = 0; i < ps.length(); i++) placeCard(ps.optJSONObject(i));
        listWaiting();

        Button off = Ui.end(Ui.gap(Ui.flat(this, "Turn off location reminders"), 24, 0));
        off.setOnClickListener(v -> { Places.setOn(this, false); build(); });
        box.addView(off);
    }

    /** One place: its name, its reminders (each with Remove), and a box to add one. */
    private void placeCard(final JSONObject p) {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.text(this, p.optString("name"), 18, true, Ui.color(this, R.color.k_fg)));
        card.addView(Ui.dim(this, "Within " + Math.round(p.optDouble("r", PlaceRules.RADIUS_M)) + " m of where you saved it"));
        JSONArray rs = Places.remindersFor(this, p.optString("name"));
        if (rs.length() == 0) card.addView(Ui.dim(this, "No reminders here yet."));
        for (int i = 0; i < rs.length(); i++) card.addView(reminderRow(rs.optJSONObject(i)));
        final EditText what = Ui.field(this, "Remind me here to…");
        what.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        card.addView(what);
        final CheckBox every = new CheckBox(this);
        every.setText("Every time I arrive (else once)");
        every.setTextColor(Ui.color(this, R.color.k_fg));
        card.addView(every);
        Button add = Ui.tonal(this, "Add reminder");
        add.setOnClickListener(v -> {
            if (Places.addReminder(this, p.optString("name"), what.getText().toString(), every.isChecked(), "phone") != null) build();
        });
        card.addView(add);
        Button forget = Ui.end(Ui.flat(this, "Remove this place"));
        forget.setTextColor(Ui.color(this, R.color.k_bad));
        forget.setOnClickListener(v -> { Places.removePlace(this, p.optString("id")); build(); });
        card.addView(forget);
        box.addView(card);
    }

    private LinearLayout reminderRow(final JSONObject r) {
        LinearLayout row = Ui.row(this);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        row.addView(Ui.text(this, r.optString("text") + (r.optBoolean("every") ? " (every time)" : ""), 16, false, Ui.color(this, R.color.k_fg)), lp);
        Button x = Ui.flat(this, "Remove");
        x.setOnClickListener(v -> { Places.removeReminder(this, r.optString("id")); build(); });
        row.addView(x, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return row;
    }

    /** Reminders for places not saved here yet: save where you are under that name when you're there. */
    private void listWaiting() {
        JSONObject w = Places.waiting(this);
        if (w.length() == 0) return;
        box.addView(Ui.heading(this, "Waiting for a place"));
        Iterator<String> names = w.keys();
        while (names.hasNext()) {
            final String n = names.next();
            JSONArray rs = w.optJSONArray(n);
            LinearLayout card = Ui.card(this);
            card.addView(Ui.text(this, n, 18, true, Ui.color(this, R.color.k_fg)));
            for (int i = 0; rs != null && i < rs.length(); i++) card.addView(reminderRow(rs.optJSONObject(i)));
            if (Places.on(this)) {
                final Button here = Ui.tonal(this, "I'm here: save it as " + n);
                here.setOnClickListener(v -> saveHere(n, here));
                card.addView(here);
            } else {
                card.addView(Ui.dim(this, "Turn on location reminders to save " + n + " when you're there."));
            }
            box.addView(card);
        }
    }

    private void saveHere(final String name, final Button b) {
        if (name.isEmpty()) { status.setText("Give the place a name first."); Ui.bad(status); return; }
        b.setEnabled(false);
        status.setTextColor(Ui.color(this, R.color.k_dim));
        status.setText("Finding where this phone is… (up to 30 seconds)");
        Places.here(this, (l, why) -> {
            if (isFinishing() || isDestroyed()) return;
            b.setEnabled(true);
            if (l == null) { status.setText(why); Ui.bad(status); return; }
            Places.addPlace(this, name, l.getLatitude(), l.getLongitude());
            build();
            status.setText("Saved " + name + " (to about " + Math.round(l.getAccuracy()) + " m).");
            Ui.ok(status);
        });
    }

    // ---------- turning on: the permission, asked only now ----------
    private void turnOn() {
        if (Places.permitted(this)) { on(); return; }
        List<String> want = new ArrayList<>();
        want.add(Manifest.permission.ACCESS_FINE_LOCATION);
        want.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        if (Places.SDK == 29) want.add(Manifest.permission.ACCESS_BACKGROUND_LOCATION); // asked together only on Android 10
        requestPermissions(want.toArray(new String[0]), ASK_FINE);
    }

    private void on() {
        Places.setOn(this, true);
        build();
        if (!Places.background(this)) askBackground();
    }

    /** Android 11+: "All the time" is chosen in the app's location settings, which Android opens. */
    private void askBackground() {
        if (Places.SDK >= 29) requestPermissions(new String[]{Manifest.permission.ACCESS_BACKGROUND_LOCATION}, ASK_BACKGROUND);
    }

    @Override public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        if (code == ASK_FINE) {
            if (Places.permitted(this)) { on(); return; }
            build();
            status.setText("Location wasn't allowed, so location reminders stay off. You can allow it in the app's settings.");
            Ui.bad(status);
            Button settings = Ui.tonal(this, "Open the app's settings");
            settings.setOnClickListener(v -> {
                try { startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()))); }
                catch (Exception ignored) { }
            });
            box.addView(settings);
        } else if (code == ASK_BACKGROUND) {
            build();
            if (results.length > 0 && results[0] != PackageManager.PERMISSION_GRANTED) {
                status.setText("Without \"All the time\", reminders only come while the app is open.");
            }
        }
    }
}
