package io.github.avtarfr.kurooto

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import kotlin.concurrent.thread

/**
 * A question, approval or message from Kurooto, with every way to answer it: all the choices, a box to type in, the
 * message's buttons, Later, Dismiss. Opened by tapping its notification (and by Reply on Android 6), and from the
 * waiting list. 0.8.10 (the Rail design): a floating sheet with the assistant's mark, the message as a chat bubble, the
 * choices as filled pills, the message's buttons as tonal ones (a link's with an arrow), the answer box with a round
 * Send, and Later or Dismiss at the foot next to how it went. In dev builds a made-up item ("demo-…") sends nothing.
 */
class AnswerActivity : SheetActivity() {
    private var sending by mutableStateOf(false)
    private var said by mutableStateOf<Said?>(null)

    @OptIn(ExperimentalLayoutApi::class)
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val item = try { JSONObject(intent.getStringExtra("item") ?: "") } catch (e: Exception) { finish(); return }
        val name = Prefs.assistant(this)
        val title = item.optString("title", name).ifBlank { name }
        val choices = item.optJSONArray("choices").let { a -> (0 until (a?.length() ?: 0)).map { a!!.optString(it) } }
        val buttons = item.optJSONArray("buttons").let { a -> (0 until (a?.length() ?: 0)).mapNotNull { a!!.optJSONObject(it)?.let { x -> it to x } } }
        sheet {
            var typed by remember { mutableStateOf("") }
            SheetHeader(title, if (title != name) "From $name" else null) {
                ShapeBadge(MaterialShapes.Cookie9Sided, MaterialTheme.colorScheme.primary, size = 48) {
                    Text(
                        name.take(1).uppercase(),
                        style = MaterialTheme.typography.titleLargeEmphasized,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                }
            }
            SheetBubble(Inbox.text(item))
            if (choices.isNotEmpty()) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (c in choices) {
                        Button({ send(item, field("answer", c)) }, enabled = !sending, shapes = ButtonDefaults.shapes()) { Text(c) }
                    }
                }
            }
            if (buttons.isNotEmpty()) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    for ((i, x) in buttons) {
                        val url = x.optString("url")
                        val link = url.startsWith("https://")
                        FilledTonalButton(
                            {
                                if (link) {
                                    try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } catch (_: Exception) {}
                                } else {
                                    send(item, field("button", i))
                                }
                            },
                            enabled = !sending,
                            shapes = ButtonDefaults.shapes(),
                        ) {
                            Text(x.optString("label"))
                            if (link) Icon(painterResource(R.drawable.ic_sheet_open), contentDescription = "opens a link", modifier = Modifier.padding(start = 6.dp).size(16.dp))
                        }
                    }
                }
            }
            if (item.optBoolean("reply")) {
                KField(
                    value = typed,
                    onValueChange = { typed = it },
                    placeholder = if (choices.isNotEmpty()) "Or type an answer" else "Your answer",
                    enabled = !sending,
                    maxLines = 6,
                    trailing = {
                        RoundAction(R.drawable.ic_sheet_send, "Send", enabled = !sending && typed.isNotBlank()) {
                            send(item, field("answer", typed.trim()))
                        }
                    },
                )
            }
            SheetFoot(said) {
                if (item.optBoolean("later")) {
                    TextButton({ send(item, field("answer", "later")) }, enabled = !sending, shapes = ButtonDefaults.shapes()) { Text("Later") }
                } else {
                    TextButton({ send(item, field("dismiss", true)) }, enabled = !sending, shapes = ButtonDefaults.shapes()) { Text("Dismiss") }
                }
            }
        }
    }

    private fun field(k: String, v: Any): JSONObject = try { JSONObject().put(k, v) } catch (e: Exception) { JSONObject() }

    private fun send(item: JSONObject, fields: JSONObject) {
        val id = item.optString("id")
        if (Demo.ON && id.startsWith("demo-")) { // a made-up item (dev builds): nothing to send it to
            said = Said("Demo: nothing was sent.")
            return
        }
        sending = true
        said = Said("Sending…")
        thread {
            val r = Line.answer(this, id, fields)
            h.post {
                said = Said(r.note, if (r.delivered()) Said.OK else Said.BAD)
                if (r.delivered() || r.gone()) {
                    Inbox.cancel(this, id)
                    h.postDelayed({ finish() }, 1800)
                } else {
                    sending = false
                }
            }
        }
    }
}
