package io.github.avtarfr.kurooto

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import androidx.activity.compose.BackHandler
import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.animation.core.AnimationSpec
import androidx.compose.animation.core.animate
import androidx.compose.animation.core.snap
import androidx.compose.foundation.MutatePriority
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.DraggableState
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.min
import androidx.core.util.Consumer
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.util.WeakHashMap
import kotlin.concurrent.thread
import kotlin.coroutines.cancellation.CancellationException

/**
 * The Chat pane (0.8.10), the screen the app opens on: Telegram's chat with sessions on top, laid out as the "Rail"
 * design. The sessions sit on a floating rail of shaped avatars down the left edge (each its own Material shape and
 * tonal colour, unread badges, "+" for a new chat, Kurooto's own pinned first; ChatRail.kt); tap one to switch, drag
 * the rail right (or tap the active one) to pull it open into a drawer with names, last lines, search, what's waiting
 * for you (WaitingBar), pinned/recent/archived and New chat. The navigation folds into the rail's foot
 * (`KNav(vertical = true)`). The thread fills the rest (ChatThread.kt), with the composer at its foot
 * (ChatComposer.kt). The store is Chat's; ChatStore reads it off the main thread.
 */
@Composable
fun ChatPane(a: MainActivity, ui: HomeState, room: PaddingValues) {
    val scope = rememberCoroutineScope()
    val cu = remember(a) { ChatUi(a, ui, scope) }
    ChatLife(a, ui, cu)
    val reduced = LocalReducedMotion.current
    val spatial = MaterialTheme.motionScheme.defaultSpatialSpec<Float>()
    cu.spec = if (reduced) snap() else spatial
    BoxWithConstraints(Modifier.fillMaxSize().padding(room).consumeWindowInsets(room)) {
        val density = LocalDensity.current
        val drawerW = min(maxWidth - 40.dp, 400.dp)
        cu.drawer.width = with(density) { drawerW.toPx() }
        cu.drawer.over = with(density) { 40.dp.toPx() }
        val sides = WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal)
        Row(Modifier.fillMaxSize().windowInsetsPadding(sides)) {
            ChatRail(cu, Modifier.padding(start = 8.dp, top = 8.dp, bottom = 8.dp).width(RAIL_W))
            ChatThread(cu, Modifier.weight(1f))
        }
        // the drawer: over the rail and the thread, with a scrim that darkens as it opens
        val shown by remember { derivedStateOf { cu.drawer.pos > 0.5f } }
        if (shown) {
            val none = remember { MutableInteractionSource() }
            Box(
                Modifier.fillMaxSize()
                    .graphicsLayer { alpha = cu.drawer.progress }
                    .background(Color.Black.copy(alpha = 0.5f))
                    .clickable(none, indication = null) { cu.closeDrawer() },
            )
            ChatDrawer(cu, drawerW, Modifier.windowInsetsPadding(sides))
        }
        SnackbarHost(
            cu.snack,
            Modifier.align(Alignment.BottomCenter).windowInsetsPadding(WindowInsets.navigationBars.union(WindowInsets.ime)).padding(bottom = 88.dp),
        )
        ChatDialogs(cu)
        ImageViewer(cu)
    }
    // Back: closes what's open first (the drawer follows the predictive back gesture), then the app goes as usual
    val open by remember { derivedStateOf { cu.drawer.pos > cu.drawer.width / 2 } }
    PredictiveBackHandler(enabled = open) { progress ->
        val start = cu.drawer.pos
        try {
            progress.collect { e -> cu.drawer.pos = start * (1f - e.progress) }
            cu.closeDrawer()
        } catch (e: CancellationException) {
            cu.openDrawer()
            throw e
        }
    }
    BackHandler(enabled = !open && (cu.selected.isNotEmpty() || cu.replyTo != null || cu.editing != null)) {
        when {
            cu.selected.isNotEmpty() -> cu.selected.clear()
            cu.editing != null -> { cu.editing = null; cu.typed = TextFieldValue("") }
            else -> cu.replyTo = null
        }
    }
}

/** The rail's width (its avatars and the navigation at its foot). */
val RAIL_W = 72.dp

/** Chat's own settings (Settings → Chat, placed by the Settings pane): this phone's switches for the chat. Your
 *  computer's chat switches (sessions, files inline, edit, AI titles) are on its dashboard. */
@Composable
fun ChatSettings(a: MainActivity) {
    val rev = ChatPrefs.rev
    Group(
        ChatPrefs.ALL.map { s ->
            val on = remember(rev, s.key) { ChatPrefs.on(a, s) }
            Item(s.title, s.sub, onClick = { ChatPrefs.set(a, s, !on) }, checked = on)
        },
    )
    Footnote("Kurooto's own chat settings (sessions, files in the chat, editing, titles) are on your computer's dashboard → Settings.")
}

/** The drawer's place: 0 folded, `width` open (a little more while a spring settles); dragged 1:1, settled by a spring
 *  from the motion scheme with the fling's speed. */
@Stable
class RailDrawer {
    var width = 1f
    var over = 0f
    var pos by mutableFloatStateOf(0f)
    val progress get() = (pos / width).coerceIn(0f, 1f)
    val drag = DraggableState { d -> pos = (pos + d).coerceIn(0f, width + over) }

    suspend fun settle(target: Float, velocity: Float, spec: AnimationSpec<Float>) {
        drag.drag(MutatePriority.Default) {
            var prev = pos
            animate(prev, target, velocity, spec) { v, _ ->
                dragBy(v - prev)
                prev = v
            }
        }
    }

    /** Where a drag that ends at this speed (px/s) goes: a fling decides, else the nearer end. */
    fun target(velocity: Float, flingPx: Float) = when {
        velocity > flingPx -> width
        velocity < -flingPx -> 0f
        else -> if (pos > width / 2) width else 0f
    }
}

/** What the Chat pane remembers while it's up: the open session lives in ChatStore; this holds the composer, the
 *  reply or edit in progress, a selection, the drawer and the dialogs. */
@Stable
class ChatUi(val a: MainActivity, val ui: HomeState, val scope: CoroutineScope) {
    val snack = SnackbarHostState()
    val drawer = RailDrawer()
    var spec: AnimationSpec<Float> = snap()
    var typed by mutableStateOf(TextFieldValue(""))
    var replyTo by mutableStateOf<ChatMsg?>(null)
    var editing by mutableStateOf<ChatMsg?>(null)
    var pending by mutableStateOf<ChatFiles.Picked?>(null)
    val selected = mutableStateListOf<String>()
    /** Long answers opened with Show more. */
    val expanded = mutableStateMapOf<String, Boolean>()
    /** Chats deleted a moment ago, gone from the lists while Undo is offered. */
    val deleting = mutableStateListOf<String>()
    var renaming by mutableStateOf<ChatSession?>(null)
    var deletingMsg by mutableStateOf<ChatMsg?>(null)
    var viewer by mutableStateOf<ChatMsg?>(null)
    /** A message to scroll to and flash (a quote, the pinned bar, a search hit). */
    var jump by mutableStateOf<String?>(null)
    var search by mutableStateOf("")
    val focus = FocusRequester()
    var wantFocus by mutableStateOf(false)
    /** A voice note being recorded (the mic held). */
    var recording by mutableStateOf<Rec?>(null)

    val demo get() = ui.demo

    fun say(text: String) {
        if (text.isBlank()) return
        scope.launch { snack.showSnackbar(text, withDismissAction = true, duration = SnackbarDuration.Short) }
    }

    fun openDrawer() = scope.launch { drawer.settle(drawer.width, 0f, spec) }

    fun closeDrawer() = scope.launch { drawer.settle(0f, 0f, spec) }

    /** Show a session: the composer's reply, edit and selection are for the one before, so they go. */
    fun open(sid: String) {
        if (ChatStore.current != sid) {
            replyTo = null
            if (editing != null) { editing = null; typed = TextFieldValue("") }
            selected.clear()
        }
        ChatStore.current = sid
        if (ChatStore.visible != null) ChatStore.visible = sid
        Chat.read(a, sid)
        ChatNotes.cancel(a, sid)
    }

    fun newChat() {
        val sid = Chat.newSession(a, null)
        open(sid)
        closeDrawer()
        wantFocus = true
    }

    /** Send what's in the composer: an edit of yours, a file with its caption, or a message. */
    fun send() {
        val text = typed.text.trim()
        val sid = ChatStore.current
        editing?.let { m ->
            if (text.isNotEmpty() && text != m.text) Chat.edit(a, m.id, text)
            editing = null
            typed = TextFieldValue("")
            return
        }
        val re = replyTo?.id.orEmpty()
        pending?.let { p ->
            ChatFiles.send(a, sid, p, text, re)
            pending = null
            replyTo = null
            typed = TextFieldValue("")
            if (demo) demoAnswer(sid, "Demo: here Kurooto would read ${p.name}.")
            return
        }
        if (text.isEmpty()) return
        val id = Chat.newId()
        typed = TextFieldValue("")
        replyTo = null
        val app = a.applicationContext
        // yours shows at once (Chat.IO may be busy with an earlier send); then it goes, in order
        thread {
            val mine = JSONObject().put("id", id).put("from", "you").put("text", text).put("session", sid)
                .put("at", System.currentTimeMillis() / 1000).put("state", "sending").put("re", re)
            Chat.find(app, re)?.let { mine.put("quote", Chat.quoteOf(it)) }
            Chat.put(app, mine)
        }
        Chat.IO.execute { Chat.send(app, sid, id, text, re, null) }
        if (demo) demoAnswer(sid, "Demo: this is where Kurooto's answer comes. Nothing was sent.", id)
    }

    /** Demo: "working…" for a moment, then a made-up answer. */
    private fun demoAnswer(sid: String, text: String, re: String = "") {
        val h = a.h
        h.postDelayed({ Chat.status(JSONObject().put("session", sid).put("state", "working")) }, 500)
        h.postDelayed({
            thread {
                Chat.status(JSONObject().put("session", sid).put("state", "idle"))
                Chat.put(a, JSONObject().put("id", Chat.newId()).put("from", "kurooto").put("text", text).put("session", sid)
                    .put("at", System.currentTimeMillis() / 1000).put("re", re))
                if (ChatStore.current == sid) Chat.read(a, sid)
            }
        }, 2600)
    }

    fun resend(m: ChatMsg) {
        if (m.file != null) { ChatFiles.resend(a, m); return }
        val app = a.applicationContext
        Chat.IO.execute { Chat.send(app, m.session, m.id, m.text, m.re, null) }
    }

    fun reply(m: ChatMsg) {
        editing = null
        replyTo = m
        wantFocus = true
    }

    fun edit(m: ChatMsg) {
        replyTo = null
        editing = m
        typed = TextFieldValue(m.text, TextRange(m.text.length))
        wantFocus = true
    }

    fun copy(text: String) {
        (a.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("message", text))
        if (android.os.Build.VERSION.SDK_INT < 33) say("Copied.") // Android 13+ says so itself
    }

    fun share(text: String) {
        a.launch(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text), null))
    }

    /** Copy or share the selected messages together, oldest first, each "Name: text". */
    fun selectedText(): String {
        val ids = selected.toSet()
        val name = Prefs.assistant(a)
        return ChatStore.snap.threads[ChatStore.current].orEmpty().filter { it.id in ids }
            .joinToString("\n\n") { (if (it.mine) "You" else name) + ": " + ChatRules.plain(it.text).ifEmpty { it.file?.name.orEmpty() } }
    }

    /** Delete a chat, with Undo for a few seconds before it goes everywhere. */
    fun deleteChat(s: ChatSession) {
        if (s.main) return
        deleting.add(s.id)
        if (ChatStore.current == s.id) open(Chat.MAIN)
        scope.launch {
            val r = snack.showSnackbar("Deleted ${s.title}", actionLabel = "Undo", duration = SnackbarDuration.Short)
            deleting.remove(s.id)
            if (r != SnackbarResult.ActionPerformed) thread { Chat.deleteSession(a, s.id) }
        }
    }

    fun tap(m: ChatMsg, n: Int, b: ChatButton, busy: (Boolean) -> Unit) {
        if (b.url.startsWith("https://")) {
            a.launch(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(b.url)))
            return
        }
        if (demo) { say("Demo: nothing was sent."); return }
        busy(true)
        thread {
            val s = Chat.tap(a, m.id, n, b.label)
            a.h.post {
                busy(false)
                if (!s.ok || s.queued) say(if (s.queued) "Tapped. It waits on your call line for your computer." else s.note)
            }
        }
    }

    /** The call button: a call line link, then the call (as Today's Call did). */
    fun call() {
        if (demo) { say("Demo: there's no call line to call."); return }
        a.requestCall()
    }
}

/** Where the pane is in the activity's life: while it's on screen and resumed, it listens to the store, catches up
 *  with the call line, marks the open chat read and keeps its notification away. Also opens a chat a notification,
 *  the Talk widget or bedside mode asked for (ChatActivity's extras on the main screen). */
@Composable
private fun ChatLife(a: MainActivity, ui: HomeState, cu: ChatUi) {
    // demo: the made-up chats in memory; never the real store's
    if (ui.demo && Chat.demo == null && ChatDemo.ON) {
        Chat.demo = ChatDemo.store()
        Chat.working[ChatDemo.FOURIER] = System.currentTimeMillis()
        ChatStore.current = ChatDemo.FOURIER
    } else if (!ui.demo && Chat.demo != null) {
        Chat.demo = null
        Chat.working.clear()
        ChatStore.current = Chat.MAIN
    }
    DisposableEffect(a, ui.demo) {
        val listener = Runnable { ChatStore.reload(a) }
        var resumed = false
        val say = Chat.Say { t -> a.h.post { cu.say(t) } }
        fun up() {
            resumed = true
            Chat.listener = listener
            Chat.say = say
            ChatStore.visible = ChatStore.current
            ChatStore.reload(a)
            ChatNotes.cancel(a, ChatStore.current)
            Chat.read(a, ChatStore.current)
            if (!ui.demo && Prefs.paired(a)) {
                thread {
                    val ok = Chat.sync(a)
                    if (!ok) a.h.post { cu.say("Couldn't reach your call line. Is this phone online?") }
                    else if (Chat.sessions(Chat.load(a)).length() <= 1) Chat.askSessions(a) // the computer's list, once
                }
            }
        }
        fun down() {
            resumed = false
            if (Chat.listener === listener) Chat.listener = null
            if (Chat.say === say) Chat.say = null
            ChatStore.visible = null
        }
        val obs = LifecycleEventObserver { _, e ->
            when (e) {
                Lifecycle.Event.ON_RESUME -> up()
                Lifecycle.Event.ON_PAUSE -> down()
                else -> {}
            }
        }
        a.lifecycle.addObserver(obs) // brought up to where the activity is: ON_RESUME now if it's resumed
        onDispose {
            a.lifecycle.removeObserver(obs)
            if (resumed) down()
        }
    }
    // a chat asked for from outside: now (the intent that started the screen) or later (a new one)
    LaunchedEffect(a) { ChatOpen.take(a, ui, a.intent) }
    LaunchedEffect(ChatOpen.wanted) {
        val w = ChatOpen.wanted ?: return@LaunchedEffect
        ChatOpen.wanted = null
        cu.open(w.first)
        if (cu.drawer.pos > 0f) cu.closeDrawer()
        if (w.second) cu.wantFocus = true
    }
    // the Chat badge in the navigation: every session's unread messages
    val unread = ChatStore.snap.sessions.sumOf { it.unread }
    LaunchedEffect(unread) { ui.unread = unread }
    // a new message in the chat on screen: read
    val count = ChatStore.snap.threads[ChatStore.current]?.size ?: 0
    LaunchedEffect(ChatStore.current, count) {
        if (ChatStore.visible != null) {
            ChatStore.visible = ChatStore.current
            Chat.read(a, ChatStore.current)
        }
    }
    // what a call (the top bar's Call) says goes in a snackbar here
    LaunchedEffect(ui.status) {
        if (ui.status !== ChatOpen.lastSaid && ui.status.tone != Said.OK) cu.say(ui.status.text)
        ChatOpen.lastSaid = ui.status
    }
}

/** A chat asked for by an intent (ChatActivity's extras): the main screen comes to Chat and opens it. The listener
 *  stays for the activity's life (one per activity), so it works while another pane shows. */
object ChatOpen {
    var wanted by mutableStateOf<Pair<String, Boolean>?>(null)
    /** The main screen's last status line already shown here (so coming back to Chat doesn't say it again). */
    var lastSaid: Said? = null
    private val listening = WeakHashMap<MainActivity, Boolean>()

    fun take(a: MainActivity, ui: HomeState, i: Intent?) {
        if (listening[a] == null) {
            listening[a] = true
            a.addOnNewIntentListener(Consumer { n -> take(a, ui, n) })
        }
        val sid = i?.getStringExtra(ChatActivity.OPEN) ?: return
        val type = i.getBooleanExtra(ChatActivity.TYPE, false)
        i.removeExtra(ChatActivity.OPEN)
        ui.pane = Pane.CHAT
        wanted = (if (ChatRules.isSession(sid)) sid else Chat.MAIN) to type
    }
}

/** The pane's dialogs: rename a chat, delete a message. */
@Composable
private fun ChatDialogs(cu: ChatUi) {
    cu.renaming?.let { s ->
        var name by remember(s.id) { mutableStateOf(TextFieldValue(s.title, TextRange(0, s.title.length))) }
        val fr = remember { FocusRequester() }
        LaunchedEffect(s.id) { fr.requestFocus() }
        AlertDialog(
            onDismissRequest = { cu.renaming = null },
            title = { Text("Rename chat") },
            text = {
                OutlinedTextField(
                    name, { name = it }, singleLine = true, shape = MaterialTheme.shapes.large,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    modifier = Modifier.fillMaxWidth().focusRequester(fr),
                )
            },
            confirmButton = {
                TextButton({
                    val t = name.text.trim()
                    if (t.isNotEmpty()) thread { Chat.renameSession(cu.a, s.id, t.take(80)) }
                    cu.renaming = null
                }) { Text("Rename") }
            },
            dismissButton = { TextButton({ cu.renaming = null }) { Text("Cancel") } },
        )
    }
    cu.deletingMsg?.let { m ->
        AlertDialog(
            onDismissRequest = { cu.deletingMsg = null },
            title = { Text("Delete message?") },
            text = {
                Text(
                    if (m.mine) "Delete it everywhere (your computer and your other phones too), or only on this phone."
                    else "It goes from this phone; your computer keeps its copy.",
                )
            },
            confirmButton = {
                Column(horizontalAlignment = Alignment.End) {
                    if (m.mine) TextButton({ thread { Chat.deleteMessage(cu.a, m.id, true) }; cu.deletingMsg = null }) { Text("Delete everywhere") }
                    TextButton({ thread { Chat.deleteMessage(cu.a, m.id, false) }; cu.deletingMsg = null }) { Text("Delete on this phone") }
                    TextButton({ cu.deletingMsg = null }) { Text("Cancel") }
                }
            },
        )
    }
}
