package io.github.avtarfr.kurooto

import android.app.NotificationManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withLink
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import kotlin.concurrent.thread

/**
 * Chat with Kurooto here, like on Telegram: what you type goes through your call line to your computer and is handled
 * like a Telegram message; the answers come back here (and as a notification when this screen isn't open). Buttons under
 * an answer work as on Telegram; Reply under a message that takes one answers it. With your computer off, what you send
 * waits on your call line ("Waiting for your computer") and goes to it when it's back. Without Telegram (0.5.18), this
 * chat is where everything Kurooto says comes; a file comes as a button that opens a link (Google Drive, or a sealed copy
 * on your call line for a day) in the browser. (0.7.6: Compose, Material 3 Expressive: floating bubbles over the sky.)
 */
class ChatActivity : ComponentActivity() {
    private val h = android.os.Handler(android.os.Looper.getMainLooper())
    private val msgs = mutableStateListOf<JSONObject>()
    private var status by mutableStateOf("")
    private var replyTo by mutableStateOf<Pair<String, String>?>(null)

    override fun onCreate(b: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(b)
        if (!Prefs.paired(this)) { startActivity(Intent(this, MainActivity::class.java)); finish(); return }
        val typeNow = intent.getBooleanExtra("type", false) // opened from the Talk widget: straight to typing
        setContent { KurootoTheme { ChatScreen(typeNow) } }
    }

    override fun onResume() {
        super.onResume()
        visible = true
        Chat.listener = Runnable { h.post { render() } }
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).cancel("chat", ID_NOTE)
        render()
        thread {
            val ok = Chat.sync(this)
            h.post { if (!ok) status = "Couldn't reach your call line. Is this phone online?" else render() }
        }
    }

    override fun onPause() {
        visible = false
        Chat.listener = null
        super.onPause()
    }

    /** Read the chat again from what's stored, newest at the bottom. */
    private fun render() {
        status = if ("offline" == Chat.computer) "Your computer is off: what you send waits on your call line and goes to it when it's back." else ""
        val all = Chat.msgs(Chat.load(this))
        val next = (0 until all.length()).mapNotNull { all.optJSONObject(it) }
        msgs.clear()
        msgs.addAll(next)
    }

    private fun send(text: String) {
        val to = replyTo?.first ?: ""
        replyTo = null
        val id = Chat.newId()
        thread { Chat.send(this, id, text, to) }
    }

    private fun resend(m: JSONObject) {
        thread { Chat.send(this, m.optString("id"), m.optString("text"), m.optString("re")) }
    }

    /** The back arrow: back to the main screen (opened from the widget, there's nothing under the chat). */
    private fun up() {
        if (isTaskRoot) startActivity(Intent(this, MainActivity::class.java))
        finish()
    }

    @Composable
    private fun ChatScreen(typeNow: Boolean) {
        val cs = MaterialTheme.colorScheme
        val list = rememberLazyListState()
        var typed by remember { mutableStateOf("") }
        val focus = remember { FocusRequester() }
        LaunchedEffect(msgs.size) { if (msgs.isNotEmpty()) list.scrollToItem(msgs.size - 1) }
        LaunchedEffect(Unit) { if (typeNow) focus.requestFocus() }
        Box(Modifier.fillMaxSize().background(cs.background)) {
            Sky(this@ChatActivity, strength = { 0.35f }, scroll = { 0f }, modifier = Modifier.fillMaxSize())
            Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars.union(WindowInsets.ime)), horizontalAlignment = Alignment.CenterHorizontally) {
                Column(Modifier.widthIn(max = 640.dp).fillMaxWidth().weight(1f)) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        TextButton({ up() }) { Text("‹ Back") }
                        Text("Chat with ${Prefs.assistant(this@ChatActivity)}", style = MaterialTheme.typography.titleLargeEmphasized, color = cs.onBackground)
                    }
                    if (status.isNotEmpty()) Dim(status, Modifier.padding(horizontal = 16.dp))
                    LazyColumn(Modifier.weight(1f).fillMaxWidth(), state = list, verticalArrangement = Arrangement.spacedBy(8.dp), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp)) {
                        items(msgs.toList(), key = { it.optString("id") + it.optString("state") }) { Bubble(it) { text -> focus.requestFocus(); replyTo = it.optString("id") to text } }
                    }
                    replyTo?.let { (_, text) ->
                        Text(
                            "Replying to: " + (if (text.length > 60) text.take(59) + "…" else text) + "  (tap to cancel)",
                            style = MaterialTheme.typography.bodySmall, color = cs.primary,
                            modifier = Modifier.fillMaxWidth().clickable { replyTo = null }.padding(horizontal = 16.dp, vertical = 4.dp),
                        )
                    }
                    Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 12.dp, bottom = 12.dp), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = typed, onValueChange = { typed = it }, maxLines = 5, shape = RoundedCornerShape(28.dp),
                            placeholder = { Text("Message ${Prefs.assistant(this@ChatActivity)}") },
                            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                            modifier = Modifier.weight(1f).focusRequester(focus),
                        )
                        SendButton(enabled = typed.isNotBlank()) { send(typed.trim()); typed = "" }
                    }
                }
            }
        }
    }

    @OptIn(ExperimentalMaterial3ExpressiveApi::class)
    @Composable
    private fun SendButton(enabled: Boolean, onClick: () -> Unit) =
        Button(onClick, enabled = enabled, shapes = ButtonDefaults.shapes(), modifier = Modifier.padding(bottom = 4.dp)) { Text("Send") }

    /** One message: yours on the right in the primary container, Kurooto's on the left on a tinted card. */
    @OptIn(ExperimentalMaterial3ExpressiveApi::class)
    @Composable
    private fun Bubble(m: JSONObject, reply: (String) -> Unit) {
        val cs = MaterialTheme.colorScheme
        val mine = "you" == m.optString("from")
        val state = m.optString("state")
        val k = LocalKurooto.current
        Row(Modifier.fillMaxWidth(), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
            Surface(
                shape = RoundedCornerShape(24.dp),
                color = if (mine) cs.primaryContainer else rowColor(1),
                contentColor = if (mine) cs.onPrimaryContainer else cs.onSurface,
                modifier = Modifier.widthIn(max = 520.dp).then(if ("failed" == state) Modifier.clickable { resend(m) } else Modifier),
            ) {
                Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                    SelectionContainer { Text(linked(m.optString("text", ""), cs.primary), style = MaterialTheme.typography.bodyLarge) }
                    if (mine && state.isNotEmpty()) {
                        Text(
                            when (state) {
                                "sending" -> "Sending…"
                                "waiting" -> "Waiting for your computer"
                                else -> "Not sent: tap to try again" + (if (m.optString("note").isEmpty()) "" else " (${m.optString("note")})")
                            },
                            style = MaterialTheme.typography.labelMedium, color = if ("failed" == state) k.bad else cs.onPrimaryContainer,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                    val bs = m.optJSONArray("buttons")
                    if (!mine) for (i in 0 until (bs?.length() ?: 0)) {
                        val x = bs!!.optJSONObject(i) ?: continue
                        var busy by remember(m.optString("id"), i) { mutableStateOf(false) }
                        FilledTonalButton(
                            onClick = { tap(m, i, x) { busy = it } }, enabled = !busy, shapes = ButtonDefaults.shapes(),
                            modifier = Modifier.padding(top = 8.dp),
                        ) { Text(x.optString("label")) }
                    }
                    if (!mine && m.optBoolean("reply")) {
                        FilledTonalButton({ reply(m.optString("text")) }, shapes = ButtonDefaults.shapes(), modifier = Modifier.padding(top = 8.dp)) { Text("Reply") }
                    }
                }
            }
        }
    }

    private fun tap(m: JSONObject, n: Int, x: JSONObject, busy: (Boolean) -> Unit) {
        val url = x.optString("url")
        if (url.startsWith("https://")) {
            try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } catch (_: Exception) {}
            return
        }
        busy(true)
        thread {
            val s = Chat.tap(this, m.optString("id"), n, x.optString("label"))
            h.post {
                busy(false)
                if (!s.ok || s.queued) status = if (s.queued) "Tapped. It waits on your call line for your computer." else s.note
            }
        }
    }

    /** The text with its web addresses as links (/help's wiki links open). */
    private fun linked(t: String, colour: androidx.compose.ui.graphics.Color) = buildAnnotatedString {
        var at = 0
        for (r in URL.findAll(t)) {
            append(t.substring(at, r.range.first))
            withLink(LinkAnnotation.Url(r.value)) {
                withStyleLink(colour) { append(r.value) }
            }
            at = r.range.last + 1
        }
        append(t.substring(at))
    }

    private inline fun androidx.compose.ui.text.AnnotatedString.Builder.withStyleLink(c: androidx.compose.ui.graphics.Color, block: () -> Unit) {
        pushStyle(SpanStyle(color = c, textDecoration = TextDecoration.Underline))
        try { block() } finally { pop() }
    }

    companion object {
        const val ID_NOTE = 9 // chat notifications (tag "chat")
        @JvmField @Volatile var visible = false
        private val URL = Regex("https?://[^\\s<>\"]+")
    }
}
