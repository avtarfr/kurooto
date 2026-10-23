package io.github.avtarfr.kurooto

import android.content.Intent
import org.json.JSONObject

/** Release builds: no demo (the "demo" extra does nothing) and no sample data. Debug and dev builds have the real
 *  one in src-demo. */
object Demo {
    const val ON = false

    fun today() = JSONObject()

    fun waiting() = emptyList<JSONObject>()

    fun queued() = emptyList<String>()

    fun update(): Pair<String, String>? = null

    fun checks(appInfo: Intent) = emptyList<MainActivity.Check>()
}
