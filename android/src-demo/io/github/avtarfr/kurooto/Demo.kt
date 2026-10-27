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
 * --ez demo true [--es tab today|alarms|settings|inbox] [--es call ring|in] (BedsideActivity and CallActivity take the same
 * extra, 0.8.7; "call", 0.8.16, opens the call screen with [callPage], as Call on Today does). Nothing here is sent
 * anywhere: in demo, Chat, answers, Done and +1 only say so;
 * the Views tab shows made-up copies of Systems and the Notes map (view()).
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
            .put("classes", demoClasses())
            .put("events", JSONArray().put("16:30 Study group, library").put("19:00 Call with Sam"))
            .put("due", JSONArray()
                .put(JSONObject().put("id", "d1").put("title", "Problem set 4 (Linear algebra)").put("when", "tomorrow")
                    .put("acts", JSONArray().put("done").put("+1")).put("parts", 7).put("done", 4))
                .put(JSONObject().put("id", "d2").put("title", "Lab report").put("when", "Fri").put("acts", JSONArray().put("done")))
                .put(JSONObject().put("id", "d3").put("title", "Midterm (Topology)").put("when", "Mon 03 Nov").put("exam", true)))
            .put("reminders", JSONArray().put(JSONObject().put("when", "Sat 18:00").put("what", "Return the library books")))
            .put("alarm", JSONObject().put("next", "Tomorrow 07:00").put("daily", "07:00").put("reason", "First class at 08:30")
                .put("at", demoAlarms()))
            .put("threads", JSONArray().put(JSONObject().put("text", "Ask about the project deadline"))
                .put(JSONObject().put("text", "Find a room for the study group")))
            .put("questions", 2)
        return JSONObject().put("list", list).put("at", iso.format(Date(now.time - 12 * 60_000))).put("computer", "online")
    }

    /** The day's classes (0.8.10: with their ends, as your computer sends them): one on now, one gone by, one skipped,
     *  one still to come, so Today's big card and its strip both have something to show at any hour. */
    private fun demoClasses(): JSONArray {
        val c = java.util.Calendar.getInstance()
        val h = c.get(java.util.Calendar.HOUR_OF_DAY)
        fun span(from: Int, to: Int) = String.format(Locale.ROOT, "%02d:00–%02d:00", (from + 24) % 24, (to + 24) % 24)
        return JSONArray()
            .put(JSONObject().put("time", span(h - 3, h - 2)).put("name", "Linear algebra"))
            .put(JSONObject().put("time", span(h - 1, h + 1)).put("name", "Waves and oscillations"))
            .put(JSONObject().put("time", span(h + 1, h + 2)).put("name", "Chemistry lab").put("skipping", true))
            .put(JSONObject().put("time", span(h + 3, h + 4)).put("name", "Topology seminar"))
    }

    /** The wake-up alarms still to ring (0.8.10: several, for the Alarms pane): tomorrow 06:50, then three more. */
    private fun demoAlarms(): JSONArray {
        val c = java.util.Calendar.getInstance()
        fun at(days: Int, h: Int, m: Int): Long {
            val x = c.clone() as java.util.Calendar
            x.add(java.util.Calendar.DAY_OF_YEAR, days)
            x.set(java.util.Calendar.HOUR_OF_DAY, h); x.set(java.util.Calendar.MINUTE, m); x.set(java.util.Calendar.SECOND, 0)
            return x.timeInMillis / 1000
        }
        return JSONArray().put(at(1, 6, 50)).put(at(2, 7, 0)).put(at(3, 7, 30)).put(at(4, 9, 0)).put(at(5, 7, 0))
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

    /** What's coming, as the call line's /upcoming answers it (bedside mode in demo, 0.8.7): two calls, the wake-up call,
     *  two things waiting, the computer off (so its note shows). */
    fun upcoming(): JSONObject {
        val now = System.currentTimeMillis() / 1000
        return JSONObject()
            .put("calls", JSONArray()
                .put(JSONObject().put("at", now + 2 * 3600).put("reason", "Evening check-in"))
                .put(JSONObject().put("at", now + 5 * 3600).put("reason", "Start the lab report"))
                .put(JSONObject().put("at", now + 10 * 3600).put("reason", "Wake-up call").put("alarm", true)))
            .put("waiting", 2).put("computer", "offline")
    }

    /** Made-up copies of Systems and the Notes map (ViewsActivity in demo), kept as Views keeps a fetched one. */
    fun view(kind: String): JSONObject {
        val now = System.currentTimeMillis() / 1000
        val snap = if (kind == "notes") demoNotes(now) else demoSystems(now)
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.ROOT).apply { timeZone = TimeZone.getTimeZone("UTC") }
        return JSONObject().put("snap", snap.put("made", now - 90).toString()).put("rev", 1)
            .put("at", iso.format(Date((now - 90) * 1000))).put("computer", "online").put("reach", true)
    }

    private fun demoSystems(now: Long): JSONObject {
        val on = listOf("reminders" to "Reminders", "checkins" to "Check-ins", "deadlines" to "Deadlines",
            "subjects" to "Subjects and timetable", "quiz" to "Quiz", "chat" to "Chat with your AI",
            "calls" to "Calls", "weekly" to "Weekly summary", "files" to "Files into notes")
        val cells = JSONArray()
        val features = JSONArray()
        on.forEachIndexed { i, (id, title) ->
            val events = listOf(3, 0, 1, 0, 2, 5, 1, 0, 0)[i]
            cells.put(JSONObject().put("id", id).put("title", title).put("act", minOf(1.0, events / 6.0)).put("events", events))
            features.put(JSONObject().put("id", id).put("title", title).put("events", events)
                .put("last", if (events > 0) now - 40L * (i + 1) else JSONObject.NULL)
                .put("next", now + 900L * (i + 1)).put("proc", JSONObject.NULL)
                .put("down", false).put("idle", events == 0).put("intermittent", false))
        }
        return JSONObject().put("v", 1).put("kind", "systems").put("name", "Kurooto").put("version", "0.7.0")
            .put("sys", JSONObject().put("cpu", 0.18).put("mem", 0.52)).put("cells", cells).put("features", features)
            .put("core", JSONObject().put("cpu", 0.004).put("mem", 61_000_000)).put("link", JSONObject().put("connected", true))
            .put("today", JSONObject().put("items", JSONArray())).put("health", JSONArray())
    }

    private fun demoNotes(now: Long): JSONObject {
        val nodes = JSONArray()
        val links = JSONArray()
        val ids = mutableListOf<String>()
        fun note(id: String, title: String, words: Int): Int {
            ids += id
            nodes.put(JSONArray().put(id).put(title).put(now - 3600L * ids.size).put(words))
            return ids.size - 1
        }
        val courses = listOf("linear-algebra" to "Linear algebra", "topology" to "Topology", "chemistry" to "Chemistry lab")
        val topics = listOf("Eigenvalues", "Inner products", "Compactness", "Connectedness", "Titration", "Spectra",
            "Quotient spaces", "Bases", "Open sets", "Kinetics", "Determinants", "Metric spaces")
        val home = note("maps/index", "Home", 40)
        courses.forEachIndexed { c, (dir, title) ->
            val course = note("sources/$dir/course", title, 120)
            links.put(JSONArray().put(home).put(course))
            val first = ids.size
            for (k in 0 until 10) {
                val n = note("sources/$dir/note-$k", "${topics[(c * 4 + k) % topics.size]} ${k + 1}", 200 + 37 * k)
                links.put(JSONArray().put(course).put(n))
                if (k > 0) links.put(JSONArray().put(n).put(first + (k * 7 + 3) % k))
                if (k % 4 == 3) links.put(JSONArray().put(n).put(first + (k + 3) % 10).put(1)) // a "Seen in" link
            }
        }
        val project = note("projects/ring-model/index", "Ring model", 300)
        links.put(JSONArray().put(home).put(project))
        for (k in 0 until 6) {
            val z = note("zettel/idea-$k", "Idea ${k + 1}", 90)
            links.put(JSONArray().put(z).put(3 + 11 * (k % 3) + k))
            if (k < 3) links.put(JSONArray().put(project).put(z))
        }
        val order = ids.indices.sortedBy { ids[it] }
        val at = IntArray(ids.size).also { a -> order.forEachIndexed { i, old -> a[old] = i } }
        val sortedNodes = JSONArray().also { s -> order.forEach { s.put(nodes.getJSONArray(it)) } }
        val sortedLinks = JSONArray()
        for (i in 0 until links.length()) {
            val l = links.getJSONArray(i)
            val p = JSONArray().put(at[l.getInt(0)]).put(at[l.getInt(1)])
            if (l.length() > 2) p.put(1)
            sortedLinks.put(p)
        }
        return JSONObject().put("v", 1).put("kind", "notes").put("nodes", sortedNodes).put("links", sortedLinks)
            .put("layout", JSONObject()).put("research", JSONObject())
            .put("total", JSONObject().put("notes", ids.size).put("links", links.length()))
            .put("cut", JSONObject().put("notes", 0).put("links", 0))
    }

    fun checks(appInfo: Intent) = listOf(
        MainActivity.Check("Notifications", true, appInfo),
        MainActivity.Check("Microphone", true, appInfo),
        MainActivity.Check("Full-screen calls (ring on the lock screen)", false, appInfo),
        MainActivity.Check("Alarms at the exact time (the wake-up alarm on this phone)", true, appInfo),
        MainActivity.Check("Battery: unrestricted (keeps listening)", false, appInfo),
    )

    /**
     * The call page's stand-in (CallActivity in demo, 0.8.16): the call page's own elements (the ids in
     * src/kurooto/data/worker/public/index.html) acting out a short call, so the call screen can be looked at without a
     * call line: it connects, the level moves, a few lines are said, and Mute, Speaker and the mic gate change what the
     * page shows as they do in a real call. No microphone, nothing fetched, nothing sent.
     */
    @JvmStatic
    fun callPage(): String = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>body{background:#0b0f0a;color:#f2eee8;font:16px sans-serif;margin:16px}.m{margin:4px 0}.me{text-align:right}</style></head><body><main>
<div><h1 id="who">Kurooto</h1><div id="reason">Evening check-in: how did today go?</div></div>
<div id="status">Connecting…</div><div id="log"></div>
<div class="gate" id="gatebox"><div class="bar"><div id="level"></div></div>
<label>Mic gate <span id="gateval">normal</span> <input id="gate" type="range" min="0.6" max="3" step="0.2" value="1"></label></div>
<button id="int" hidden>Interrupt</button><p id="mode" hidden></p><div id="heard" hidden></div><button id="talk" hidden>Talk</button>
<div class="row"><button id="call" class="end">Hang up</button><button id="mute">Mute</button><button id="out">Earpiece</button></div>
</main><script>
var el=function(i){return document.getElementById(i);};
function say(t,c){var d=document.createElement('div');d.className='m '+c;d.textContent=t;el('log').append(d);}
var lines=[[1800,'Hi! Quick evening check-in: how did today go?','ai'],[4200,'Pretty good. I finished the problem set.','me'],
[5200,'searching notes: study plan','sys'],[6800,'Nice work. Tomorrow has two hours free after lunch: shall I put topology revision there?','ai'],
[9200,'Yes, do that.','me'],[10400,'Done. It’s on your calendar for 14:00.','ai']];
setTimeout(function(){el('status').textContent='Connected';el('status').className='live';el('out').textContent='Speaker';},1200);
lines.forEach(function(l){setTimeout(function(){say(l[1],l[2]);},l[0]);});
var muted=false;
setInterval(function(){var lv=el('level'),x=muted?0:Math.random();lv.style.width=Math.round(x*100)+'%';lv.style.background=x>0.45?'var(--ok)':'var(--dim)';},300);
el('mute').onclick=function(){muted=!muted;el('mute').textContent=muted?'Unmute':'Mute';};
el('out').onclick=function(){var sp=el('out').textContent==='Speaker';el('out').textContent=sp?'Earpiece':'Speaker';el('status').textContent=sp?'Speaker':'Earpiece';};
el('gate').oninput=function(e){var v=Number(e.target.value);el('gateval').textContent=v===1?'normal':v>1?'stricter ×'+v:'looser ×'+v;};
el('call').onclick=function(){el('status').textContent='Call ended';el('status').className='';el('call').textContent='Call';el('call').className='';};
</script></body></html>"""
}
