package io.github.avtarfr.kurooto

import org.json.JSONArray
import org.json.JSONObject

/**
 * Made-up chats for looking at the Chat pane without pairing (debug and dev builds, `--ez demo true`; release builds
 * have the empty one in src-nodemo): Kurooto's own chat with a reminder and its buttons, a chat with a PDF, a photo, a
 * reply and a pinned message whose AI request is still running ("working"), a long formatted answer, a photo from
 * Kurooto, and two archived chats. Kept in memory (Chat.demo); nothing is sent anywhere.
 */
object ChatDemo {
    const val ON = true
    const val FOURIER = "f0a1b2c3d4e5f607"

    fun store(): JSONObject {
        val now = System.currentTimeMillis() / 1000
        val msgs = JSONArray()
        var ln = 0L
        fun m(id: String, session: String, from: String, text: String, ago: Long, extra: JSONObject.() -> Unit = {}) {
            val o = JSONObject().put("id", id).put("session", session).put("from", from).put("text", text).put("at", now - ago)
                .put("buttons", JSONArray()).put("ln", ++ln).put("state", "")
            o.extra()
            msgs.put(o)
        }
        fun file(name: String, mime: String, size: Long) = JSONObject().put("name", name).put("mime", mime).put("size", size).put("url", "demo:$name")
        fun buttons(vararg l: String) = JSONArray().apply { l.forEach { put(JSONObject().put("label", it)) } }

        val thesis = "a1b2c3d4e5f60718"
        val trip = "b2c3d4e5f6071829"
        val lab = "c3d4e5f60718293a"
        val reading = "d4e5f60718293a4b"
        val old1 = "e5f60718293a4b5c"
        val old2 = "f60718293a4b5c6d"

        m("0000000000000a01", "main", "kurooto", "Good morning. Today: Linear algebra at 09:30, the study group at 16:30.", 5 * 3600)
        m("0000000000000a02", "main", "kurooto", "Reminder: **Problem sheet 4** is due Thursday 17:00.", 13 * 60) {
            put("buttons", buttons("Done", "Snooze 1h"))
        }
        m("0000000000000a03", "main", "kurooto", "Your computer finished the backup.", 12 * 60)

        m("0000000000000b01", reading, "you", "add the two papers on stochastic forcing to my reading list", 3 * 86400)
        m("0000000000000b02", lab, "you", "can you make the figure for the pendulum data?", 4 * 86400 + 600)
        m("0000000000000b03", lab, "kurooto", "", 4 * 86400) { put("file", file("pendulum-plot.jpg", "image/jpeg", 186_000)) }
        m("0000000000000b04", trip, "you", "what does the trip come to for three?", 86400 + 1200)
        m("0000000000000b05", trip, "kurooto", "The total comes to **6,840** for three: 2,280 each.", 86400 + 1100)
        m("0000000000000b06", old1, "kurooto", "Here are the notes from last term.", 40 * 86400)
        m("0000000000000b07", old2, "kurooto", "The exam timetable is out.", 50 * 86400)

        m("0000000000000c01", thesis, "you", "help me outline my thesis on stochastic parameterisation", 3 * 3600)
        m("0000000000000c02", thesis, "kurooto", """
            Here's a five-part outline:

            1. **Introduction**: why subgrid processes matter, and what *stochastic* adds.
            2. **The model**: the two-scale system, its parameters and the truth runs.
            3. **Methods**: the deterministic baseline, then the stochastic schemes (AR(1) noise, `sigma` fitted from data).
            4. **Results**: forecast skill, the spread–error relation, the long-run statistics.
            5. **Discussion**: limits, and what the next step would be.

            Key references to start with:
            - the original two-scale paper
            - a review of stochastic parameterisation

            ```
            outline/
              01-intro.tex
              02-model.tex
            ```
            Want me to draft the introduction next? See https://example.org/thesis-guide for the department's rules.
        """.trimIndent(), 3 * 3600 - 120)

        m("0000000000000d01", FOURIER, "you", "Q3 and Q5, I'm stuck on both", 82 * 60) { put("file", file("fourier-sheet-4.pdf", "application/pdf", 412 * 1024)) }
        m("0000000000000d02", FOURIER, "kurooto", "Q3: the partial sums overshoot each jump by about 9%; more terms make it *narrower*, not smaller. " +
            "That's the Gibbs phenomenon: near a jump discontinuity, the Fourier series converges pointwise but not uniformly, " +
            "and the overshoot tends to about 8.95% of the jump however many terms you take. The width of the overshoot shrinks like 1/N, " +
            "so the area under it goes to zero, which is why the series still converges in the mean-square sense. " +
            "For the sheet, show this by writing the partial sum as a convolution with the Dirichlet kernel, then evaluate it at x = π/N.", 81 * 60)
        m("0000000000000d03", FOURIER, "you", "my lab plot, same thing?", 79 * 60) { put("file", file("lab-plot.jpg", "image/jpeg", 240_000)) }
        m("0000000000000d04", FOURIER, "kurooto", "Yes. Those edge ripples are it; N = 15 peaks near 1.18.", 78 * 60) {
            put("re", "0000000000000d03")
            put("quote", JSONObject().put("id", "0000000000000d03").put("from", "you").put("text", "Photo · my lab plot, same thing?"))
        }
        m("0000000000000d05", FOURIER, "kurooto", "Sheet 4 is due Thursday 17:00", 77 * 60 + 30) { put("pinned", true) }
        m("0000000000000d06", FOURIER, "kurooto", "Q5 is on tonight's list at 21:00.", 77 * 60) { put("buttons", buttons("Done", "Snooze 1h")) }
        m("0000000000000d07", FOURIER, "you", "and Q5 itself? the half-range one", 60)

        fun s(id: String, title: String, ago: Long, pinned: Boolean = false) =
            JSONObject().put("id", id).put("title", title).put("created", now - ago - 3600).put("updated", now - ago).put("pinned", pinned).put("last", "")
        val sessions = JSONArray()
            .put(s("main", "Kurooto", 12 * 60, true))
            .put(s(thesis, "Thesis outline", 3 * 3600 - 120))
            .put(s(FOURIER, "Fourier series doubts", 60))
            .put(s(trip, "Trip budget", 86400 + 1100))
            .put(s(lab, "Lab report figures", 4 * 86400))
            .put(s(reading, "Reading list", 3 * 86400))
            .put(s(old1, "Last term's notes", 40 * 86400))
            .put(s(old2, "Exam timetable", 50 * 86400))
        val commands = JSONArray()
        listOf(
            "help" to "What Kurooto can do", "today" to "Today's plan", "remind" to "A reminder: /remind 18:00 call home",
            "hours" to "Study hours this week", "quiz" to "A quiz from your notes", "note" to "Save a note", "new" to "A new chat",
        ).forEach { (n, h) -> commands.put(JSONObject().put("name", n).put("help", h)) }
        // read up to just before the unread ones: two in Kurooto's chat, one in the thesis chat
        val read = JSONObject().put("main", 1).put(thesis, ln - 9).put(FOURIER, ln).put(trip, ln).put(lab, ln).put(reading, ln)
            .put(old1, ln).put(old2, ln)
        return JSONObject().put("v", 2).put("ln", ln).put("msgs", msgs).put("sessions", sessions).put("commands", commands)
            .put("read", read).put("archived", JSONArray().put(old1).put(old2))
    }
}
