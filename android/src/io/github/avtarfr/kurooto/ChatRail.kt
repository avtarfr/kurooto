package io.github.avtarfr.kurooto

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Badge
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.toPath
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Matrix
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.graphics.shapes.Morph
import androidx.graphics.shapes.RoundedPolygon
import com.materialkolor.hct.Hct
import java.util.TimeZone
import kotlin.math.roundToInt

/** The shapes a chat's avatar takes (Kurooto's own is the sunny one); the active chat's morphs into a soft square. */
private val SHAPES: List<RoundedPolygon> by lazy {
    listOf(
        MaterialShapes.Cookie9Sided, MaterialShapes.Clover4Leaf, MaterialShapes.Pentagon, MaterialShapes.Gem,
        MaterialShapes.Cookie6Sided, MaterialShapes.SoftBurst, MaterialShapes.Arch, MaterialShapes.Cookie7Sided,
        MaterialShapes.Diamond, MaterialShapes.Clover8Leaf,
    )
}

private fun shapeOf(s: ChatSession): RoundedPolygon = if (s.main) MaterialShapes.Sunny else SHAPES[Math.floorMod(s.id.hashCode(), SHAPES.size)]

/** A Material shape morphing into another, drawn at `progress` (read where it's drawn, so a change only redraws). */
private class MorphShape(private val morph: Morph, private val progress: Float) : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline {
        val p: Path = morph.toPath(progress, Path())
        p.transform(Matrix().apply { scale(size.width, size.height) })
        return Outline.Generic(p)
    }
}

/** A chat's own tonal colour: a hue from its id (Kurooto's: the scheme's primary), as a container and the colour on it. */
@Immutable
private data class Tone(val bg: Color, val fg: Color)

@Composable
private fun toneOf(s: ChatSession): Tone {
    val cs = MaterialTheme.colorScheme
    val dark = !LocalKurooto.current.light
    if (s.main) return Tone(cs.primaryContainer, cs.onPrimaryContainer)
    return remember(s.id, dark) {
        val hue = (Math.floorMod(s.id.hashCode(), 360)).toDouble()
        Tone(
            Color(Hct.from(hue, 36.0, if (dark) 28.0 else 88.0).toInt()),
            Color(Hct.from(hue, 40.0, if (dark) 88.0 else 22.0).toInt()),
        )
    }
}

/** A chat's avatar: its shape and tonal colour with its initials (Kurooto's: the assistant's initial); the active one
 *  morphs into the soft square in the primary colour. The morph and the colour run in the draw phase. */
@Composable
private fun Avatar(s: ChatSession, active: Boolean, size: Dp, modifier: Modifier = Modifier) {
    val cs = MaterialTheme.colorScheme
    val tone = toneOf(s)
    val spatial = MaterialTheme.motionScheme.fastSpatialSpec<Float>()
    val reduced = LocalReducedMotion.current
    val t by animateFloatAsState(if (active) 1f else 0f, if (reduced) androidx.compose.animation.core.snap() else spatial, label = "avatar")
    val bg by animateColorAsState(if (active) cs.primary else tone.bg, MaterialTheme.motionScheme.fastEffectsSpec(), label = "avatarBg")
    val fg = if (active) cs.onPrimary else tone.fg
    val morph = remember(s.id) { Morph(shapeOf(s), MaterialShapes.Square) }
    Box(
        modifier.size(size)
            .graphicsLayer {
                shape = MorphShape(morph, t)
                clip = true
            }
            .drawBehind { drawRect(bg) },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            ChatRules.initials(s.title),
            color = fg,
            style = MaterialTheme.typography.titleMediumEmphasized,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
        )
    }
}

/** The unread count over an avatar or at a row's end. */
@Composable
private fun Unread(n: Int, modifier: Modifier = Modifier) {
    if (n <= 0) return
    Badge(modifier, containerColor = MaterialTheme.colorScheme.tertiary, contentColor = MaterialTheme.colorScheme.onTertiary) {
        Text(if (n > 99) "99+" else "$n")
    }
}

/**
 * The rail: a floating column down the left edge with "+" (a new chat) on top, the chats' avatars (Kurooto's first,
 * then pinned, then the newest; archived ones only in the drawer), and the navigation at its foot. Drag it right to
 * pull the drawer open (it follows the finger, then a spring settles it, faster with a fling); tap the active avatar
 * to open the drawer too.
 */
@Composable
fun ChatRail(cu: ChatUi, modifier: Modifier) {
    val snap = ChatStore.snap
    val current = ChatStore.current
    val density = LocalDensity.current
    val fling = with(density) { 400.dp.toPx() }
    val shown = snap.sessions.filter { !it.archived && it.id !in cu.deleting }
    Surface(
        shape = RoundedCornerShape(36.dp),
        color = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.94f),
        modifier = modifier.fillMaxHeight()
            .windowInsetsPadding(WindowInsets.navigationBars)
            .draggable(
                cu.drawer.drag, Orientation.Horizontal,
                onDragStopped = { v -> cu.drawer.settle(cu.drawer.target(v, fling), v, cu.spec) },
            ),
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            // "+" only while your computer has chats on (calls.chat_sessions)
            if (snap.on("chat_sessions")) FilledIconButton(
                onClick = { cu.newChat() },
                shape = RoundedCornerShape(20.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer, contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ),
                modifier = Modifier.padding(top = 10.dp).size(56.dp),
            ) { Icon(painterResource(R.drawable.ic_chat_add), contentDescription = "New chat") }
            Box(Modifier.padding(vertical = 10.dp).width(28.dp).height(3.dp).background(MaterialTheme.colorScheme.outlineVariant, CircleShape))
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                itemsIndexed(shown, key = { _, s -> s.id }, contentType = { _, _ -> "avatar" }) { i, s ->
                    // paneStagger(i) from Nav.kt goes here at merge (the avatars leave with a 20 ms stagger)
                    RailItem(cu, s, s.id == current)
                }
            }
            // one navigation at a time: the drawer shows its own (a row) once it's more than half open
            val nav by remember { derivedStateOf { cu.drawer.progress <= 0.5f } }
            if (nav) KNav(cu.a, cu.ui, vertical = true, modifier = Modifier.padding(bottom = 8.dp))
        }
    }
}

@Composable
private fun RailItem(cu: ChatUi, s: ChatSession, active: Boolean) {
    val cs = MaterialTheme.colorScheme
    val spatial = MaterialTheme.motionScheme.fastSpatialSpec<Float>()
    val mark by animateFloatAsState(if (active) 1f else 0f, spatial, label = "mark")
    Box(Modifier.fillMaxWidth().height(56.dp), contentAlignment = Alignment.Center) {
        // the active chat's mark at the rail's edge
        Box(
            Modifier.align(Alignment.CenterStart).width(4.dp).height(28.dp)
                .graphicsLayer { scaleY = mark; alpha = mark }
                .background(cs.primary, RoundedCornerShape(topEnd = 4.dp, bottomEnd = 4.dp)),
        )
        Box(contentAlignment = Alignment.Center) {
            Avatar(
                s, active, 52.dp,
                Modifier.clickable(
                    interactionSource = null, indication = null,
                    onClickLabel = s.title,
                ) { if (active) cu.openDrawer() else cu.open(s.id) },
            )
            Unread(s.unread, Modifier.align(Alignment.TopEnd).offset(x = 4.dp, y = (-2).dp))
            if (s.working) {
                Box(
                    Modifier.align(Alignment.BottomEnd).size(12.dp).background(cs.tertiary, CircleShape)
                        .padding(2.dp).background(cs.onTertiary, CircleShape),
                )
            }
        }
    }
}

/**
 * The drawer the rail pulls open: "Chats" with the call button, New chat and search, what's waiting for you, then the
 * chats (pinned, recent, archived folded away), each with its last line or "Kurooto is working…", its time and unread
 * count. Long-press a chat: rename, pin, archive, delete (with Undo). The navigation sits at its foot, as a row. It
 * slides with the drag (a transform, drawn only), wider on its left so a spring's overshoot shows no gap.
 */
@Composable
fun ChatDrawer(cu: ChatUi, width: Dp, modifier: Modifier) {
    val cs = MaterialTheme.colorScheme
    val density = LocalDensity.current
    val fling = with(density) { 400.dp.toPx() }
    val extra = 40.dp
    Box(
        modifier.fillMaxHeight().width(width + extra)
            .offset { IntOffset((cu.drawer.pos - cu.drawer.width - with(density) { extra.toPx() }).roundToInt(), 0) }
            .draggable(
                cu.drawer.drag, Orientation.Horizontal,
                onDragStopped = { v -> cu.drawer.settle(cu.drawer.target(v, fling), v, cu.spec) },
            ),
    ) {
        Surface(
            shape = RoundedCornerShape(topEnd = 36.dp, bottomEnd = 36.dp),
            color = cs.surfaceContainer,
            tonalElevation = 2.dp,
            modifier = Modifier.fillMaxSize().padding(top = 8.dp, bottom = 8.dp),
        ) {
            Column(Modifier.fillMaxSize().padding(start = extra).windowInsetsPadding(WindowInsets.navigationBars)) {
                DrawerHead(cu)
                Box(Modifier.padding(horizontal = 12.dp)) { WaitingBar(cu.a, cu.ui) }
                DrawerList(cu, Modifier.weight(1f))
                // the navigation, as a row here; it fades in as the drawer opens (the rail's own sits under it)
                val nav by remember { derivedStateOf { cu.drawer.progress > 0.5f } }
                Box(Modifier.fillMaxWidth().padding(12.dp).graphicsLayer { alpha = ((cu.drawer.progress - 0.5f) * 2f).coerceIn(0f, 1f) }, contentAlignment = Alignment.Center) {
                    if (nav) KNav(cu.a, cu.ui, vertical = false)
                }
            }
        }
    }
}

@Composable
private fun DrawerHead(cu: ChatUi) {
    val cs = MaterialTheme.colorScheme
    var searching by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 12.dp, top = 16.dp), verticalAlignment = Alignment.CenterVertically) {
        Text("Chats", style = MaterialTheme.typography.displaySmallEmphasized, color = cs.onSurface, modifier = Modifier.weight(1f))
        FilledIconButton(
            onClick = { cu.call() },
            shape = RoundedCornerShape(20.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = cs.primary, contentColor = cs.onPrimary),
            modifier = Modifier.size(56.dp),
        ) { Icon(painterResource(R.drawable.ic_call), contentDescription = "Call ${Prefs.assistant(cu.a)}") }
    }
    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        if (searching) {
            TextField(
                value = cu.search, onValueChange = { cu.search = it }, singleLine = true,
                placeholder = { Text("Search chats") },
                leadingIcon = { Icon(painterResource(R.drawable.ic_chat_search), null) },
                trailingIcon = { IconButton({ cu.search = ""; searching = false }) { Icon(painterResource(R.drawable.ic_chat_close), "Close search") } },
                shape = RoundedCornerShape(28.dp),
                colors = TextFieldDefaults.colors(
                    focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent,
                    focusedContainerColor = cs.surfaceContainerHighest, unfocusedContainerColor = cs.surfaceContainerHighest,
                ),
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None),
                modifier = Modifier.weight(1f),
            )
        } else {
            val h = ButtonDefaults.MediumContainerHeight
            if (ChatStore.snap.on("chat_sessions")) Button(
                onClick = { cu.newChat() },
                shapes = ButtonDefaults.shapesFor(h),
                contentPadding = ButtonDefaults.contentPaddingFor(h),
                colors = ButtonDefaults.buttonColors(containerColor = cs.primaryContainer, contentColor = cs.onPrimaryContainer),
                modifier = Modifier.weight(1f).heightIn(min = h),
            ) {
                Icon(painterResource(R.drawable.ic_chat_new), null, Modifier.size(ButtonDefaults.iconSizeFor(h)))
                Spacer(Modifier.width(ButtonDefaults.iconSpacingFor(h)))
                Text("New chat", style = ButtonDefaults.textStyleFor(h))
            }
            FilledTonalIconButton(
                onClick = { searching = true },
                shape = RoundedCornerShape(28.dp),
                modifier = Modifier.weight(0.8f).height(h),
            ) { Icon(painterResource(R.drawable.ic_chat_search), contentDescription = "Search chats") }
        }
    }
}

/** One line of the drawer's list. */
@Immutable
private sealed class DrawerRow(val key: String) {
    class Head(val text: String) : DrawerRow("h:$text")
    class Session(val s: ChatSession) : DrawerRow(s.id)
    class Hit(val s: ChatSession, val m: ChatMsg) : DrawerRow("m:" + m.id)
    class Archived(val n: Int) : DrawerRow("archived")
}

@Composable
private fun DrawerList(cu: ChatUi, modifier: Modifier) {
    val snap = ChatStore.snap
    var archivedOpen by remember { mutableStateOf(false) }
    val q = cu.search.trim()
    val rows = remember(snap, q, archivedOpen, cu.deleting.toList()) {
        val all = snap.sessions.filter { it.id !in cu.deleting }
        val out = ArrayList<DrawerRow>()
        if (q.isNotEmpty()) {
            val chats = all.filter { it.title.contains(q, true) || it.last.contains(q, true) }
            if (chats.isNotEmpty()) out.add(DrawerRow.Head("Chats"))
            chats.forEach { out.add(DrawerRow.Session(it)) }
            val byId = all.associateBy { it.id }
            val hits = snap.threads.values.asSequence().flatten()
                .filter { !it.deleted && it.text.contains(q, true) }
                .sortedByDescending { it.at }.take(40)
                .mapNotNull { m -> byId[m.session]?.let { DrawerRow.Hit(it, m) } }.toList()
            if (hits.isNotEmpty()) out.add(DrawerRow.Head("Messages"))
            out.addAll(hits)
        } else {
            val live = all.filter { !it.archived }
            val pinned = live.filter { it.pinned }
            val recent = live.filter { !it.pinned }
            val archived = all.filter { it.archived }
            if (pinned.isNotEmpty()) out.add(DrawerRow.Head("Pinned"))
            pinned.forEach { out.add(DrawerRow.Session(it)) }
            if (recent.isNotEmpty()) out.add(DrawerRow.Head("Recent"))
            recent.forEach { out.add(DrawerRow.Session(it)) }
            if (archived.isNotEmpty()) {
                out.add(DrawerRow.Archived(archived.size))
                if (archivedOpen) archived.forEach { out.add(DrawerRow.Session(it)) }
            }
        }
        out
    }
    LazyColumn(modifier.fillMaxWidth(), contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp, vertical = 4.dp)) {
        items(rows, key = { it.key }, contentType = { it::class.simpleName }) { r ->
            when (r) {
                is DrawerRow.Head -> Text(
                    r.text.uppercase(), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(start = 16.dp, top = 16.dp, bottom = 6.dp),
                )
                is DrawerRow.Session -> SessionRow(cu, r.s)
                is DrawerRow.Hit -> HitRow(cu, r.s, r.m, q)
                is DrawerRow.Archived -> Row(
                    Modifier.fillMaxWidth().clip28().clickable { archivedOpen = !archivedOpen }.padding(horizontal = 16.dp, vertical = 14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(painterResource(R.drawable.ic_chat_archive), null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.width(20.dp))
                    Text("Archived · ${r.n}", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

private fun Modifier.clip28() = this.then(Modifier.graphicsLayer { shape = RoundedCornerShape(28.dp); clip = true })

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun SessionRow(cu: ChatUi, s: ChatSession) {
    val cs = MaterialTheme.colorScheme
    val active = s.id == ChatStore.current
    var menu by remember { mutableStateOf(false) }
    val haptic = LocalHapticFeedback.current
    Box {
        Row(
            Modifier.fillMaxWidth().clip28()
                .background(if (active) cs.surfaceContainerHighest else Color.Transparent)
                .combinedClickable(
                    onClick = { cu.open(s.id); cu.closeDrawer() },
                    onLongClick = { if (ChatPrefs.on(cu.a, ChatPrefs.HAPTICS)) haptic.performHapticFeedback(HapticFeedbackType.LongPress); menu = true },
                )
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Avatar(s, false, 48.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(s.title, style = MaterialTheme.typography.titleMediumEmphasized, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                    if (s.pinned && !s.main) Icon(painterResource(R.drawable.ic_chat_pin), null, Modifier.padding(start = 4.dp).size(14.dp), tint = cs.onSurfaceVariant)
                    Spacer(Modifier.weight(1f))
                    if (s.updated > 0) Text(ChatRules.`when`(s.updated, System.currentTimeMillis(), TimeZone.getDefault()), style = MaterialTheme.typography.labelMedium, color = cs.onSurfaceVariant)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        if (s.working) "${Prefs.assistant(cu.a)} is working…" else s.last.ifEmpty { "No messages yet" },
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (s.working) cs.primary else cs.onSurfaceVariant,
                        maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
                    )
                    Unread(s.unread, Modifier.padding(start = 8.dp))
                }
            }
        }
        DropdownMenu(menu, { menu = false }, shape = RoundedCornerShape(20.dp)) {
            if (!s.main) DropdownMenuItem({ Text("Rename") }, { menu = false; cu.renaming = s }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_edit), null) })
            if (!s.main) DropdownMenuItem(
                { Text(if (s.pinned) "Unpin" else "Pin") },
                { menu = false; Thread { Chat.pinSession(cu.a, s.id, !s.pinned) }.start() },
                leadingIcon = { Icon(painterResource(R.drawable.ic_chat_pin), null) },
            )
            if (!s.main) DropdownMenuItem(
                { Text(if (s.archived) "Unarchive" else "Archive") },
                { menu = false; Thread { Chat.setArchived(cu.a, s.id, !s.archived) }.start() },
                leadingIcon = { Icon(painterResource(R.drawable.ic_chat_archive), null) },
            )
            if (!s.main) DropdownMenuItem({ Text("Delete") }, { menu = false; cu.deleteChat(s) }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_delete), null) })
            if (s.main) DropdownMenuItem({ Text("Mark read") }, { menu = false; Chat.read(cu.a, s.id) }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_done_all), null) })
        }
    }
}

@Composable
private fun HitRow(cu: ChatUi, s: ChatSession, m: ChatMsg, q: String) {
    val cs = MaterialTheme.colorScheme
    val text = ChatRules.plain(m.text).replace('\n', ' ')
    val at = text.indexOf(q, ignoreCase = true).coerceAtLeast(0)
    val snippet = (if (at > 30) "…" + text.substring(at - 24) else text)
    Row(
        Modifier.fillMaxWidth().clip28().clickable { cu.open(s.id); cu.jump = m.id; cu.closeDrawer() }.padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Avatar(s, false, 40.dp)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(s.title, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text((if (m.mine) "You: " else "") + snippet, style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** For the thread's top bar: the chat's avatar, small. */
@Composable
fun ChatAvatarSmall(s: ChatSession, modifier: Modifier = Modifier) = Avatar(s, false, 36.dp, modifier)
