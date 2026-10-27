package io.github.avtarfr.kurooto

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.ButtonGroup
import androidx.compose.material3.ButtonGroupDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.ToggleButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

// 0.8.10: the Views pane (Being · Brain · Systems · Notes). Owned by the being part of the 0.8.10 build; the shell only calls it.
/** The Views pane: an Expressive connected button group picks the drawing, and ViewsPane's shut-in WebView draws it:
 *  the being (the dashboard's own being.js, set for touch), the Brain console, Systems, or the Notes map. It fetches
 *  while the pane is showing and the screen is in front, and stops otherwise. Back goes up one level inside the being
 *  (a part → its organ → the whole body) before it leaves the pane. */
@Composable
fun ViewsTab(a: MainActivity, ui: HomeState, room: PaddingValues) {
    val pane = remember { ViewsPane(a, null, ui.demo, null) }
    var mode by remember { mutableStateOf(pane.startMode()) }
    var beingOk by remember { mutableStateOf(pane.beingOk()) }
    var depth by remember { mutableIntStateOf(0) }
    val brainReady = remember { brainConsoleShipped(a) }
    DisposableEffect(pane) {
        pane.setWatcher { beingOk = pane.beingOk(); depth = pane.depth() }
        val obs = androidx.lifecycle.LifecycleEventObserver { _, e ->
            if (e == androidx.lifecycle.Lifecycle.Event.ON_RESUME) pane.resume() else if (e == androidx.lifecycle.Lifecycle.Event.ON_PAUSE) pane.pause()
        }
        a.lifecycle.addObserver(obs)
        if (a.lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.RESUMED)) pane.resume()
        onDispose {
            a.lifecycle.removeObserver(obs)
            pane.pause()
            pane.destroy()
        }
    }
    BackHandler(enabled = mode == "being" && beingOk && depth > 0) { pane.back() }
    Column(Modifier.fillMaxSize().padding(room).statusBarsPadding()) {
        ViewsChoice(mode) { m ->
            mode = m
            depth = 0
            if (m != "brain" || brainReady) pane.show(m)
        }
        Box(Modifier.fillMaxWidth().weight(1f)) {
            androidx.compose.ui.viewinterop.AndroidView(factory = { pane.page() }, modifier = Modifier.fillMaxSize())
            when {
                mode == "brain" && !brainReady -> Note(
                    "The Brain console comes with this update.",
                    "When it's here, this shows what the Brain is doing and why, live and read-only.",
                    cover = true,
                )
                mode == "being" && !beingOk -> Note(
                    "This phone can't draw the being.",
                    "It needs WebGL 2 and a recent Android System WebView (update it from the Play Store). Here's Systems instead.",
                    cover = false,
                )
            }
        }
    }
}

/** Being · Brain · Systems · Notes: one row of connected toggle buttons; the one showing is filled, a pressed one widens. */
@Composable
private fun ViewsChoice(mode: String, pick: (String) -> Unit) {
    val items = listOf("being" to "Being", "brain" to "Brain", "systems" to "Systems", "notes" to "Notes")
    ButtonGroup(
        overflowIndicator = {},
        horizontalArrangement = Arrangement.spacedBy(ButtonGroupDefaults.ConnectedSpaceBetween),
        modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 8.dp),
    ) {
        items.forEachIndexed { i, (id, label) ->
            customItem(
                buttonGroupContent = {
                    val src = remember { MutableInteractionSource() }
                    ToggleButton(
                        checked = mode == id,
                        onCheckedChange = { pick(id) },
                        shapes = when (i) {
                            0 -> ButtonGroupDefaults.connectedLeadingButtonShapes()
                            items.lastIndex -> ButtonGroupDefaults.connectedTrailingButtonShapes()
                            else -> ButtonGroupDefaults.connectedMiddleButtonShapes()
                        },
                        interactionSource = src,
                        contentPadding = PaddingValues(horizontal = 8.dp),
                        modifier = Modifier.weight(1f).animateWidth(src).semantics { role = Role.RadioButton },
                    ) { Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                },
                menuContent = {},
            )
        }
    }
}

/** A plain note over the drawing: cover hides it (nothing to show yet), else it floats at the top of what's shown. */
@Composable
private fun Note(title: String, body: String, cover: Boolean) {
    Box(
        Modifier.fillMaxSize().then(if (cover) Modifier.background(MaterialTheme.colorScheme.surface) else Modifier),
        contentAlignment = if (cover) Alignment.Center else Alignment.TopCenter,
    ) {
        Surface(
            color = MaterialTheme.colorScheme.surfaceContainerHigh,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
        ) {
            Column(Modifier.padding(20.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp))
            }
        }
    }
}

/** The Brain console's drawing code is in this app (the brain-console part's static/views/brainconsole.js). */
private fun brainConsoleShipped(a: MainActivity): Boolean =
    try { a.assets.list("views")?.contains("brainconsole.js") == true } catch (e: Exception) { false }
