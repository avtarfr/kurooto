package io.github.avtarfr.kurooto

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Parcelable
import android.provider.OpenableColumns
import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LoadingIndicator
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Where a share goes. Today there's one: [NotesInbox], your computer's notes inbox through the call line. The hook for
 * sharing into a chat session later: a second sink (it uploads the same way, then sends a chat message whose `file` names
 * the upload, with the session's id) and [ShareActivity.sink] choosing it, e.g. from an extra the chat's own share sheet
 * sets. The sheet shows the sink's [label] and reports each item with what [send] answers (Line.NOT_SENT, WAITING, SENT).
 */
interface ShareSink {
    val label: String

    fun send(c: Context, name: String, data: InputStream, note: String): Int
}

/** Your computer's notes inbox (Line.upload, in parts, this phone's key; the call line keeps it while the computer is off). */
object NotesInbox : ShareSink {
    override val label = "To your notes inbox"

    override fun send(c: Context, name: String, data: InputStream, note: String): Int = Line.upload(c, name, data, note)
}

/** Dev builds' `demo` extra: nothing leaves the phone; each item takes a moment and is "sent". */
private object DemoSink : ShareSink {
    override val label = "Demo: nothing is sent"

    override fun send(c: Context, name: String, data: InputStream, note: String): Int {
        try { data.close() } catch (_: Exception) {}
        Thread.sleep(900)
        return Line.SENT
    }
}

/**
 * "Share to Kurooto": files, photos, links and text from any app go to your computer's notes inbox (through your call
 * line). With your computer off, the call line keeps them (up to 20 MB) until it's back. With Chat on, the AI files
 * them and tells you where (in the app's chat, or on Telegram), and you can ask about them in the chat. 0.8.10 (the
 * Rail design): a floating sheet that lists what's going, each with its kind as a small tile (PDF, PNG, LINK...), its
 * size, and how it's doing (a loading shape, then a tick, a clock while it waits for your computer, or a warning).
 */
class ShareActivity : SheetActivity() {
    private var said by mutableStateOf(Said(""))
    private var working by mutableStateOf(true)
    private val items = mutableStateListOf<Shared>()

    /** One thing being shared: its name, kind (the tile's word), size (-1 unknown) and state. */
    private data class Shared(val name: String, val kind: String, val size: Long, val state: Int = WAITING_TO_GO)

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val demo = Demo.ON && intent.getBooleanExtra("demo", false)
        val sink = if (demo) DemoSink else sink(intent)
        val name = Prefs.assistant(this)
        said = Said("Sending to $name…")
        sheet {
            SheetHeader("Share to $name", sink.label) {
                IconBadge(MaterialShapes.Sunny, R.drawable.ic_sheet_share, tone = 0, size = 48)
            }
            if (items.isEmpty() && working) LoadingIndicator(Modifier.align(Alignment.CenterHorizontally))
            for (it in items) SharedRow(it)
            SheetFoot(said) {
                if (!working) TextButton({ finish() }, shapes = ButtonDefaults.shapes()) { Text("Close") }
            }
        }
        if (!demo && !Prefs.paired(this)) { done("Pair this phone first: open the Kurooto app.", false); return }

        val text = intent.getStringExtra(Intent.EXTRA_TEXT)
        val subject = intent.getStringExtra(Intent.EXTRA_SUBJECT)
        val uris = streams(intent)
        val note = ((subject?.let { "$it " } ?: "") + (text ?: "")).trim()
        thread {
            // what's going, with names and sizes (the content resolver's queries, off the main thread)
            val list = ArrayList<Pair<Shared, () -> InputStream?>>()
            if (uris.isEmpty()) {
                if (note.isNotEmpty()) {
                    val bytes = note.toByteArray(Crypto.UTF8)
                    val kind = if (note.startsWith("http://") || note.startsWith("https://")) "LINK" else "TEXT"
                    list.add(Shared("shared-text.txt", kind, bytes.size.toLong()) to { ByteArrayInputStream(bytes) })
                } else if (demo) {
                    for ((n, s) in DEMO_ITEMS) list.add(Shared(n, kindOf(n), s) to { ByteArrayInputStream(ByteArray(0)) })
                }
            } else {
                for (u in uris) {
                    val (n, s) = describe(u)
                    list.add(Shared(n, kindOf(n), s) to { contentResolver.openInputStream(u) })
                }
            }
            h.post { items.addAll(list.map { it.first }) }
            if (list.isEmpty()) {
                done("Not sent: there was nothing to send.", false)
                return@thread
            }
            var ok = 0
            var waiting = 0
            for ((i, p) in list.withIndex()) {
                h.post { mark(i, GOING) }
                val r = try {
                    val s = p.second()
                    if (s == null) Line.NOT_SENT else sink.send(this, p.first.name, s, if (uris.isEmpty()) "" else note)
                } catch (_: Exception) {
                    Line.NOT_SENT
                }
                if (r != Line.NOT_SENT) ok++
                if (r == Line.WAITING) waiting++
                h.post { mark(i, r) }
            }
            val total = list.size
            done(
                when {
                    demo -> "Demo: nothing was sent."
                    ok == total && waiting > 0 -> "Your computer is off: it waits on your call line and goes to your notes inbox when the computer is back."
                    ok == total -> "Sent. It's in your notes inbox; with Chat on, the AI files it and tells you where. Ask about it in Chat (\"summarise what I just sent\")."
                    ok == 0 -> "Not sent: is this phone online? Your call line may also be full while your computer is off."
                    else -> "Sent $ok of $total."
                },
                ok == total,
            )
        }
    }

    /** Where this share goes: the notes inbox (the one place there is; see [ShareSink] for adding a chat session). */
    private fun sink(@Suppress("UNUSED_PARAMETER") i: Intent): ShareSink = NotesInbox

    private fun mark(i: Int, state: Int) {
        if (i in items.indices) items[i] = items[i].copy(state = state)
    }

    @Composable
    private fun SharedRow(s: Shared) {
        val cs = MaterialTheme.colorScheme
        val k = LocalKurooto.current
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            // the kind as a small tile, as the chat shows a file
            Surface(shape = RoundedCornerShape(12.dp), color = cs.primaryContainer, contentColor = cs.onPrimaryContainer, modifier = Modifier.size(width = 42.dp, height = 48.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Text(s.kind, style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.ExtraBold))
                }
            }
            Column(Modifier.weight(1f)) {
                Text(s.name, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis, color = cs.onSurface)
                Text(
                    when (s.state) {
                        Line.SENT -> "Sent"
                        Line.WAITING -> "Waits for your computer"
                        Line.NOT_SENT -> "Not sent"
                        else -> if (s.size >= 0) Formatter.formatShortFileSize(this@ShareActivity, s.size) else "…"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (s.state == Line.NOT_SENT) k.bad else cs.onSurfaceVariant,
                )
            }
            Box(Modifier.size(32.dp), contentAlignment = Alignment.Center) {
                when (s.state) {
                    GOING -> LoadingIndicator(Modifier.size(32.dp))
                    Line.SENT -> Icon(painterResource(R.drawable.ic_ok), contentDescription = "sent", tint = k.ok, modifier = Modifier.size(24.dp))
                    Line.WAITING -> Icon(painterResource(R.drawable.ic_sheet_wait), contentDescription = "waiting", tint = cs.primary, modifier = Modifier.size(24.dp))
                    Line.NOT_SENT -> Icon(painterResource(R.drawable.ic_sheet_error), contentDescription = "not sent", tint = k.bad, modifier = Modifier.size(24.dp))
                }
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun streams(i: Intent): List<Uri> {
        val out = ArrayList<Uri>()
        try {
            if (Intent.ACTION_SEND == i.action) {
                (i.getParcelableExtra<Parcelable>(Intent.EXTRA_STREAM) as? Uri)?.let { out.add(it) }
            } else if (Intent.ACTION_SEND_MULTIPLE == i.action) {
                i.getParcelableArrayListExtra<Parcelable>(Intent.EXTRA_STREAM)?.forEach { if (it is Uri) out.add(it) }
            }
        } catch (_: Exception) {}
        return out
    }

    private fun done(text: String, worked: Boolean) {
        h.post {
            said = Said(text, if (worked) Said.OK else Said.BAD)
            working = false
            h.postDelayed({ finish() }, 3000)
        }
    }

    /** A shared item's name and size (-1 when the app sharing it doesn't say). */
    private fun describe(u: Uri): Pair<String, Long> {
        try {
            contentResolver.query(u, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    val n = c.getString(0) ?: u.lastPathSegment ?: "shared"
                    return n to (if (c.isNull(1)) -1L else c.getLong(1))
                }
            }
        } catch (_: Exception) {}
        return (u.lastPathSegment ?: "shared") to -1L
    }

    companion object {
        private const val WAITING_TO_GO = -1
        private const val GOING = -2

        /** The tile's word: the name's extension (PDF, PNG...), at most four letters, else FILE. */
        private fun kindOf(name: String): String {
            val ext = name.substringAfterLast('.', "").uppercase(Locale.ROOT)
            return if (ext.isNotEmpty() && ext.length <= 4 && ext.all { it.isLetterOrDigit() }) ext else "FILE"
        }

        /** Made-up items for the demo extra when nothing was shared (names and sizes only). */
        private val DEMO_ITEMS = listOf("problem-set-4.pdf" to 412_000L, "lab-plot.png" to 1_830_000L, "reading-list.md" to 2_400L)
    }
}
