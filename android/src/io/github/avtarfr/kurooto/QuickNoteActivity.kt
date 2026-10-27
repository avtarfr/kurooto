package io.github.avtarfr.kurooto

import android.content.Intent
import android.os.Bundle
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import java.io.ByteArrayInputStream
import kotlin.concurrent.thread

/**
 * Quick note: a small box to type a note into, from the launcher shortcut (long-press the app's icon, Android 7.1+) or
 * the Quick Settings tile (NoteTile, Android 7+). Save sends it as quick-note.md to your computer's notes inbox the way
 * Share to Kurooto does (Line.upload, this phone's key); with your computer off it waits on your call line (the phone
 * outbox) and goes to the inbox when the computer is back. A note that couldn't be sent stays in the box (and is kept
 * if you close it) until it goes. 0.8.10 (the Rail design): a floating sheet with a pencil in a clover, a large rounded
 * box, Cancel and Save at the foot next to how it went. Dev builds: the `demo` extra shows it paired and sends nothing.
 */
class QuickNoteActivity : SheetActivity() {
    private var typed by mutableStateOf("")
    private var busy by mutableStateOf(false)
    private var said by mutableStateOf<Said?>(null)
    private var sent = false
    private var demo = false

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        demo = Demo.ON && intent.getBooleanExtra("demo", false)
        if (!demo) typed = Prefs.noteDraft(this) ?: ""
        val paired = demo || Prefs.paired(this)
        val name = Prefs.assistant(this)
        sheet {
            SheetHeader("Quick note", "To your notes inbox on your computer") {
                IconBadge(MaterialShapes.Clover4Leaf, R.drawable.ic_note, tone = 2, size = 48)
            }
            if (!paired) {
                SaidLine(Said("Pair this phone with your computer first.", Said.BAD))
                SheetButton("Open Kurooto") {
                    startActivity(Intent(this@QuickNoteActivity, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    finish()
                }
                return@sheet
            }
            val focus = remember { FocusRequester() }
            KField(
                value = typed,
                onValueChange = { typed = it },
                placeholder = "Your note",
                enabled = !busy,
                minLines = 4,
                maxLines = 10,
                modifier = Modifier.focusRequester(focus),
            )
            LaunchedEffect(Unit) { focus.requestFocus() }
            Dim("With Chat on, $name files it where it belongs.")
            SheetFoot(said) {
                TextButton({ finish() }, shapes = ButtonDefaults.shapes()) { Text("Cancel") }
                Button({ save() }, enabled = !busy && typed.isNotBlank(), shapes = ButtonDefaults.shapes()) { Text("Save to notes") }
            }
        }
    }

    override fun onPause() {
        // closed before it went (Cancel, Back, Home): keep it for next time
        if (!demo && Prefs.paired(this) && !sent) Prefs.setNoteDraft(this, typed)
        super.onPause()
    }

    private fun save() {
        val text = typed.trim()
        if (text.isEmpty()) return
        if (demo) {
            said = Said("Demo: nothing was sent.")
            return
        }
        busy = true
        said = Said("Sending to ${Prefs.assistant(this)}…")
        val body = (text + "\n").toByteArray(Crypto.UTF8)
        thread {
            val r = Line.upload(this, "quick-note.md", ByteArrayInputStream(body), "")
            h.post {
                if (r == Line.NOT_SENT) {
                    said = Said("Not sent: is this phone online? Your call line may also be full while your computer is off. The note stays here.", Said.BAD)
                    busy = false
                    return@post
                }
                sent = true
                Prefs.setNoteDraft(this, "")
                said = Said(
                    if (r == Line.WAITING) "Your computer is off: the note waits on your call line and goes to your notes inbox when it's back."
                    else "Saved to your notes inbox.",
                    Said.OK,
                )
                h.postDelayed({ finish() }, if (r == Line.WAITING) 2500L else 1200L)
            }
        }
    }
}
