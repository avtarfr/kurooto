package io.github.avtarfr.kurooto

import android.graphics.Bitmap
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animate
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Badge
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LoadingIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

/**
 * The conversation (0.8.10): a top bar (the chat's name, "Kurooto is working…", the call button, the chat's menu), a
 * pinned bar, the messages (newest at the bottom: bubbles grouped by sender and minute, date separators, Markdown,
 * long answers folded, files, buttons, ticks on yours), a scroll-to-bottom button with how many came since, and the
 * composer. Swipe a message right to reply; hold it for the menu (reply, copy, share, pin, edit, delete, select).
 */
@Composable
fun ChatThread(cu: ChatUi, modifier: Modifier) {
    val snap = ChatStore.snap
    val current = ChatStore.current
    val session = snap.sessions.firstOrNull { it.id == current }
    val reduced = LocalReducedMotion.current
    val fade = MaterialTheme.motionScheme.fastEffectsSpec<Float>()
    Column(modifier.fillMaxSize()) {
        if (cu.selected.isNotEmpty()) SelectionBar(cu) else TopBar(cu, session)
        AnimatedContent(
            targetState = current,
            transitionSpec = {
                if (reduced) EnterTransition.None togetherWith ExitTransition.None
                else fadeIn(fade) togetherWith fadeOut(fade)
            },
            label = "thread",
            modifier = Modifier.weight(1f),
        ) { sid ->
            val rows = snap.rows[sid].orEmpty()
            Column(Modifier.fillMaxSize()) {
                PinnedBar(cu, snap.threads[sid].orEmpty())
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    Messages(cu, sid, rows, snap.sessions.firstOrNull { it.id == sid }?.working == true)
                }
            }
        }
        ChatComposer(cu)
    }
}

/** The chat's top bar: its name and state, the call button, and its menu. */
@Composable
private fun TopBar(cu: ChatUi, s: ChatSession?) {
    val cs = MaterialTheme.colorScheme
    var menu by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp, top = 8.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f).clickable(interactionSource = null, indication = null) { cu.openDrawer() }) {
            Text(
                s?.title ?: Prefs.assistant(cu.a), style = MaterialTheme.typography.titleLargeEmphasized, color = cs.onBackground,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            val off = ChatStore.snap.computer == "offline"
            when {
                s?.working == true -> Row(verticalAlignment = Alignment.CenterVertically) {
                    LoadingIndicator(Modifier.size(20.dp), color = cs.primary)
                    Spacer(Modifier.width(6.dp))
                    Text("${Prefs.assistant(cu.a)} is working…", style = MaterialTheme.typography.labelLarge, color = cs.primary, maxLines = 1)
                }
                off -> Text("Your computer is off: messages wait on your call line", style = MaterialTheme.typography.labelMedium, color = cs.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        FilledIconButton(
            onClick = { cu.call() },
            shape = RoundedCornerShape(20.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = cs.primary, contentColor = cs.onPrimary),
            modifier = Modifier.size(56.dp),
        ) { Icon(painterResource(R.drawable.ic_call), contentDescription = "Call ${Prefs.assistant(cu.a)}") }
        Box {
            IconButton({ menu = true }) { Icon(painterResource(R.drawable.ic_chat_more), contentDescription = "This chat") }
            DropdownMenu(menu, { menu = false }, shape = RoundedCornerShape(20.dp)) {
                DropdownMenuItem({ Text("Chats") }, { menu = false; cu.openDrawer() }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_search), null) })
                if (s != null && !s.main) {
                    DropdownMenuItem({ Text("Rename") }, { menu = false; cu.renaming = s }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_edit), null) })
                    DropdownMenuItem(
                        { Text(if (s.pinned) "Unpin chat" else "Pin chat") },
                        { menu = false; Thread { Chat.pinSession(cu.a, s.id, !s.pinned) }.start() },
                        leadingIcon = { Icon(painterResource(R.drawable.ic_chat_pin), null) },
                    )
                    DropdownMenuItem(
                        { Text(if (s.archived) "Unarchive" else "Archive") },
                        { menu = false; Thread { Chat.setArchived(cu.a, s.id, !s.archived) }.start() },
                        leadingIcon = { Icon(painterResource(R.drawable.ic_chat_archive), null) },
                    )
                    DropdownMenuItem({ Text("Delete chat") }, { menu = false; cu.deleteChat(s) }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_delete), null) })
                }
            }
        }
    }
}

/** While messages are selected: how many, Copy, Share, Delete (on this phone). */
@Composable
private fun SelectionBar(cu: ChatUi) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton({ cu.selected.clear() }) { Icon(painterResource(R.drawable.ic_chat_close), contentDescription = "Done selecting") }
        Text("${cu.selected.size} selected", style = MaterialTheme.typography.titleLargeEmphasized, modifier = Modifier.weight(1f))
        IconButton({ cu.copy(cu.selectedText()); cu.selected.clear() }) { Icon(painterResource(R.drawable.ic_chat_copy), contentDescription = "Copy") }
        IconButton({ cu.share(cu.selectedText()); cu.selected.clear() }) { Icon(painterResource(R.drawable.ic_chat_share), contentDescription = "Share") }
        IconButton({
            val ids = cu.selected.toList()
            cu.selected.clear()
            Thread { ids.forEach { Chat.deleteMessage(cu.a, it, false) } }.start()
        }) { Icon(painterResource(R.drawable.ic_chat_delete), contentDescription = "Delete on this phone") }
    }
}

/** The newest pinned message: tap to go to it, × to unpin. */
@Composable
private fun PinnedBar(cu: ChatUi, msgs: List<ChatMsg>) {
    val p = remember(msgs) { msgs.lastOrNull { it.pinned && !it.deleted } } ?: return
    val cs = MaterialTheme.colorScheme
    Surface(
        shape = RoundedCornerShape(24.dp), color = cs.surfaceContainerHigh,
        modifier = Modifier.fillMaxWidth().padding(start = 8.dp, end = 8.dp, bottom = 4.dp),
        onClick = { cu.jump = p.id },
    ) {
        Row(Modifier.padding(start = 14.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(painterResource(R.drawable.ic_chat_pin), null, Modifier.size(18.dp), tint = cs.primary)
            Spacer(Modifier.width(10.dp))
            Text(
                buildAnnotatedString {
                    withStyle(SpanStyle(color = cs.primary, fontWeight = FontWeight.SemiBold)) { append("Pinned") }
                    append(" · ")
                    append(ChatRules.plain(p.text).replace('\n', ' ').ifEmpty { p.file?.name.orEmpty() })
                },
                style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
            )
            IconButton({ Thread { Chat.pinMessage(cu.a, p.id, false) }.start() }, Modifier.size(40.dp)) {
                Icon(painterResource(R.drawable.ic_chat_close), contentDescription = "Unpin", Modifier.size(18.dp))
            }
        }
    }
}

/** Each chat's scroll position, kept while the pane is up. */
private val lists = HashMap<String, LazyListState>()

@Composable
private fun Messages(cu: ChatUi, sid: String, rows: List<ChatRow>, working: Boolean) {
    val list = remember(sid) { lists.getOrPut(sid) { LazyListState() } }
    val scope = rememberCoroutineScope()
    // with "working", a bubble with the loading indicator sits under the newest message (index 0)
    val shift = if (working) 1 else 0
    // the newest message when you were last at the bottom: what came after it is "new"
    var seen by remember(sid) { mutableStateOf(rows.firstOrNull()?.key) }
    val atBottom by remember(list) { derivedStateOf { list.firstVisibleItemIndex <= 1 } }
    val latest by rememberUpdatedState(rows)
    LaunchedEffect(sid, list) {
        snapshotFlow { latest.firstOrNull()?.key }.collect { newest ->
            if (atBottom) {
                seen = newest
                if (list.firstVisibleItemIndex > 0 || list.firstVisibleItemScrollOffset > 0) list.animateScrollToItem(0)
            }
        }
    }
    LaunchedEffect(atBottom) { if (atBottom) seen = latest.firstOrNull()?.key }
    LaunchedEffect(cu.jump, rows) {
        val id = cu.jump ?: return@LaunchedEffect
        val i = rows.indexOfFirst { it.key == id }
        if (i >= 0) {
            list.animateScrollToItem(i + shift)
            flash[id] = System.currentTimeMillis()
            cu.jump = null
        }
    }
    val newCount = remember(rows, seen) {
        val i = rows.indexOfFirst { it.key == seen }
        if (i <= 0) 0 else rows.subList(0, i).count { it is ChatRow.Msg && !it.m.mine }
    }
    val cs = MaterialTheme.colorScheme
    LazyColumn(
        Modifier.fillMaxSize(),
        state = list,
        reverseLayout = true,
        contentPadding = PaddingValues(start = 10.dp, end = 10.dp, top = 8.dp, bottom = 8.dp),
    ) {
        if (working) item(key = "working", contentType = "working") { WorkingBubble() }
        items(rows, key = { it.key }, contentType = { r -> if (r is ChatRow.Msg) (if (r.m.mine) "mine" else "theirs") else "day" }) { r ->
            when (r) {
                is ChatRow.Day -> DayChip(r.label)
                is ChatRow.Msg -> BubbleRow(cu, r)
            }
        }
        if (rows.isEmpty()) item(key = "empty", contentType = "empty") { Empty(cu, sid) }
    }
    val show by remember(list) { derivedStateOf { list.firstVisibleItemIndex > 2 } }
    val fade = MaterialTheme.motionScheme.fastEffectsSpec<Float>()
    val pop = MaterialTheme.motionScheme.fastSpatialSpec<Float>()
    Box(Modifier.fillMaxSize().padding(12.dp), contentAlignment = Alignment.BottomEnd) {
        AnimatedVisibility(show, enter = fadeIn(fade) + scaleIn(pop, initialScale = 0.6f), exit = fadeOut(fade) + scaleOut(pop, targetScale = 0.6f)) {
            Box {
                SmallFloatingActionButton(
                    onClick = { scope.launch { list.animateScrollToItem(0) } },
                    containerColor = cs.surfaceContainerHighest, contentColor = cs.onSurface,
                ) { Icon(painterResource(R.drawable.ic_chat_down), contentDescription = "To the newest") }
                if (newCount > 0) Badge(Modifier.align(Alignment.TopEnd).offset(x = 2.dp, y = (-4).dp), containerColor = cs.tertiary, contentColor = cs.onTertiary) {
                    Text(if (newCount > 99) "99+" else "$newCount")
                }
            }
        }
    }
}

/** Messages flashed after a jump (by id: when). */
private val flash = mutableStateMapOf<String, Long>()

@Composable
private fun Empty(cu: ChatUi, sid: String) {
    Column(Modifier.fillMaxWidth().padding(top = 80.dp, start = 24.dp, end = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        val name = Prefs.assistant(cu.a)
        Text(
            if (sid == Chat.MAIN) "$name's own messages come here: reminders, results, what it found." else "A new chat with $name. It remembers what's said here for as long as the chat lives.",
            style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun DayChip(label: String) {
    Box(Modifier.fillMaxWidth().padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
        Text(
            label.uppercase(), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.background(MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.85f), CircleShape).padding(horizontal = 12.dp, vertical = 4.dp),
        )
    }
}

/** "Kurooto is working…": a bubble of Kurooto's with the expressive loading indicator. */
@Composable
private fun WorkingBubble() {
    Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
        Surface(shape = RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp), color = MaterialTheme.colorScheme.surfaceContainerHigh) {
            LoadingIndicator(Modifier.padding(horizontal = 14.dp, vertical = 6.dp).size(36.dp), color = MaterialTheme.colorScheme.primary)
        }
    }
}

private val TIME = object : ThreadLocal<SimpleDateFormat>() {
    override fun initialValue() = SimpleDateFormat("HH:mm", Locale.ROOT)
}

/**
 * One message: its bubble (yours right in the primary container, Kurooto's left), with the swipe to reply (the bubble
 * follows the finger, a reply arrow fades in, and past the line it ticks and springs back) and the long-press menu.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun BubbleRow(cu: ChatUi, r: ChatRow.Msg) {
    val m = r.m
    val cs = MaterialTheme.colorScheme
    val density = LocalDensity.current
    val haptic = LocalHapticFeedback.current
    val haptics = remember(ChatPrefs.rev) { ChatPrefs.on(cu.a, ChatPrefs.HAPTICS) }
    val swipeOn = remember(ChatPrefs.rev) { ChatPrefs.on(cu.a, ChatPrefs.SWIPE_REPLY) } && !m.deleted && cu.selected.isEmpty()
    val line = with(density) { 64.dp.toPx() }
    var dx by remember { mutableStateOf(0f) }
    var armed by remember { mutableStateOf(false) }
    val spring = MaterialTheme.motionScheme.fastSpatialSpec<Float>()
    val drag = rememberDraggableState { d ->
        dx = (dx + d).coerceIn(0f, line * 2f)
        val now = dx >= line
        if (now && !armed && haptics) haptic.performHapticFeedback(HapticFeedbackType.GestureThresholdActivate)
        armed = now
    }
    val selected = m.id in cu.selected
    var menu by remember { mutableStateOf(false) }
    // a jump here flashes it once
    val glow = remember { Animatable(0f) }
    val flashed = flash[m.id]
    val slow = MaterialTheme.motionScheme.slowEffectsSpec<Float>()
    LaunchedEffect(flashed) {
        if (flashed != null) {
            glow.snapTo(1f)
            delay(350)
            glow.animateTo(0f, slow)
            flash.remove(m.id)
        }
    }
    Box(
        Modifier.fillMaxWidth()
            .padding(top = if (r.first) 8.dp else 2.dp)
            .background(if (selected) cs.primary.copy(alpha = 0.16f) else Color.Transparent, RoundedCornerShape(12.dp)),
    ) {
        // the reply arrow, under the bubble's start, as it's pulled
        Icon(
            painterResource(R.drawable.ic_chat_reply), null,
            tint = cs.primary,
            modifier = Modifier.align(Alignment.CenterStart).padding(start = 8.dp).size(24.dp).graphicsLayer {
                val p = (dx / line).coerceIn(0f, 1f)
                alpha = p
                scaleX = 0.6f + 0.4f * p
                scaleY = 0.6f + 0.4f * p
            },
        )
        Row(
            Modifier.fillMaxWidth()
                .offset { IntOffset((if (dx <= line) dx else line + (dx - line) * 0.3f).roundToInt(), 0) }
                .draggable(
                    drag, Orientation.Horizontal, enabled = swipeOn,
                    onDragStopped = { v ->
                        if (dx >= line) cu.reply(m)
                        armed = false
                        drag.drag {
                            var prev = dx
                            animate(prev, 0f, v.coerceAtMost(0f), spring) { x, _ -> dragBy(x - prev); prev = x }
                        }
                    },
                ),
            horizontalArrangement = if (m.mine) Arrangement.End else Arrangement.Start,
        ) {
            Column(horizontalAlignment = if (m.mine) Alignment.End else Alignment.Start, modifier = Modifier.widthIn(max = 320.dp)) {
                Box {
                    Bubble(
                        cu, r, glow,
                        Modifier.combinedClickable(
                            onClick = {
                                when {
                                    cu.selected.isNotEmpty() -> if (selected) cu.selected.remove(m.id) else cu.selected.add(m.id)
                                    m.mine && m.state == "failed" -> cu.resend(m)
                                }
                            },
                            onLongClick = {
                                if (haptics) haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                if (cu.selected.isNotEmpty()) { if (selected) cu.selected.remove(m.id) else cu.selected.add(m.id) } else menu = true
                            },
                        ),
                    )
                    MessageMenu(cu, m, menu) { menu = false }
                }
                if (!m.mine && !m.deleted && (m.buttons.isNotEmpty() || m.takesReply)) Buttons(cu, m)
            }
        }
    }
}

@Composable
private fun MessageMenu(cu: ChatUi, m: ChatMsg, open: Boolean, close: () -> Unit) {
    DropdownMenu(open, close, shape = RoundedCornerShape(20.dp)) {
        if (m.deleted) {
            DropdownMenuItem({ Text("Delete on this phone") }, { close(); Thread { Chat.deleteMessage(cu.a, m.id, false) }.start() }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_delete), null) })
            return@DropdownMenu
        }
        val text = ChatRules.plain(m.text)
        DropdownMenuItem({ Text("Reply") }, { close(); cu.reply(m) }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_reply), null) })
        if (text.isNotEmpty()) {
            DropdownMenuItem({ Text("Copy") }, { close(); cu.copy(text) }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_copy), null) })
        }
        DropdownMenuItem({ Text("Share") }, {
            close()
            val f = m.file
            if (f != null) openFile(cu, f, share = true) else cu.share(text)
        }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_share), null) })
        DropdownMenuItem(
            { Text(if (m.pinned) "Unpin" else "Pin") },
            { close(); Thread { Chat.pinMessage(cu.a, m.id, !m.pinned) }.start() },
            leadingIcon = { Icon(painterResource(R.drawable.ic_chat_pin), null) },
        )
        if (m.text.isNotEmpty() && ChatStore.snap.on("chat_edit") && ChatRules.editable(m.mine, m.at, System.currentTimeMillis())) {
            DropdownMenuItem({ Text("Edit") }, { close(); cu.edit(m) }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_edit), null) })
        }
        DropdownMenuItem({ Text("Delete") }, { close(); cu.deletingMsg = m }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_delete), null) })
        DropdownMenuItem({ Text("Select") }, { close(); cu.selected.add(m.id) }, leadingIcon = { Icon(painterResource(R.drawable.ic_chat_select), null) })
    }
}

/** The bubble: a quote, a file, the text (Markdown, folded when long), and the time with your message's ticks. Corners
 *  are smaller where a run of one sender's messages joins. */
@Composable
private fun Bubble(cu: ChatUi, r: ChatRow.Msg, glow: Animatable<Float, androidx.compose.animation.core.AnimationVector1D>, modifier: Modifier) {
    val m = r.m
    val cs = MaterialTheme.colorScheme
    val big = 22.dp
    val small = 6.dp
    // the corner on the sender's side is small where the run continues, and at its end (the tail)
    val shape = if (m.mine) RoundedCornerShape(big, if (r.first) big else small, small, big)
    else RoundedCornerShape(if (r.first) big else small, big, big, small)
    val bg = if (m.mine) cs.primaryContainer else cs.surfaceContainerHigh
    val fg = if (m.mine) cs.onPrimaryContainer else cs.onSurface
    Surface(shape = shape, color = bg, contentColor = fg, modifier = modifier) {
        Box {
            Column(Modifier.padding(horizontal = 6.dp, vertical = 6.dp)) {
                m.quote?.let { Quote(cu, it, m.mine) }
                m.file?.let { FileView(cu, m, it) }
                when {
                    m.deleted -> Text(
                        "This message was deleted", style = MaterialTheme.typography.bodyLarge, fontStyle = FontStyle.Italic,
                        color = fg.copy(alpha = 0.7f), modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    )
                    m.text.isNotEmpty() -> Box(Modifier.padding(horizontal = 10.dp, vertical = 4.dp)) { MessageText(cu, m, fg) }
                }
                Footer(m, fg)
            }
            // the flash after a jump, over the whole bubble (only while it flashes)
            if (flash[m.id] != null) Box(Modifier.matchParentSize().graphicsLayer { alpha = glow.value * 0.35f }.background(cs.primary))
        }
    }
}

@Composable
private fun ColumnScope.Footer(m: ChatMsg, fg: Color) {
    val k = LocalKurooto.current
    Row(
        Modifier.padding(start = 10.dp, end = 8.dp, bottom = 2.dp).then(if (m.mine) Modifier.align(Alignment.End) else Modifier),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (m.mine && m.state == "failed") {
            Text("Not sent: tap to try again" + if (m.note.isEmpty()) "" else " (${m.note})", style = MaterialTheme.typography.labelMedium, color = k.bad, modifier = Modifier.weight(1f, fill = false))
            Spacer(Modifier.width(6.dp))
        } else if (m.mine && m.state == "waiting") {
            Text("Waiting for your computer", style = MaterialTheme.typography.labelMedium, color = fg.copy(alpha = 0.7f))
            Spacer(Modifier.width(6.dp))
        }
        if (m.edited && !m.deleted) Text("edited ", style = MaterialTheme.typography.labelSmall, color = fg.copy(alpha = 0.7f))
        Text(TIME.get()!!.format(Date(m.at * 1000)), style = MaterialTheme.typography.labelSmall, color = fg.copy(alpha = 0.7f))
        if (m.mine) {
            Spacer(Modifier.width(4.dp))
            val (icon, what, tint) = when (m.state) {
                "sending" -> Triple(R.drawable.ic_chat_clock, "Sending", fg.copy(alpha = 0.7f))
                "waiting" -> Triple(R.drawable.ic_chat_check, "Waiting on your call line", fg.copy(alpha = 0.7f))
                "failed" -> Triple(R.drawable.ic_chat_error, "Not sent", k.bad)
                else -> Triple(R.drawable.ic_chat_done_all, if (m.answered) "Answered" else "Reached your computer", if (m.answered) MaterialTheme.colorScheme.tertiary else fg.copy(alpha = 0.7f))
            }
            Icon(painterResource(icon), contentDescription = what, tint = tint, modifier = Modifier.size(16.dp))
        }
    }
}

/** The message a reply quotes: who and what, in a tinted block; tap goes to it. */
@Composable
private fun Quote(cu: ChatUi, q: ChatQuote, mine: Boolean) {
    val cs = MaterialTheme.colorScheme
    val who = if (q.from == "you") "You" else Prefs.assistant(cu.a)
    Row(
        Modifier.fillMaxWidth().padding(bottom = 4.dp).clip(RoundedCornerShape(16.dp))
            .background((if (mine) cs.onPrimaryContainer else cs.onSurface).copy(alpha = 0.08f))
            .clickable { cu.jump = q.id }
            .padding(end = 12.dp),
    ) {
        Box(Modifier.padding(vertical = 8.dp, horizontal = 8.dp).width(3.dp).height(36.dp).background(cs.tertiary, CircleShape))
        Column(Modifier.padding(vertical = 6.dp)) {
            Text(who, style = MaterialTheme.typography.labelLarge, color = cs.tertiary)
            Text(q.text, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** A message's buttons (as on Telegram: the first filled, the rest tonal), and Reply under one that takes a reply.
 *  (0.9.1) Feedback buttons (Wrong, Why?, Less of this: "quiet") come last as small text buttons; each keeps its number. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Buttons(cu: ChatUi, m: ChatMsg) {
    val cs = MaterialTheme.colorScheme
    val order = remember(m.buttons) { m.buttons.indices.sortedBy { if (m.buttons[it].quiet) 1 else 0 } }
    val first = order.firstOrNull { !m.buttons[it].quiet }
    FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        order.forEach { i ->
            val b = m.buttons[i]
            var busy by remember(m.id, i) { mutableStateOf(false) }
            if (b.quiet) {
                TextButton({ cu.tap(m, i, b) { busy = it } }, enabled = !busy, shapes = ButtonDefaults.shapes()) { Text(b.label) }
            } else if (i == first) {
                Button({ cu.tap(m, i, b) { busy = it } }, enabled = !busy, shapes = ButtonDefaults.shapes()) { Text(b.label) }
            } else {
                FilledTonalButton(
                    { cu.tap(m, i, b) { busy = it } }, enabled = !busy, shapes = ButtonDefaults.shapes(),
                    colors = ButtonDefaults.filledTonalButtonColors(containerColor = cs.tertiaryContainer, contentColor = cs.onTertiaryContainer),
                ) { Text(b.label) }
            }
        }
        if (m.takesReply) {
            TextButton({ cu.reply(m) }, shapes = ButtonDefaults.shapes()) {
                Icon(painterResource(R.drawable.ic_chat_reply), null, Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Reply")
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ the text
/** The message's text: Markdown blocks (paragraphs, lists, code, headings, quotes) with inline bold, italic, code and
 *  links; a long answer shows its start and Show more. Plain text with Formatting off. */
@Composable
private fun MessageText(cu: ChatUi, m: ChatMsg, fg: Color) {
    val cs = MaterialTheme.colorScheme
    val md = remember(ChatPrefs.rev) { ChatPrefs.on(cu.a, ChatPrefs.MARKDOWN) }
    val foldOn = remember(ChatPrefs.rev) { ChatPrefs.on(cu.a, ChatPrefs.FOLD) }
    val blocks = remember(m.text, md) { if (md) ChatRules.blocks(m.text) else listOf(ChatRules.Block(ChatRules.PARA, m.text, "")) }
    val long = foldOn && !m.mine && (m.text.length > 700 || blocks.size > 8)
    val open = cu.expanded[m.id] == true
    val shown = remember(blocks, long, open) {
        if (!long || open) blocks
        else {
            var n = 0
            val out = ArrayList<ChatRules.Block>()
            for (b in blocks) {
                out.add(b)
                n += b.text.length
                if (n > 360 || out.size >= 4) break
            }
            out
        }
    }
    val code = if (m.mine) cs.onPrimaryContainer.copy(alpha = 0.1f) else cs.surfaceContainerHighest
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        shown.forEachIndexed { i, b ->
            val lastFolded = long && !open && i == shown.size - 1
            when (b.kind) {
                ChatRules.CODE -> Surface(shape = RoundedCornerShape(12.dp), color = code, modifier = Modifier.fillMaxWidth()) {
                    Text(
                        b.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodyMedium,
                        softWrap = false, modifier = Modifier.horizontalScroll(rememberScrollState()).padding(10.dp),
                    )
                }
                ChatRules.BULLET, ChatRules.NUMBER -> Row {
                    Text(b.marker, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.width(if (b.kind == ChatRules.NUMBER) 26.dp else 16.dp))
                    Inline(b.text, md, fg, MaterialTheme.typography.bodyLarge, if (lastFolded) 3 else Int.MAX_VALUE)
                }
                ChatRules.HEADING -> Inline(b.text, md, fg, MaterialTheme.typography.titleMediumEmphasized, Int.MAX_VALUE)
                ChatRules.QUOTE -> Row {
                    Box(Modifier.padding(end = 8.dp).width(3.dp).height(20.dp).background(fg.copy(alpha = 0.4f), CircleShape))
                    Inline(b.text, md, fg.copy(alpha = 0.85f), MaterialTheme.typography.bodyLarge, Int.MAX_VALUE)
                }
                else -> Inline(b.text, md, fg, MaterialTheme.typography.bodyLarge, if (lastFolded) 6 else Int.MAX_VALUE)
            }
        }
        if (long) {
            Text(
                if (open) "Show less" else "Show more",
                style = MaterialTheme.typography.labelLarge, color = cs.primary, fontWeight = FontWeight.Bold,
                modifier = Modifier.clickable { cu.expanded[m.id] = !open }.padding(vertical = 2.dp),
            )
        }
    }
}

@Composable
private fun Inline(text: String, md: Boolean, fg: Color, style: androidx.compose.ui.text.TextStyle, lines: Int) {
    val cs = MaterialTheme.colorScheme
    val s = remember(text, md, cs.primary) { annotated(text, md, cs.primary, cs.onSurface.copy(alpha = 0.12f)) }
    Text(s, style = style, color = fg, maxLines = lines, overflow = TextOverflow.Ellipsis)
}

private fun annotated(text: String, md: Boolean, link: Color, codeBg: Color): AnnotatedString = buildAnnotatedString {
    val linkStyle = TextLinkStyles(SpanStyle(color = link, textDecoration = TextDecoration.Underline))
    val spans = if (md) ChatRules.inline(text) else ChatRules.inline(text).map { if (it.kind == ChatRules.LINK && it.url == it.text) it else ChatRules.Span(ChatRules.TEXT, it.text, null) }
    for (x in spans) {
        when (x.kind) {
            ChatRules.BOLD -> withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(x.text) }
            ChatRules.ITALIC -> withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(x.text) }
            ChatRules.BOLD_ITALIC -> withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontStyle = FontStyle.Italic)) { append(x.text) }
            ChatRules.MONO -> withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = codeBg)) { append(x.text) }
            ChatRules.LINK -> withLink(LinkAnnotation.Url(x.url, linkStyle)) { append(x.text) }
            else -> append(x.text)
        }
    }
}

// ------------------------------------------------------------------------------------------------ files
/** A file in a message: a photo as a picture (tap: full screen), a voice note or audio with a play button, anything
 *  else as a card with its name and size (tap: fetched, opened here, then opened with the phone's app for it). */
@Composable
private fun FileView(cu: ChatUi, m: ChatMsg, f: ChatFile) {
    when {
        f.image -> Photo(cu, m, f)
        f.audio -> Audio(cu, m, f)
        else -> FileCard(cu, m, f)
    }
}

@Composable
private fun Photo(cu: ChatUi, m: ChatMsg, f: ChatFile) {
    val c = LocalContext.current
    val auto = remember(ChatPrefs.rev) { ChatPrefs.on(c, ChatPrefs.AUTO_PHOTOS) } || m.mine
    var asked by remember(m.id) { mutableStateOf(auto) }
    val px = with(LocalDensity.current) { 300.dp.roundToPx() }
    val bmp by produceState<Bitmap?>(null, f.url, f.path, asked) {
        if (asked) value = withContext(Dispatchers.IO) { ChatFiles.bitmap(c, f, px) }
    }
    val cs = MaterialTheme.colorScheme
    // a fixed frame (4:3), so the list never jumps when the picture comes
    Box(
        Modifier.width(280.dp).aspectRatio(4f / 3f).clip(RoundedCornerShape(18.dp)).background(cs.surfaceContainerHighest)
            .clickable { if (bmp != null) cu.viewer = m else asked = true },
        contentAlignment = Alignment.Center,
    ) {
        val b = bmp
        if (b != null) Image(b.asImageBitmap(), contentDescription = f.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        else if (asked) LoadingIndicator(Modifier.size(40.dp))
        else Text("Tap to load the photo (${ChatRules.size(f.size)})", style = MaterialTheme.typography.labelLarge, color = cs.onSurfaceVariant)
    }
}

@Composable
private fun FileCard(cu: ChatUi, m: ChatMsg, f: ChatFile) {
    val cs = MaterialTheme.colorScheme
    val busy = busyFiles[m.id] == true
    Row(
        Modifier.widthIn(min = 220.dp).clip(RoundedCornerShape(18.dp))
            .background((if (m.mine) cs.onPrimaryContainer else cs.onSurface).copy(alpha = 0.08f))
            .clickable { openFile(cu, f, share = false, id = m.id) }
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(48.dp).clip(RoundedCornerShape(14.dp)).background(if (m.mine) cs.onPrimaryContainer else cs.primary), contentAlignment = Alignment.Center) {
            if (busy) LoadingIndicator(Modifier.size(32.dp), color = if (m.mine) cs.primaryContainer else cs.onPrimary)
            else Text(f.badge, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = if (m.mine) cs.primaryContainer else cs.onPrimary)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f, fill = false)) {
            Text(f.name, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(ChatRules.size(f.size), style = MaterialTheme.typography.bodySmall, color = androidx.compose.material3.LocalContentColor.current.copy(alpha = 0.7f))
        }
    }
}

@Composable
private fun Audio(cu: ChatUi, m: ChatMsg, f: ChatFile) {
    val cs = MaterialTheme.colorScheme
    val c = LocalContext.current
    val playing = ChatFiles.Player.playing == m.id
    val progress by produceState(0f, playing) {
        while (playing) { value = ChatFiles.Player.position(); delay(100) }
        value = 0f
    }
    val scope = rememberCoroutineScope()
    Row(Modifier.widthIn(min = 220.dp).padding(4.dp), verticalAlignment = Alignment.CenterVertically) {
        FilledIconButton({
            scope.launch {
                val file = withContext(Dispatchers.IO) { ChatFiles.local(c, f) }
                if (file == null) cu.say("That voice note is gone: files in the chat last a day on your call line.") else ChatFiles.Player.toggle(m.id, file)
            }
        }, Modifier.size(44.dp)) {
            Icon(painterResource(if (playing) R.drawable.ic_chat_pause else R.drawable.ic_chat_play), contentDescription = if (playing) "Pause" else "Play")
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            // the progress as a bar that fills (drawn, not laid out, each frame)
            Box(Modifier.fillMaxWidth().height(4.dp).clip(CircleShape).background(cs.onSurface.copy(alpha = 0.15f))) {
                Box(Modifier.fillMaxSize().graphicsLayer { scaleX = progress; transformOrigin = androidx.compose.ui.graphics.TransformOrigin(0f, 0.5f) }.background(cs.primary))
            }
            Text(if (f.name.startsWith("voice-")) "Voice note · ${ChatRules.size(f.size)}" else "${f.name} · ${ChatRules.size(f.size)}", style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 6.dp))
        }
    }
}

/** Files being fetched (by message id). */
private val busyFiles = mutableStateMapOf<String, Boolean>()

/** Fetch (and open, off the main thread) a file, then open it with the phone's app for it, or share it. */
private fun openFile(cu: ChatUi, f: ChatFile, share: Boolean, id: String = "") {
    if (id.isNotEmpty()) busyFiles[id] = true
    cu.scope.launch {
        val file = withContext(Dispatchers.IO) { ChatFiles.local(cu.a, f) }
        if (id.isNotEmpty()) busyFiles.remove(id)
        if (file == null) { cu.say("That file is gone: files in the chat last a day on your call line. Ask for it again."); return@launch }
        try {
            cu.a.startActivity(if (share) ChatFiles.shareIntent(cu.a, file, f) else ChatFiles.openIntent(cu.a, file, f))
        } catch (_: Exception) {
            cu.say("No app on this phone opens ${f.badge} files.")
        }
    }
}

/** A photo full screen: pinch to zoom, drag to look around; Share and Save. */
@Composable
fun ImageViewer(cu: ChatUi) {
    val m = cu.viewer ?: return
    val f = m.file ?: return
    val c = LocalContext.current
    val bmp by produceState<Bitmap?>(null, f.url, f.path) { value = withContext(Dispatchers.IO) { ChatFiles.bitmap(c, f, 2048) } }
    var scale by remember { mutableStateOf(1f) }
    var off by remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }
    val zoom = rememberTransformableState { z, pan, _ ->
        scale = (scale * z).coerceIn(1f, 6f)
        off = if (scale == 1f) androidx.compose.ui.geometry.Offset.Zero else off + pan
    }
    val save = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument(f.mime)) { to ->
        if (to != null) cu.scope.launch {
            val ok = withContext(Dispatchers.IO) { ChatFiles.local(c, f)?.let { ChatFiles.saveTo(c, it, to) } == true }
            cu.say(if (ok) "Saved." else "Couldn't save it.")
        }
    }
    Dialog({ cu.viewer = null }, DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Box(Modifier.fillMaxSize().background(Color.Black)) {
            bmp?.let {
                Image(
                    it.asImageBitmap(), f.name, contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxSize().transformable(zoom).graphicsLayer {
                        scaleX = scale
                        scaleY = scale
                        translationX = off.x
                        translationY = off.y
                    },
                )
            } ?: LoadingIndicator(Modifier.align(Alignment.Center))
            Row(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.safeDrawing).padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton({ cu.viewer = null }) { Icon(painterResource(R.drawable.ic_chat_close), "Close", tint = Color.White) }
                Text(f.name, color = Color.White, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                IconButton({ openFile(cu, f, share = true) }) { Icon(painterResource(R.drawable.ic_chat_share), "Share", tint = Color.White) }
                IconButton({ save.launch(f.name) }) { Icon(painterResource(R.drawable.ic_chat_download), "Save", tint = Color.White) }
            }
        }
    }
}
