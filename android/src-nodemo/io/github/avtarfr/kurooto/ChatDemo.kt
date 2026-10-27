package io.github.avtarfr.kurooto

import org.json.JSONObject

/** Release builds: no made-up chats (debug and dev builds have them in src-demo). */
object ChatDemo {
    const val ON = false
    const val FOURIER = ""

    fun store() = JSONObject()
}
