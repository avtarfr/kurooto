package io.github.avtarfr.kurooto

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.material3.ButtonGroup
import androidx.compose.material3.ButtonGroupDefaults
import androidx.compose.material3.ToggleButton
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.LinearWavyProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * The Today pane (0.6.0's Today screen, 0.7.0 in Compose, 0.8.10 a bento grid): the date, big; the class you're in now
 * as a large card with a ring of the time left (or what's next); what's waiting for you and what's due soon as two cards;
 * the day as a strip of its classes and events with a line at now; what Kurooto asked you (answered right here, as in
 * the waiting sheet); what's next and the next alarm; then what's due (parts done, "4/7"; tap one for Done and +1, which
 * go through the phone outbox), reminders and open threads. All from your computer's last copy (Today), so it shows with
 * the computer asleep; "as of" says when your call line got it. Calls and the chat live in Chat now: no buttons for them
 * here.
 */
@Composable
fun TodayPane(a: MainActivity, ui: HomeState, room: PaddingValues) {
    val now = remember(ui.tick) { Date() }
    val grid = rememberLazyGridState()
    val scope = rememberCoroutineScope()
    val keys = remember { ArrayList<String>() } // the grid's keys in order, to scroll to a section
    val goTo = { key: String -> scope.launch { keys.indexOf(key).takeIf { it >= 0 }?.let { grid.animateScrollToItem(it) } }; Unit }
    val d = ui.today
    val t = d.optJSONObject("list")
    val waiting = ui.waiting ?: emptyList()
    val due = objects(t?.optJSONArray("due"))
    val slots = remember(t) { slots(t) }
    PaneGrid(a, ui, room, grid, onScroll = { ui.todayScroll = it }) {
        keys.clear()
        fun add(key: String, type: String = key, content: @Composable () -> Unit) { keys.add(key); wide(key, type, content) }
        keys.add("title")
        paneTitle(
            SimpleDateFormat("EEE d", Locale.getDefault()).format(now),
            over = SimpleDateFormat("MMMM", Locale.getDefault()).format(now),
        ) { Mark(ui.name) }
        add("now") { NowCard(a, d, t, slots) }
        if (t != null) {
            keys.add("waiting")
            item(key = "waiting", contentType = "count") {
                val cs = MaterialTheme.colorScheme
                CountTile(
                    "Waiting", R.drawable.ic_hourglass, waiting.size,
                    if (waiting.isEmpty()) "nothing for you" else waitingWhat(waiting),
                    cs.tertiaryContainer, cs.onTertiaryContainer,
                ) { if (waiting.isNotEmpty()) goTo("asked") }
            }
            keys.add("dueSoon")
            item(key = "dueSoon", contentType = "count") {
                val cs = MaterialTheme.colorScheme
                val first = due.firstOrNull()
                CountTile(
                    "Due soon", R.drawable.ic_flag, due.size,
                    if (first == null) "nothing due" else first.optString("title") + " · " + first.optString("when"),
                    cs.secondaryContainer, cs.onSecondaryContainer,
                ) { if (due.isNotEmpty()) goTo("due") }
            }
            if (slots.isNotEmpty()) add("day") { DayStrip(slots) }
        }
        if (waiting.isNotEmpty()) add("asked") {
            Tile(tileColor(), MaterialTheme.colorScheme.onSurface, Modifier.fillMaxWidth()) {
                TileLabel("Asked you", R.drawable.ic_help, MaterialTheme.colorScheme.onSurfaceVariant)
                InboxContent(a, ui)
            }
        }
        if (t != null) {
            val nowMin = minuteOfDay(System.currentTimeMillis())
            val next = slots.filter { it.start > nowMin && !it.skipping }.minByOrNull { it.start }
            keys.add("next")
            item(key = "next", contentType = "small") {
                SmallTile("Next", next?.let { hm(it.start) } ?: "—", next?.name ?: "Nothing else today")
            }
            keys.add("alarm")
            item(key = "alarm", contentType = "small") {
                val at = alarmTimes(t).firstOrNull()
                SmallTile("Alarm", at?.let { clock(it) } ?: "Off", at?.let { dayWord(it) } ?: "None set", R.drawable.ic_nav_alarm) {
                    ui.pane = Pane.ALARMS
                }
            }
            if (due.isNotEmpty()) add("due", "section") { Section("Due", R.drawable.ic_flag) { Due(a, ui, due) } }
            val rem = objects(t.optJSONArray("reminders")).map { Item(it.optString("what"), it.optString("when")) }
            if (rem.isNotEmpty()) add("reminders", "section") { Section("Reminders", R.drawable.ic_bell) { Group(rem) } }
            val th = objects(t.optJSONArray("threads")).map { Item(it.optString("text")) }
            if (th.isNotEmpty()) add("threads", "section") { Section("Open threads", R.drawable.ic_nav_chat) { Group(th) } }
            // (0.9.0) the day's plan and what to start (calls.today_plan)
            val plan = t.optJSONArray("plan")
            val planRows = (0 until (plan?.length() ?: 0)).map { Item(plan!!.optString(it)) } +
                objects(t.optJSONArray("start")).map { Item(it.optString("title"), it.optString("when")) }
            if (planRows.isNotEmpty()) add("plan", "section") { Section("Plan", R.drawable.ic_clock) { Group(planRows) } }
            // (0.9.0) what waits on the computer (calls.today_waiting), hours studied, the laptop's camera (face.phone_badge)
            val w = t.optJSONObject("waiting")
            val cam = t.optJSONObject("camera")
            val more = ArrayList<Item>()
            if (w != null) {
                val held = w.optInt("held")
                if (held > 0) more.add(Item("$held held " + (if (held == 1) "message" else "messages"), "Tap to send today's now", onClick = { a.dueAct("", "send_held", "Send held messages") }))
                val props = w.optInt("proposals")
                if (props > 0) more.add(Item("$props " + (if (props == 1) "proposal waits" else "proposals wait") + " for your tap", "On the dashboard, or /proposals"))
                val brain = w.optString("brain")
                if (brain.isNotEmpty()) more.add(Item("Brain: $brain"))
            }
            if (t.has("study_h")) more.add(Item("Studied today", t.optString("study_h") + " h"))
            if (cam != null) more.add(Item(if (cam.optBoolean("on")) "Laptop camera on" else "Laptop camera off", cam.optString("why")))
            if (more.isNotEmpty()) add("computer", "section") { Section("On your computer", R.drawable.ic_hourglass) { Group(more) } }
            // (0.9.2) the room mode at the desk (Voice's room modes): only while Voice and room modes are on
            val roomJ = t.optJSONObject("room")
            if (roomJ != null) add("room", "section") { Section("Room", R.drawable.ic_volume_up) { RoomChoice(a, roomJ) } }
        }
        add("foot") { Foot(a, ui, d, t) }
    }
}

/** Kurooto's mark (the moth, as on the launcher) at the title's end, named for the assistant. */
@Composable
private fun Mark(name: String) {
    Image(
        painterResource(R.drawable.k_mark), // a bitmap: the mipmap is an adaptive icon, which painterResource can't draw
        contentDescription = name,
        modifier = Modifier.padding(bottom = 8.dp).size(44.dp),
    )
}

/** One class or event on the day's strip: minutes of the day. */
internal class Slot(val start: Int, val end: Int, val name: String, val event: Boolean, val skipping: Boolean)

private val SPAN = Regex("""^\s*(\d{1,2}):(\d{2})(?:\s*[–-]\s*(\d{1,2}):(\d{2}))?\s*(.*)$""")

/** The day's classes ("09:30–11:00") and events ("16:30 Study group"; an hour long when they don't say), by start. */
internal fun slots(t: JSONObject?): List<Slot> {
    if (t == null) return emptyList()
    val out = ArrayList<Slot>()
    fun parse(time: String, name: String, event: Boolean, skipping: Boolean) {
        val m = SPAN.find(time) ?: return
        val s = m.groupValues[1].toInt() * 60 + m.groupValues[2].toInt()
        val e = if (m.groupValues[3].isNotEmpty()) m.groupValues[3].toInt() * 60 + m.groupValues[4].toInt() else s + 60
        val n = name.ifEmpty { m.groupValues[5] }.trim()
        out.add(Slot(s, if (e > s) e else s + 60, n.ifEmpty { "Event" }, event, skipping))
    }
    objects(t.optJSONArray("classes")).forEach { parse(it.optString("time"), it.optString("name"), false, it.optBoolean("skipping")) }
    val ev = t.optJSONArray("events")
    for (i in 0 until (ev?.length() ?: 0)) parse(ev!!.optString(i), "", true, false)
    return out.sortedBy { it.start }
}

internal fun minuteOfDay(ms: Long): Int = Calendar.getInstance().apply { timeInMillis = ms }.let { it.get(Calendar.HOUR_OF_DAY) * 60 + it.get(Calendar.MINUTE) }

internal fun hm(min: Int): String = String.format(Locale.ROOT, "%02d:%02d", (min / 60) % 24, min % 60)

/** "24m", "1h 5m", "3h". */
internal fun span(min: Int): String = when {
    min < 60 -> "${min}m"
    min % 60 == 0 || min >= 180 -> "${min / 60}h"
    else -> "${min / 60}h ${min % 60}m"
}

/** The clock, as state that changes every half minute: the cards that show "now" read it, nothing else. */
@Composable
internal fun rememberNow(): State<Long> {
    val s = remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(30_000L - System.currentTimeMillis() % 30_000L)
            s.longValue = System.currentTimeMillis()
        }
    }
    return s
}

/** The big card: the class you're in (until when, a ring of the time left), else what's next (how long until), else that
 *  the day is done; before the computer has sent a list, why there's none. */
@Composable
private fun NowCard(a: MainActivity, d: JSONObject, t: JSONObject?, slots: List<Slot>) {
    val cs = MaterialTheme.colorScheme
    val vivid = Prefs.vivid(a)
    val bg = if (vivid) cs.primary else cs.primaryContainer
    val fg = if (vivid) cs.onPrimary else cs.onPrimaryContainer
    if (t == null) {
        Tile(bg, fg, Modifier.fillMaxWidth()) {
            TileLabel("Today")
            Text(
                if (d.optBoolean("off")) "Turned off on your computer (Settings → calls → today)."
                else "Nothing here yet. Your computer sends today's classes, what's due and your alarm to your call line, " +
                    "sealed for this phone; they show here once it has.",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        return
    }
    val nowMs by rememberNow()
    val now = minuteOfDay(nowMs)
    val cur = slots.firstOrNull { it.start <= now && now < it.end && !it.skipping }
    val next = slots.filter { it.start > now && !it.skipping }.minByOrNull { it.start }
    val (over, title, sub, ring) = when {
        cur != null -> {
            val after = slots.firstOrNull { it.start >= cur.end && !it.skipping }
            Quad(
                "Now · until " + hm(cur.end), cur.name,
                after?.let { "then " + it.name + " at " + hm(it.start) } ?: "the last one today",
                Pair((cur.end - now).toFloat() / (cur.end - cur.start), span(cur.end - now)),
            )
        }
        next != null -> Quad(
            "Next · " + hm(next.start), next.name, "in " + span(next.start - now),
            Pair(1f - minOf(next.start - now, 180) / 180f, span(next.start - now)),
        )
        else -> Quad("Today", "Nothing else on today", if (slots.isEmpty()) "No classes or events" else "The day's done", null)
    }
    Tile(bg, fg, Modifier.fillMaxWidth(), padding = 20.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                TileLabel(over)
                Text(
                    title,
                    style = MaterialTheme.typography.headlineMediumEmphasized,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Text(sub, style = MaterialTheme.typography.bodyLarge, color = fg.copy(alpha = 0.8f), modifier = Modifier.padding(top = 2.dp))
            }
            if (ring != null) Ring(ring.first, ring.second, fg, Modifier.padding(start = 12.dp))
        }
    }
}

private data class Quad(val over: String, val title: String, val sub: String, val ring: Pair<Float, String>?)

/** A ring of `left` (0..1) with a word in it ("24m"). */
@Composable
private fun Ring(left: Float, label: String, color: Color, modifier: Modifier = Modifier) {
    Box(modifier.size(84.dp).semantics { contentDescription = "$label left" }, contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(84.dp)) {
            val w = 8.dp.toPx()
            val inset = w / 2
            val sz = Size(size.width - w, size.height - w)
            drawArc(color.copy(alpha = 0.22f), 0f, 360f, false, Offset(inset, inset), sz, style = Stroke(w))
            drawArc(color, -90f, 360f * left.coerceIn(0f, 1f), false, Offset(inset, inset), sz, style = Stroke(w, cap = StrokeCap.Round))
        }
        Text(label, style = MaterialTheme.typography.titleMediumEmphasized, color = color)
    }
}

/** A half-width card with a big number: Waiting, Due soon. */
@Composable
private fun CountTile(label: String, icon: Int, n: Int, line: String, bg: Color, fg: Color, onClick: () -> Unit) {
    Tile(bg, fg, Modifier.fillMaxWidth().heightIn(min = 168.dp), onClick = onClick) {
        TileLabel(label, icon)
        Text("$n", style = MaterialTheme.typography.displayMediumEmphasized, modifier = Modifier.padding(top = 4.dp))
        Text(line, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

/** A half-width card with a time: Next, Alarm. */
@Composable
private fun SmallTile(label: String, big: String, line: String, icon: Int = R.drawable.ic_clock, onClick: (() -> Unit)? = null) {
    val cs = MaterialTheme.colorScheme
    Tile(tileColor(), cs.onSurface, Modifier.fillMaxWidth(), onClick = onClick) {
        TileLabel(label, icon, cs.onSurfaceVariant)
        Text(big, style = MaterialTheme.typography.displaySmallEmphasized, maxLines = 1, modifier = Modifier.padding(top = 4.dp))
        Text(line, style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

/** The day as one strip: each class and event a rounded block in its colour along the hours (8 to 20 at least), the
 *  ones gone by dimmed, a line at now; the names under it. Drawn in one pass. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DayStrip(slots: List<Slot>) {
    val cs = MaterialTheme.colorScheme
    val colours = listOf(cs.primary, cs.tertiary, cs.secondary, cs.primaryContainer, cs.tertiaryContainer, cs.inversePrimary)
    val names = slots.map { it.name }.distinct()
    val colour = { s: Slot -> colours[names.indexOf(s.name) % colours.size] }
    val from = minOf(8 * 60, slots.minOf { it.start } / 60 * 60)
    val to = maxOf(20 * 60, (slots.maxOf { it.end } + 59) / 60 * 60)
    val nowMs by rememberNow()
    val now = minuteOfDay(nowMs)
    val track = cs.surfaceContainerHighest
    val past = cs.onSurface.copy(alpha = 0.18f)
    val line = cs.onSurface
    Tile(tileColor(), cs.onSurface, Modifier.fillMaxWidth()) {
        TileLabel("The day", R.drawable.ic_nav_today, cs.onSurfaceVariant)
        Canvas(Modifier.fillMaxWidth().height(52.dp).padding(top = 12.dp).semantics { contentDescription = "The day: " + names.joinToString(", ") }) {
            val w = size.width
            val h = size.height
            val x = { m: Int -> (m - from).toFloat() / (to - from) * w }
            val r = CornerRadius(12.dp.toPx())
            drawRoundRect(track, Offset.Zero, Size(w, h), r)
            slots.forEach { s ->
                val x0 = x(s.start)
                val x1 = maxOf(x(s.end), x0 + 10.dp.toPx())
                val c = if (s.end <= now || s.skipping) past else colour(s)
                drawRoundRect(c, Offset(x0 + 1.dp.toPx(), 0f), Size(x1 - x0 - 2.dp.toPx(), h), r)
            }
            if (now in from..to) {
                val nx = x(now)
                drawLine(line, Offset(nx, -4.dp.toPx()), Offset(nx, h + 4.dp.toPx()), 3.dp.toPx(), StrokeCap.Round)
            }
        }
        Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
            // the hour marks every three hours
            val marks = (from / 60..to / 60 step 3).toList()
            marks.forEachIndexed { i, hr ->
                Text(
                    "$hr",
                    style = MaterialTheme.typography.labelMedium,
                    color = cs.onSurfaceVariant,
                    modifier = if (i < marks.size - 1) Modifier.weight(1f) else Modifier,
                )
            }
        }
        FlowRow(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            names.forEach { n ->
                val s = slots.first { it.name == n }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(10.dp).clip(CircleShape).background(if (s.skipping) past else colour(s)))
                    Spacer(Modifier.width(6.dp))
                    Text(
                        hm(s.start) + " " + n + if (s.skipping) " (skipping)" else "",
                        style = MaterialTheme.typography.bodyMedium,
                        color = cs.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

private val ROOM_MODES = listOf("alone" to "Alone", "company" to "Company", "night" to "Night", "silent" to "Silent")
private val ROOM_WHAT = mapOf(
    "alone" to "As you set it",
    "company" to "Nothing of yours said aloud by itself",
    "night" to "Quieter, nothing of yours said aloud by itself",
    "silent" to "Nothing aloud: answers on screen only",
)

/** (0.9.2) The room mode: four connected toggle buttons (the one on is filled), what it does and until when. A tap asks
 *  your computer (BeingAsk, op voice.room) and shows its answer; the next Today copy follows it. A mode ends by itself. */
@Composable
private fun RoomChoice(a: MainActivity, room: JSONObject) {
    var mode by remember(room.optString("mode")) { mutableStateOf(room.optString("mode", "alone")) }
    var until by remember(room.optString("until")) { mutableStateOf(room.optString("until")) }
    var note by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxWidth().padding(horizontal = 4.dp)) {
        ButtonGroup(
            overflowIndicator = {},
            horizontalArrangement = Arrangement.spacedBy(ButtonGroupDefaults.ConnectedSpaceBetween),
            modifier = Modifier.fillMaxWidth(),
        ) {
            ROOM_MODES.forEachIndexed { i, (id, label) ->
                customItem(
                    buttonGroupContent = {
                        val src = remember { MutableInteractionSource() }
                        ToggleButton(
                            checked = mode == id,
                            enabled = !busy,
                            onCheckedChange = {
                                if (id != mode) {
                                    busy = true
                                    scope.launch {
                                        val r = withContext(Dispatchers.IO) {
                                            runCatching { JSONObject(BeingAsk.send(a, "voice.room", JSONObject().put("mode", id).toString())) }.getOrNull()
                                        }
                                        busy = false
                                        if (r != null && r.optBoolean("ok")) {
                                            mode = r.optString("mode", id)
                                            until = r.optString("until_hm")
                                        }
                                        note = r?.optString("note") ?: "That didn't work."
                                    }
                                }
                            },
                            shapes = when (i) {
                                0 -> ButtonGroupDefaults.connectedLeadingButtonShapes()
                                ROOM_MODES.lastIndex -> ButtonGroupDefaults.connectedTrailingButtonShapes()
                                else -> ButtonGroupDefaults.connectedMiddleButtonShapes()
                            },
                            interactionSource = src,
                            contentPadding = PaddingValues(horizontal = 6.dp),
                            modifier = Modifier.weight(1f).animateWidth(src).semantics { role = Role.RadioButton },
                        ) { Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                    },
                    menuContent = {},
                )
            }
        }
        val what = (ROOM_WHAT[mode] ?: "") + if (mode != "alone" && until.isNotEmpty()) " · until $until" else ""
        Text(
            note.ifEmpty { what },
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 8.dp, top = 8.dp, bottom = 4.dp),
        )
    }
}

/** A section card: its label, then its rows. */
@Composable
private fun Section(name: String, icon: Int, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        Box(Modifier.padding(start = 8.dp, top = 8.dp, bottom = 10.dp)) { TileLabel(name, icon, MaterialTheme.colorScheme.primary) }
        content()
    }
}

/** What's due: title, parts done and when. Tap one for Done and +1 (quizzes and exams have none). */
@Composable
private fun Due(a: MainActivity, ui: HomeState, ds: List<JSONObject>) {
    val rows = ds.map { x ->
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
    Group(rows)
    SaidLine(ui.todaySaid, Modifier.padding(start = 8.dp))
}

/** The end of the page: "as of", the computer off, an old list, a newer app. */
@Composable
private fun Foot(a: MainActivity, ui: HomeState, d: JSONObject, t: JSONObject?) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 4.dp)) {
        val day = t?.optString("day", "") ?: ""
        val date = t?.optString("date", "") ?: ""
        if (day.isNotEmpty() && date.isNotEmpty() && date != SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(Date())) {
            Dim("This list is from $day.", Modifier.padding(top = 4.dp))
        }
        val asOf = asOf(d.optString("at", ""))
        val off = if (d.optString("computer") == "offline") "your computer is off" else ""
        val line = listOf(if (asOf.isEmpty()) "" else "As of $asOf", off).filter { it.isNotEmpty() }.joinToString(" · ")
        if (line.isNotEmpty()) Dim(line.replaceFirstChar { it.uppercase() }, Modifier.padding(top = 4.dp))
        if (d.optBoolean("old")) {
            Dim("Your call line doesn't have Today yet: your computer updates it by itself (at 05:10).", Modifier.padding(top = 8.dp))
        }
        ui.update?.let { (name, link) ->
            Button(
                onClick = { a.launch(Intent(Intent.ACTION_VIEW, Uri.parse(link))) },
                shapes = ButtonDefaults.shapes(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ),
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) { Text("Update available: $name") }
        }
    }
}

/** The alarms still to ring from your computer's list (s), soonest first. */
internal fun alarmTimes(t: JSONObject?): List<Long> {
    val at = t?.optJSONObject("alarm")?.optJSONArray("at") ?: return emptyList()
    val now = System.currentTimeMillis() / 1000
    return (0 until at.length()).map { at.optLong(it) }.filter { it > now - 60 }.sorted()
}

/** "06:50" for an alarm (s). */
internal fun clock(s: Long): String = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(s * 1000))

/** "Today", "Tomorrow" or "Wed 29" for an alarm (s). */
internal fun dayWord(s: Long): String {
    val c = Calendar.getInstance()
    val d = Calendar.getInstance().apply { timeInMillis = s * 1000 }
    val days = (d.get(Calendar.YEAR) - c.get(Calendar.YEAR)) * 366 + d.get(Calendar.DAY_OF_YEAR) - c.get(Calendar.DAY_OF_YEAR)
    return when (days) {
        0 -> "Today"
        1 -> "Tomorrow"
        else -> SimpleDateFormat("EEE d", Locale.getDefault()).format(Date(s * 1000))
    }
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
