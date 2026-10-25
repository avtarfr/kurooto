package io.github.avtarfr.kurooto

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Parcelable
import android.provider.OpenableColumns
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.LoadingIndicator
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.io.ByteArrayInputStream
import kotlin.concurrent.thread

/**
 * "Share to Kurooto": files, photos, links and text from any app go to your computer's notes inbox (through your call
 * line). With your computer off, the call line keeps them (up to 20 MB) until it's back. With Chat on, the AI files
 * them and tells you where (in the app's chat, or on Telegram), and you can ask about them in the chat. (0.7.6: a
 * floating Compose sheet.)
 */
class ShareActivity : SheetActivity() {
    private var said by mutableStateOf(Said(""))
    private var working by mutableStateOf(true)

    @OptIn(ExperimentalMaterial3ExpressiveApi::class)
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        said = Said("Sending to ${Prefs.assistant(this)}…")
        sheet {
            SheetTitle("Share to ${Prefs.assistant(this@ShareActivity)}")
            if (working) LoadingIndicator()
            SaidLine(said)
        }
        if (!Prefs.paired(this)) { done("Pair this phone first: open the Kurooto app.", false); return }

        val text = intent.getStringExtra(Intent.EXTRA_TEXT)
        val subject = intent.getStringExtra(Intent.EXTRA_SUBJECT)
        val uris = streams(intent)
        val note = ((subject?.let { "$it " } ?: "") + (text ?: "")).trim()
        thread {
            var ok = 0
            var waiting = 0
            var total = uris.size
            if (uris.isEmpty()) {
                total = 1
                val r = if (note.isEmpty()) Line.NOT_SENT else Line.upload(this, "shared-text.txt", ByteArrayInputStream(note.toByteArray(Crypto.UTF8)), "")
                if (r != Line.NOT_SENT) ok++
                if (r == Line.WAITING) waiting++
            } else {
                for (u in uris) {
                    val name = nameOf(u)
                    h.post { said = Said("Uploading $name…") }
                    try {
                        val s = contentResolver.openInputStream(u)
                        val r = if (s == null) Line.NOT_SENT else Line.upload(this, name, s, note)
                        if (r != Line.NOT_SENT) ok++
                        if (r == Line.WAITING) waiting++
                    } catch (_: Exception) {}
                }
            }
            done(
                when {
                    ok == total && waiting > 0 -> "Your computer is off: it waits on your call line and goes to your notes inbox when the computer is back."
                    ok == total -> "Sent. It's in your notes inbox; with Chat on, the AI files it and tells you where. Ask about it in Chat (\"summarise what I just sent\")."
                    ok == 0 -> "Not sent: is this phone online? Your call line may also be full while your computer is off."
                    else -> "Sent $ok of $total."
                },
                ok == total,
            )
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

    private fun nameOf(u: Uri): String {
        try {
            contentResolver.query(u, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) return c.getString(0)
            }
        } catch (_: Exception) {}
        return u.lastPathSegment ?: "shared"
    }
}
