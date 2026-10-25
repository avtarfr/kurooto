package io.github.avtarfr.kurooto

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.LoadingIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/**
 * The Inbox tab (0.7.0): what's waiting for you on your call line (/pending), newest first. Check-in and quiz cards
 * are answered right here (InboxCard); questions, approvals and messages open the answer window (AnswerActivity) with
 * every way to answer them. Then what waits for your computer (the phone outbox on the call line), which goes when
 * it's back. The navigation bar's badge counts what waits for you.
 */
@Composable
fun InboxPage(a: MainActivity, ui: HomeState, outer: PaddingValues) {
    val n = ui.waiting?.size
    val sub = when {
        n == null -> "Looking…"
        n == 0 -> "Nothing waiting for you"
        n == 1 -> "1 waiting for you"
        else -> "$n waiting for you"
    }
    TabPage(a, ui, outer, "Inbox", sub) { InboxTab(a, ui) }
}

@Composable
private fun ColumnScope.InboxTab(a: MainActivity, ui: HomeState) {
    val items = ui.waiting
    if (items == null) {
        Box(Modifier.fillMaxWidth().padding(top = 48.dp), contentAlignment = Alignment.Center) { LoadingIndicator() }
        return
    }
    if (ui.waitingFailed) Dim("Couldn't reach your call line just now. Pull down to try again.", Modifier.padding(start = 4.dp, top = 8.dp))
    val cards = items.filter { CardRules.kind(it.optString("card"), Inbox.text(it)).isNotEmpty() }
    val rest = items.filter { CardRules.kind(it.optString("card"), Inbox.text(it)).isEmpty() }
    if (items.isEmpty() && !ui.waitingFailed) {
        // all answered: a soft burst with a tick
        ShapeBadge(
            MaterialShapes.SoftBurst,
            MaterialTheme.colorScheme.tertiaryContainer,
            Modifier.align(Alignment.CenterHorizontally).padding(top = 40.dp),
            size = 120,
        ) {
            Icon(
                painterResource(R.drawable.ic_ok),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onTertiaryContainer,
                modifier = Modifier.size(48.dp),
            )
        }
        Text(
            "Nothing is waiting for you.",
            style = MaterialTheme.typography.titleLargeEmphasized,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(top = 20.dp, bottom = 8.dp),
        )
    }
    if (cards.isNotEmpty()) {
        Heading("Answer here")
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            cards.forEach { InboxCard(a, it) }
        }
    }
    if (rest.isNotEmpty()) {
        Heading("Waiting for you")
        Group(
            rest.map {
                Item(
                    it.optString("title", "Kurooto").ifEmpty { "Kurooto" },
                    Inbox.text(it),
                    onClick = { a.openItem(it) },
                    titleColor = MaterialTheme.colorScheme.primary,
                    subLines = 3,
                    trailing = { Chevron() },
                )
            },
        )
    }
    if (ui.queued.isNotEmpty()) {
        Heading("Waiting for your computer")
        Group(ui.queued.map { Item(it) })
        Footnote("Kept on your call line; they go to your computer when it's back.")
    }
}

/**
 * A check-in or quiz card (0.6.0, Cards; 0.7.0 in Compose): the question, its options as buttons (In 30 min, Not
 * tonight; Forgot / Hard / Good / Easy) and an answer box. They are the same items as the notifications, and an
 * answer goes the same way (Line.answer: sealed, single use), so with your computer asleep it waits in the phone
 * outbox on the call line. A quiz answer's grading comes back as the next card.
 */
object InboxCard {
    /** What you typed and didn't send yet, by item id, so it survives the screen being rebuilt. */
    val drafts = HashMap<String, String>()

    private fun field(k: String, v: Any): JSONObject = JSONObject().put(k, v)

    @Composable
    operator fun invoke(a: MainActivity, it: JSONObject) {
        val id = it.optString("id")
        val text = Inbox.text(it)
        val kind = CardRules.kind(it.optString("card"), text)
        var busy by remember(id) { mutableStateOf(false) }
        var said by remember(id) { mutableStateOf<Said?>(null) }
        var typed by rememberSaveable(id) { mutableStateOf(drafts[id] ?: "") }
        val send = { f: JSONObject ->
            busy = true
            said = Said("Sending…")
            a.answer(id, f) { s, over ->
                said = s
                if (!over) busy = false
            }
        }
        // the options: a question's choices, then the message's buttons (by number: their data stays on your computer)
        val labels = ArrayList<String>()
        val sends = ArrayList<JSONObject>()
        val ch = it.optJSONArray("choices")
        for (i in 0 until (ch?.length() ?: 0)) { labels.add(ch!!.optString(i)); sends.add(field("answer", ch.optString(i))) }
        val bs = it.optJSONArray("buttons")
        for (i in 0 until (bs?.length() ?: 0)) {
            val b = bs!!.optJSONObject(i) ?: continue
            if (b.optString("url").startsWith("https://")) continue // a link: the answer window has it
            labels.add(b.optString("label"))
            sends.add(field("button", i))
        }
        KCard(accent = 2) {
            Text(CardRules.label(kind, text), style = MaterialTheme.typography.titleSmallEmphasized, color = MaterialTheme.colorScheme.primary)
            Text(CardRules.body(kind, text), style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(top = 6.dp))
            val per = CardRules.perRow(labels.toTypedArray())
            labels.indices.chunked(per).forEach { row ->
                Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    row.forEach { i ->
                        FilledTonalButton(
                            onClick = { send(sends[i]) },
                            enabled = !busy,
                            shapes = ButtonDefaults.shapes(),
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
                            modifier = Modifier.weight(1f),
                        ) { Text(labels[i], maxLines = 1, overflow = TextOverflow.Ellipsis) }
                    }
                    repeat(per - row.size) { Spacer(Modifier.weight(1f)) }
                }
            }
            if (it.optBoolean("reply")) {
                OutlinedTextField(
                    value = typed,
                    onValueChange = { v -> typed = v; drafts[id] = v },
                    enabled = !busy,
                    placeholder = { Text(if (labels.isEmpty()) CardRules.hint(kind) else "Or type an answer") },
                    minLines = 2,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    shape = MaterialTheme.shapes.large,
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                )
                Button(
                    onClick = {
                        val t = typed.trim()
                        if (t.isEmpty()) said = Said("Type an answer first.", Said.BAD) else send(field("answer", t))
                    },
                    enabled = !busy,
                    shapes = ButtonDefaults.shapes(),
                    modifier = Modifier.align(Alignment.End).padding(top = 8.dp).heightIn(min = 48.dp),
                ) { Text("Send") }
            }
            SaidLine(said)
        }
    }
}
