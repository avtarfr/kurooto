package io.github.avtarfr.kurooto

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

/** The Chat pane (0.8.10; owned by the app-chat part of the build): the sessions on a rail beside the thread, with the
 *  navigation folded into the rail's foot (`KNav(vertical = true)`). This stub is the contract: its signature stays. */
@Composable
fun ChatPane(a: MainActivity, ui: HomeState, room: PaddingValues) {
    Box(Modifier.fillMaxSize().padding(room)) {
        Text("Chat", Modifier.align(Alignment.Center))
        KNav(a, ui, vertical = true, modifier = Modifier.align(Alignment.BottomStart))
    }
}

/** Chat's own settings, shown by the Settings pane in its "Chat" group (owned by the app-chat part). */
@Composable
fun ChatSettings(a: MainActivity) {
}
