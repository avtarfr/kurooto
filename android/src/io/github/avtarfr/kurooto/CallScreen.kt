package io.github.avtarfr.kurooto

import android.view.View
import android.view.ViewGroup
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.toShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView

/**
 * The call screen (0.8.7: Compose, Material 3 Expressive; Phone tab → Switches → "New call screen", on by default; off,
 * CallActivity builds the framework screen from before 0.8.7). CallActivity keeps all of a call's plumbing (the intents, the
 * lock screen, audio routing, the proximity sensor, the WebView and its KurootoApp bridge, the phone's own speech) and
 * asks this for what to draw:
 * - [ringing]: over the app's sky, always dark, a slowly turning cookie badge (still with "Remove animations"), who's
 *   calling and why, and Decline / Later / Answer (this phone's alarm: Stop / Snooze) as big expressive buttons in a
 *   floating bar at the bottom;
 * - [page]: the call page (the WebView, in its container) edge to edge on the call page's own background, kept clear of
 *   the status and navigation bars.
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

    /** The call page: `page` (the WebView's container, made once by CallActivity) moved into this screen. */
    @JvmStatic
    fun page(a: ComponentActivity, page: View) {
        a.setContent {
            Box(Modifier.fillMaxSize().background(colorResource(R.color.k_call_bg))) {
                AndroidView(
                    factory = { (page.parent as? ViewGroup)?.removeView(page); page },
                    modifier = Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars),
                )
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
                    val h = Modifier.weight(1f).height(64.dp)
                    val text = MaterialTheme.typography.titleMedium
                    Button(
                        onClick = { onDecline.run() }, shapes = ButtonDefaults.shapes(), modifier = h,
                        colors = ButtonDefaults.buttonColors(containerColor = cs.error, contentColor = cs.onError),
                    ) { Text(declineLabel, style = text, maxLines = 1) }
                    FilledTonalButton(onClick = { onLater.run() }, shapes = ButtonDefaults.shapes(), modifier = h) {
                        Text(laterLabel, style = text, maxLines = 1)
                    }
                    if (canAnswer) {
                        Button(onClick = { onAnswer.run() }, shapes = ButtonDefaults.shapes(), modifier = h) {
                            Icon(painterResource(R.drawable.ic_call), contentDescription = null, modifier = Modifier.size(22.dp))
                            Spacer(Modifier.size(6.dp))
                            Text("Answer", style = text, maxLines = 1)
                        }
                    }
                }
            }
        }
    }
}
