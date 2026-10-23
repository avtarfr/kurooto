package io.github.avtarfr.kurooto

import android.content.Intent
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Made-up data for looking at the screens without pairing (debug and dev builds only; release builds have the empty
 * Demo in src-nodemo): adb shell am start -n io.github.avtarfr.kurooto.dev/io.github.avtarfr.kurooto.MainActivity
 * --ez demo true [--es tab inbox]. Nothing here is sent anywhere: in demo, Call, Chat, answers, Done and +1 only say so.
 */
object Demo {
    const val ON = true

    fun today(): JSONObject {
        val now = Date()
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.ROOT).apply { timeZone = TimeZone.getTimeZone("UTC") }
        val list = JSONObject()
            .put("v", 1)
            .put("date", SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(now))
            .put("day", SimpleDateFormat("EEEE d MMMM", Locale.ENGLISH).format(now))
            .put("classes", JSONArray()
                .put(JSONObject().put("time", "09:30").put("name", "Linear algebra"))
                .put(JSONObject().put("time", "11:30").put("name", "Chemistry lab").put("skipping", true))
                .put(JSONObject().put("time", "14:00").put("name", "Topology seminar")))
            .put("events", JSONArray().put("16:30 Study group, library").put("19:00 Call with Sam"))
            .put("due", JSONArray()
                .put(JSONObject().put("id", "d1").put("title", "Problem set 4 (Linear algebra)").put("when", "tomorrow")
                    .put("acts", JSONArray().put("done").put("+1")).put("parts", 7).put("done", 4))
                .put(JSONObject().put("id", "d2").put("title", "Lab report").put("when", "Fri").put("acts", JSONArray().put("done")))
                .put(JSONObject().put("id", "d3").put("title", "Midterm (Topology)").put("when", "Mon 03 Nov").put("exam", true)))
            .put("reminders", JSONArray().put(JSONObject().put("when", "Sat 18:00").put("what", "Return the library books")))
            .put("alarm", JSONObject().put("next", "Tomorrow 07:00").put("daily", "07:00")
                .put("at", JSONArray().put(now.time / 1000 + 36000)))
            .put("threads", JSONArray().put(JSONObject().put("text", "Ask about the project deadline"))
                .put(JSONObject().put("text", "Find a room for the study group")))
            .put("questions", 2)
        return JSONObject().put("list", list).put("at", iso.format(Date(now.time - 12 * 60_000))).put("computer", "online")
    }

    fun waiting(): List<JSONObject> = listOf(
        JSONObject().put("id", "demo-checkin").put("card", "checkin").put("reply", true)
            .put("message", "Evening check-in: How did today go? Did problem set 4 move along? (Reply to this message.)")
            .put("buttons", JSONArray().put(JSONObject().put("label", "In 30 min")).put(JSONObject().put("label", "Not tonight"))),
        JSONObject().put("id", "demo-quiz").put("card", "quiz")
            .put("message", "Quiz (topology, Must know): What makes a space compact?")
            .put("buttons", JSONArray().put(JSONObject().put("label", "Forgot")).put(JSONObject().put("label", "Hard"))
                .put(JSONObject().put("label", "Good")).put(JSONObject().put("label", "Easy"))),
        JSONObject().put("id", "demo-approve").put("title", "Approval")
            .put("message", "Send the lab report to your lab partner by mail?")
            .put("buttons", JSONArray().put(JSONObject().put("label", "Send")).put(JSONObject().put("label", "Not now"))),
        JSONObject().put("id", "demo-question").put("title", "Question").put("reply", true)
            .put("message", "Which room should the study group use on Thursday?"),
    )

    fun queued() = listOf("Done: Problem set 3", "Note: buy graph paper")

    fun update(): Pair<String, String>? = Pair("0.7.1", "https://avtarfr.github.io/kurooto/")

    fun checks(appInfo: Intent) = listOf(
        MainActivity.Check("Notifications", true, appInfo),
        MainActivity.Check("Microphone", true, appInfo),
        MainActivity.Check("Full-screen calls (ring on the lock screen)", false, appInfo),
        MainActivity.Check("Alarms at the exact time (the wake-up alarm on this phone)", true, appInfo),
        MainActivity.Check("Battery: unrestricted (keeps listening)", false, appInfo),
    )
}
