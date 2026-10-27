package io.github.avtarfr.kurooto

import androidx.activity.compose.BackHandler
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonGroup
import androidx.compose.material3.ButtonGroupDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.ToggleButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.layout.positionInParent
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import org.json.JSONObject

// 0.8.10: Views as organ pages (Prefs.viewsOrgans). Owned by the views part of the 0.8.10 build; ViewsTab only calls it.
/** Views as four pages, Brain · Heart · Senses · Memory: one organ of the being alone in ViewsPane's WebView (the
 *  dashboard's own being.js with opts.only, the same meshes, shaders and glow; switched on the same page, never loaded
 *  again), turned with a finger and pinched to zoom, and its parts listed here under it with their live state. A part
 *  tapped here or on the drawing is focused in both: brightened and zoomed in 3D with its ring, the others faded, and
 *  here in full (its rows, Brain parts, features and settings; the switches go sealed to your computer, as the
 *  dashboard's panels do). Back goes from a part to its organ, then leaves. More: Systems, the Notes map and the Brain
 *  console, as before. */
@Composable
internal fun OrganViews(a: MainActivity, ui: HomeState, room: PaddingValues) {
    val reduced = LocalReducedMotion.current
    val pane = remember { ViewsPane(a, null, ui.demo, null).organs(reduced) }
    var mode by remember { mutableStateOf(pane.startMode()) }
    var organ by remember { mutableStateOf(pane.organ() ?: "brain") }
    var beingOk by remember { mutableStateOf(pane.beingOk()) }
    var depth by remember { mutableIntStateOf(0) }
    var st by remember { mutableStateOf(OrganState.of(JSONObject())) }
    val brainReady = remember { brainConsoleShipped(a) }
    DisposableEffect(pane) {
        pane.setWatcher {
            beingOk = pane.beingOk()
            depth = pane.depth()
            val s = OrganState.of(pane.organState())
            if (s.page.isEmpty() || s.page == organ) st = s // a list from the organ before a switch: not shown
        }
        val obs = androidx.lifecycle.LifecycleEventObserver { _, e ->
            if (e == androidx.lifecycle.Lifecycle.Event.ON_RESUME) pane.resume() else if (e == androidx.lifecycle.Lifecycle.Event.ON_PAUSE) pane.pause()
        }
        a.lifecycle.addObserver(obs)
        if (a.lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.RESUMED)) pane.resume()
        onDispose {
            a.lifecycle.removeObserver(obs)
            pane.pause()
            pane.destroy()
        }
    }
    BackHandler(enabled = mode == "being" && beingOk && depth > 0) { pane.back() }
    val shown = mode == "being" && beingOk
    // where the floating bars are, so the organ sits centred in what's left of the drawing (being-phone.js inset)
    val density = LocalDensity.current
    var boxH by remember { mutableIntStateOf(0) }
    var barBottom by remember { mutableIntStateOf(0) }
    var panelTop by remember { mutableIntStateOf(0) }
    LaunchedEffect(shown, boxH, barBottom, panelTop) {
        if (shown && boxH > 0) with(density) {
            pane.inset(barBottom.toDp().value, (boxH - (if (panelTop > 0) panelTop else boxH)).toDp().value)
        }
    }
    Box(Modifier.fillMaxSize().padding(room).statusBarsPadding().onSizeChanged { boxH = it.height }) {
        // Systems, the Notes map and the Brain console start under the floating row (their own words are at their top)
        val under = if (shown || barBottom == 0) 0.dp else with(density) { barBottom.toDp() }
        AndroidView(factory = { pane.page() }, modifier = Modifier.fillMaxSize().padding(top = under))
        when {
            mode == "brain" && !brainReady -> Note(
                "The Brain console comes with this update.",
                "When it's here, this shows what the Brain is doing and why, live and read-only.",
                cover = true,
            )
            mode == "being" && !beingOk -> Note(
                "This phone can't draw the being.",
                "It needs WebGL 2 and a recent Android System WebView (update it from the Play Store). Here's Systems instead.",
                cover = false,
            )
        }
        OrganPicker(
            mode, organ,
            Modifier.align(Alignment.TopCenter).onGloballyPositioned { barBottom = (it.positionInParent().y + it.size.height).toInt() },
            pickOrgan = { o ->
                if (o != organ) st = OrganState.of(JSONObject())
                organ = o
                mode = "being"
                depth = 0
                pane.showOrgan(o)
            },
            pickMore = { m ->
                mode = m
                depth = 0
                if (m != "brain" || brainReady) pane.show(m)
            },
        )
        if (shown) {
            OrganPanel(
                st, organ, pane,
                Modifier.align(Alignment.BottomCenter).onGloballyPositioned { panelTop = it.positionInParent().y.toInt() },
            )
        }
    }
}

private val ORGAN_NAMES = listOf("brain" to "Brain", "heart" to "Heart", "senses" to "Senses", "memory" to "Memory")
private val MORE = listOf("systems" to "Systems", "notes" to "Notes map", "brain" to "Brain console")

/** Brain · Heart · Senses · Memory, and More (Systems, the Notes map, the Brain console): one floating row of connected
 *  toggle buttons; the one showing is filled, a pressed one widens. */
@Composable
private fun OrganPicker(mode: String, organ: String, modifier: Modifier, pickOrgan: (String) -> Unit, pickMore: (String) -> Unit) {
    var menu by remember { mutableStateOf(false) }
    val more = mode != "being"
    Surface(
        shape = CircleShape,
        color = MaterialTheme.colorScheme.surfaceContainer,
        shadowElevation = 6.dp,
        modifier = modifier.padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        ButtonGroup(
            overflowIndicator = {},
            horizontalArrangement = Arrangement.spacedBy(ButtonGroupDefaults.ConnectedSpaceBetween),
            modifier = Modifier.fillMaxWidth().padding(6.dp),
        ) {
            ORGAN_NAMES.forEachIndexed { i, (id, label) ->
                customItem(
                    buttonGroupContent = {
                        val src = remember { MutableInteractionSource() }
                        ToggleButton(
                            checked = !more && organ == id,
                            onCheckedChange = { pickOrgan(id) },
                            shapes = if (i == 0) ButtonGroupDefaults.connectedLeadingButtonShapes() else ButtonGroupDefaults.connectedMiddleButtonShapes(),
                            interactionSource = src,
                            contentPadding = PaddingValues(horizontal = 6.dp),
                            modifier = Modifier.weight(1f).animateWidth(src).semantics { role = Role.RadioButton },
                        ) { Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                    },
                    menuContent = {},
                )
            }
            customItem(
                buttonGroupContent = {
                    val src = remember { MutableInteractionSource() }
                    Box(Modifier.animateWidth(src)) {
                        ToggleButton(
                            checked = more,
                            onCheckedChange = { menu = true },
                            shapes = ButtonGroupDefaults.connectedTrailingButtonShapes(),
                            interactionSource = src,
                            contentPadding = PaddingValues(horizontal = 12.dp),
                        ) {
                            Icon(
                                painterResource(R.drawable.ic_chat_more),
                                contentDescription = if (more) "Showing " + (MORE.firstOrNull { it.first == mode }?.second ?: "") + ": more views" else "More views: Systems, Notes map, Brain console",
                            )
                        }
                        DropdownMenu(menu, { menu = false }) {
                            MORE.forEach { (id, label) ->
                                DropdownMenuItem(
                                    text = { Text(label) },
                                    onClick = {
                                        menu = false
                                        pickMore(id)
                                    },
                                    trailingIcon = { if (mode == id) Icon(painterResource(R.drawable.ic_ok), contentDescription = "showing") },
                                )
                            }
                        }
                    }
                },
                menuContent = {},
            )
        }
    }
}

/** The organ's parts under the drawing, each with its live state; the part picked opens under them in full. Memory has
 *  a card of its own for its features (they're lights around the notes, not a part of them). */
@Composable
private fun OrganPanel(st: OrganState, organ: String, pane: ViewsPane, modifier: Modifier) {
    val cs = MaterialTheme.colorScheme
    val reduced = LocalReducedMotion.current
    var feats by remember(organ) { mutableStateOf(false) } // Memory's Features card is open
    var want by remember(organ) { mutableStateOf<String?>(null) } // a card just tapped, until the page says it's picked
    LaunchedEffect(st.selId) { want = null }
    val sel = want ?: st.selId
    val row = rememberLazyListState()
    val lead = if (organ == "memory" && st.feats.isNotEmpty()) 1 else 0
    LaunchedEffect(st.selId, st.parts.size) { // a part tapped on the drawing: its card comes into sight
        val i = st.parts.indexOfFirst { it.id == st.selId }
        if (i >= 0) if (reduced) row.scrollToItem(i + lead) else row.animateScrollToItem(i + lead)
    }
    Surface(
        shape = MaterialTheme.shapes.extraLarge,
        color = cs.surfaceContainer,
        shadowElevation = 8.dp,
        modifier = modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp)
            .animateContentSize(MaterialTheme.motionScheme.defaultSpatialSpec()),
    ) {
        Column(Modifier.padding(vertical = 14.dp)) {
            Column(Modifier.padding(horizontal = 18.dp)) {
                Text(ORGAN_NAMES.firstOrNull { it.first == organ }?.second ?: "", style = MaterialTheme.typography.titleLarge)
                val line = listOf(st.head, st.status).filter { it.isNotEmpty() }.joinToString(" · ")
                if (line.isNotEmpty()) Text(line, style = MaterialTheme.typography.bodySmall, color = cs.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (st.warn.isNotEmpty()) Text(st.warn, style = MaterialTheme.typography.bodySmall, color = cs.error)
                if (st.mind.isNotEmpty()) MindLine(st) { pane.uneasy() }
                if (organ == "brain" && st.parts.isNotEmpty()) BrainLook(st.mode) { pane.brainMode(it) }
            }
            if (st.parts.isNotEmpty() || lead > 0) {
                LazyRow(
                    state = row,
                    contentPadding = PaddingValues(horizontal = 14.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(top = 12.dp),
                ) {
                    if (lead > 0) item(key = "features") {
                        val on = st.feats.count { it.on }
                        PartCard("Features", "$on of ${st.feats.size} on", feats && st.sel == null) {
                            feats = !feats
                            if (st.sel != null) pane.pick("", "")
                        }
                    }
                    items(st.parts, key = { it.id }) { p ->
                        PartCard(p.name, p.live, sel == p.id) {
                            feats = false
                            if (sel == p.id) {
                                want = ""
                                pane.pick("", "")
                            } else {
                                want = p.id
                                pane.pick(p.kind, p.key)
                            }
                        }
                    }
                }
            }
            val d = st.detail
            if (d != null || (feats && lead > 0 && st.sel == null)) {
                Column(
                    Modifier.heightIn(max = 300.dp).verticalScroll(rememberScrollState()).padding(horizontal = 18.dp).padding(top = 12.dp),
                ) {
                    if (d != null) Detail(d, st, pane) else Feats(st.feats, st, pane)
                }
            } else if (st.parts.isNotEmpty()) {
                Text(
                    "Tap a part here or on the drawing. Drag to turn it, pinch to zoom.",
                    style = MaterialTheme.typography.bodySmall,
                    color = cs.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 18.dp).padding(top = 10.dp),
                )
            }
            if (st.said.isNotEmpty()) Text(st.said, style = MaterialTheme.typography.bodyMedium, color = cs.error, modifier = Modifier.padding(horizontal = 18.dp).padding(top = 8.dp))
        }
    }
}

/** (0.8.14) Brain's status under the organ's name, from its status stream: eyes shut, held, the one thing it's uneasy
 *  about (a tap shows where on the drawing), quieter or bright. Plain words from enums; never how you are. */
@Composable
private fun MindLine(st: OrganState, openUneasy: () -> Unit) {
    val cs = MaterialTheme.colorScheme
    val tap = st.uneasy != null
    Text(
        st.mind,
        style = MaterialTheme.typography.bodySmall,
        color = if (tap) cs.tertiary else cs.onSurfaceVariant,
        maxLines = 2,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier.padding(top = 2.dp).then(
            if (tap) Modifier.clickable(onClickLabel = "Show what it's uneasy about") { openUneasy() }.semantics { role = Role.Button } else Modifier,
        ),
    )
}

/** One part: its name and what it's doing now; the picked one filled. */
@Composable
private fun PartCard(name: String, live: String, picked: Boolean, onClick: () -> Unit) {
    val cs = MaterialTheme.colorScheme
    Surface(
        onClick = onClick,
        shape = MaterialTheme.shapes.large,
        color = if (picked) cs.primaryContainer else cs.surfaceContainerHighest,
        contentColor = if (picked) cs.onPrimaryContainer else cs.onSurface,
        modifier = Modifier.width(168.dp).heightIn(min = 76.dp).semantics { role = Role.Tab },
    ) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
            Text(name, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(
                live,
                style = MaterialTheme.typography.bodySmall,
                color = if (picked) cs.onPrimaryContainer else cs.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** Solid · Cutaway · X-ray: how the brain is seen (the dashboard's three). */
@Composable
private fun BrainLook(mode: String, pick: (String) -> Unit) {
    val items = listOf("solid" to "Solid", "cut" to "Cutaway", "xray" to "X-ray")
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(ButtonGroupDefaults.ConnectedSpaceBetween)) {
        items.forEachIndexed { i, (id, label) ->
            ToggleButton(
                checked = mode == id,
                onCheckedChange = { pick(id) },
                shapes = when (i) {
                    0 -> ButtonGroupDefaults.connectedLeadingButtonShapes()
                    items.lastIndex -> ButtonGroupDefaults.connectedTrailingButtonShapes()
                    else -> ButtonGroupDefaults.connectedMiddleButtonShapes()
                },
                modifier = Modifier.weight(1f).semantics { role = Role.RadioButton },
            ) { Text(label, maxLines = 1) }
        }
    }
}

/** The part picked, in full: what it's doing now, its Brain parts, features and settings, a neighbourhood's notes, a
 *  note's first lines. */
@Composable
private fun Detail(d: JSONObject, st: OrganState, pane: ViewsPane) {
    val cs = MaterialTheme.colorScheme
    Text(d.optString("title"), style = MaterialTheme.typography.titleMedium)
    d.optString("sub").takeIf { it.isNotEmpty() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = cs.onSurfaceVariant) }
    val rows = d.optJSONArray("rows")
    if (rows != null && rows.length() > 0) {
        Section("Now")
        for (i in 0 until rows.length()) {
            val r = rows.optJSONArray(i) ?: continue
            Words(r.optString(0), r.optString(1))
        }
    }
    val bars = d.optJSONArray("bars")
    if (bars != null && bars.length() > 0) {
        Section("This computer")
        for (i in 0 until bars.length()) {
            val b = bars.optJSONObject(i) ?: continue
            val v = b.optDouble("v", 0.0).toFloat()
            Words(b.optString("name"), b.optString("text"))
            LinearProgressIndicator(
                progress = { v },
                color = if (v > .85f) cs.error else cs.primary,
                modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp),
            )
        }
    }
    objects(d.optJSONArray("parts")).takeIf { it.isNotEmpty() }?.let { parts ->
        Section("Brain parts")
        for (p in parts) {
            val key = p.optString("key")
            if (key.isNotEmpty()) Toggle(p.optString("name"), p.optString("state"), p.optBoolean("on"), st) { pane.setting(key, it) }
            else Words(p.optString("name"), p.optString("state"))
        }
    }
    objects(d.optJSONArray("feats")).takeIf { it.isNotEmpty() }?.let { Feats(it.map { f -> Feat(f) }, st, pane) }
    d.optJSONObject("feature")?.let { f -> Toggle("On", null, f.optBoolean("on"), st) { pane.feature(f.optString("id"), it) } }
    objects(d.optJSONArray("notes")).takeIf { it.isNotEmpty() }?.let { notes ->
        Section("Most linked")
        for (n in notes) {
            Row(
                Modifier.fillMaxWidth().clickable { pane.pick("note", n.optString("key")) }.padding(vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(n.optString("title"), style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                Text("${n.optInt("links")} links", style = MaterialTheme.typography.bodySmall, color = cs.onSurfaceVariant, modifier = Modifier.padding(start = 12.dp))
            }
        }
    }
    if (d.has("text")) Text(d.optString("text"), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 10.dp))
    var group = ""
    for (s in objects(d.optJSONArray("settings"))) {
        if (s.optString("group") != group) {
            group = s.optString("group")
            Section("$group · settings")
        }
        if (s.optBoolean("bool")) Toggle(s.optString("name"), null, s.optBoolean("on"), st) { pane.setting(s.optString("key"), it) }
        else Words(s.optString("name"), s.optString("value"))
    }
}

/** The features on a part (or Memory's): each a switch, its name opens it (its light focused, its own settings). */
@Composable
private fun Feats(list: List<Feat>, st: OrganState, pane: ViewsPane) {
    Section("Features")
    for (f in list) Toggle(f.title, null, f.on, st, open = { pane.pick("feature", f.id) }) { pane.feature(f.id, it) }
}

@Composable
private fun Section(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 14.dp, bottom = 4.dp),
    )
}

@Composable
private fun Words(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(112.dp))
        Text(value, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
    }
}

/** A switch row: it moves at once and settles to what your computer says when the page next lists it (back, if the
 *  change didn't go through: the page says why). */
@Composable
private fun Toggle(name: String, state: String?, on: Boolean, st: OrganState, open: (() -> Unit)? = null, flip: (Boolean) -> Unit) {
    var now by remember(name, on, st) { mutableStateOf(on) }
    Row(Modifier.fillMaxWidth().heightIn(min = 52.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f).then(if (open != null) Modifier.clickable(onClick = open) else Modifier).padding(vertical = 6.dp)) {
            Text(name + if (open != null) " ›" else "", style = MaterialTheme.typography.bodyMedium)
            if (!state.isNullOrEmpty()) Text(state, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = now, onCheckedChange = { now = it; flip(it) }, modifier = Modifier.padding(start = 12.dp))
    }
}


internal class Feat(j: JSONObject) {
    val id: String = j.optString("id")
    val title: String = j.optString("title")
    val on: Boolean = j.optBoolean("on")
}

internal class OrganPart(j: JSONObject) {
    val kind: String = j.optString("kind")
    val key: String = j.optString("key")
    val name: String = j.optString("name")
    val live: String = j.optString("live")
    val id: String get() = "$kind:$key"
}

/** What an organ page lists (being.js describe(), read by ViewsPane.organState): its parts, the one picked, its detail. */
internal class OrganState private constructor(j: JSONObject) {
    val page: String = j.optString("page")
    val head: String = j.optString("head")
    val status: String = j.optString("status")
    val warn: String = j.optString("warn")
    val mode: String = j.optString("mode", "solid")
    val said: String = j.optString("said")
    val sel: JSONObject? = j.optJSONObject("sel")
    val selId: String? = sel?.let { it.optString("kind") + ":" + it.optString("key") }
    val parts: List<OrganPart> = objects(j.optJSONArray("parts")).map { OrganPart(it) }
    val detail: JSONObject? = j.optJSONObject("detail")
    val feats: List<Feat> = objects(j.optJSONArray("feats")).map { Feat(it) }
    val mind: String = j.optString("mind") // (0.8.14) Brain's status line, "" with Brain or look.being_status off
    val uneasy: JSONObject? = j.optJSONObject("uneasy")

    companion object {
        fun of(j: JSONObject) = OrganState(j)
    }
}
