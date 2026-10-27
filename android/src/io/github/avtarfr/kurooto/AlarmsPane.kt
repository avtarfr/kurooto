package io.github.avtarfr.kurooto

import android.content.Intent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * The Alarms pane (0.8.10): the wake-up alarms your computer set (they come with Today, Alarms.java sets the soonest on
 * this phone too) as a bento grid: the next one as the big card ("Morning alarm · from your computer", its tone, and the
 * switch for ringing on this phone too), the rest as big numerals two to a row, then the ringtones (calls and alarms)
 * and bedside mode as cards. Alarms are set and changed on your computer (tell Kurooto, or its dashboard); this phone
 * only rings them.
 */
@Composable
fun AlarmsPane(a: MainActivity, ui: HomeState, room: PaddingValues) {
    @Suppress("UNUSED_VARIABLE") val tick = ui.tick // the switch and the tones are re-read after a change
    val t = ui.today.optJSONObject("list")
    val al = t?.optJSONObject("alarm")
    val times = alarmTimes(t)
    val daily = al?.optString("daily", "") ?: ""
    PaneGrid(a, ui, room) {
        paneTitle("Alarms")
        wide("hero") { Hero(a, al, times.firstOrNull()) }
        val on = a.alarmOn()
        if (times.isNotEmpty() && on && !a.exactAlarms()) wide("exact") {
            Tile(MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer, Modifier.fillMaxWidth()) {
                Text("Android doesn't allow exact alarms for Kurooto yet: the alarm may ring a few minutes late.", style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = { a.allowExact() }, modifier = Modifier.align(Alignment.End)) { Text("Allow exact alarms") }
            }
        }
        times.drop(1).forEach { s ->
            item(key = "at-$s", contentType = "alarm") {
                val c = clock(s)
                Numeral(c, dayWord(s) + if (daily.isNotEmpty() && daily == c) " · daily" else "", on)
            }
        }
        item(key = "tones", contentType = "tile") { Tones(a) }
        item(key = "bedside", contentType = "tile") { Bedside(a, ui, times.firstOrNull()) }
        wide("note") {
            Footnote(
                "Alarms are set on your computer: tell Kurooto (\"wake me at 6:50\") or use its dashboard. The alarm tone plays on " +
                    "the alarm volume, so it rings even on silent.",
                Modifier.padding(bottom = 8.dp),
            )
        }
    }
}

/** The next alarm, big: when, which day and why, its tone, and whether this phone rings it too. */
@Composable
private fun Hero(a: MainActivity, al: org.json.JSONObject?, next: Long?) {
    val cs = MaterialTheme.colorScheme
    val vivid = Prefs.vivid(a)
    val bg = if (vivid) cs.primary else cs.primaryContainer
    val fg = if (vivid) cs.onPrimary else cs.onPrimaryContainer
    Tile(bg, fg, Modifier.fillMaxWidth(), padding = 20.dp) {
        TileLabel("Morning alarm · from your computer", R.drawable.ic_laptop)
        if (next == null) {
            Text(
                if (al == null || al.length() == 0) "The alarm is off on your computer, or it hasn't sent today's list yet."
                else "No alarm set. Tell Kurooto when to wake you; it shows here once your computer sends it.",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(top = 10.dp),
            )
            return@Tile
        }
        Text(clock(next), style = MaterialTheme.typography.displayLargeEmphasized.copy(fontSize = MaterialTheme.typography.displayLarge.fontSize * 1.45f, lineHeight = MaterialTheme.typography.displayLarge.lineHeight * 1.4f))
        val day = SimpleDateFormat("EEEE", Locale.getDefault()).format(Date(next * 1000))
        val why = al?.optString("reason", "")?.takeIf { it.isNotEmpty() && it != "Wake-up call" }
        Text(listOfNotNull(day, why).joinToString(" · "), style = MaterialTheme.typography.bodyLarge)
        val on = a.alarmOn()
        Row(Modifier.fillMaxWidth().padding(top = 14.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Surface(
                onClick = { a.pickTone(true) },
                shape = CircleShape,
                color = fg.copy(alpha = 0.08f),
                contentColor = fg,
                border = BorderStroke(1.dp, fg.copy(alpha = 0.3f)),
                modifier = Modifier.weight(1f, fill = false),
            ) {
                Row(Modifier.padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(painterResource(R.drawable.ic_music), contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(a.toneName(true), style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
            Spacer(Modifier.width(12.dp))
            Switch(
                checked = on,
                onCheckedChange = { a.toggleAlarm() },
                thumbContent = if (on) ({ Icon(painterResource(R.drawable.ic_ok), contentDescription = null, modifier = Modifier.size(SwitchDefaults.IconSize)) }) else null,
                colors = SwitchDefaults.colors(
                    checkedTrackColor = fg, checkedThumbColor = bg, checkedIconColor = fg,
                    uncheckedTrackColor = bg, uncheckedBorderColor = fg.copy(alpha = 0.6f), uncheckedThumbColor = fg.copy(alpha = 0.6f),
                ),
                modifier = Modifier.semantics { contentDescription = "Ring on this phone too" },
            )
        }
        Text(
            if (on) "Rings on this phone too, even with your computer and call line out of reach." else "Only the call from your call line rings.",
            style = MaterialTheme.typography.bodySmall,
            color = fg.copy(alpha = 0.8f),
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}

/** One of the later alarms: the time as a big numeral, the day under it. Dimmer when this phone doesn't ring them. */
@Composable
private fun Numeral(time: String, day: String, on: Boolean) {
    val cs = MaterialTheme.colorScheme
    Tile(tileColor(), cs.onSurface, Modifier.fillMaxWidth()) {
        Text(
            time,
            style = MaterialTheme.typography.displayMediumEmphasized,
            color = if (on) cs.onSurface else cs.onSurfaceVariant,
            maxLines = 1,
        )
        Text(day, style = MaterialTheme.typography.bodyLarge, color = cs.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

/** The ringtones: calls and alarms, each a tap to change it (the phone's own picker). */
@Composable
private fun Tones(a: MainActivity) {
    val cs = MaterialTheme.colorScheme
    Tile(cs.tertiaryContainer, cs.onTertiaryContainer, Modifier.fillMaxWidth().heightIn(min = 190.dp)) {
        TileLabel("Ringtones", R.drawable.ic_music)
        listOf(false to "calls", true to "alarms").forEach { (alarm, what) ->
            Column(
                Modifier.fillMaxWidth().padding(top = 10.dp).clip(RoundedCornerShape(12.dp)).clickable { a.pickTone(alarm) }
                    .semantics { contentDescription = (if (alarm) "Wake-up alarm tone: " else "Call ringtone: ") + a.toneName(alarm) },
            ) {
                Text(a.toneName(alarm), style = MaterialTheme.typography.titleMediumEmphasized, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(what, style = MaterialTheme.typography.bodyMedium, color = cs.onTertiaryContainer.copy(alpha = 0.8f))
            }
        }
    }
}

/** Bedside mode: a dark card with the clock as it shows there, the next alarm, and when it opens by itself. Tap: open it. */
@Composable
private fun Bedside(a: MainActivity, ui: HomeState, next: Long?) {
    val cs = MaterialTheme.colorScheme
    val now by rememberNow()
    Tile(
        cs.surfaceContainerLowest.copy(alpha = 0.94f), cs.onSurface, Modifier.fillMaxWidth().heightIn(min = 190.dp),
        onClick = { a.startActivity(Intent(a, BedsideActivity::class.java).putExtra("demo", ui.demo)) },
        border = BorderStroke(1.dp, cs.outlineVariant),
    ) {
        TileLabel("Bedside", R.drawable.ic_bedtime, cs.onSurfaceVariant)
        Text(
            SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(now)),
            style = MaterialTheme.typography.displaySmall.copy(fontWeight = FontWeight.Light),
            color = cs.primary.copy(alpha = 0.75f),
            modifier = Modifier.padding(top = 6.dp),
        )
        if (next != null) Text("alarm " + clock(next), style = MaterialTheme.typography.bodyMedium, color = cs.primary.copy(alpha = 0.75f))
        Text(
            if (Prefs.bedsideAuto(a)) "On the charger from " + Prefs.bedsideFrom(a) + " to " + Prefs.bedsideTo(a) else "Tap to open it",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}
