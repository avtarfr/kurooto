package io.github.avtarfr.kurooto

import android.content.Intent
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.FloatingToolbarDefaults
import androidx.compose.material3.HorizontalFloatingToolbar
import androidx.compose.material3.Surface
import androidx.compose.ui.draw.clip
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ShortNavigationBar
import androidx.compose.material3.ShortNavigationBarItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.TwoRowsTopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.PullToRefreshDefaults
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.getValue
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

/** The main screen: pairing, or the tabs. */
@Composable
fun Home(a: MainActivity, ui: HomeState) {
    if (ui.paired || ui.demo) Tabs(a, ui) else Pairing(a, ui)
}

/** A navigation bar destination: a page here (`page`: 0 Today, 1 Inbox, 2 Phone, as HomeState.tab), or another
 *  screen it opens (`opens`, e.g. a WebView activity for the dashboard's SYSTEMS view and the notes map). The bar
 *  takes up to five; a fourth goes in its place in this list (Today, Inbox, Views, Phone). */
private class Tab(val label: String, val icon: Int, val page: Int, val opens: Class<*>? = null)

private val TABS = listOf(
    Tab("Today", R.drawable.ic_nav_today, 0),
    Tab("Inbox", R.drawable.ic_nav_inbox, 1),
    // your computer's Systems and Notes map, drawn by the dashboard's own code (0.7.0), now a page of this screen (0.8.0: the bar
    // stays); ViewsPane switches between the two at its top and opens on the one you looked at last
    Tab("Views", R.drawable.ic_nav_views, 3),
    Tab("Phone", R.drawable.ic_nav_phone, 2),
)

/** The navigation bar (Material 3 Expressive's short bar: icon over label, a badge on Inbox) and the selected tab
 *  above it. Switching is a quick cross-fade from the motion scheme (none with "Remove animations"); each tab keeps
 *  where it was scrolled to; Back on Inbox or Phone goes to Today first (with the predictive back gesture). */
@Composable
private fun Tabs(a: MainActivity, ui: HomeState) {
    val reduced = LocalReducedMotion.current
    val holder = rememberSaveableStateHolder()
    val waiting = ui.waiting?.size ?: 0
    val floating = Prefs.floatingBar(a)
    val fade = MaterialTheme.motionScheme.fastEffectsSpec<Float>()
    BackHandler(enabled = ui.tab != 0) { ui.tab = 0 }
    // the sky: strongest behind Today, quieter behind Inbox and Phone; its parallax follows Today's scroll
    val strength by animateFloatAsState(if (ui.tab == 0) 1f else 0.35f, MaterialTheme.motionScheme.slowEffectsSpec(), label = "sky")
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Sky(a, strength = { strength }, scroll = { ui.todayScroll * ((strength - 0.35f) / 0.65f) }, modifier = Modifier.fillMaxSize(), fixedHour = ui.demoHour)
        Scaffold(
            containerColor = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onBackground, // a transparent container has no "on" colour of its own
            contentWindowInsets = WindowInsets(0),
            bottomBar = {
                if (!floating) DockedBar(a, ui, waiting)
            },
        ) { pad ->
            Box(Modifier.fillMaxSize()) {
                // the page, clear of the bar: its own height when docked; room for the floating toolbar over the content
                val room = if (floating) PaddingValues(bottom = pad.calculateBottomPadding() + FLOAT_ROOM) else pad
                AnimatedContent(
                    targetState = ui.tab,
                    transitionSpec = { if (reduced) EnterTransition.None togetherWith ExitTransition.None else fadeIn(fade) togetherWith fadeOut(fade) },
                    label = "tab",
                ) { tab ->
                    holder.SaveableStateProvider(tab) {
                        when (tab) {
                            0 -> TodayPage(a, ui, room)
                            1 -> InboxPage(a, ui, room)
                            3 -> ViewsPage(a, ui, room)
                            else -> PhonePage(a, ui, room)
                        }
                    }
                }
                if (floating) FloatingBar(a, ui, waiting, Modifier.align(Alignment.BottomCenter))
            }
        }
    }
}

/** The Views tab (0.8.0): Systems and the Notes map in the shut-in WebView of ViewsPane, inside this screen so the bar stays. It
 *  fetches while the tab is showing and the screen is in front, and stops otherwise. */
@Composable
private fun ViewsPage(a: MainActivity, ui: HomeState, room: PaddingValues) {
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

/** How much room a page leaves at its end for the floating toolbar (its height plus the gap below it). */
private val FLOAT_ROOM = 104.dp

private fun openTab(a: MainActivity, ui: HomeState, t: Tab) {
    if (t.opens != null) a.startActivity(Intent(a, t.opens).putExtra("demo", ui.demo)) else ui.tab = t.page
}

/** Material 3 Expressive's floating toolbar (0.7.5): a rounded pill that floats above the page, the sky showing around it,
 *  holding the four tabs. The tab you're on shows its label in a coloured pill; the others are icons. Docked: Look → Bar. */
@Composable
private fun FloatingBar(a: MainActivity, ui: HomeState, waiting: Int, modifier: Modifier = Modifier) {
    HorizontalFloatingToolbar(
        expanded = true,
        modifier = modifier.navigationBarsPadding().padding(bottom = 12.dp),
        colors = FloatingToolbarDefaults.vibrantFloatingToolbarColors(),
        content = {
            TABS.forEach { t ->
                val on = t.opens == null && ui.tab == t.page
                Row(
                    Modifier.clip(CircleShape).background(if (on) MaterialTheme.colorScheme.primary else Color.Transparent)
                        .clickable { openTab(a, ui, t) }.padding(horizontal = if (on) 16.dp else 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    BadgedBox(badge = { if (t.page == 1 && t.opens == null && waiting > 0) Badge { Text(if (waiting > 99) "99+" else "$waiting") } }) {
                        Icon(
                            painterResource(t.icon), contentDescription = t.label,
                            tint = if (on) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (on) {
                        Spacer(Modifier.width(8.dp))
                        Text(t.label, color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.labelLarge)
                    }
                }
            }
        },
    )
}

/** The docked navigation bar (Look → Bar: Docked): Expressive's short bar, tonal and nearly opaque (a hint of the sky, never
 *  the page scrolling under it). */
@Composable
private fun DockedBar(a: MainActivity, ui: HomeState, waiting: Int) {
    ShortNavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.97f)) {
        TABS.forEach { t ->
            ShortNavigationBarItem(
                selected = t.opens == null && ui.tab == t.page,
                onClick = { openTab(a, ui, t) },
                icon = {
                    BadgedBox(badge = { if (t.page == 1 && t.opens == null && waiting > 0) Badge { Text(if (waiting > 99) "99+" else "$waiting") } }) {
                        Icon(painterResource(t.icon), contentDescription = null)
                    }
                },
                label = { Text(t.label) },
            )
        }
    }
}

/**
 * One tab's page: a two-row top app bar sized as the large flexible one (Material 3 Expressive: a big emphasized
 * title and a subtitle that collapse as the page scrolls; `hero`: a bigger title, Today's date), pull to refresh
 * with the expressive loading indicator, and the page's column, clear of the navigation bar (`outer`) and the
 * keyboard, at most 640dp wide (tablets, landscape). `collapsing` false: the bar stays open.
 */
@Composable
fun TabPage(
    a: MainActivity,
    ui: HomeState,
    outer: PaddingValues,
    title: String,
    subtitle: String?,
    actions: @Composable RowScope.() -> Unit = {},
    hero: Boolean = false,
    onScroll: ((Float) -> Unit)? = null,
    collapsing: Boolean = true,
    content: @Composable ColumnScope.() -> Unit,
) {
    val bar = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(canScroll = { collapsing })
    val state = rememberPullToRefreshState()
    val bottom = outer.calculateBottomPadding()
    val scroll = rememberScrollState()
    if (onScroll != null) LaunchedEffect(scroll) { snapshotFlow { scroll.value.toFloat() }.collect { onScroll(it) } }
    Box(Modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.nestedScroll(bar.nestedScrollConnection),
            containerColor = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onBackground,
            contentWindowInsets = WindowInsets(0),
            topBar = {
                // the large flexible app bar's layout and heights, with the emphasized display type while expanded
                TwoRowsTopAppBar(
                    title = { expanded ->
                        if (expanded) {
                            val t = MaterialTheme.typography
                            Text(title, maxLines = 1, style = if (hero) t.displayMediumEmphasized else t.displaySmallEmphasized)
                        }
                        else Text(title, maxLines = 1)
                    },
                    subtitle = subtitle?.let { { _ -> Text(it, maxLines = 1) } },
                    collapsedHeight = TopAppBarDefaults.LargeAppBarCollapsedHeight,
                    expandedHeight = (if (subtitle != null) TopAppBarDefaults.LargeFlexibleAppBarWithSubtitleExpandedHeight
                    else TopAppBarDefaults.LargeFlexibleAppBarWithoutSubtitleExpandedHeight) + if (hero) 20.dp else 0.dp,
                    actions = actions,
                    scrollBehavior = bar,
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Transparent,
                        scrolledContainerColor = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.92f),
                    ),
                )
            },
        ) { inner ->
            PullToRefreshBox(
                isRefreshing = ui.refreshing,
                onRefresh = { a.pull() },
                state = state,
                modifier = Modifier.fillMaxSize().padding(inner),
                indicator = {
                    PullToRefreshDefaults.LoadingIndicator(state = state, isRefreshing = ui.refreshing, modifier = Modifier.align(Alignment.TopCenter))
                },
            ) {
                Column(
                    Modifier
                        .align(Alignment.TopCenter)
                        .widthIn(max = 640.dp)
                        .fillMaxSize()
                        .consumeWindowInsets(PaddingValues(bottom = bottom))
                        .imePadding()
                        .verticalScroll(scroll)
                        .padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = bottom + 32.dp),
                ) { content() }
            }
        }
    }
}

/** First run: pair this phone with Kurooto on your computer (the QR code or the link). */
@Composable
private fun Pairing(a: MainActivity, ui: HomeState) {
    var link by rememberSaveable { mutableStateOf("") }
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Sky(a, strength = { 1f }, scroll = { 0f }, modifier = Modifier.fillMaxSize(), fixedHour = ui.demoHour)
        // the bar stays open here: the page is short, and the keyboard would leave it half folded
        TabPage(a, ui, WindowInsets.navigationBars.asPaddingValues(), "Kurooto", "Pair this phone", collapsing = false) {
            ShapeBadge(MaterialShapes.Cookie9Sided, MaterialTheme.colorScheme.primaryContainer, Modifier.padding(top = 8.dp, bottom = 20.dp), size = 96) {
                Icon(
                    painterResource(R.drawable.ic_call),
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onPrimaryContainer,
                    modifier = Modifier.size(40.dp),
                )
            }
            Text(
                "Pair this phone with Kurooto on your computer, so it can call you and you can call it.",
                style = MaterialTheme.typography.headlineSmallEmphasized,
            )
            Spacer(Modifier.height(20.dp))
            KCard {
                Text("On your computer", style = MaterialTheme.typography.titleMediumEmphasized, color = MaterialTheme.colorScheme.primary)
                Dim(
                    "Open Kurooto's dashboard → Phone → Pair a phone. Scan the QR code with this phone's camera " +
                        "and tap Pair the app. Or send /phone to your Telegram bot and open the link here.",
                    Modifier.padding(top = 6.dp),
                )
            }
            Heading("Or paste the pairing link")
            OutlinedTextField(
                value = link,
                onValueChange = { link = it },
                placeholder = { Text("https://…/pair#c=…") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, autoCorrectEnabled = false),
                shape = MaterialTheme.shapes.large,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))
            val h = ButtonDefaults.LargeContainerHeight
            Button(
                onClick = { a.pair(link) },
                shapes = ButtonDefaults.shapesFor(h),
                modifier = Modifier.fillMaxWidth().heightIn(min = h),
                contentPadding = ButtonDefaults.contentPaddingFor(h),
            ) { Text("Pair", style = ButtonDefaults.textStyleFor(h)) }
            SaidLine(ui.status)
        }
    }
}
