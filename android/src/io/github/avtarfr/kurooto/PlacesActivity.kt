package io.github.avtarfr.kurooto

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject

/**
 * Places: turn location reminders on or off (the battery cost said first; location asked for only then), save where you
 * are as a named place, and see or add each place's reminders. See Places for how it works. (0.7.6: a Compose page.)
 */
class PlacesActivity : PageActivity() {
    private var tick by mutableIntStateOf(0)
    private var said by mutableStateOf<Said?>(null)
    private var finding by mutableStateOf(false)
    private var needSettings by mutableStateOf(false)

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        page("Places", "Reminders for when you reach a place. Say \"remind me when I reach the library to return the book\" on Telegram or in the chat, or add one here. Your places stay on this phone: your computer only knows their names.") {
            val t = tick // everything below is read again when something changes
            KCard { Text(PlaceRules.BATTERY, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface) }
            var on = Places.on(this@PlacesActivity)
            if (on && !Places.permitted(this@PlacesActivity)) { Places.setOn(this@PlacesActivity, false); on = false } // location taken away in Settings
            if (!on) {
                SheetButton("Turn on location reminders") { turnOn() }
                Dim("Android then asks to let Kurooto use this phone's location.")
                SaidLine(said)
                if (needSettings) SheetTonal("Open the app's settings") { openSettings() }
                Waiting(t)
                return@page
            }
            if (!Places.background(this@PlacesActivity)) {
                KCard(accent = 2) {
                    Text("Reminders only come while the app is open: let Kurooto use location \"All the time\".", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
                    SheetTonal("Allow all the time") { askBackground() }
                }
            }
            var name by remember { mutableStateOf("") }
            Heading("Save where you are now")
            OutlinedTextField(
                value = name, onValueChange = { name = it }, label = { Text("A name, e.g. library") }, singleLine = true,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences), modifier = Modifier.fillMaxWidth(),
            )
            SheetButton("Save this place", enabled = !finding) { saveHere(PlaceRules.name(name)) { name = "" } }
            SaidLine(said)
            val ps = Places.places(this@PlacesActivity)
            if (ps.length() > 0) Heading("Your places")
            for (i in 0 until ps.length()) ps.optJSONObject(i)?.let { PlaceCard(it) }
            Waiting(t)
            SheetFlat("Turn off location reminders") { Places.setOn(this@PlacesActivity, false); tick++ }
        }
    }

    override fun onResume() {
        super.onResume()
        tick++
    }

    /** One place: its name, its reminders (each with Remove), and a box to add one. */
    @androidx.compose.runtime.Composable
    private fun PlaceCard(p: JSONObject) {
        val place = p.optString("name")
        val rs = Places.remindersFor(this, place)
        var what by remember(place) { mutableStateOf("") }
        var every by remember(place) { mutableStateOf(false) }
        KCard(accent = 1) {
            Text(place, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
            Dim("Within ${Math.round(p.optDouble("r", PlaceRules.RADIUS_M.toDouble()))} m of where you saved it")
            if (rs.length() == 0) Dim("No reminders here yet.")
            for (i in 0 until rs.length()) rs.optJSONObject(i)?.let { ReminderRow(it) }
            OutlinedTextField(
                value = what, onValueChange = { what = it }, label = { Text("Remind me here to…") },
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences), modifier = Modifier.fillMaxWidth(),
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(every, { every = it })
                Text("Every time I arrive (else once)", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
            }
            SheetTonal("Add reminder", enabled = what.isNotBlank()) {
                if (Places.addReminder(this@PlacesActivity, place, what, every, "phone") != null) { what = ""; tick++ }
            }
            SheetFlat("Remove this place") { Places.removePlace(this@PlacesActivity, p.optString("id")); tick++ }
        }
    }

    @androidx.compose.runtime.Composable
    private fun ReminderRow(r: JSONObject) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Text(
                r.optString("text") + if (r.optBoolean("every")) " (every time)" else "",
                style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f),
            )
            TextButton({ Places.removeReminder(this@PlacesActivity, r.optString("id")); tick++ }) { Text("Remove") }
        }
    }

    /** Reminders for places not saved here yet: save where you are under that name when you're there. */
    @androidx.compose.runtime.Composable
    private fun Waiting(@Suppress("UNUSED_PARAMETER") t: Int) {
        val w = Places.waiting(this)
        if (w.length() == 0) return
        Heading("Waiting for a place")
        for (n in w.keys()) {
            val rs: JSONArray? = w.optJSONArray(n)
            KCard(accent = 2) {
                Text(n, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
                for (i in 0 until (rs?.length() ?: 0)) rs?.optJSONObject(i)?.let { ReminderRow(it) }
                if (Places.on(this@PlacesActivity)) SheetTonal("I'm here: save it as $n", enabled = !finding) { saveHere(n) {} }
                else Dim("Turn on location reminders to save $n when you're there.")
            }
        }
    }

    private fun saveHere(name: String, saved: () -> Unit) {
        if (name.isEmpty()) { said = Said("Give the place a name first.", Said.BAD); return }
        finding = true
        said = Said("Finding where this phone is… (up to 30 seconds)")
        Places.here(this) { l, why ->
            if (isFinishing || isDestroyed) return@here
            finding = false
            if (l == null) { said = Said(why, Said.BAD); return@here }
            Places.addPlace(this, name, l.latitude, l.longitude)
            saved()
            tick++
            said = Said("Saved $name (to about ${Math.round(l.accuracy)} m).", Said.OK)
        }
    }

    // ---------- turning on: the permission, asked only now ----------
    private fun turnOn() {
        if (Places.permitted(this)) { on(); return }
        val want = arrayListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Places.SDK == 29) want.add(Manifest.permission.ACCESS_BACKGROUND_LOCATION) // asked together only on Android 10
        requestPermissions(want.toTypedArray(), ASK_FINE)
    }

    private fun on() {
        Places.setOn(this, true)
        tick++
        if (!Places.background(this)) askBackground()
    }

    /** Android 11+: "All the time" is chosen in the app's location settings, which Android opens. */
    private fun askBackground() {
        if (Places.SDK >= 29) requestPermissions(arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION), ASK_BACKGROUND)
    }

    private fun openSettings() {
        try { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))) } catch (_: Exception) {}
    }

    override fun onRequestPermissionsResult(code: Int, perms: Array<String>, results: IntArray) {
        super.onRequestPermissionsResult(code, perms, results)
        if (code == ASK_FINE) {
            if (Places.permitted(this)) { on(); return }
            tick++
            said = Said("Location wasn't allowed, so location reminders stay off. You can allow it in the app's settings.", Said.BAD)
            needSettings = true
        } else if (code == ASK_BACKGROUND) {
            tick++
            if (results.isNotEmpty() && results[0] != PackageManager.PERMISSION_GRANTED) {
                said = Said("Without \"All the time\", reminders only come while the app is open.")
            }
        }
    }

    companion object {
        private const val ASK_FINE = 21
        private const val ASK_BACKGROUND = 22
    }
}
