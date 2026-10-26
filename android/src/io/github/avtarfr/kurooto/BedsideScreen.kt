package io.github.avtarfr.kurooto

import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.displayCutout
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Bedside mode's screen (0.8.7: Compose, Material 3 Expressive; until 0.8.6 framework views). BedsideActivity keeps every
 * rule (the clock's minute, brightness and colours by the hour from Dock, what's coming, the lock screen, opening by itself)
 * and writes what to show into [BedsideState]; this only draws it: the big clock, the date, the next alarm, the calls due
 * next in a floating card, the waiting count as a pill (tap: Inbox), the Talk button (an expressive pill that morphs when
 * pressed), the status line, and Chat and Close in a floating bar. Always on black. From 20:00 to 07:00 everything takes
 * Dock's warm inks (no blue at night, the cards barely there); in the daytime the Talk button and cards take the app's
 * colours (Vivid or Calm, as the Phone tab's Look says).
 */
class BedsideState {
    var clock by mutableStateOf("")
    var date by mutableStateOf("")
    var alarm by mutableStateOf("")
    var calls by mutableStateOf<List<String>>(emptyList())
    var waiting by mutableStateOf("")
    var status by mutableStateOf("")
    var talk by mutableStateOf("")
    var talkEnabled by mutableStateOf(true)
    var ink by mutableStateOf(0xFFF2EEE8.toInt())
    var dim by mutableStateOf(0xFF95A682.toInt())
    var night by mutableStateOf(false)
}

object BedsideScreen {
    /** Draw `a`'s screen from `s` (once, in onCreate). */
    @JvmStatic
    fun show(a: BedsideActivity, s: BedsideState) {
        a.setContent { KurootoTheme(forceDark = true) { Bedside(a, s) } }
    }
}

@Composable
private fun Bedside(a: BedsideActivity, s: BedsideState) {
    val ink = Color(s.ink)
    val dim = Color(s.dim)
    val cs = MaterialTheme.colorScheme
    // the cards and the bar: a breath of the ink at night, the scheme's container (a little translucent) by day
    val card = if (s.night) ink.copy(alpha = 0.07f) else cs.surfaceContainerHigh.copy(alpha = 0.7f)
    val none = remember { MutableInteractionSource() }
    val conf = LocalConfiguration.current
    // as big as fits: a third of the width, under 40% of the height, 56 to 160
    val clockSp = maxOf(56f, minOf(160f, minOf(conf.screenWidthDp / 3.3f, conf.screenHeightDp / 2.6f)))
    Box(
        Modifier.fillMaxSize().background(Color.Black)
            .clickable(interactionSource = none, indication = null) { a.tapped() }, // a tap brightens it for 15 s
    ) {
        Column(
            Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.displayCutout).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.weight(1f))
            Text(
                s.clock, color = ink, fontSize = clockSp.sp, lineHeight = clockSp.sp, fontWeight = FontWeight.Light,
                textAlign = TextAlign.Center, maxLines = 1,
            )
            Text(s.date, color = dim, fontSize = 18.sp, textAlign = TextAlign.Center)
            if (s.alarm.isNotEmpty()) {
                Text(s.alarm, color = ink, fontSize = 20.sp, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 16.dp))
            }
            if (s.calls.isNotEmpty()) {
                Surface(
                    shape = MaterialTheme.shapes.extraLarge, color = card, contentColor = dim,
                    modifier = Modifier.padding(top = 16.dp).widthIn(max = 520.dp),
                ) {
                    Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        s.calls.forEach {
                            Text(it, color = dim, fontSize = 17.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center,
                                modifier = Modifier.fillMaxWidth())
                        }
                    }
                }
            }
            if (s.waiting.isNotEmpty()) {
                Surface(onClick = { a.openInbox() }, shape = CircleShape, color = card, contentColor = dim, modifier = Modifier.padding(top = 12.dp)) {
                    Text(s.waiting, color = dim, fontSize = 16.sp, modifier = Modifier.padding(horizontal = 18.dp, vertical = 10.dp))
                }
            }
            Spacer(Modifier.weight(1f))
            val fill = if (s.night) Color(0xFF2A1408) else cs.primary
            val text = if (s.night) ink else cs.onPrimary
            Button(
                onClick = { a.talk() },
                enabled = s.talkEnabled,
                shapes = ButtonDefaults.shapes(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = fill, contentColor = text,
                    disabledContainerColor = fill.copy(alpha = 0.5f), disabledContentColor = text.copy(alpha = 0.6f),
                ),
                modifier = Modifier.padding(top = 16.dp).fillMaxWidth().widthIn(max = 560.dp).heightIn(min = 80.dp),
            ) {
                Icon(painterResource(R.drawable.ic_call), contentDescription = null, modifier = Modifier.size(28.dp))
                Spacer(Modifier.width(12.dp))
                Text(s.talk, fontSize = 22.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Text(
                s.status, color = dim, fontSize = 14.sp, textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 8.dp).fillMaxWidth(),
            )
            Surface(shape = CircleShape, color = card, modifier = Modifier.padding(top = 8.dp).widthIn(max = 360.dp).fillMaxWidth()) {
                Row(Modifier.padding(4.dp)) {
                    TextButton(onClick = { a.openChat() }, shapes = ButtonDefaults.shapes(), modifier = Modifier.weight(1f)) {
                        Text("Chat", color = dim, fontSize = 16.sp)
                    }
                    TextButton(onClick = { a.finish() }, shapes = ButtonDefaults.shapes(), modifier = Modifier.weight(1f)) {
                        Text("Close", color = dim, fontSize = 16.sp)
                    }
                }
            }
        }
    }
}
