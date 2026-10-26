package io.github.avtarfr.kurooto

import android.Manifest
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONObject
import java.util.Locale
import kotlin.concurrent.thread

/**
 * The main screen (0.7.0: Compose, Material 3 Expressive). Paired: tabs under a navigation bar (Home.kt): Today
 * (the day from your computer's last copy, Call and Chat), Inbox (what's waiting for you, answered in place or in
 * AnswerActivity, and what waits for your computer), Views (opens ViewsActivity: Systems and the Notes map) and Phone
 * (the checklist, location reminders, ringtones, bedside mode, this phone). Not paired: the pairing screen. This class holds the screen's state (HomeState) and does what
 * the screens ask (calls, fetches, answers, settings); the composables only draw it.
 * Extras: "tab" (today, inbox or phone) opens on that tab; "bedside" opens bedside mode on top (smoke.sh, the
 * shortcut); "justPaired" says so; "demo" (debug and dev builds only, Demo.ON) shows made-up data without pairing,
 * "palette" (the same builds) a named palette instead of Material You, and "hour" (a float) the sky at that hour.
 */
class MainActivity : ComponentActivity() {
    internal val h = Handler(Looper.getMainLooper())
    internal val ui = HomeState()
    private val todayListener = Runnable { h.post { if (!isDestroyed && !ui.demo) ui.today = Today.load(this) } }
    private var refreshes = 0

    private val callTone = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { picked(false, it.resultCode, it.data) }
    private val alarmTone = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { picked(true, it.resultCode, it.data) }

    override fun onCreate(b: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(b)
        ui.demo = Demo.ON && intent.getBooleanExtra("demo", false)
        ui.tab = tabOf(intent) ?: b?.getInt("tab", 0) ?: 0
        ListenService.channels(this)
        if (!ui.demo) {
            askPermissions()
            if (Prefs.paired(this)) ListenService.start(this)
        }
        if (intent.getBooleanExtra("justPaired", false)) ui.status = Said("Paired. You're all set.", Said.OK)
        Today.listener = todayListener
        // debug and dev builds: "palette" (e.g. kuro) shows that palette instead of Material You, to look at it here
        if (Demo.ON) ui.palette = intent.getStringExtra("palette") ?: b?.getString("palette")
        if (Demo.ON && intent.hasExtra("hour")) ui.demoHour = intent.getFloatExtra("hour", 12f)
        setContent { KurootoTheme(palette = ui.palette ?: "kuro", dynamic = ui.palette == null) { Home(this, ui) } }
        if (intent.getBooleanExtra("bedside", false)) startActivity(Intent(this, BedsideActivity::class.java))
    }

    override fun onNewIntent(i: Intent) {
        super.onNewIntent(i)
        setIntent(i)
        if (Demo.ON && i.getBooleanExtra("demo", false)) ui.demo = true
        if (Demo.ON && i.hasExtra("palette")) ui.palette = i.getStringExtra("palette")
        if (Demo.ON && i.hasExtra("hour")) ui.demoHour = i.getFloatExtra("hour", 12f)
        tabOf(i)?.let { ui.tab = it }
        if (i.getBooleanExtra("justPaired", false)) ui.status = Said("Paired. You're all set.", Said.OK)
        if (i.getBooleanExtra("bedside", false)) startActivity(Intent(this, BedsideActivity::class.java))
    }

    override fun onSaveInstanceState(out: Bundle) {
        super.onSaveInstanceState(out)
        out.putInt("tab", ui.tab)
        ui.palette?.let { out.putString("palette", it) }
    }

    override fun onResume() {
        super.onResume()
        refresh(false)
        checkForUpdate()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (Today.listener === todayListener) Today.listener = null
    }

    private fun tabOf(i: Intent?): Int? = when (i?.getStringExtra("tab")) {
        "today" -> 0
        "inbox" -> 1
        "phone" -> 2
        else -> null
    }

    private fun askPermissions() {
        val want = ArrayList<String>()
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) want.add(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            want.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (want.isNotEmpty()) requestPermissions(want.toTypedArray(), 1)
    }

    // ---------- what the screens show ----------
    /** Re-read everything (on resume, after a change); `force` (pull to refresh) also asks the call line again even
     *  when the last copy of Today is fresh. */
    internal fun refresh(force: Boolean) {
        ui.tick++
        ui.paired = Prefs.paired(this)
        if (ui.demo) {
            ui.name = "Kurooto"
            ui.today = Demo.today()
            ui.waiting = Demo.waiting()
            ui.queued = Demo.queued()
            ui.update = Demo.update()
            return
        }
        ui.name = Prefs.assistant(this)
        updateInfo()
        if (!ui.paired) return
        ui.today = Today.load(this)
        val q = Chat.waiting(Chat.load(this))
        ui.queued = (0 until q.length()).mapNotNull { q.optJSONObject(it)?.optString("label") }
        val fetchToday = force || System.currentTimeMillis() - Today.fetchedAt(this) > 30_000
        if (force) {
            ui.refreshing = true
            refreshes = if (fetchToday) 2 else 1
        }
        if (fetchToday) thread { Today.fetch(applicationContext); if (force) h.post { refreshed() } }
        loadWaiting { if (force) refreshed() }
    }

    private fun refreshed() {
        if (--refreshes <= 0) ui.refreshing = false
    }

    /** Pull to refresh. */
    internal fun pull() {
        if (ui.demo) {
            ui.refreshing = true
            h.postDelayed({ ui.refreshing = false }, 600)
            return
        }
        refresh(true)
    }

    /** Open questions, approvals and messages from the call line, newest first (place reminders go to Places). */
    internal fun loadWaiting(then: (() -> Unit)? = null) {
        if (ui.demo) { then?.invoke(); return }
        thread {
            val items = Line.waiting(this)
            h.post {
                if (isDestroyed) return@post
                ui.name = Prefs.assistant(this) // renamed on the computer?
                if (items == null) {
                    ui.waitingFailed = true
                    if (ui.waiting == null) ui.waiting = emptyList()
                } else {
                    TalkWidget.waiting(this, items) // the 2x1 widget, without asking the line again
                    ui.waitingFailed = false
                    ui.waiting = (items.length() - 1 downTo 0).mapNotNull { items.optJSONObject(it) }.filter { !Places.adopt(this, it) }
                }
                then?.invoke()
            }
        }
    }

    // ---------- Today ----------
    /** A call line link (works with your computer on or off), then the call. */
    internal fun requestCall() {
        if (ui.demo) { ui.status = Said("Demo: there's no call line to call.", Said.DIM); return }
        ui.status = Said("Opening a call line…")
        thread {
            val link = Line.callLink(this)
            h.post {
                if (link == null) { ui.status = Said("Couldn't reach your call line. Is this phone online?", Said.BAD); return@post }
                ui.status = Said("")
                startActivity(Intent(this, CallActivity::class.java).putExtra("url", link))
            }
        }
    }

    internal fun chat() {
        if (ui.demo) { ui.status = Said("Demo: the chat needs a paired phone.", Said.DIM); return }
        startActivity(Intent(this, ChatActivity::class.java))
    }

    /** Done or +1 on a deadline: to your computer through the call line (kept there while it's off). */
    internal fun dueAct(id: String, act: String, title: String) {
        ui.openDue = ""
        if (ui.demo) { ui.todaySaid = Said("Demo: nothing was sent.", Said.DIM); return }
        val label = (if (act == "done") "Done" else act) + ": " + title
        ui.todaySaid = Said("Sending…")
        thread {
            val s = Today.act(applicationContext, id, act, label)
            h.post {
                val said = if (s.queued) "Saved on your call line: it goes to your computer when it's back." else s.note.ifEmpty { "Sent." }
                ui.todaySaid = Said(said, if (s.ok) Said.OK else Said.BAD)
            }
            if (s.ok && !s.queued) Today.fetch(applicationContext) // your computer sends the new list at once
        }
    }

    internal fun alarmOn(): Boolean = if (ui.demo) ui.demoAlarm else Alarms.on(this)

    internal fun toggleAlarm() {
        if (ui.demo) ui.demoAlarm = !ui.demoAlarm else Alarms.setOn(this, !Alarms.on(this))
        ui.tick++
    }

    /** Whether the wake-up alarm is set on this phone now (0: nothing set), and whether it can ring on the minute. */
    internal fun alarmSet(): Long = if (ui.demo) 1L else Alarms.set(this)

    internal fun exactAlarms(): Boolean = ui.demo || Alarms.exact(this)

    internal fun allowExact() = launch(Alarms.allowExact(this))

    // ---------- Inbox ----------
    /** Answer a check-in or quiz card in place (or press one of its buttons); `done` gets how it went. */
    internal fun answer(id: String, fields: JSONObject, done: (Said, Boolean) -> Unit) {
        if (ui.demo) { done(Said("Demo: nothing was sent.", Said.DIM), false); return }
        thread {
            val r = Line.answer(this, id, fields)
            h.post {
                if (isDestroyed) return@post
                val over = r.delivered() || r.gone()
                if (over) {
                    InboxCard.drafts.remove(id)
                    Inbox.cancel(this, id) // its notification too
                    h.postDelayed({ if (!isDestroyed) loadWaiting() }, 2500) // a quiz's grading: the next card
                }
                done(Said(r.note, if (r.delivered()) Said.OK else Said.BAD), over)
            }
        }
    }

    internal fun openItem(it: JSONObject) = startActivity(Intent(this, AnswerActivity::class.java).putExtra("item", it.toString()))

    // ---------- Phone ----------
    /** One checklist row: what it is, whether it's done, and where Fix goes. */
    class Check(val what: String, val ok: Boolean, val fix: Intent)

    internal fun checks(): List<Check> {
        val appInfo = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))
        if (ui.demo) return Demo.checks(appInfo)
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        val out = ArrayList<Check>()
        val notes = if (Build.VERSION.SDK_INT >= 26) {
            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
        } else appInfo
        out.add(Check("Notifications", Build.VERSION.SDK_INT < 24 || nm.areNotificationsEnabled(), notes))
        out.add(Check("Microphone", checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED, appInfo))
        if (Build.VERSION.SDK_INT >= 34) {
            out.add(Check("Full-screen calls (ring on the lock screen)", nm.canUseFullScreenIntent(),
                Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:$packageName"))))
        }
        if (Build.VERSION.SDK_INT >= 31) {
            out.add(Check("Alarms at the exact time (the wake-up alarm on this phone)", Alarms.exact(this), Alarms.allowExact(this)))
        }
        out.add(Check("Battery: unrestricted (keeps listening)", pm.isIgnoringBatteryOptimizations(packageName),
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName"))))
        return out
    }

    /** Phones that put apps to sleep on their own: the checklist says what else to change. */
    internal fun sleepyMaker(): String? =
        Build.MANUFACTURER.takeIf { it.lowercase(Locale.ROOT).matches(Regex(".*(samsung|xiaomi|redmi|poco|oppo|realme|vivo|oneplus|huawei|honor).*")) }

    internal fun fix(c: Check) {
        try { startActivity(c.fix) } catch (e: Exception) {
            launch(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
        }
    }

    internal fun launch(i: Intent) {
        try { startActivity(i) } catch (_: Exception) { }
    }

    internal fun toneName(alarm: Boolean): String {
        val u = Prefs.tone(this, alarm)
        if (u.isEmpty()) return "phone default"
        return try { RingtoneManager.getRingtone(this, Uri.parse(u))?.getTitle(this) ?: "custom" } catch (e: Exception) { "custom" }
    }

    internal fun pickTone(alarm: Boolean) {
        val i = Intent(RingtoneManager.ACTION_RINGTONE_PICKER)
            .putExtra(RingtoneManager.EXTRA_RINGTONE_TYPE, if (alarm) RingtoneManager.TYPE_ALARM else RingtoneManager.TYPE_RINGTONE)
            .putExtra(RingtoneManager.EXTRA_RINGTONE_TITLE, if (alarm) "Wake-up alarm tone" else "Call ringtone")
            .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_SILENT, false)
            .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_DEFAULT, true)
        val cur = Prefs.tone(this, alarm)
        if (cur.isNotEmpty()) i.putExtra(RingtoneManager.EXTRA_RINGTONE_EXISTING_URI, Uri.parse(cur))
        try { (if (alarm) alarmTone else callTone).launch(i) } catch (_: Exception) { }
    }

    @Suppress("DEPRECATION")
    private fun picked(alarm: Boolean, result: Int, data: Intent?) {
        if (result != RESULT_OK || data == null) return
        val u = data.getParcelableExtra<Uri>(RingtoneManager.EXTRA_RINGTONE_PICKED_URI)
        Prefs.setTone(this, alarm, u?.toString() ?: "")
        ui.tick++
    }

    internal fun bedsideHours() = BedsideActivity.hours(this) { ui.tick++ }

    /** The Phone tab's switch for the line's own connection: the listening service starts again without (or with) it. */
    internal fun toggleDirect() {
        Prefs.setDirect(this, !Prefs.direct(this))
        if (!Prefs.direct(this)) Direct.disarm(this)
        stopService(Intent(this, ListenService::class.java))
        ListenService.start(this)
        ui.tick++
    }

    /** The Phone tab's switch for the moving background; the screen is drawn again with it. */
    internal fun toggleMoving() {
        Prefs.setMoving(this, !Prefs.moving(this))
        recreate()
    }

    internal fun toggleSense(sensor: String) {
        Senses.set(this, sensor, !Senses.on(this, sensor))
        ui.tick++
    }

    /** Look → Vivid colours (0.7.5): off brings back the wallpaper's own quiet scheme. */
    internal fun toggleVivid() {
        Prefs.setVivid(this, !Prefs.vivid(this))
        recreate()
    }

    /** Look → Floating bar (0.7.5): off docks the navigation bar to the bottom edge again. */
    internal fun toggleFloatingBar() {
        Prefs.setFloatingBar(this, !Prefs.floatingBar(this))
        recreate()
    }

    /** The call screen (0.8.7): the Compose one, or the one from before; the next call opens with it. */
    internal fun toggleNewCallScreen() {
        Prefs.setNewCallScreen(this, !Prefs.newCallScreen(this))
        ui.tick++
    }

    internal fun toggleKeepOn() {
        Prefs.setBedsideKeepOn(this, !Prefs.bedsideKeepOn(this))
        ui.tick++
    }

    internal fun unpair() {
        if (!ui.demo) {
            Prefs.forget(this)
            stopService(Intent(this, ListenService::class.java))
        }
        ui.demo = false
        ui.tab = 0
        refresh(false)
        ui.status = Said("Unpaired here. Also remove it on your computer (the dashboard's Phone tab).")
    }

    // ---------- pairing ----------
    internal fun pair(link: String) {
        val p = Line.parse(link)
        if (p == null) { ui.status = Said("That isn't a pairing link. It looks like https://…/pair#c=ABCD2345.", Said.BAD); return }
        ui.status = Said("Pairing…")
        thread {
            val err = Line.claim(this, p)
            h.post {
                if (err != null) { ui.status = Said(err, Said.BAD); return@post }
                ListenService.start(this)
                ui.status = Said("Paired. You're all set.", Said.OK)
                refresh(false)
            }
        }
    }

    // ---------- updates ----------
    @Suppress("DEPRECATION")
    private fun versionCode(): Long = try {
        val p = packageManager.getPackageInfo(packageName, 0)
        if (Build.VERSION.SDK_INT >= 28) p.longVersionCode else p.versionCode.toLong()
    } catch (e: Exception) { 0 }

    internal fun versionName(): String = try { packageManager.getPackageInfo(packageName, 0).versionName ?: "?" } catch (e: Exception) { "?" }

    private fun updateInfo() {
        val sp = Prefs.sp(this)
        val link = sp.getString("updateLink", "") ?: ""
        val name = sp.getString("updateName", "") ?: ""
        ui.update = if (link.isNotEmpty() && versionName() != name) Pair(name, link) else null
    }

    /** Check if there is a newer app on Kurooto's release page (at most every two minutes). */
    private fun checkForUpdate() {
        if (ui.demo || System.currentTimeMillis() - Prefs.lastUpdateCheck(this) < 120_000) return
        thread {
            val r = Net.request("GET", UPDATES, null, null, null, 20000)
            try {
                val j = JSONObject(if (r.ok()) r.body else "{}")
                val newer = j.optLong("versionCode", 0) > versionCode() && j.optString("url", "").startsWith("https://")
                Prefs.setUpdate(this, if (newer) j.optString("versionName") else "", if (newer) j.optString("url") else "")
                h.post { if (!isDestroyed) updateInfo() }
            } catch (e: Exception) {
                Prefs.setUpdate(this, "", "")
            }
        }
    }

    companion object {
        const val UPDATES = "https://avtarfr.github.io/kurooto/android.json"
    }
}

/** What the main screen shows; Compose redraws what reads a field when it changes. */
class HomeState {
    var demo by mutableStateOf(false)
    var demoAlarm by mutableStateOf(true)
    /** A named palette instead of Material You (debug and dev builds, the "palette" extra). */
    var palette by mutableStateOf<String?>(null)
    /** The sky at this hour instead of the clock's (debug and dev builds, the "hour" extra, e.g. --ef hour 7.5). */
    var demoHour by mutableStateOf<Float?>(null)
    var paired by mutableStateOf(false)
    var name by mutableStateOf("Kurooto")
    /** 0 Today, 1 Inbox, 2 Phone (kept across rotation, onSaveInstanceState). */
    var tab by mutableIntStateOf(0)
    /** Today.load's copy: {"list", "at", "computer", "off", "old"}. */
    var today by mutableStateOf(JSONObject())
    /** What's waiting for you, newest first; null until the call line answered once. */
    var waiting by mutableStateOf<List<JSONObject>?>(null)
    var waitingFailed by mutableStateOf(false)
    /** What waits for your computer (the phone outbox on the call line). */
    var queued by mutableStateOf(listOf<String>())
    /** Under Call and Chat (and on the pairing screen): calls, pairing, unpairing. */
    var status by mutableStateOf(Said(""))
    /** How Done or +1 on a deadline went. */
    var todaySaid by mutableStateOf<Said?>(null)
    /** The deadline whose Done and +1 show. */
    var openDue by mutableStateOf("")
    /** A newer app: its version and link. */
    var update by mutableStateOf<Pair<String, String>?>(null)
    var refreshing by mutableStateOf(false)
    /** How far Today is scrolled (px): the sky's parallax. */
    var todayScroll by mutableFloatStateOf(0f)
    /** Bumped when settings or permissions may have changed: what reads it re-reads them. */
    var tick by mutableIntStateOf(0)
}
