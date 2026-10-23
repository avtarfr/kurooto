package io.github.avtarfr.kurooto

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ButtonGroup
import androidx.compose.material3.ButtonGroupDefaults
import androidx.compose.material3.LinearWavyProgressIndicator
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * The Today tab (0.6.0's Today screen, 0.7.0 in Compose): today's date, Call and Chat, then the dashboard's Today from
 * your computer's last copy (Today), so it shows with the computer asleep: the alarm (and whether this phone rings it
 * too, Alarms), classes and events, what's due (parts done, "4/7"; tap one for Done and +1, which go through the phone
 * outbox), reminders, open threads, how many questions wait in Inbox, "as of" when your call line got it, and a newer
 * app when there is one.
 */
@Composable
fun TodayPage(a: MainActivity, ui: HomeState, outer: PaddingValues) {
    val now = remember(ui.tick) { Date() }
    TabPage(
        a, ui, outer,
        title = SimpleDateFormat("EEEE", Locale.getDefault()).format(now),
        subtitle = SimpleDateFormat("d MMMM", Locale.getDefault()).format(now),
        actions = { Mark(ui.name) },
        hero = true,
        onScroll = { ui.todayScroll = it }, // the sky's parallax
    ) { TodayTab(a, ui) }
}

/** The assistant's initial in a nine-sided cookie (MaterialShapes), at the top bar's end. */
@Composable
private fun Mark(name: String) {
    ShapeBadge(
        MaterialShapes.Cookie9Sided,
        MaterialTheme.colorScheme.primaryContainer,
        Modifier.padding(end = 12.dp).semantics { contentDescription = name },
        size = 44,
    ) {
        Text(
            name.take(1).uppercase(),
            style = MaterialTheme.typography.titleLargeEmphasized,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
}

@Composable
private fun ColumnScope.TodayTab(a: MainActivity, ui: HomeState) {
    @Suppress("UNUSED_VARIABLE") val tick = ui.tick // settings re-read on resume and after a change
    CallChat(a, ui.name)
    SaidLine(ui.status, Modifier.padding(start = 4.dp))
    val d = ui.today
    val t = d.optJSONObject("list")
    if (t == null) {
        Spacer(Modifier.size(16.dp))
        KCard {
            Dim(
                if (d.optBoolean("off")) "Turned off on your computer (Settings → calls → today)."
                else "Nothing here yet. Your computer sends today's classes, what's due and your alarm to your call line, " +
                    "sealed for this phone; they show here once it has.",
            )
        }
    } else {
        val day = t.optString("day", "")
        val date = t.optString("date", "")
        if (day.isNotEmpty() && date.isNotEmpty() && date != SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(Date())) {
            Dim("This list is from $day.", Modifier.padding(start = 4.dp, top = 12.dp))
        }
        Alarm(a, t.optJSONObject("alarm"))
        val day1 = ArrayList<Item>()
        objects(t.optJSONArray("classes")).forEach {
            day1.add(Item(it.optString("name"), it.optString("time") + if (it.optBoolean("skipping")) " · skipping" else ""))
        }
        val ev = t.optJSONArray("events")
        for (i in 0 until (ev?.length() ?: 0)) day1.add(Item(ev!!.optString(i)))
        Section("Classes and events", day1)
        Due(a, ui, t.optJSONArray("due"))
        Section("Reminders", objects(t.optJSONArray("reminders")).map { Item(it.optString("what"), it.optString("when")) })
        Section("Open threads", objects(t.optJSONArray("threads")).map { Item(it.optString("text")) })
        val q = t.optInt("questions")
        if (q > 0) {
            TextButton(onClick = { ui.tab = 1 }, modifier = Modifier.padding(top = 8.dp)) {
                Text(if (q == 1) "1 question waits for you in Inbox" else "$q questions wait for you in Inbox")
            }
        }
        SaidLine(ui.todaySaid, Modifier.padding(start = 4.dp))
    }
    val asOf = asOf(d.optString("at", ""))
    val off = if (d.optString("computer") == "offline") "your computer is off" else ""
    val line = listOf(if (asOf.isEmpty()) "" else "As of $asOf", off).filter { it.isNotEmpty() }.joinToString(" · ")
    if (line.isNotEmpty()) Dim(line.replaceFirstChar { it.uppercase() }, Modifier.padding(start = 4.dp, top = 20.dp))
    if (d.optBoolean("old")) {
        Dim("Your call line doesn't have Today yet: your computer updates it by itself (at 05:10).", Modifier.padding(start = 4.dp, top = 8.dp))
    }
    ui.update?.let { (name, link) ->
        Button(
            onClick = { a.launch(Intent(Intent.ACTION_VIEW, Uri.parse(link))) },
            shapes = ButtonDefaults.shapes(),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.primaryContainer,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
            ),
            modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
        ) { Text("Update available: $name") }
    }
}

/** Call and Chat as a connected button group (Material 3 Expressive): large buttons whose inner corners are
 *  small; the pressed one widens and its corners morph. */
@Composable
private fun CallChat(a: MainActivity, name: String) {
    val h = ButtonDefaults.LargeContainerHeight
    ButtonGroup(
        overflowIndicator = {},
        horizontalArrangement = Arrangement.spacedBy(ButtonGroupDefaults.ConnectedSpaceBetween),
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
    ) {
        customItem(
            buttonGroupContent = {
                val src = remember { MutableInteractionSource() }
                Button(
                    onClick = { a.requestCall() },
                    shapes = ButtonDefaults.shapes(ButtonGroupDefaults.connectedLeadingButtonShape, ButtonGroupDefaults.connectedLeadingButtonPressShape),
                    interactionSource = src,
                    contentPadding = PaddingValues(horizontal = 16.dp), // the large size's own padding leaves no room for "Chat" on a narrow phone
                    modifier = Modifier.weight(1f).animateWidth(src).heightIn(min = h),
                ) {
                    Icon(painterResource(R.drawable.ic_call), contentDescription = null, modifier = Modifier.size(ButtonDefaults.iconSizeFor(h)))
                    Spacer(Modifier.width(ButtonDefaults.iconSpacingFor(h)))
                    Text("Call", modifier = Modifier.semantics { contentDescription = "Call $name" }, style = ButtonDefaults.textStyleFor(h), maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            },
            menuContent = {},
        )
        customItem(
            buttonGroupContent = {
                val src = remember { MutableInteractionSource() }
                FilledTonalButton(
                    onClick = { a.chat() },
                    shapes = ButtonDefaults.shapes(ButtonGroupDefaults.connectedTrailingButtonShape, ButtonGroupDefaults.connectedTrailingButtonPressShape),
                    interactionSource = src,
                    contentPadding = PaddingValues(horizontal = 16.dp), // the large size's own padding leaves no room for "Chat" on a narrow phone
                    modifier = Modifier.weight(1f).animateWidth(src).heightIn(min = h),
                ) {
                    Icon(painterResource(R.drawable.ic_talk), contentDescription = null, modifier = Modifier.size(ButtonDefaults.iconSizeFor(h)))
                    Spacer(Modifier.width(ButtonDefaults.iconSpacingFor(h)))
                    Text("Chat", style = ButtonDefaults.textStyleFor(h), maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            },
            menuContent = {},
        )
    }
}

/** A section: its heading, then its group; left out when there's nothing in it. */
@Composable
private fun Section(name: String, rows: List<Item>) {
    if (rows.isEmpty()) return
    Heading(name)
    Group(rows)
}

/** The next alarm, and whether this phone rings it too (a switch); Android 12+ without exact alarms: why that
 *  matters, and Allow. */
@Composable
private fun ColumnScope.Alarm(a: MainActivity, al: JSONObject?) {
    if (al == null || al.length() == 0) return
    val at = al.optJSONArray("at")
    val next = al.optString("next", "")
    val daily = al.optString("daily", "")
    val rows = arrayListOf(Item(if (next.isEmpty()) "No alarm set" else next, if (daily.isEmpty()) null else "Daily alarm $daily"))
    var on = false
    if (at != null && at.length() > 0) {
        on = a.alarmOn()
        val sub = when {
            !on -> "Off: only the call from your call line rings."
            a.alarmSet() == 0L -> "On: rings here too, even with your computer and call line out of reach."
            a.exactAlarms() -> "On: set on this phone too, so it rings even with your computer and call line out of reach."
            else -> "On, but Android doesn't allow exact alarms for Kurooto yet: it may ring a few minutes late."
        }
        rows.add(Item("Ring on this phone too", sub, checked = on, onClick = { a.toggleAlarm() }))
    }
    Section("Alarm", rows)
    if (on && !a.exactAlarms()) {
        TextButton(onClick = { a.allowExact() }, modifier = Modifier.align(Alignment.End)) { Text("Allow exact alarms") }
    }
}

/** What's due: title, parts done and when. Tap one for Done and +1 (quizzes and exams have none). */
@Composable
private fun Due(a: MainActivity, ui: HomeState, ds: JSONArray?) {
    val rows = objects(ds).map { x ->
        val id = x.optString("id")
        val parts = if (x.has("parts")) "${x.optInt("done")}/${x.optInt("parts")} · " else ""
        val acts = x.optJSONArray("acts")
        val can = acts != null && acts.length() > 0
        val open = can && id == ui.openDue
        Item(
            x.optString("title"),
            parts + "due " + x.optString("when") + if (x.optBoolean("exam")) " · quiz or exam" else "",
            onClick = if (can) ({ ui.openDue = if (id == ui.openDue) "" else id }) else null,
            extra = if (!open && !x.has("parts")) null else ({
                if (x.optInt("parts") > 0) {
                    val f = (x.optInt("done").toFloat() / x.optInt("parts")).coerceIn(0f, 1f)
                    // the wave holds still: a deadline's parts don't need to move (and a moving wave redraws every frame)
                    LinearWavyProgressIndicator(progress = { f }, waveSpeed = 0.dp, modifier = Modifier.fillMaxWidth().padding(top = 10.dp))
                }
                if (open) Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (k in 0 until acts!!.length()) {
                        val act = acts.optString(k)
                        val go = { a.dueAct(id, act, x.optString("title")) }
                        if (act == "done") Button(onClick = go, shapes = ButtonDefaults.shapes(), modifier = Modifier.weight(1f)) { Text("Done") }
                        else FilledTonalButton(onClick = go, shapes = ButtonDefaults.shapes(), modifier = Modifier.weight(1f)) { Text(act) }
                    }
                }
            }),
        )
    }
    Section("Due", rows)
}

internal fun objects(a: JSONArray?): List<JSONObject> = (0 until (a?.length() ?: 0)).mapNotNull { a!!.optJSONObject(it) }

/** "14:05" for an ISO time today, "Thu 14:05" another day; "" if there's none. */
internal fun asOf(iso: String?): String {
    if (iso == null || iso.length < 19) return ""
    return try {
        val inp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.ROOT)
        inp.timeZone = TimeZone.getTimeZone("UTC")
        val t = inp.parse(iso.substring(0, 19)) ?: return ""
        val day = SimpleDateFormat("yyyyMMdd", Locale.ROOT)
        val today = day.format(t) == day.format(Date())
        SimpleDateFormat(if (today) "HH:mm" else "EEE HH:mm", Locale.getDefault()).format(t)
    } catch (e: Exception) {
        ""
    }
}
