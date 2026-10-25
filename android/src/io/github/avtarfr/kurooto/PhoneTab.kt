package io.github.avtarfr.kurooto

import android.content.Intent
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.foundation.BorderStroke
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp

/**
 * The Phone tab (0.7.0): this phone's own settings, as the end of the old main screen had them. The checklist (what
 * the phone must allow for calls to ring; Fix goes to the setting), location reminders (PlacesActivity), ringtones,
 * bedside mode (BedsideActivity: open it, its hours, the screen kept on), and this phone (the call line it's paired
 * with, the app's version, Unpair).
 */
@Composable
fun PhonePage(a: MainActivity, ui: HomeState, outer: PaddingValues) {
    @Suppress("UNUSED_VARIABLE") val tick = ui.tick
    val toFix = a.checks().count { !it.ok }
    val sub = when (toFix) {
        0 -> "Ready to ring"
        1 -> "1 thing to fix"
        else -> "$toFix things to fix"
    }
    TabPage(a, ui, outer, "Phone", sub) { PhoneTab(a, ui) }
}

private val SensesList = listOf("screen", "charging", "motion", "steps", "light", "places", "headphones", "dnd", "alarm", "wifi", "usage")

@Composable
private fun ColumnScope.PhoneTab(a: MainActivity, ui: HomeState) {
    @Suppress("UNUSED_VARIABLE") val tick = ui.tick // re-read on resume and after a change
    val k = LocalKurooto.current

    Heading("Checklist")
    Group(
        a.checks().map { c ->
            Item(
                c.what,
                if (c.ok) null else "Needs your OK",
                onClick = if (c.ok) null else ({ a.fix(c) }),
                leading = {
                    // done: a calm circle; not done: a burst, which catches the eye
                    ShapeBadge(
                        if (c.ok) MaterialShapes.Circle else MaterialShapes.SoftBurst,
                        (if (c.ok) k.ok else k.bad).copy(alpha = 0.16f),
                    ) {
                        Icon(
                            painterResource(if (c.ok) R.drawable.ic_ok else R.drawable.ic_fix),
                            contentDescription = if (c.ok) "Done" else "Not done",
                            tint = if (c.ok) k.ok else k.bad,
                            modifier = Modifier.size(22.dp),
                        )
                    }
                },
                trailing = if (c.ok) null else ({ TextButton(onClick = { a.fix(c) }) { Text("Fix") } }),
            )
        },
    )
    a.sleepyMaker()?.let {
        Footnote(
            "$it phones also put apps to sleep on their own: in Settings → Battery, set Kurooto to \"Unrestricted\" or " +
                "\"No restrictions\" and take it off any \"sleeping apps\" list, or calls may not ring.",
        )
    }

    Heading("Location reminders")
    Group(
        listOf(
            Item(
                "Places",
                if (Places.on(a)) "On: " + Places.places(a).length() + " saved" else "Off",
                onClick = { a.startActivity(Intent(a, PlacesActivity::class.java)) },
                trailing = { Chevron() },
            ),
        ),
    )

    Heading("Ringtones")
    Group(
        listOf(
            Item("Call ringtone", a.toneName(false), onClick = { a.pickTone(false) }),
            Item("Wake-up alarm tone", a.toneName(true), onClick = { a.pickTone(true) }),
        ),
    )
    Footnote("The alarm tone plays on the alarm stream, so wake-up calls ring even on silent.")

    Heading("Bedside mode")
    Group(
        listOf(
            Item(
                "Open bedside mode",
                "A big clock, the next alarm and calls, and one button to talk. Dims at night.",
                onClick = { a.startActivity(Intent(a, BedsideActivity::class.java)) },
                trailing = { Chevron() },
            ),
            Item(
                "Open by itself while charging",
                if (Prefs.bedsideAuto(a)) Prefs.bedsideFrom(a) + " to " + Prefs.bedsideTo(a) else "Off",
                onClick = { a.bedsideHours() },
            ),
            Item("Keep the screen on while charging", null, checked = Prefs.bedsideKeepOn(a), onClick = { a.toggleKeepOn() }),
        ),
    )
    Footnote(
        "An old phone on a charger by your bed works well. Talk works with the phone locked; leave the app listening " +
            "(the checklist above) so wake-up calls ring there.",
    )

    Heading("Senses")
    Group(
        SensesList.map { s ->
            Item(Senses.label(s), Senses.note(s).ifEmpty { null }, checked = Senses.on(a, s), onClick = { a.toggleSense(s) })
        },
    )
    Footnote(
        "Off until you switch one on. Each reading is worked out on this phone, sealed with this phone's key and sent to your " +
            "computer through your call line, which can't read it; if your computer is off it waits there. The microphone is never used.",
    )

    Heading("Switches")
    Group(
        listOf(
            Item(
                "Connect straight to your call line",
                "Off: calls and messages come through ntfy.sh only",
                checked = Prefs.direct(a),
                onClick = { a.toggleDirect() },
            ),
            Item("Moving background", "Off: a still picture", checked = Prefs.moving(a), onClick = { a.toggleMoving() }),
            Item("Vivid colours", "Off: the wallpaper's quieter colours", checked = Prefs.vivid(a), onClick = { a.toggleVivid() }),
            Item("Floating bar", "Off: the bar sits on the bottom edge", checked = Prefs.floatingBar(a), onClick = { a.toggleFloatingBar() }),
        ),
    )

    Heading("This phone")
    var asking by rememberSaveable { mutableStateOf(false) }
    KCard(accent = 1) {
        Text(if (ui.demo) "Demo: not paired" else "Paired with " + Prefs.url(a), style = MaterialTheme.typography.bodyLarge)
        if (!ui.demo) Dim(
            if (!Prefs.direct(a)) "Calls come through ntfy.sh (the straight connection is switched off above)"
            else if (ListenService.direct()) "Connected straight to your call line"
            else "Not connected to your call line right now: calls still come through ntfy.sh",
            Modifier.padding(top = 4.dp),
        )
        Dim("App " + a.versionName(), Modifier.padding(top = 4.dp))
        Dim(
            "${ui.name}'s calls ring here like phone calls (earpiece, screen off at your ear); wake-up calls ring like an alarm.",
            Modifier.padding(top = 8.dp),
        )
        OutlinedButton(
            onClick = { asking = true },
            shapes = ButtonDefaults.shapes(),
            border = BorderStroke(1.dp, k.bad),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = k.bad),
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        ) { Text("Unpair this phone") }
    }
    if (asking) {
        AlertDialog(
            onDismissRequest = { asking = false },
            title = { Text("Unpair this phone?") },
            text = { Text("${ui.name} stops calling this phone, and the chat and Today kept here are forgotten. You can pair it again from your computer.") },
            confirmButton = { TextButton(onClick = { asking = false; a.unpair() }) { Text("Unpair", color = k.bad) } },
            dismissButton = { TextButton(onClick = { asking = false }) { Text("Cancel") } },
        )
    }
}
