package io.github.avtarfr.kurooto

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource

/** The app's panes (0.8.10): it opens on Chat. HomeState.pane holds the one showing. */
enum class Pane(val label: String, val icon: Int) {
    CHAT("Chat", R.drawable.ic_nav_inbox),
    TODAY("Today", R.drawable.ic_nav_today),
    ALARMS("Alarms", R.drawable.ic_nav_phone),
    VIEWS("Views", R.drawable.ic_nav_views),
    SETTINGS("Settings", R.drawable.ic_nav_phone),
}

/** The navigation between the panes (owned by the shell part of the 0.8.10 build): a horizontal floating toolbar on
 *  every pane but Chat, where Chat's rail shows it upright (`vertical`), and the two morph into each other. This stub
 *  is the contract: its signature stays; the shell part replaces the body. */
@Composable
fun KNav(a: MainActivity, ui: HomeState, vertical: Boolean, modifier: Modifier = Modifier) {
    val items: @Composable () -> Unit = {
        Pane.entries.forEach { p -> IconButton(onClick = { ui.pane = p }) { Icon(painterResource(p.icon), contentDescription = p.label) } }
    }
    if (vertical) Column(modifier) { items() } else Row(modifier) { items() }
}
