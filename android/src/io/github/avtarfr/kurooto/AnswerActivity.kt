package io.github.avtarfr.kurooto

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardCapitalization
import org.json.JSONObject
import kotlin.concurrent.thread

/**
 * A question, approval or message from Kurooto, with every way to answer it: all the choices, a box to type in, the
 * message's buttons, Later, Dismiss (0.7.6: a floating Compose sheet; before, framework views). Opened by tapping its
 * notification (and by Reply on Android 6).
 */
class AnswerActivity : SheetActivity() {
    private var sending by mutableStateOf(false)
    private var said by mutableStateOf<Said?>(null)

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val item = try { JSONObject(intent.getStringExtra("item") ?: "") } catch (e: Exception) { finish(); return }
        sheet {
            val choices = item.optJSONArray("choices")
            val buttons = item.optJSONArray("buttons")
            var typed by remember { mutableStateOf("") }
            SheetTitle(item.optString("title", Prefs.assistant(this@AnswerActivity)))
            SheetText(Inbox.text(item))
            for (i in 0 until (choices?.length() ?: 0)) {
                val c = choices!!.optString(i)
                SheetButton(c, enabled = !sending) { send(item, field("answer", c)) }
            }
            for (i in 0 until (buttons?.length() ?: 0)) {
                val x = buttons!!.optJSONObject(i) ?: continue
                val url = x.optString("url")
                SheetTonal(x.optString("label"), enabled = !sending) {
                    if (url.startsWith("https://")) {
                        try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } catch (_: Exception) {}
                    } else {
                        send(item, field("button", i))
                    }
                }
            }
            if (item.optBoolean("reply")) {
                OutlinedTextField(
                    value = typed, onValueChange = { typed = it }, enabled = !sending, minLines = 2,
                    label = { Text(if ((choices?.length() ?: 0) > 0) "Or type an answer" else "Your answer") },
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    modifier = Modifier.fillMaxWidth(),
                )
                SheetButton("Send", enabled = !sending && typed.isNotBlank()) { send(item, field("answer", typed.trim())) }
            }
            if (item.optBoolean("later")) SheetFlat("Later", enabled = !sending) { send(item, field("answer", "later")) }
            else SheetFlat("Dismiss", enabled = !sending) { send(item, field("dismiss", true)) }
            SaidLine(said)
        }
    }

    private fun field(k: String, v: Any): JSONObject = try { JSONObject().put(k, v) } catch (e: Exception) { JSONObject() }

    private fun send(item: JSONObject, fields: JSONObject) {
        sending = true
        said = Said("Sending…")
        val id = item.optString("id")
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
