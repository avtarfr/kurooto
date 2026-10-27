package io.github.avtarfr.kurooto

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyItemScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import java.util.concurrent.Executors

/**
 * Places: turn location reminders on or off (the battery cost said first; location asked for only then), save where you
 * are as a named place, and see or add each place's reminders. See Places for how it works. 0.8.10 (the Rail design): a
 * page of rounded cards over the sky, the place's pin in a shape of its own colour, reminders as removable pills, a box
 * with a round Add, "every time" as a chip; cards that come and go move with the motion scheme. What's saved is read and
 * written off the main thread ([io]); the screen draws the latest [Snap].
 */
class PlacesActivity : PageActivity() {
    private var snap by mutableStateOf<Snap?>(null)
    private var said by mutableStateOf<Said?>(null)
    private var finding by mutableStateOf(false)
    private var needSettings by mutableStateOf(false)
    private val io = Executors.newSingleThreadExecutor()

    private class Rem(val id: String, val text: String, val every: Boolean)

    private class Place(val id: String, val name: String, val radius: Long, val reminders: List<Rem>)

    /** What the page shows, read in one go: on, "all the time", the places, and reminders for places not saved here. */
    private class Snap(val on: Boolean, val background: Boolean, val places: List<Place>, val waiting: List<Pair<String, List<Rem>>>)

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        page("Places", "Reminders for when you reach a place. Say \"remind me when I reach the library to return the book\" on Telegram or in the chat, or add one here. Your places stay on this phone: your computer only knows their names.") {
            val s = snap ?: return@page
            if (!s.on) {
                item(key = "turn-on", contentType = "hero") { TurnOn(this) }
            } else {
                if (!s.background) item(key = "background", contentType = "note") { AllTheTime(this) }
                item(key = "save-here", contentType = "hero") { SaveHere(this) }
                if (s.places.isNotEmpty()) item(key = "places-head", contentType = "head") { Section("Your places", this) }
                itemsIndexed(s.places, key = { _, p -> p.id }, contentType = { _, _ -> "place" }) { i, p -> PlaceCard(p, i, this) }
            }
            if (s.waiting.isNotEmpty()) {
                item(key = "waiting-head", contentType = "head") { Section("Waiting for a place", this) }
                items(s.waiting, key = { "w:" + it.first }, contentType = { "waiting" }) { w -> WaitingCard(w.first, w.second, s.on, this) }
            }
            if (s.on) item(key = "turn-off", contentType = "foot") { TurnOff(this) }
        }
    }

    override fun onResume() {
        super.onResume()
        reload()
    }

    override fun onDestroy() {
        io.shutdown()
        super.onDestroy()
    }

    /** Read everything again (off the main thread) and draw it. */
    private fun reload() {
        if (io.isShutdown) return
        io.execute {
            val s = load()
            h.post { if (!isDestroyed) snap = s }
        }
    }

    /** Change something (off the main thread), then read again. */
    private fun change(what: () -> Unit) {
        if (io.isShutdown) return
        io.execute { what() }
        reload()
    }

    private fun load(): Snap {
        var on = Places.on(this)
        if (on && !Places.permitted(this)) { Places.setOn(this, false); on = false } // location taken away in Settings
        fun rems(a: JSONArray?) = (0 until (a?.length() ?: 0)).mapNotNull { i ->
            a?.optJSONObject(i)?.let { Rem(it.optString("id"), it.optString("text"), it.optBoolean("every")) }
        }
        val ps = Places.places(this)
        val places = (0 until ps.length()).mapNotNull { i ->
            ps.optJSONObject(i)?.let {
                val name = it.optString("name")
                Place(it.optString("id"), name, Math.round(it.optDouble("r", PlaceRules.RADIUS_M.toDouble())), rems(Places.remindersFor(this, name)))
            }
        }
        val w = Places.waiting(this)
        val waiting = w.keys().asSequence().map { it to rems(w.optJSONArray(it)) }.toList()
        return Snap(on, Places.background(this), places, waiting)
    }

    // ---------- the cards ----------

    @Composable
    private fun Modifier.animated(scope: LazyItemScope): Modifier {
        val m = MaterialTheme.motionScheme
        val base = this
        return with(scope) { base.animateItem(fadeInSpec = m.defaultEffectsSpec(), placementSpec = m.defaultSpatialSpec(), fadeOutSpec = m.fastEffectsSpec()) }
    }

    @Composable
    private fun Section(text: String, scope: LazyItemScope) {
        Text(
            text,
            style = MaterialTheme.typography.titleMediumEmphasized,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.animated(scope).padding(start = 4.dp, top = 16.dp, bottom = 2.dp),
        )
    }

    @Composable
    private fun TurnOn(scope: LazyItemScope) {
        val cs = MaterialTheme.colorScheme
        KCard(Modifier.animated(scope), container = cs.primaryContainer) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBadge(MaterialShapes.Flower, R.drawable.ic_place_pin, tone = 4, size = 56)
                Spacer(Modifier.width(14.dp))
                Text("Location reminders", style = MaterialTheme.typography.headlineSmallEmphasized, modifier = Modifier.weight(1f))
            }
            Spacer(Modifier.height(14.dp))
            BatteryNote()
            Spacer(Modifier.height(16.dp))
            SheetButton("Turn on location reminders") { turnOn() }
            Text(
                "Android then asks to let Kurooto use this phone's location.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 10.dp, start = 4.dp),
            )
            SaidLine(said)
            if (needSettings) {
                Spacer(Modifier.height(10.dp))
                CardButton("Open the app's settings", cs.surfaceContainerHighest, cs.onSurface) { openSettings() }
            }
        }
    }

    @Composable
    private fun BatteryNote() {
        Row(verticalAlignment = Alignment.Top) {
            Icon(painterResource(R.drawable.ic_place_battery), contentDescription = null, modifier = Modifier.padding(top = 2.dp, end = 10.dp).size(18.dp))
            Text(PlaceRules.BATTERY, style = MaterialTheme.typography.bodyMedium)
        }
    }

    @Composable
    private fun AllTheTime(scope: LazyItemScope) {
        val cs = MaterialTheme.colorScheme
        KCard(Modifier.animated(scope), container = cs.secondaryContainer) {
            Overline("Only while the app is open", icon = R.drawable.ic_place_pin, color = cs.onSecondaryContainer)
            Text(
                "Reminders only come while the app is open: let Kurooto use location \"All the time\".",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(top = 8.dp, bottom = 14.dp),
            )
            CardButton("Allow all the time", cs.secondary, cs.onSecondary) { askBackground() }
        }
    }

    @Composable
    private fun SaveHere(scope: LazyItemScope) {
        val cs = MaterialTheme.colorScheme
        var name by remember { mutableStateOf("") }
        KCard(Modifier.animated(scope), container = cs.primaryContainer) {
            Overline("Save where you are now", icon = R.drawable.ic_place_here, color = cs.onPrimaryContainer)
            Spacer(Modifier.height(12.dp))
            KField(name, { name = it }, "A name, e.g. library", singleLine = true, container = cs.surfaceContainerLow)
            Spacer(Modifier.height(12.dp))
            SheetButton("Save this place", enabled = !finding) { saveHere(PlaceRules.name(name)) { name = "" } }
            SaidLine(said)
        }
    }

    /** One place: its pin in a shape of its own, its name and reach, its reminders (each with Remove), and a box to add one. */
    @Composable
    private fun PlaceCard(p: Place, index: Int, scope: LazyItemScope) {
        var what by remember(p.id) { mutableStateOf("") }
        var every by remember(p.id) { mutableStateOf(false) }
        KCard(Modifier.animated(scope), container = MaterialTheme.colorScheme.surfaceContainerHigh) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBadge(SHAPES[Math.floorMod(index, SHAPES.size)], R.drawable.ic_place_pin, tone = index + 1, size = 48)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text(p.name, style = MaterialTheme.typography.titleLargeEmphasized)
                    Dim("Within ${p.radius} m of where you saved it")
                }
            }
            Spacer(Modifier.height(14.dp))
            if (p.reminders.isEmpty()) Dim("No reminders here yet.", Modifier.padding(start = 4.dp, bottom = 10.dp))
            for (r in p.reminders) ReminderPill(r)
            KField(
                what,
                { what = it },
                "Remind me here to…",
                maxLines = 3,
                trailing = {
                    RoundAction(R.drawable.ic_place_add, "Add reminder", enabled = what.isNotBlank()) {
                        val text = what
                        val each = every
                        what = ""
                        every = false
                        change { Places.addReminder(this@PlacesActivity, p.name, text, each, "phone") }
                    }
                },
            )
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                FilterChip(
                    selected = every,
                    onClick = { every = !every },
                    label = { Text("Every time I arrive (else once)") },
                    leadingIcon = if (every) {
                        { Icon(painterResource(R.drawable.ic_place_repeat), contentDescription = null, modifier = Modifier.size(18.dp)) }
                    } else {
                        null
                    },
                )
                Spacer(Modifier.weight(1f))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                TextButton({ change { Places.removePlace(this@PlacesActivity, p.id) } }, shapes = ButtonDefaults.shapes()) {
                    Icon(painterResource(R.drawable.ic_place_delete), contentDescription = null, modifier = Modifier.padding(end = 6.dp).size(18.dp))
                    Text("Remove this place")
                }
            }
        }
    }

    /** A reminder as a pill: "every time" marked, Remove at its end. `on`: the card's content colour (the pill is a
     *  light wash of it, so it reads on a neutral card and on the plum one alike). */
    @Composable
    private fun ReminderPill(r: Rem, on: Color = MaterialTheme.colorScheme.onSurface) {
        Surface(
            shape = MaterialTheme.shapes.large,
            color = on.copy(alpha = 0.08f),
            contentColor = on,
            modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(start = 16.dp, end = 4.dp, top = 4.dp, bottom = 4.dp)) {
                if (r.every) {
                    Icon(
                        painterResource(R.drawable.ic_place_repeat),
                        contentDescription = "every time",
                        modifier = Modifier.padding(end = 10.dp).size(18.dp),
                    )
                }
                Text(r.text, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                IconButton({ change { Places.removeReminder(this@PlacesActivity, r.id) } }, shapes = IconButtonDefaults.shapes()) {
                    Icon(painterResource(R.drawable.ic_place_remove), contentDescription = "Remove reminder", modifier = Modifier.size(20.dp))
                }
            }
        }
    }

    /** Reminders for a place not saved here yet: save where you are under that name when you're there. */
    @Composable
    private fun WaitingCard(n: String, rs: List<Rem>, on: Boolean, scope: LazyItemScope) {
        val cs = MaterialTheme.colorScheme
        KCard(Modifier.animated(scope), container = cs.secondaryContainer) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBadge(MaterialShapes.Cookie7Sided, R.drawable.ic_place_pin, tone = 1, size = 44)
                Spacer(Modifier.width(14.dp))
                Text(n, style = MaterialTheme.typography.titleLargeEmphasized, modifier = Modifier.weight(1f))
            }
            Spacer(Modifier.height(12.dp))
            for (r in rs) ReminderPill(r, cs.onSecondaryContainer)
            if (on) {
                Spacer(Modifier.height(4.dp))
                CardButton("I'm here: save it as $n", cs.secondary, cs.onSecondary, enabled = !finding) { saveHere(n) {} }
            } else {
                Text("Turn on location reminders to save $n when you're there.", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }

    @Composable
    private fun TurnOff(scope: LazyItemScope) {
        Column(Modifier.animated(scope).padding(top = 12.dp)) {
            Column(Modifier.padding(horizontal = 8.dp)) {
                CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurfaceVariant) {
                    BatteryNote()
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.End) {
                TextButton({ change { Places.setOn(this@PlacesActivity, false) } }, shapes = ButtonDefaults.shapes()) { Text("Turn off location reminders") }
            }
        }
    }

    /** A full-width button in a card's own colours (a tonal one would vanish on a tonal card). */
    @Composable
    private fun CardButton(text: String, container: Color, content: Color, enabled: Boolean = true, onClick: () -> Unit) {
        val tall = ButtonDefaults.MediumContainerHeight
        Button(
            onClick,
            enabled = enabled,
            shapes = ButtonDefaults.shapes(),
            colors = ButtonDefaults.buttonColors(containerColor = container, contentColor = content),
            contentPadding = ButtonDefaults.contentPaddingFor(tall),
            modifier = Modifier.fillMaxWidth().height(tall),
        ) { Text(text, style = ButtonDefaults.textStyleFor(tall)) }
    }

    private fun saveHere(name: String, saved: () -> Unit) {
        if (name.isEmpty()) { said = Said("Give the place a name first.", Said.BAD); return }
        finding = true
        said = Said("Finding where this phone is… (up to 30 seconds)")
        Places.here(this) { l, why ->
            if (isFinishing || isDestroyed) return@here
            finding = false
            if (l == null) { said = Said(why, Said.BAD); return@here }
            saved()
            change { Places.addPlace(this@PlacesActivity, name, l.latitude, l.longitude) }
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
        change { Places.setOn(this@PlacesActivity, true) }
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
            reload()
            said = Said("Location wasn't allowed, so location reminders stay off. You can allow it in the app's settings.", Said.BAD)
            needSettings = true
        } else if (code == ASK_BACKGROUND) {
            reload()
            if (results.isNotEmpty() && results[0] != PackageManager.PERMISSION_GRANTED) {
                said = Said("Without \"All the time\", reminders only come while the app is open.")
            }
        }
    }

    companion object {
        private const val ASK_FINE = 21
        private const val ASK_BACKGROUND = 22

        /** Each place's pin sits in its own shape, in turn. */
        private val SHAPES = listOf(MaterialShapes.Flower, MaterialShapes.Cookie7Sided, MaterialShapes.Clover4Leaf, MaterialShapes.Sunny, MaterialShapes.Cookie9Sided, MaterialShapes.SoftBurst)
    }
}
