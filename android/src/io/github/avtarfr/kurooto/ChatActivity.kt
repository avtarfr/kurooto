package io.github.avtarfr.kurooto

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity

/**
 * The way in to the chat from outside the main screen (0.8.10): the chat's notifications, the Talk widget, bedside mode
 * and older shortcuts open this, and it hands over to the main screen's Chat pane (ChatPane) at once: extra
 * [SESSION] opens that chat, "type" (the Talk widget) puts the cursor in the message box. Since 0.8.10 the chat
 * itself lives in the main screen (it opens on Chat); this keeps every old way in working.
 */
class ChatActivity : ComponentActivity() {
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val sid = intent.getStringExtra(SESSION)?.takeIf { ChatRules.isSession(it) } ?: Chat.MAIN
        startActivity(
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(OPEN, sid)
                .putExtra(TYPE, intent.getBooleanExtra("type", false)),
        )
        finish()
        overridePendingTransition(0, 0)
    }

    companion object {
        const val ID_NOTE = ChatNotes.ID // the chat's notifications (each session under its own tag, ChatNotes.tag)
        /** This chat (a session id). */
        const val SESSION = "session"
        /** On MainActivity: open the Chat pane on this session (read by ChatPane, which also brings Chat to the front). */
        const val OPEN = "chat_open"
        /** On MainActivity: and put the cursor in the message box. */
        const val TYPE = "chat_type"
    }
}
