package io.github.avtarfr.kurooto

import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.ToggleButton
import androidx.compose.material3.toShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import org.json.JSONObject
import java.util.Locale

/**
 * The call screen (0.8.7: Compose, Material 3 Expressive; Phone tab → Switches → "New call screen", on by default; off,
 * CallActivity builds the framework screen from before 0.8.7). CallActivity keeps all of a call's plumbing (the intents, the
 * lock screen, audio routing, the proximity sensor, the WebView and its KurootoApp bridge, the phone's own speech) and
 * asks this for what to draw:
 * - [ringing]: over the app's sky, always dark, a slowly turning cookie badge (still with "Remove animations"), who's
 *   calling and why, and Decline / Later / Answer (this phone's alarm: Stop / Snooze) as big expressive buttons in a
 *   floating bar at the bottom;
 * - [call] (0.8.16): the call itself. Up to 0.8.15 the answered call showed the call line's own web page (dark green,
 *   "Ready", the mic gate, Hang up / Mute / Earpiece), whichever way the call came (rung, placed from the app, answered
 *   from the notification), because only the ringing screen was redrawn. The page still runs the call (the microphone,
 *   Gemini Live or turn by turn, the transcript sent to your computer), so it stays loaded, but as a 1 dp view under the
 *   sky: [MIRROR] watches its elements and sends what they show to [CallUi] (KurootoScreen.state), and the buttons here
 *   press the page's own ([press], [gate]). The page needs no change, so it works with a call line not yet updated.
 *   If the page isn't the call page (no #call or #status), or says nothing within 8 s, the page itself is shown, as
 *   before ([CallUi.raw]).
 */
object CallScreen {
    @JvmStatic
    fun ringing(
        a: ComponentActivity,
        who: String,
        why: String,
        declineLabel: String,
        laterLabel: String,
        canAnswer: Boolean,
        onDecline: Runnable,
        onLater: Runnable,
        onAnswer: Runnable,
    ) {
        a.setContent {
            KurootoTheme(forceDark = true) {
                Ringing(a, who, why, declineLabel, laterLabel, canAnswer, onDecline, onLater, onAnswer)
            }
        }
    }

    /** The call: `page` (the WebView's container, made once by CallActivity) runs it out of sight; this draws it. */
    @JvmStatic
    fun call(a: ComponentActivity, page: View, ui: CallUi, act: CallActions) {
        a.setContent {
            KurootoTheme(forceDark = true) { InCall(a, page, ui, act) }
        }
    }

    /** The page's buttons this screen may press (nothing else is ever clicked). */
    private val PRESSABLE = setOf("call", "mute", "out", "int", "talk")

    /** Script that presses one of the page's buttons, as a tap there would. */
    @JvmStatic
    fun press(id: String): String {
        if (id !in PRESSABLE) return ""
        return "(function(){var e=document.getElementById('$id');if(e&&!e.disabled&&!e.hidden)e.click();})()"
    }

    /** Script that sets the page's mic gate (its slider, 0.6 to 3), as dragging it there would. */
    @JvmStatic
    fun gate(v: Float): String {
        val x = String.format(Locale.ROOT, "%.1f", v.coerceIn(0.6f, 3f))
        return "(function(){var g=document.getElementById('gate');if(g){g.value='$x';g.dispatchEvent(new Event('input'));}})()"
    }

    /**
     * Runs in the call page once it has loaded: a MutationObserver on the page sends a snapshot of what its elements
     * show (at most every 60 ms, the transcript only when it changed: its length or its last line, which a repeated tool
     * line's "×N" changes in place, 0.8.17) to window.KurootoScreen.state. The element ids are
     * the call page's (src/kurooto/data/worker/public/index.html; tests/unit/test_calls.py checks they're all there).
     * Running it again only asks for a fresh snapshot.
     */
    const val MIRROR = """(function(){
if(window.__kurootoScreen){window.__kurootoScreen();return;}
var S=window.KurootoScreen;if(!S)return;
var el=function(i){return document.getElementById(i);};
var on=function(e){return !!e&&!e.hidden;};
var tx=function(e){return e?(e.textContent||''):'';};
var last='',timer=0;
function snap(){timer=0;try{
var call=el('call'),st=el('status'),o={ok:!!(call&&st)};
if(o.ok){
var lv=el('level'),t=el('talk'),g=el('gate'),lg=el('log');
o.who=tx(el('who'));o.reason=tx(el('reason'));o.status=tx(st);o.tone=st.className||'';
o.call={t:tx(call),end:call.className==='end',off:!!call.disabled};
o.mute={on:on(el('mute')),t:tx(el('mute'))};o.out={on:on(el('out')),t:tx(el('out'))};o.int=on(el('int'));
o.gate={on:on(el('gatebox')),v:g?Number(g.value)||1:1,t:tx(el('gateval'))};
o.level={w:lv?(parseFloat(lv.style.width)||0):0,open:lv?/ok/.test(lv.style.background||''):false};
o.mode={on:on(el('mode')),t:tx(el('mode'))};o.heard={on:on(el('heard')),t:tx(el('heard'))};
o.talk={on:on(t),t:tx(t),s:t&&t.dataset?(t.dataset.state||''):'',off:t?!!t.disabled:false};
var k=lg?lg.children:[],n=k.length,sig=n+':'+(n?tx(k[n-1]):'');
if(sig!==last){last=sig;var a=[];for(var i=Math.max(0,n-80);i<n;i++)a.push({c:String(k[i].className||'').replace(/^m\s*/,''),t:tx(k[i])});o.log=a;}
}
S.state(JSON.stringify(o));
}catch(e){}}
function soon(){if(!timer)timer=setTimeout(snap,60);}
window.__kurootoScreen=function(){last='';soon();};
new MutationObserver(soon).observe(document.body||document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true});
snap();
})();"""

    /** How long the page has, once loaded, to show it's the call page before it's shown itself (ms). */
    const val MIRROR_WAIT_MS = 8000L
}

/** What the screen's buttons do: CallActivity presses the page's own buttons, or closes. */
interface CallActions {
    /** Press one of the call page's buttons ("call", "mute", "out", "int", "talk"). */
    fun press(id: String)

    /** Set the page's mic gate. */
    fun gate(v: Float)

    /** Hang up: the page's own Hang up while the call is on (it tells your computer the call is over), else close. */
    fun hangUp()

    fun close()
}

/** One line of the call's transcript, as the page shows it: "ai" (Kurooto), "me" (you) or "sys" (a note). */
data class CallLine(val who: String, val text: String)

/** The call page's state, mirrored (Compose state; [apply] on the main thread). */
class CallUi(assistant: String) {
    /** A snapshot came with the page's controls. */
    var ready by mutableStateOf(false)

    /** The page itself is shown instead (it isn't the call page, or never said anything). */
    var raw by mutableStateOf(false)
    var who by mutableStateOf(assistant)
    var reason by mutableStateOf("")
    var status by mutableStateOf("Connecting…")

    /** The status line's class on the page: "live", "err" or "". */
    var tone by mutableStateOf("")
    var callLabel by mutableStateOf("Hang up")
    var inCall by mutableStateOf(true)
    var callOff by mutableStateOf(false)
    var muteShown by mutableStateOf(false)
    var muted by mutableStateOf(false)
    var outShown by mutableStateOf(false)

    /** On the loudspeaker (CallActivity says, as it routes the audio; the demo page says it itself). */
    var speaker by mutableStateOf(false)
    var speakerFromPage = false
    var interrupt by mutableStateOf(false)
    var gateShown by mutableStateOf(false)
    var gate by mutableFloatStateOf(1f)
    var gateLabel by mutableStateOf("normal")

    /** The microphone's level against the gate (0 to 1), and whether the gate is open (your voice goes through). */
    var level by mutableFloatStateOf(0f)
    var open by mutableStateOf(false)
    var turnsHint by mutableStateOf("")
    var heard by mutableStateOf("")
    var talkShown by mutableStateOf(false)
    var talkLabel by mutableStateOf("Talk")
    var talkState by mutableStateOf("")
    var talkOff by mutableStateOf(false)
    val lines = mutableStateListOf<CallLine>()

    fun apply(json: String) {
        val o = try { JSONObject(json) } catch (_: Exception) { return }
        if (!o.optBoolean("ok")) { raw = true; return }
        ready = true
        o.optString("who").takeIf { it.isNotBlank() }?.let { who = it }
        reason = o.optString("reason")
        status = o.optString("status")
        tone = o.optString("tone")
        o.optJSONObject("call")?.let { callLabel = it.optString("t"); inCall = it.optBoolean("end"); callOff = it.optBoolean("off") }
        o.optJSONObject("mute")?.let { muteShown = it.optBoolean("on"); muted = it.optString("t") == "Unmute" }
        o.optJSONObject("out")?.let {
            outShown = it.optBoolean("on")
            // the page's button names where a tap goes: "Earpiece" while on the speaker
            if (speakerFromPage) speaker = it.optString("t") == "Earpiece"
        }
        interrupt = o.optBoolean("int")
        o.optJSONObject("gate")?.let { gateShown = it.optBoolean("on"); gate = it.optDouble("v", 1.0).toFloat(); gateLabel = it.optString("t") }
        o.optJSONObject("level")?.let { level = (it.optDouble("w", 0.0) / 100.0).toFloat().coerceIn(0f, 1f); open = it.optBoolean("open") }
        turnsHint = o.optJSONObject("mode")?.takeIf { it.optBoolean("on") }?.optString("t").orEmpty()
        heard = o.optJSONObject("heard")?.takeIf { it.optBoolean("on") }?.optString("t").orEmpty()
        o.optJSONObject("talk")?.let { talkShown = it.optBoolean("on"); talkLabel = it.optString("t"); talkState = it.optString("s"); talkOff = it.optBoolean("off") }
        o.optJSONArray("log")?.let { a ->
            val next = (0 until a.length()).mapNotNull { a.optJSONObject(it) }.map { CallLine(it.optString("c"), it.optString("t")) }.filter { it.text.isNotBlank() }
            if (next != lines.toList()) {
                lines.clear()
                lines.addAll(next)
            }
        }
    }
}

/** The page's window.KurootoScreen: its snapshots, to [CallUi] on the main thread. */
class CallMirror(private val ui: CallUi) {
    private val h = Handler(Looper.getMainLooper())

    @JavascriptInterface
    fun state(json: String) {
        h.post { ui.apply(json) }
    }
}

@Composable
private fun InCall(a: ComponentActivity, page: View, ui: CallUi, act: CallActions) {
    val cs = MaterialTheme.colorScheme
    Box(Modifier.fillMaxSize().background(if (ui.raw) colorResource(R.color.k_call_bg) else cs.background)) {
        // the call page: 1 dp under the sky while it runs the call; the whole screen when it's shown itself
        AndroidView(
            factory = { (page.parent as? ViewGroup)?.removeView(page); page },
            update = {
                it.importantForAccessibility = if (ui.raw) View.IMPORTANT_FOR_ACCESSIBILITY_AUTO else View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
            },
            modifier = if (ui.raw) Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars) else Modifier.size(1.dp),
        )
        if (!ui.raw) {
            Sky(a, strength = { 0.45f }, scroll = { 0f }, modifier = Modifier.fillMaxSize())
            BoxWithConstraints(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars).padding(horizontal = 16.dp, vertical = 12.dp)) {
                val talked = ui.lines.isNotEmpty() || ui.heard.isNotEmpty()
                if (maxWidth > maxHeight && maxHeight < 560.dp) {
                    // a phone on its side: the call on the left, the transcript beside it (stacked, it would get no room)
                    Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Column(Modifier.weight(1f).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally) {
                            SmallHeader(ui)
                            // the controls scroll if they don't fit (the mic gate open), so the bar always shows
                            Box(Modifier.weight(1f).fillMaxWidth().padding(top = 10.dp), contentAlignment = Alignment.BottomCenter) {
                                val sc = rememberScrollState()
                                LaunchedEffect(sc.maxValue) { sc.animateScrollTo(sc.maxValue) } // what just opened (the gate's slider)
                                Column(Modifier.verticalScroll(sc), horizontalAlignment = Alignment.CenterHorizontally) {
                                    TurnsHint(ui)
                                    Controls(ui, act, compact = true)
                                }
                            }
                            Bar(ui, act)
                        }
                        if (talked) Transcript(ui, Modifier.weight(1f).fillMaxHeight())
                    }
                } else {
                    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
                        if (!talked) {
                            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) { BigHeader(ui) }
                        } else {
                            SmallHeader(ui)
                            Transcript(ui, Modifier.weight(1f).widthIn(max = 640.dp).fillMaxWidth())
                        }
                        TurnsHint(ui)
                        Controls(ui, act)
                        Bar(ui, act)
                    }
                }
            }
        }
    }
}

/** Turn by turn's hint ("speak after it finishes"), as the page words it. */
@Composable
private fun TurnsHint(ui: CallUi) {
    if (ui.turnsHint.isEmpty()) return
    Text(
        ui.turnsHint, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center, modifier = Modifier.padding(bottom = 8.dp),
    )
}

/** Kurooto's badge: a cookie that swells with your voice while the gate lets it through and turns slowly while the call
 *  is on (still with "Remove animations"). */
@Composable
private fun Badge(ui: CallUi, size: Dp) {
    val cs = MaterialTheme.colorScheme
    val reduced = LocalReducedMotion.current
    val t = rememberInfiniteTransition(label = "call")
    val turn by t.animateFloat(0f, 360f, infiniteRepeatable(tween(24_000, easing = LinearEasing)), label = "turn")
    val swell by animateFloatAsState(if (ui.open) 1f + ui.level * 0.14f else 1f, tween(140), label = "swell")
    val fill by animateColorAsState(if (ui.open) cs.primary else cs.primaryContainer, label = "fill")
    val ink by animateColorAsState(if (ui.open) cs.onPrimary else cs.onPrimaryContainer, label = "ink")
    val spin = !reduced && ui.inCall
    Box(
        Modifier.size(size)
            .graphicsLayer {
                if (spin) rotationZ = turn
                if (!reduced) {
                    scaleX = swell
                    scaleY = swell
                }
            }
            .clip(MaterialShapes.Cookie9Sided.toShape()).background(fill),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painterResource(R.drawable.ic_stat), contentDescription = null, tint = ink,
            modifier = Modifier.size(size * 0.36f).graphicsLayer { if (spin) rotationZ = -turn },
        )
    }
}

/** How the call is going, as the page says it: a pill in the call's colours (live, an error, or neither). */
@Composable
private fun StatusPill(ui: CallUi) {
    if (ui.status.isBlank()) return
    val cs = MaterialTheme.colorScheme
    val (bg, fg) = when (ui.tone) {
        "live" -> cs.primaryContainer to cs.onPrimaryContainer
        "err" -> cs.errorContainer to cs.onErrorContainer
        else -> cs.surfaceContainerHighest to cs.onSurface
    }
    Surface(shape = CircleShape, color = bg, contentColor = fg) {
        Text(ui.status, style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp))
    }
}

/** Nothing said yet: the badge, who and why, big in the middle. */
@Composable
private fun BigHeader(ui: CallUi) {
    val cs = MaterialTheme.colorScheme
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 8.dp)) {
        Badge(ui, 148.dp)
        Text(
            ui.who, style = MaterialTheme.typography.displaySmallEmphasized, color = cs.onBackground, textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 28.dp),
        )
        if (ui.reason.isNotBlank()) {
            Text(
                ui.reason, style = MaterialTheme.typography.titleLarge, color = cs.onSurfaceVariant, textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 10.dp),
            )
        }
        Box(Modifier.padding(top = 20.dp)) { StatusPill(ui) }
    }
}

/** Once the transcript starts: the badge, who and how it's going, in a floating card at the top. */
@Composable
private fun SmallHeader(ui: CallUi) {
    val cs = MaterialTheme.colorScheme
    Surface(
        shape = MaterialTheme.shapes.extraLarge,
        color = cs.surfaceContainerHigh.copy(alpha = 0.92f),
        contentColor = cs.onSurface,
        tonalElevation = 6.dp,
        shadowElevation = 6.dp,
        modifier = Modifier.widthIn(max = 640.dp).fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Badge(ui, 56.dp)
            Column(Modifier.padding(start = 14.dp).weight(1f)) {
                Text(ui.who, style = MaterialTheme.typography.titleLargeEmphasized, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (ui.reason.isNotBlank()) {
                    Text(ui.reason, style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                Box(Modifier.padding(top = 6.dp)) { StatusPill(ui) }
            }
        }
    }
}

/** What Kurooto and you said (when the call shows it), and notes like "searching notes", newest at the bottom. */
@Composable
private fun Transcript(ui: CallUi, modifier: Modifier) {
    val list = rememberLazyListState()
    val reduced = LocalReducedMotion.current
    val n = ui.lines.size + if (ui.heard.isNotEmpty()) 1 else 0
    LaunchedEffect(n, ui.lines.lastOrNull()?.text?.length, ui.heard.length) {
        if (n > 0) { if (reduced) list.scrollToItem(n - 1) else list.animateScrollToItem(n - 1) }
    }
    LazyColumn(modifier, state = list, contentPadding = PaddingValues(vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        itemsIndexed(ui.lines) { _, l -> Bubble(l) }
        if (ui.heard.isNotEmpty()) item(key = "heard") { Bubble(CallLine("heard", ui.heard)) }
    }
}

@Composable
private fun Bubble(l: CallLine) {
    val cs = MaterialTheme.colorScheme
    if (l.who == "sys") {
        Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            Surface(shape = CircleShape, color = cs.tertiaryContainer.copy(alpha = 0.85f), contentColor = cs.onTertiaryContainer) {
                Text(l.text, style = MaterialTheme.typography.labelMedium, textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 12.dp, vertical = 5.dp))
            }
        }
        return
    }
    val mine = l.who == "me" || l.who == "heard"
    val shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp, bottomEnd = if (mine) 6.dp else 22.dp, bottomStart = if (mine) 22.dp else 6.dp)
    val bg = if (mine) cs.secondaryContainer else cs.primaryContainer
    val fg = if (mine) cs.onSecondaryContainer else cs.onPrimaryContainer
    Box(Modifier.fillMaxWidth(), contentAlignment = if (mine) Alignment.CenterEnd else Alignment.CenterStart) {
        Surface(
            shape = shape,
            color = if (l.who == "heard") bg.copy(alpha = 0.55f) else bg,
            contentColor = fg,
            modifier = Modifier.widthIn(max = 480.dp).padding(start = if (mine) 40.dp else 0.dp, end = if (mine) 0.dp else 40.dp),
        ) {
            Text(l.text, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp))
        }
    }
}

/** Turn by turn's Talk and the live call's Interrupt, and the microphone: its level and the mic gate (folded away until
 *  you open it), in a floating card above the bar. */
@Composable
private fun Controls(ui: CallUi, act: CallActions, compact: Boolean = false) {
    if (!ui.talkShown && !ui.interrupt && !ui.gateShown) return
    val cs = MaterialTheme.colorScheme
    var tuning by remember { mutableStateOf(false) }
    Surface(
        shape = MaterialTheme.shapes.extraLarge,
        color = cs.surfaceContainerHigh.copy(alpha = 0.92f),
        contentColor = cs.onSurface,
        tonalElevation = 6.dp,
        shadowElevation = 6.dp,
        modifier = Modifier.widthIn(max = 560.dp).fillMaxWidth().padding(bottom = 10.dp),
    ) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (ui.talkShown) {
                val listening = ui.talkState == "listening"
                Button(
                    onClick = { act.press("talk") }, enabled = !ui.talkOff, shapes = ButtonDefaults.shapes(),
                    modifier = Modifier.fillMaxWidth().height(72.dp),
                    colors = if (listening) ButtonDefaults.buttonColors(containerColor = cs.tertiary, contentColor = cs.onTertiary) else ButtonDefaults.buttonColors(),
                ) {
                    Icon(painterResource(R.drawable.ic_chat_mic), contentDescription = null, modifier = Modifier.size(24.dp))
                    Spacer(Modifier.size(8.dp))
                    Text(ui.talkLabel, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
            if (ui.interrupt) {
                FilledTonalButton(onClick = { act.press("int") }, shapes = ButtonDefaults.shapes(), modifier = Modifier.fillMaxWidth().height(56.dp)) {
                    Text("Interrupt", style = MaterialTheme.typography.titleMedium)
                }
            }
            if (ui.gateShown) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(painterResource(if (ui.muted) R.drawable.ic_mic_off else R.drawable.ic_chat_mic), contentDescription = null, tint = cs.onSurfaceVariant, modifier = Modifier.size(20.dp))
                    val w by animateFloatAsState(if (ui.muted) 0f else ui.level, tween(140), label = "level")
                    Box(
                        Modifier.padding(horizontal = 12.dp).weight(1f).height(8.dp).clip(CircleShape).background(cs.surfaceContainerHighest)
                            .semantics { contentDescription = if (ui.open) "Your voice is going through" else "Listening" },
                    ) {
                        Box(Modifier.fillMaxHeight().fillMaxWidth(w).clip(CircleShape).background(if (ui.open) cs.primary else cs.outline))
                    }
                    TextButton(onClick = { tuning = !tuning }, shapes = ButtonDefaults.shapes()) {
                        Text("Mic gate: ${ui.gateLabel}", style = MaterialTheme.typography.labelLarge, maxLines = 1)
                    }
                }
                AnimatedVisibility(tuning) {
                    var g by remember { mutableFloatStateOf(ui.gate) }
                    LaunchedEffect(ui.gate) { g = ui.gate }
                    Column {
                        Slider(
                            value = g,
                            onValueChange = { v -> g = Math.round(v * 5f) / 5f; act.gate(g) },
                            valueRange = 0.6f..3f,
                            steps = 11,
                        )
                        if (!compact) { // a phone on its side has no room for it
                            Text(
                                "Higher needs a louder voice, so a noisy room doesn't cut in; lower lets a quiet voice through.",
                                style = MaterialTheme.typography.bodySmall, color = cs.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
    }
}

/** A bar button's face: its icon over its word, so the three fit side by side on any phone (a word beside the icon got
 *  cut short on narrow ones). */
@Composable
private fun Face(icon: Int, label: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(painterResource(icon), contentDescription = null, modifier = Modifier.size(24.dp))
        Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 2.dp))
    }
}

/** The floating bar: Mute, Speaker and Hang up while the call is on; Close and the page's Call or Answer before it. */
@Composable
private fun Bar(ui: CallUi, act: CallActions) {
    val cs = MaterialTheme.colorScheme
    Surface(
        shape = CircleShape,
        color = cs.surfaceContainerHigh.copy(alpha = 0.92f),
        contentColor = cs.onSurface,
        tonalElevation = 6.dp,
        shadowElevation = 6.dp,
        modifier = Modifier.widthIn(max = 560.dp).fillMaxWidth(),
    ) {
        Row(Modifier.padding(8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            val h = Modifier.weight(1f).height(72.dp)
            val pad = PaddingValues(horizontal = 8.dp, vertical = 6.dp)
            if (ui.inCall) {
                if (ui.muteShown) {
                    ToggleButton(checked = ui.muted, onCheckedChange = { act.press("mute") }, modifier = h, contentPadding = pad) {
                        Face(if (ui.muted) R.drawable.ic_mic_off else R.drawable.ic_chat_mic, if (ui.muted) "Muted" else "Mute")
                    }
                }
                if (ui.outShown) {
                    ToggleButton(checked = ui.speaker, onCheckedChange = { act.press("out") }, modifier = h, contentPadding = pad) {
                        Face(if (ui.speaker) R.drawable.ic_volume_up else R.drawable.ic_phone_in_talk, "Speaker")
                    }
                }
                Button(
                    onClick = { act.hangUp() }, shapes = ButtonDefaults.shapes(), modifier = h, contentPadding = pad,
                    colors = ButtonDefaults.buttonColors(containerColor = cs.error, contentColor = cs.onError),
                ) { Face(R.drawable.ic_call_end, "Hang up") }
            } else {
                FilledTonalButton(onClick = { act.close() }, shapes = ButtonDefaults.shapes(), modifier = h, contentPadding = pad) {
                    Face(R.drawable.ic_chat_close, "Close")
                }
                if (!ui.callOff && ui.callLabel.isNotBlank()) {
                    Button(onClick = { act.press("call") }, shapes = ButtonDefaults.shapes(), modifier = h, contentPadding = pad) {
                        Face(R.drawable.ic_call, ui.callLabel)
                    }
                }
            }
        }
    }
}

@Composable
private fun Ringing(
    a: ComponentActivity,
    who: String,
    why: String,
    declineLabel: String,
    laterLabel: String,
    canAnswer: Boolean,
    onDecline: Runnable,
    onLater: Runnable,
    onAnswer: Runnable,
) {
    val cs = MaterialTheme.colorScheme
    val reduced = LocalReducedMotion.current
    Box(Modifier.fillMaxSize().background(cs.background)) {
        Sky(a, strength = { 0.6f }, scroll = { 0f }, modifier = Modifier.fillMaxSize())
        Column(
            Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars).padding(horizontal = 24.dp, vertical = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.weight(1f))
            // the badge turns slowly and breathes while it rings
            val t = rememberInfiniteTransition(label = "ring")
            val turn by t.animateFloat(0f, 360f, infiniteRepeatable(tween(12_000, easing = LinearEasing)), label = "turn")
            val breathe by t.animateFloat(1f, 1.08f, infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse), label = "breathe")
            Box(
                Modifier.size(132.dp)
                    .graphicsLayer {
                        if (!reduced) {
                            rotationZ = turn
                            scaleX = breathe
                            scaleY = breathe
                        }
                    }
                    .clip(MaterialShapes.Cookie9Sided.toShape()).background(cs.primaryContainer),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    painterResource(R.drawable.ic_stat), contentDescription = null, tint = cs.onPrimaryContainer,
                    modifier = Modifier.size(48.dp).graphicsLayer { if (!reduced) rotationZ = -turn },
                )
            }
            Text(
                who, style = MaterialTheme.typography.displaySmallEmphasized, color = cs.onBackground, textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 28.dp),
            )
            if (why.isNotEmpty()) {
                Text(
                    why, style = MaterialTheme.typography.titleLarge, color = cs.onSurfaceVariant, textAlign = TextAlign.Center,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
            Spacer(Modifier.weight(1f))
            Surface(
                shape = CircleShape,
                color = cs.surfaceContainerHigh.copy(alpha = 0.92f),
                contentColor = cs.onSurface,
                tonalElevation = 6.dp,
                shadowElevation = 6.dp,
                modifier = Modifier.widthIn(max = 560.dp).fillMaxWidth(),
            ) {
                Row(Modifier.padding(8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    // icon over word (0.8.16): a word beside the icon was cut short on narrow phones ("An" for Answer)
                    val h = Modifier.weight(1f).height(72.dp)
                    val pad = PaddingValues(horizontal = 8.dp, vertical = 6.dp)
                    Button(
                        onClick = { onDecline.run() }, shapes = ButtonDefaults.shapes(), modifier = h, contentPadding = pad,
                        colors = ButtonDefaults.buttonColors(containerColor = cs.error, contentColor = cs.onError),
                    ) { Face(R.drawable.ic_call_end, declineLabel) }
                    FilledTonalButton(onClick = { onLater.run() }, shapes = ButtonDefaults.shapes(), modifier = h, contentPadding = pad) {
                        Face(R.drawable.ic_clock, laterLabel)
                    }
                    if (canAnswer) {
                        Button(onClick = { onAnswer.run() }, shapes = ButtonDefaults.shapes(), modifier = h, contentPadding = pad) {
                            Face(R.drawable.ic_call, "Answer")
                        }
                    }
                }
            }
        }
    }
}
