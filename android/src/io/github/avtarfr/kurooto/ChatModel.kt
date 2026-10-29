package io.github.avtarfr.kurooto

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import java.util.TimeZone
import java.util.concurrent.Executors

/**
 * What the Chat pane shows (0.8.10), read from Chat's store off the main thread and handed to Compose as plain
 * immutable values: the sessions (with unread counts, "working", archived), each session's messages and the rows of its
 * thread (date separators and grouping worked out here, not while drawing), the slash commands. [ChatStore] is the one
 * place the pane reads; it re-reads when Chat says the store changed.
 */

@Immutable
data class ChatSession(
    val id: String,
    val title: String,
    val last: String,
    val updated: Long,
    val pinned: Boolean,
    val archived: Boolean,
    val unread: Int,
    val working: Boolean,
) {
    val main get() = id == Chat.MAIN
}

@Immutable
data class ChatQuote(val id: String, val from: String, val text: String)

@Immutable
data class ChatFile(val name: String, val size: Long, val mime: String, val url: String, val fid: String, val path: String) {
    val image get() = mime.startsWith("image/")
    val audio get() = mime.startsWith("audio/")
    /** "PDF", "ZIP"...: the badge on a file card. */
    val badge get() = name.substringAfterLast('.', "").uppercase().take(4).ifEmpty { "FILE" }
}

@Immutable
/** A button under one of Kurooto's messages. quiet (0.9.1): feedback (Wrong, Why?, Less of this), shown small, after the
 *  message's own buttons. */
data class ChatButton(val label: String, val url: String, val quiet: Boolean = false)

@Immutable
data class ChatMsg(
    val id: String,
    val session: String,
    val mine: Boolean,
    val text: String,
    val at: Long,
    /** Yours: "sending", "waiting" (on the call line), "failed", or "" (your computer has it). */
    val state: String,
    val note: String,
    val re: String,
    val quote: ChatQuote?,
    val file: ChatFile?,
    val buttons: List<ChatButton>,
    /** Kurooto's message that takes a reply (it goes to the feature that asked). */
    val takesReply: Boolean,
    val edited: Boolean,
    val deleted: Boolean,
    val pinned: Boolean,
    /** Yours, and Kurooto has answered it (the third tick). */
    val answered: Boolean,
)

/** One row of a thread: a message (with whether it starts or ends a group from one sender within a few minutes) or
 *  a date separator. */
@Immutable
sealed class ChatRow(val key: String) {
    class Msg(val m: ChatMsg, val first: Boolean, val last: Boolean) : ChatRow(m.id)
    class Day(val label: String, k: String) : ChatRow("day:$k")
}

@Immutable
data class ChatSnapshot(
    val sessions: List<ChatSession> = emptyList(),
    val threads: Map<String, List<ChatMsg>> = emptyMap(),
    /** Each session's rows, newest first (the thread is a reversed list). */
    val rows: Map<String, List<ChatRow>> = emptyMap(),
    val commands: List<Array<String>> = emptyList(),
    val computer: String = "",
    /** Your computer's chat switches (the "sessions" message): chat_sessions, chat_files_inline, chat_edit; missing
     *  means on (a computer from before says nothing, and the app then offers everything). */
    val switches: Map<String, Boolean> = emptyMap(),
) {
    fun on(key: String) = switches[key] != false
}

/** The Chat pane's state, shared by the pane and the notifications (which session is on screen). */
object ChatStore {
    private val main = Handler(Looper.getMainLooper())
    private val reader = Executors.newSingleThreadExecutor()
    @Volatile private var pending = false

    var snap by mutableStateOf(ChatSnapshot())
        private set
    /** The session on screen. */
    var current by mutableStateOf(Chat.MAIN)
    /** Bumped after each read: a "first load" waits for it. */
    var loads by mutableIntStateOf(0)
        private set
    /** The session the pane shows while it's on screen and resumed (no notification for it); null otherwise. */
    @Volatile @JvmStatic var visible: String? = null

    /** Read the store again (coalesced: many changes at once read it once). */
    fun reload(c: Context) {
        if (pending) return
        pending = true
        val app = c.applicationContext
        reader.execute {
            pending = false
            val s = read(app)
            main.post {
                snap = s
                loads++
            }
        }
    }

    /** The store, worked out for drawing. Off the main thread. */
    fun read(c: Context): ChatSnapshot {
        val d = Chat.load(c)
        val read = d.optJSONObject("read") ?: JSONObject()
        val archived = HashSet<String>()
        d.optJSONArray("archived")?.let { a -> for (i in 0 until a.length()) archived.add(a.optString(i)) }
        val all = Chat.msgs(d)
        val answeredIds = HashSet<String>()
        for (i in 0 until all.length()) {
            val x = all.optJSONObject(i) ?: continue
            if (x.optString("from") != "you") x.optString("re").takeIf { it.isNotEmpty() }?.let { answeredIds.add(it) }
        }
        val by = LinkedHashMap<String, MutableList<ChatMsg>>()
        val unread = HashMap<String, Int>()
        val byId = HashMap<String, ChatMsg>()
        for (i in 0 until all.length()) {
            val x = all.optJSONObject(i) ?: continue
            var m = msg(x, answeredIds)
            val list = by.getOrPut(m.session) { ArrayList() }
            // Kurooto's answer says which message it answers (`re`); quoted only when that one isn't just above
            if (!m.mine && m.quote == null && m.re.isNotEmpty()) {
                val t = byId[m.re]
                if (t != null && list.takeLast(2).none { it.id == t.id }) {
                    m = m.copy(quote = ChatQuote(t.id, if (t.mine) "you" else "kurooto", ChatRules.plain(t.text).ifEmpty { t.file?.name.orEmpty() }.take(200)))
                }
            }
            byId[m.id] = m
            list.add(m)
            if (!m.mine && !m.deleted && x.optLong("ln") > read.optLong(m.session, 0)) unread[m.session] = (unread[m.session] ?: 0) + 1
        }
        val name = Prefs.assistant(c)
        val ss = Chat.sessions(d)
        val seen = HashSet<String>()
        val sessions = ArrayList<ChatSession>()
        fun add(id: String, s: JSONObject?) {
            if (!seen.add(id)) return
            val msgs = by[id]
            val lastMsg = msgs?.lastOrNull()
            var title = s?.optString("title").orEmpty()
            if (id == Chat.MAIN) title = name
            if (title.isEmpty()) title = msgs?.firstOrNull { it.mine && it.text.isNotBlank() }?.let { ChatRules.title(it.text) } ?: "New chat"
            val last = s?.optString("last").orEmpty().ifEmpty { lastMsg?.let { lastLine(it) }.orEmpty() }
            sessions.add(
                ChatSession(
                    id = id, title = title, last = last,
                    updated = maxOf(s?.optLong("updated") ?: 0L, lastMsg?.at ?: 0L),
                    pinned = id == Chat.MAIN || s?.optBoolean("pinned") == true,
                    archived = id != Chat.MAIN && id in archived,
                    unread = unread[id] ?: 0,
                    working = Chat.isWorking(id),
                ),
            )
        }
        add(Chat.MAIN, (0 until ss.length()).map { ss.optJSONObject(it) }.firstOrNull { it?.optString("id") == Chat.MAIN })
        for (i in 0 until ss.length()) ss.optJSONObject(i)?.let { add(it.optString("id"), it) }
        for (id in by.keys) add(id, null) // a session the list hasn't caught up with yet
        // Kurooto first, then pinned, then the newest
        sessions.sortWith(compareBy<ChatSession>({ !it.main }, { !it.pinned }, { -it.updated }))
        val cmds = ArrayList<Array<String>>()
        d.optJSONArray("commands")?.let { a ->
            for (i in 0 until a.length()) a.optJSONObject(i)?.let { cmds.add(arrayOf(it.optString("name"), it.optString("help"))) }
        }
        val tz = TimeZone.getDefault()
        val now = System.currentTimeMillis()
        val rows = by.mapValues { (_, list) -> rowsOf(list, now, tz) }
        val sw = HashMap<String, Boolean>()
        d.optJSONObject("switches")?.let { o -> o.keys().forEach { k -> sw[k] = o.optBoolean(k, true) } }
        return ChatSnapshot(sessions, by, rows, cmds, Chat.computer, sw)
    }

    private fun lastLine(m: ChatMsg): String {
        val t = if (m.deleted) "Deleted" else if (m.text.isNotBlank()) ChatRules.plain(m.text).replace('\n', ' ') else m.file?.let { Chat.fileWord(fileJson(it)) }.orEmpty()
        return if (m.mine && t.isNotEmpty()) "You: $t" else t
    }

    private fun fileJson(f: ChatFile) = JSONObject().put("name", f.name).put("mime", f.mime)

    fun msg(x: JSONObject, answered: Set<String>): ChatMsg {
        val f = x.optJSONObject("file")
        val q = x.optJSONObject("quote")
        val bs = x.optJSONArray("buttons") ?: JSONArray()
        val mine = x.optString("from") == "you"
        return ChatMsg(
            id = x.optString("id"),
            session = Chat.sessionOf(x),
            mine = mine,
            text = x.optString("text"),
            at = x.optLong("at"),
            state = if (mine) x.optString("state") else "",
            note = x.optString("note"),
            re = x.optString("re"),
            quote = q?.let { ChatQuote(it.optString("id"), it.optString("from"), it.optString("text")) },
            file = f?.takeIf { !x.optBoolean("deleted") }?.let {
                ChatFile(it.optString("name", "file"), it.optLong("size"), it.optString("mime", "application/octet-stream"), it.optString("url"),
                    it.optString("fid"), it.optString("path"))
            },
            // the Open button older apps get for a file is the file itself here: hidden
            buttons = (0 until bs.length()).mapNotNull { i -> bs.optJSONObject(i)?.let { ChatButton(it.optString("label"), it.optString("url"), it.optBoolean("quiet")) } }
                .filter { b -> f == null || b.url.isEmpty() || b.url != f.optString("url") },
            takesReply = x.optBoolean("reply"),
            edited = x.optBoolean("edited"),
            deleted = x.optBoolean("deleted"),
            pinned = x.optBoolean("pinned"),
            answered = mine && x.optString("id") in answered,
        )
    }

    /** The thread's rows, newest first: a date separator over each day, and each message knowing whether it starts or
     *  ends a run from one sender (within five minutes), for the bubbles' corners and spacing. */
    fun rowsOf(list: List<ChatMsg>, now: Long, tz: TimeZone): List<ChatRow> {
        val out = ArrayList<ChatRow>(list.size + 8)
        for (i in list.indices) {
            val m = list[i]
            val prev = list.getOrNull(i - 1)
            val next = list.getOrNull(i + 1)
            val newDay = prev == null || !ChatRules.sameDay(prev.at, m.at, tz)
            if (newDay) out.add(ChatRow.Day(ChatRules.day(m.at, now, tz), m.id))
            val first = newDay || prev!!.mine != m.mine || m.at - prev.at > 300
            val last = next == null || next.mine != m.mine || next.at - m.at > 300 || !ChatRules.sameDay(m.at, next.at, tz)
            out.add(ChatRow.Msg(m, first, last))
        }
        out.reverse()
        return out
    }
}

/**
 * The chat's switches on this phone (Settings → Chat, ChatSettings): each feature of the pane can be turned off here,
 * and turning one off stops it at once. Kept in their own preferences file ("chat"), so they never touch the app's
 * other settings. Your computer's own chat switches (sessions, files inline, edit, titles) are on its dashboard.
 */
object ChatPrefs {
    class Switch(val key: String, val title: String, val sub: String, val default: Boolean = true)

    val NOTIFY = Switch("notify", "Message notifications", "A notification per chat for Kurooto's messages, unless that chat is open")
    val INLINE_REPLY = Switch("inline_reply", "Reply from the notification", "Reply and Mark read on a chat's notification")
    val SWIPE_REPLY = Switch("swipe_reply", "Swipe to reply", "Swipe a message right to reply to it")
    val MARKDOWN = Switch("markdown", "Formatting", "Bold, italic, code, lists and links in messages as Kurooto writes them")
    val FOLD = Switch("fold", "Fold long answers", "Long answers show their start and a Show more")
    val AUTO_PHOTOS = Switch("auto_photos", "Load photos by themselves", "Photos in the chat load as they come; off: tap to load")
    val COMMANDS = Switch("commands", "Command list", "Typing / lists Kurooto's commands")
    val ENTER_SENDS = Switch("enter_sends", "Enter sends", "The keyboard's Enter key sends instead of starting a new line", default = false)
    val HAPTICS = Switch("haptics", "Haptics", "A small tick when a swipe reaches reply or a message is held")

    val ALL = listOf(NOTIFY, INLINE_REPLY, SWIPE_REPLY, MARKDOWN, FOLD, AUTO_PHOTOS, COMMANDS, ENTER_SENDS, HAPTICS)

    /** Bumped on every change: what reads it reads the switches again. */
    var rev by mutableIntStateOf(0)
        private set

    private fun sp(c: Context) = c.applicationContext.getSharedPreferences("chat", Context.MODE_PRIVATE)

    @JvmStatic
    fun on(c: Context, s: Switch): Boolean = sp(c).getBoolean(s.key, s.default)

    fun set(c: Context, s: Switch, on: Boolean) {
        sp(c).edit().putBoolean(s.key, on).apply()
        rev++
    }
}
