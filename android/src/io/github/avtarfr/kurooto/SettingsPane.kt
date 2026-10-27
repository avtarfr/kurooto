package io.github.avtarfr.kurooto

import androidx.compose.runtime.CompositionLocalProvider
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibilityScope
import androidx.compose.animation.BoundsTransform
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.SharedTransitionScope
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ButtonGroupDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.ToggleButton
import androidx.compose.material3.ToggleButtonDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.material3.toShape
import androidx.graphics.shapes.RoundedPolygon
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * The Settings pane (0.8.10): every setting the app has, in groups, under a search field that searches all of them. The
 * groups are a bento grid of tiles (a shape and a colour each, and how it's set now); a tile opens its group's page with a
 * container transform (the tile grows into the page; back, or the predictive back gesture, shrinks it again). The groups:
 * Look (colours, Vivid/Calm, the bar, the moving background), Notifications, Chat (the chat's own, ChatSettings), Calls,
 * Places, Senses, Bedside and This phone (the checklist, pairing, the app's version and update, Unpair). Ringtones and the
 * alarm's switch are in Alarms (the search finds them there). Kurooto's own settings are on the computer's dashboard: a
 * note says so.
 */
@Composable
fun SettingsPane(a: MainActivity, ui: HomeState, room: PaddingValues) {
    val open = ui.settingsGroup?.let { n -> SetGroup.entries.firstOrNull { it.name == n } }
    val tr = rememberBackTransition(open, null, open != null, "settings") { ui.settingsGroup = null }
    val reduced = LocalReducedMotion.current
    val ms = MaterialTheme.motionScheme
    val holder = rememberSaveableStateHolder()
    tr.AnimatedContent(
        transitionSpec = {
            if (reduced) EnterTransition.None togetherWith ExitTransition.None
            else fadeIn(ms.defaultEffectsSpec()) togetherWith fadeOut(ms.fastEffectsSpec())
        },
    ) { g ->
        val scope = this
        if (g == null) holder.SaveableStateProvider("grid") { Groups(a, ui, room, scope) }
        else GroupPage(a, ui, room, g, scope)
    }
}

/** A group of settings: its name, its icon in a Material shape, and its tile's colours with Vivid on (dark, light). */
enum class SetGroup(val title: String, val icon: Int, val dark: Pair<Long, Long>, val light: Pair<Long, Long>) {
    LOOK("Look", R.drawable.ic_palette, 0xFFFFB873 to 0xFF4A2800, 0xFFFFDCBE to 0xFF4A2800),
    NOTIFICATIONS("Notifications", R.drawable.ic_bell, 0xFFDDB8FF to 0xFF3A1A57, 0xFFF0DBFF to 0xFF3A1A57),
    CHAT("Chat", R.drawable.ic_nav_chat, 0xFFB5DB8F to 0xFF1F3A0B, 0xFFCDEDA9 to 0xFF1F3A0B),
    CALLS("Calls", R.drawable.ic_call, 0xFF9CCBFF to 0xFF00315C, 0xFFD3E4FF to 0xFF00315C),
    PLACES("Places", R.drawable.ic_place, 0xFFFFD866 to 0xFF3D2E00, 0xFFFFE9A6 to 0xFF3D2E00),
    SENSES("Senses", R.drawable.ic_sensors, 0xFFFF9E85 to 0xFF5A1A0A, 0xFFFFDAD1 to 0xFF5A1A0A),
    BEDSIDE("Bedside", R.drawable.ic_bedtime, 0xFFF4A6D7 to 0xFF4F1238, 0xFFFFD8EE to 0xFF4F1238),
    PHONE("This phone", R.drawable.ic_phone_device, 0xFFE8DCCB to 0xFF3A3024, 0xFFEFE3D3 to 0xFF3A3024),
    ;

    val shape: RoundedPolygon
        get() = when (this) {
            LOOK -> MaterialShapes.Cookie9Sided
            NOTIFICATIONS -> MaterialShapes.Cookie12Sided
            CHAT -> MaterialShapes.Cookie4Sided
            CALLS -> MaterialShapes.Sunny
            PLACES -> MaterialShapes.Cookie7Sided
            SENSES -> MaterialShapes.SoftBurst
            BEDSIDE -> MaterialShapes.PuffyDiamond
            PHONE -> MaterialShapes.Square
        }
}

/** The group's badge colours: its own with Vivid colours, the scheme's quieter one with Calm. */
@Composable
private fun badgeColors(a: MainActivity, g: SetGroup): Pair<Color, Color> {
    val cs = MaterialTheme.colorScheme
    if (!Prefs.vivid(a)) return cs.secondaryContainer to cs.onSecondaryContainer
    val p = if (LocalKurooto.current.light) g.light else g.dark
    return Color(p.first) to Color(p.second)
}

@Composable
private fun GroupBadge(a: MainActivity, g: SetGroup, size: Int = 52) {
    val (bg, fg) = badgeColors(a, g)
    ShapeBadge(g.shape, bg, size = size) {
        Icon(painterResource(g.icon), contentDescription = null, tint = fg, modifier = Modifier.size((size * 0.46f).dp))
    }
}

/** The tile and its page are one shared bounds (the container transform), when the shell gives the scope. */
@Composable
private fun Modifier.groupBounds(g: SetGroup, scope: AnimatedVisibilityScope): Modifier {
    val st = LocalNavShared.current
    if (st == null || LocalReducedMotion.current) return this
    val spec = MaterialTheme.motionScheme.defaultSpatialSpec<Rect>()
    val bounds = remember(spec) { BoundsTransform { _, _ -> spec } }
    val m = this
    return with(st) {
        m.sharedBounds(
            rememberSharedContentState("set-" + g.name), scope,
            enter = fadeIn(MaterialTheme.motionScheme.defaultEffectsSpec()),
            exit = fadeOut(MaterialTheme.motionScheme.fastEffectsSpec()),
            boundsTransform = bounds,
            resizeMode = SharedTransitionScope.ResizeMode.RemeasureToBounds,
            clipInOverlayDuringTransition = OverlayClip(TILE),
        )
    }
}

/** The grid of groups under the search field; with words in the field, every setting they match instead. */
@Composable
private fun Groups(a: MainActivity, ui: HomeState, room: PaddingValues, scope: AnimatedVisibilityScope) {
    @Suppress("UNUSED_VARIABLE") val tick = ui.tick
    var query by rememberSaveable { mutableStateOf("") }
    BackHandler(enabled = query.isNotEmpty()) { query = "" }
    val hits = remember(query, ui.tick) { if (query.isBlank()) emptyList() else search(a, query) }
    PaneGrid(a, ui, room, refresh = false) {
        paneTitle("Settings")
        wide("search") {
            TextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("Search every setting") },
                leadingIcon = { Icon(painterResource(R.drawable.ic_search), contentDescription = null) },
                singleLine = true,
                shape = CircleShape,
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
                    unfocusedContainerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                ),
                modifier = Modifier.fillMaxWidth(),
            )
        }
        if (query.isNotBlank()) {
            wide("hits") {
                if (hits.isEmpty()) Dim("No setting matches \"${query.trim()}\".", Modifier.padding(start = 8.dp, top = 8.dp))
                else Group(
                    hits.map { h ->
                        Item(
                            h.title,
                            h.where,
                            onClick = {
                                if (h.pane != null) ui.pane = h.pane else ui.settingsGroup = h.group?.name
                            },
                            trailing = { Chevron() },
                        )
                    },
                )
            }
            return@PaneGrid
        }
        SetGroup.entries.forEach { g ->
            item(key = g.name, contentType = "group") {
                val cs = MaterialTheme.colorScheme
                Tile(
                    tileColor(), cs.onSurface, Modifier.fillMaxWidth().groupBounds(g, scope),
                    onClick = { ui.settingsGroup = g.name },
                ) {
                    GroupBadge(a, g)
                    Text(g.title, style = MaterialTheme.typography.titleLargeEmphasized, maxLines = 1, modifier = Modifier.padding(top = 14.dp))
                    Text(summary(a, ui, g), style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
        wide("computer") { ComputerNote() }
    }
}

/** "Kurooto's settings are on your computer's dashboard." in a dashed outline. */
@Composable
private fun ComputerNote() {
    val cs = MaterialTheme.colorScheme
    val line = cs.outlineVariant
    Row(
        Modifier.fillMaxWidth().drawBehind {
            drawRoundRect(
                line, cornerRadius = androidx.compose.ui.geometry.CornerRadius(28.dp.toPx()),
                style = Stroke(1.5.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(10.dp.toPx(), 6.dp.toPx()))),
            )
        }.padding(20.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(painterResource(R.drawable.ic_laptop), contentDescription = null, tint = cs.onSurfaceVariant)
        Spacer(Modifier.width(16.dp))
        Text(
            buildAnnotatedString {
                withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append("Kurooto's settings") }
                append(" are on your computer's dashboard (Settings there): what it does, when, and with which AI.")
            },
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

/** How a group is set now, in a few words (the tile's second line). */
private fun summary(a: MainActivity, ui: HomeState, g: SetGroup): String = when (g) {
    SetGroup.LOOK -> (if (Prefs.vivid(a)) "Vivid" else "Calm") + " · " + (if (Prefs.palette(a) == Apricot.NAME) "Apricot" else youName())
    SetGroup.NOTIFICATIONS -> if (Build.VERSION.SDK_INT < 24 || (a.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).areNotificationsEnabled()) "Allowed" else "Off: calls can't ring"
    SetGroup.CHAT -> "Sessions, files, replies"
    SetGroup.CALLS -> if (Prefs.newCallScreen(a)) "New call screen" else "The call screen from before"
    SetGroup.PLACES -> if (Places.on(a)) Places.places(a).length().let { if (it == 1) "1 place" else "$it places" } else "Off"
    SetGroup.SENSES -> SensesList.count { Senses.on(a, it) }.let { if (it == 0) "All off" else "$it on" }
    SetGroup.BEDSIDE -> if (Prefs.bedsideAuto(a)) "From " + Prefs.bedsideFrom(a) else "Opens when you tap"
    SetGroup.PHONE -> a.checks().count { !it.ok }.let { n ->
        (if (n == 0) "Ready" else if (n == 1) "1 to fix" else "$n to fix") + " · " + a.versionName()
    }
}

private fun youName() = if (Build.VERSION.SDK_INT >= 31) "Material You" else "Kurooto's"

/** One search result: a setting, where it lives (a group, or another pane). */
private class Hit(val title: String, val where: String, val group: SetGroup?, val pane: Pane? = null, val words: String = "")

/** Every setting by name, its group and a few more words people may type. */
private fun index(a: MainActivity): List<Hit> {
    fun h(g: SetGroup, title: String, words: String = "") = Hit(title, g.title, g, null, words)
    val out = arrayListOf(
        h(SetGroup.LOOK, "Colours: Material You or apricot and plum", "palette theme color colour wallpaper apricot plum"),
        h(SetGroup.LOOK, "Vivid colours", "calm colour color bright quiet"),
        h(SetGroup.LOOK, "Floating bar", "docked navigation toolbar bottom"),
        h(SetGroup.LOOK, "Moving background", "sky animation still cell"),
        h(SetGroup.NOTIFICATIONS, "Notifications allowed", "permission alerts"),
        h(SetGroup.NOTIFICATIONS, "Notification categories", "channels sound vibrate silent importance"),
        h(SetGroup.CHAT, "Chat settings", "sessions files replies messages titles"),
        h(SetGroup.CALLS, "New call screen", "ringing answer decline"),
        h(SetGroup.CALLS, "Connect straight to your call line", "ntfy connection direct"),
        h(SetGroup.CALLS, "Microphone", "permission audio"),
        h(SetGroup.CALLS, "Full-screen calls (ring on the lock screen)", "lock screen permission"),
        h(SetGroup.PLACES, "Location reminders", "places location geofence"),
        h(SetGroup.BEDSIDE, "Open bedside mode", "clock night charger"),
        h(SetGroup.BEDSIDE, "Open by itself while charging", "hours charger night auto"),
        h(SetGroup.BEDSIDE, "Keep the screen on while charging", "awake display"),
        h(SetGroup.PHONE, "Battery: unrestricted", "optimisation optimization sleep background doze"),
        h(SetGroup.PHONE, "Alarms at the exact time", "exact alarm permission"),
        h(SetGroup.PHONE, "Paired with your call line", "pairing pair line worker"),
        h(SetGroup.PHONE, "App version and update", "update version download"),
        h(SetGroup.PHONE, "Unpair this phone", "remove forget unpair"),
        h(SetGroup.PHONE, "Permissions checklist", "checklist fix allow"),
        Hit("Call ringtone", "Alarms", null, Pane.ALARMS, "ringtone tone sound calls"),
        Hit("Wake-up alarm tone", "Alarms", null, Pane.ALARMS, "ringtone tone sound alarm"),
        Hit("Ring the alarm on this phone too", "Alarms", null, Pane.ALARMS, "wake alarm phone switch"),
        Hit("Kurooto's own settings", "On your computer's dashboard", null, null, "kurooto computer dashboard ai brain features"),
    )
    SensesList.forEach { out.add(h(SetGroup.SENSES, Senses.label(it), "senses sense $it " + Senses.note(it))) }
    return out
}

private fun search(a: MainActivity, q: String): List<Hit> {
    val words = q.lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
    return index(a).filter { h ->
        val hay = (h.title + " " + h.where + " " + h.words).lowercase()
        words.all { hay.contains(it) }
    }
}

internal val SensesList = listOf("screen", "charging", "motion", "steps", "light", "places", "headphones", "dnd", "alarm", "wifi", "usage")

/** A group's page: its badge and name under a back arrow, then its settings; it grows out of its tile. */
@Composable
private fun GroupPage(a: MainActivity, ui: HomeState, room: PaddingValues, g: SetGroup, scope: AnimatedVisibilityScope) {
    @Suppress("UNUSED_VARIABLE") val tick = ui.tick
    Box(Modifier.fillMaxSize().groupBounds(g, scope).background(tileColor())) {
        Column(
            Modifier.align(Alignment.TopCenter).widthIn(max = 640.dp).fillMaxSize().statusBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = room.calculateBottomPadding() + 24.dp),
        ) {
            IconButton(onClick = { ui.settingsGroup = null }) {
                Icon(painterResource(R.drawable.ic_back), contentDescription = "Back to Settings")
            }
            Row(Modifier.padding(start = 8.dp, top = 8.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                GroupBadge(a, g, 56)
                Spacer(Modifier.width(16.dp))
                Text(g.title, style = MaterialTheme.typography.displaySmallEmphasized, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            // a long press on a setting opens its entry in the settings guide (SettingHelp, 0.8.10)
            val guide = rememberSettingHelp()
            var open by remember { mutableStateOf<String?>(null) }
            CompositionLocalProvider(LocalHelp provides { k: String -> open = k }) {
            when (g) {
                SetGroup.LOOK -> Look(a)
                SetGroup.NOTIFICATIONS -> Notifications(a)
                SetGroup.CHAT -> {
                    ChatSettings(a)
                    Footnote("Sessions, sending files, edits and titles can also be switched on your computer (Settings → calls).")
                }
                SetGroup.CALLS -> Calls(a, ui)
                SetGroup.PLACES -> PlacesGroup(a)
                SetGroup.SENSES -> SensesGroup(a)
                SetGroup.BEDSIDE -> BedsideGroup(a, ui)
                SetGroup.PHONE -> ThisPhone(a, ui)
            }
            }
            val entry = open?.let { k -> guide?.helpFor(k) }
            if (guide != null && entry != null) SettingHelpSheet(guide, entry) { open = null }
        }
    }
}

// ------------------------------------------------------------------------------------------------- the groups

@Composable
private fun ColumnScope.Look(a: MainActivity) {
    Heading("Colours")
    val apricot = Prefs.palette(a) == Apricot.NAME
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(ButtonGroupDefaults.ConnectedSpaceBetween)) {
        ToggleButton(
            checked = !apricot,
            onCheckedChange = { a.setPalette("you") },
            shapes = ButtonGroupDefaults.connectedLeadingButtonShapes(),
            modifier = Modifier.weight(1f).heightIn(min = 56.dp),
        ) { Text(youName(), maxLines = 1) }
        ToggleButton(
            checked = apricot,
            onCheckedChange = { a.setPalette(Apricot.NAME) },
            shapes = ButtonGroupDefaults.connectedTrailingButtonShapes(),
            modifier = Modifier.weight(1f).heightIn(min = 56.dp),
        ) { Text("Apricot and plum", maxLines = 1) }
    }
    Footnote(
        if (Build.VERSION.SDK_INT >= 31) "Material You takes its colours from your wallpaper; apricot and plum are the app's own, warm on near-black."
        else "Kurooto's own greens, or apricot and plum, warm on near-black.",
    )
    Heading("Switches")
    Group(
        listOf(
            Item("Vivid colours", "Off (Calm): quieter colours and plain cards", checked = Prefs.vivid(a), onClick = { a.toggleVivid() }, help = "app.vivid"),
            Item("Floating bar", "Off: the bar sits on the bottom edge", checked = Prefs.floatingBar(a), onClick = { a.toggleFloatingBar() }, help = "app.floatingBar"),
            Item("Moving background", "Off: a still picture", checked = Prefs.moving(a), onClick = { a.toggleMoving() }, help = "app.moving"),
        ),
    )
}

@Composable
private fun ColumnScope.Notifications(a: MainActivity) {
    val notes = a.checks().firstOrNull { it.what == "Notifications" }
    Heading("This app")
    Group(
        listOfNotNull(
            notes?.let { c -> Item("Notifications", if (c.ok) "Allowed" else "Off: calls, questions and alarms can't reach you", onClick = { a.fix(c) }, trailing = { Chevron() }) },
        ),
    )
    // the app's notification categories (Android 8+): each opens its own page in the phone's settings; read off the main thread
    var channels by remember { mutableStateOf<List<Pair<String, String>>>(emptyList()) }
    LaunchedEffect(Unit) {
        channels = withContext(Dispatchers.Default) {
            if (Build.VERSION.SDK_INT < 26) emptyList()
            else try {
                (a.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notificationChannels.map { ch ->
                    val how = when (ch.importance) {
                        NotificationManager.IMPORTANCE_NONE -> "Off"
                        NotificationManager.IMPORTANCE_MIN, NotificationManager.IMPORTANCE_LOW -> "Silent"
                        NotificationManager.IMPORTANCE_DEFAULT -> "Sound"
                        else -> "Sound and pop-up"
                    }
                    ch.id to (ch.name.toString() + "\u0000" + how)
                }
            } catch (e: Exception) { emptyList() }
        }
    }
    if (channels.isNotEmpty() && Build.VERSION.SDK_INT >= 26) {
        Heading("Categories")
        Group(
            channels.map { (id, v) ->
                val (name, how) = v.split("\u0000").let { it[0] to it.getOrElse(1) { "" } }
                Item(name, how, onClick = {
                    a.launch(
                        Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, a.packageName)
                            .putExtra(Settings.EXTRA_CHANNEL_ID, id),
                    )
                }, trailing = { Chevron() })
            },
        )
    }
    Footnote("What reaches this phone at all is chosen on your computer (Settings → notify, which kinds go to the app).")
}

@Composable
private fun ColumnScope.Calls(a: MainActivity, ui: HomeState) {
    Heading("Calls")
    Group(
        listOf(
            Item("New call screen", "Off: the call screen from before 0.8.7", checked = Prefs.newCallScreen(a), onClick = { a.toggleNewCallScreen() }, help = "app.newCallScreen"),
            Item(
                "Connect straight to your call line",
                "Off: calls and messages come through ntfy.sh only",
                checked = Prefs.direct(a),
                onClick = { a.toggleDirect() },
                help = "app.direct",
            ),
        ),
    )
    val wanted = setOf("Microphone", "Full-screen calls (ring on the lock screen)")
    Heading("What calls need")
    Group(a.checks().filter { it.what in wanted }.map { checkRow(a, it) })
    Heading("Ringtones")
    Group(listOf(Item("Call ringtone and alarm tone", "In Alarms", onClick = { ui.pane = Pane.ALARMS }, trailing = { Chevron() })))
    Footnote("${ui.name}'s calls ring here like phone calls (earpiece, screen off at your ear); wake-up calls ring like an alarm.")
}

@Composable
private fun ColumnScope.PlacesGroup(a: MainActivity) {
    Heading("Location reminders")
    Group(
        listOf(
            Item(
                "Places",
                if (Places.on(a)) "On: " + Places.places(a).length() + " saved" else "Off",
                onClick = { a.startActivity(Intent(a, PlacesActivity::class.java)) },
                trailing = { Chevron() },
                help = "app.places.on",
            ),
        ),
    )
    Footnote("Turn them on, save where you are as a place, and add what to remind you there, on the Places page.")
}

@Composable
private fun ColumnScope.SensesGroup(a: MainActivity) {
    Heading("What the phone tells Kurooto")
    Group(SensesList.map { s -> Item(Senses.label(s), Senses.note(s).ifEmpty { null }, checked = Senses.on(a, s), onClick = { a.toggleSense(s) }, help = "app.senses.$s") })
    Footnote(
        "Off until you switch one on. Each reading is worked out on this phone, sealed with this phone's key and sent to your " +
            "computer through your call line, which can't read it; if your computer is off it waits there. The microphone is never used.",
    )
}

@Composable
private fun ColumnScope.BedsideGroup(a: MainActivity, ui: HomeState) {
    Heading("Bedside mode")
    Group(
        listOf(
            Item(
                "Open bedside mode",
                "A big clock, the next alarm and calls, and one button to talk. Dims at night.",
                onClick = { a.startActivity(Intent(a, BedsideActivity::class.java).putExtra("demo", ui.demo)) },
                trailing = { Chevron() },
            ),
            Item(
                "Open by itself while charging",
                if (Prefs.bedsideAuto(a)) Prefs.bedsideFrom(a) + " to " + Prefs.bedsideTo(a) else "Off",
                onClick = { a.bedsideHours() },
                help = "app.bedsideAuto",
            ),
            Item("Keep the screen on while charging", null, checked = Prefs.bedsideKeepOn(a), onClick = { a.toggleKeepOn() }, help = "app.bedsideKeepOn"),
        ),
    )
    Footnote(
        "An old phone on a charger by your bed works well. Talk works with the phone locked; leave the app listening " +
            "(This phone → the checklist) so wake-up calls ring there.",
    )
}

/** A checklist row: done (a calm circle) or not (a burst, and Fix). */
@Composable
private fun checkRow(a: MainActivity, c: MainActivity.Check): Item {
    val k = LocalKurooto.current
    return Item(
        c.what,
        if (c.ok) null else "Needs your OK",
        onClick = if (c.ok) null else ({ a.fix(c) }),
        leading = {
            ShapeBadge(if (c.ok) MaterialShapes.Circle else MaterialShapes.SoftBurst, (if (c.ok) k.ok else k.bad).copy(alpha = 0.16f)) {
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
}

@Composable
private fun ColumnScope.ThisPhone(a: MainActivity, ui: HomeState) {
    val k = LocalKurooto.current
    Heading("Checklist")
    Group(a.checks().map { checkRow(a, it) })
    a.sleepyMaker()?.let {
        Footnote(
            "$it phones also put apps to sleep on their own: in Settings → Battery, set Kurooto to \"Unrestricted\" or " +
                "\"No restrictions\" and take it off any \"sleeping apps\" list, or calls may not ring.",
        )
    }
    Heading("Pairing")
    var asking by rememberSaveable { mutableStateOf(false) }
    KCard(accent = 1) {
        Text(if (ui.demo) "Demo: not paired" else "Paired with " + Prefs.url(a), style = MaterialTheme.typography.bodyLarge)
        if (!ui.demo) Dim(
            if (!Prefs.direct(a)) "Calls come through ntfy.sh (the straight connection is off in Calls)"
            else if (ListenService.direct()) "Connected straight to your call line"
            else "Not connected to your call line right now: calls still come through ntfy.sh",
            Modifier.padding(top = 4.dp),
        )
        OutlinedButton(
            onClick = { asking = true },
            shapes = ButtonDefaults.shapes(),
            border = BorderStroke(1.dp, k.bad),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = k.bad),
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        ) { Text("Unpair this phone") }
        SaidLine(ui.status)
    }
    Heading("The app")
    KCard {
        Text("Version " + a.versionName(), style = MaterialTheme.typography.bodyLarge)
        val up = ui.update
        if (up == null) Dim("It looks for a newer one each time you open it.", Modifier.padding(top = 4.dp))
        else Button(
            onClick = { a.launch(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(up.second))) },
            shapes = ButtonDefaults.shapes(),
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        ) { Text("Update available: " + up.first) }
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
