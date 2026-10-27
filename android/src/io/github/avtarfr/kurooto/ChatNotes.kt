package io.github.avtarfr.kurooto

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Person
import android.app.RemoteInput
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject

/**
 * The chat's notifications (0.8.10): one per session (Messaging style, the session's title; Android 6 gets the newest
 * message as plain text), holding Kurooto's messages you haven't read there, with Reply typed in the notification
 * (Android 7+), Mark read, and the newest message's quick buttons (+1, Done, the snoozes; Buttons) as before. Tapping
 * it opens that chat. None for the chat on screen. Switches: Settings → Chat (ChatPrefs NOTIFY, INLINE_REPLY).
 */
object ChatNotes {
    const val ID = 9 // the chat's notifications (ChatActivity.ID_NOTE), each under its session's tag
    private const val KEY_TEXT = "chat_reply"
    const val REPLY = "io.github.avtarfr.kurooto.CHAT_REPLY"
    const val READ = "io.github.avtarfr.kurooto.CHAT_READ"

    /** "chat" for Kurooto's own session (as before 0.8.10, so its notification is the same one), else "chat:<id>". */
    @JvmStatic
    fun tag(sid: String) = if (sid == Chat.MAIN) "chat" else "chat:$sid"

    private fun nm(c: Context) = c.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    /** A new message of Kurooto's came (ListenService): its session's notification, unless that chat is on screen. */
    @JvmStatic
    fun incoming(c: Context, m: JSONObject) {
        val sid = Chat.sessionOf(m)
        if (ChatStore.visible == sid || !ChatPrefs.on(c, ChatPrefs.NOTIFY)) return
        show(c, sid, quiet = false, said = null)
    }

    /** After a quick button on the notification (ActionReceiver.chatTap through ListenService.chatNote): the
     *  notification again, quietly, saying how it went; `buttons` the ones to offer again (a +1's), or none. */
    @JvmStatic
    fun again(c: Context, msgId: String, said: String, buttons: JSONArray?) {
        val sid = Chat.find(c, msgId)?.let { Chat.sessionOf(it) } ?: Chat.MAIN
        show(c, sid, quiet = true, said = said, buttons = buttons, buttonsOf = msgId)
    }

    /** Take a session's notification down (you opened that chat). */
    @JvmStatic
    fun cancel(c: Context, sid: String) = nm(c).cancel(tag(sid), ID)

    /** Draw a session's notification: its unread messages (and what you replied from the notification since). */
    fun show(c: Context, sid: String, quiet: Boolean, said: String?, buttons: JSONArray? = null, buttonsOf: String? = null) {
        val d = Chat.load(c)
        val readTo = d.optJSONObject("read")?.optLong(sid, 0) ?: 0
        val all = Chat.msgs(d)
        val lines = ArrayList<JSONObject>()
        for (i in 0 until all.length()) {
            val x = all.optJSONObject(i) ?: continue
            if (Chat.sessionOf(x) != sid || x.optLong("ln") <= readTo || x.optBoolean("deleted")) continue
            if (x.optString("from") == "you" && lines.isEmpty()) continue // yours count only after something unread
            lines.add(x)
        }
        val shown = lines.takeLast(7)
        if (shown.isEmpty() && said == null) { cancel(c, sid); return }
        val name = Prefs.assistant(c)
        val title = if (sid == Chat.MAIN) name else Chat.sessionIn(d, sid, false)?.optString("title").orEmpty().ifEmpty { "Chat with $name" }
        val newest = shown.lastOrNull { it.optString("from") != "you" }
        val text = said ?: newest?.let { lineOf(it) } ?: ""
        val flags = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        val code = sid.hashCode()
        val open = Intent(c, ChatActivity::class.java).putExtra(ChatActivity.SESSION, sid).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val b = ListenService.builder(c, ListenService.CH_MSG)
            .setSmallIcon(R.drawable.ic_stat)
            .setContentTitle(title)
            .setContentText(text)
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setOnlyAlertOnce(quiet)
            .setContentIntent(PendingIntent.getActivity(c, code, open, flags))
            .setAutoCancel(true)
            .setShowWhen(true)
        if (Build.VERSION.SDK_INT >= 24) b.setStyle(style(c, title, sid, shown, said, name))
        else b.setStyle(Notification.BigTextStyle().bigText(text))
        // the newest message's quick buttons (or the ones to offer again after a tap)
        val bs = buttons ?: if (buttonsOf == null) newest?.optJSONArray("buttons") else null
        val bsOf = buttonsOf ?: newest?.optString("id").orEmpty()
        val labels = Inbox.labels(bs)
        // at most three actions show: Reply, then the quick buttons, then Mark read if there's room
        val inline = Build.VERSION.SDK_INT >= 24 && ChatPrefs.on(c, ChatPrefs.INLINE_REPLY)
        var room = Buttons.MAX - if (inline) 1 else 0
        var quick = 0
        if (inline) {
            val ri = RemoteInput.Builder(KEY_TEXT).setLabel("Message").build()
            val mutable = PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            val reply = Intent(c, ActionReceiver::class.java).setAction(REPLY).putExtra("session", sid)
                .putExtra("re", newest?.takeIf { it.optBoolean("reply") }?.optString("id").orEmpty())
            val pi = PendingIntent.getBroadcast(c, ("$sid:reply").hashCode(), reply, mutable)
            b.addAction(Notification.Action.Builder(null, "Reply", pi).addRemoteInput(ri).build())
        }
        if (bs != null && Buttons.addDone(labels)) {
            val done = Intent(c, ActionReceiver::class.java).setAction(ActionReceiver.NOTE_DONE).putExtra("tag", tag(sid)).putExtra("id", ID)
            b.addAction(Notification.Action.Builder(null, "Done", PendingIntent.getBroadcast(c, ("$bsOf:done").hashCode(), done, flags)).build())
            room--
            quick++
        }
        if (bs != null) for (i in Buttons.pick(labels, room)) {
            val x = bs.optJSONObject(i) ?: continue
            val tap = Intent(c, ActionReceiver::class.java).setAction(ActionReceiver.CHAT_TAP).putExtra("msg", bsOf)
                .putExtra("n", i).putExtra("label", x.optString("label")).putExtra("buttons", bs.toString())
            b.addAction(Notification.Action.Builder(null, x.optString("label"), PendingIntent.getBroadcast(c, ("$bsOf:t$i").hashCode(), tap, flags)).build())
            quick++
        }
        if (inline && quick < Buttons.MAX - 1) {
            val read = Intent(c, ActionReceiver::class.java).setAction(READ).putExtra("session", sid)
            b.addAction(Notification.Action.Builder(null, "Mark read", PendingIntent.getBroadcast(c, ("$sid:read").hashCode(), read, flags)).build())
        }
        nm(c).notify(tag(sid), ID, b.build())
    }

    private fun lineOf(x: JSONObject): String {
        val t = x.optString("text")
        if (t.isNotBlank()) return ChatRules.plain(t)
        return x.optJSONObject("file")?.let { Chat.fileWord(it) } ?: ""
    }

    @Suppress("DEPRECATION")
    @androidx.annotation.RequiresApi(24)
    private fun style(c: Context, title: String, sid: String, shown: List<JSONObject>, said: String?, name: String): Notification.Style {
        val st: Notification.MessagingStyle
        if (Build.VERSION.SDK_INT >= 28) {
            val me = Person.Builder().setName("You").build()
            val k = Person.Builder().setName(name).setKey("kurooto").setBot(true).build()
            st = Notification.MessagingStyle(me)
            for (x in shown) st.addMessage(Notification.MessagingStyle.Message(lineOf(x), x.optLong("at") * 1000, if (x.optString("from") == "you") null else k))
            if (said != null) st.addMessage(Notification.MessagingStyle.Message(said, System.currentTimeMillis(), k))
        } else {
            st = Notification.MessagingStyle("You")
            for (x in shown) st.addMessage(lineOf(x), x.optLong("at") * 1000, if (x.optString("from") == "you") null else name)
            if (said != null) st.addMessage(said, System.currentTimeMillis(), name)
        }
        if (sid != Chat.MAIN) st.setConversationTitle(title)
        return st
    }

    /** Reply and Mark read on a notification (ActionReceiver hands them here). */
    @JvmStatic
    fun handle(c: Context, i: Intent, pr: BroadcastReceiver.PendingResult) {
        val app = c.applicationContext
        val sid = i.getStringExtra("session")?.takeIf { ChatRules.isSession(it) } ?: Chat.MAIN
        Thread {
            try {
                if (i.action == READ) {
                    Chat.markRead(app, sid)
                    Chat.read(app, sid)
                    cancel(app, sid)
                } else {
                    val text = RemoteInput.getResultsFromIntent(i)?.getCharSequence(KEY_TEXT)?.toString()?.trim().orEmpty()
                    if (text.isEmpty()) { show(app, sid, quiet = true, said = null); return@Thread }
                    val id = Chat.newId()
                    val s = Chat.send(app, sid, id, text, i.getStringExtra("re").orEmpty(), null)
                    // the notification shows your reply (Android wants it drawn again, or it keeps spinning)
                    show(app, sid, quiet = true, said = if (s.ok && !s.queued) null else s.note.ifEmpty { null })
                }
            } finally {
                pr.finish()
            }
        }.start()
    }
}
