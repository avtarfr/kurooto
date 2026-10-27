package io.github.avtarfr.kurooto

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier

// 0.8.10: the Views pane (Being · Systems · Notes). Owned by the being part of the 0.8.10 build; the shell only calls it.
/** The Views tab (0.8.0): Systems and the Notes map in the shut-in WebView of ViewsPane, inside this screen so the bar stays. It
 *  fetches while the tab is showing and the screen is in front, and stops otherwise. */
@Composable
fun ViewsTab(a: MainActivity, ui: HomeState, room: PaddingValues) {
    val pane = remember { ViewsPane(a, null, ui.demo, null) }
    DisposableEffect(pane) {
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
    androidx.compose.ui.viewinterop.AndroidView(
        factory = { pane.build() },
        modifier = Modifier.fillMaxSize().padding(room).statusBarsPadding(),
    )
}

