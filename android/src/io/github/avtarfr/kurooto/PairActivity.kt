package io.github.avtarfr.kurooto

import android.content.Intent
import android.os.Bundle
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.LoadingIndicator
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlin.concurrent.thread

/** Opened by the pairing page's "Pair the app" button (kurooto://pair?c=…&u=…): pairs, then starts listening.
 *  (0.7.6: a floating Compose sheet.) */
class PairActivity : SheetActivity() {
    private var said by mutableStateOf(Said("Pairing with your computer…"))
    private var working by mutableStateOf(true)

    @OptIn(ExperimentalMaterial3ExpressiveApi::class)
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        sheet {
            SheetTitle("Pair this phone")
            if (working) LoadingIndicator()
            SaidLine(said)
        }
        val p = Line.parse(intent.dataString)
        if (p == null) {
            said = Said("That pairing link isn't complete. Make a new one on your computer (Phone → Pair a phone).", Said.BAD)
            working = false
            return
        }
        thread {
            val err = Line.claim(this, p)
            h.post {
                if (err != null) {
                    said = Said(err, Said.BAD)
                    working = false
                    return@post
                }
                ListenService.start(this)
                startActivity(
                    Intent(this, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP).putExtra("justPaired", true),
                )
                finish()
            }
        }
    }
}
