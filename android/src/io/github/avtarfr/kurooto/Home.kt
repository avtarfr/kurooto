package io.github.avtarfr.kurooto

import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.SharedTransitionLayout
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.SeekableTransitionState
import androidx.compose.animation.core.Transition
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.rememberTransition
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyGridScope
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MaterialExpressiveTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.TwoRowsTopAppBar
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.PullToRefreshDefaults
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CancellationException

/** The main screen: pairing, or the panes. */
@Composable
fun Home(a: MainActivity, ui: HomeState) {
    if (ui.paired || ui.demo) Panes(a, ui) else Pairing(a, ui)
}

/**
 * The panes (0.8.10): Chat, where the app opens, and Today, Alarms, Views and Settings under the floating toolbar (KNav).
 * One SharedTransitionLayout holds them all, so the move between Chat and another pane is one piece: Chat slides out to
 * the left (its rail rows staggered, Modifier.paneStagger) while the next pane comes in from the right and KNav's upright
 * form at the rail's foot morphs into the horizontal bar; back to Chat reverses it. Between the other panes the bar
 * stays and its pill slides; the pages fade through with a slight scale. Every move is the motion scheme's (springs,
 * no durations of our own), and none with "Remove animations". Back from any pane returns to Chat (the predictive back
 * gesture scrubs the move with your thumb); back from Chat leaves the app. Each pane keeps where it was scrolled to.
 */
@Composable
private fun Panes(a: MainActivity, ui: HomeState) {
    val reduced = LocalReducedMotion.current
    val ms = MaterialTheme.motionScheme
    val holder = rememberSaveableStateHolder()
    val tr = rememberBackTransition(ui.pane, Pane.CHAT, ui.pane != Pane.CHAT, "pane") { ui.pane = Pane.CHAT }
    // the sky: strongest behind Today, quieter elsewhere; its parallax follows Today's scroll (read in its draw only)
    val strength by animateFloatAsState(if (ui.pane == Pane.TODAY) 1f else 0.35f, ms.slowEffectsSpec(), label = "sky")
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Sky(a, strength = { strength }, scroll = { ui.todayScroll * ((strength - 0.35f) / 0.65f) }, modifier = Modifier.fillMaxSize(), fixedHour = ui.demoHour)
        SharedTransitionLayout(Modifier.fillMaxSize()) {
            val spatial = ms.defaultSpatialSpec<androidx.compose.ui.unit.IntOffset>()
            tr.AnimatedContent(
                modifier = Modifier.fillMaxSize(),
                contentKey = { it == Pane.CHAT },
                transitionSpec = {
                    when {
                        reduced -> EnterTransition.None togetherWith ExitTransition.None
                        // back to Chat: it comes in from the left, the pane leaves to the right
                        targetState == Pane.CHAT -> slideInHorizontally(spatial) { -it } togetherWith
                            (slideOutHorizontally(spatial) { it } + fadeOut(ms.slowEffectsSpec()))
                        // leaving Chat: it goes out to the left, the pane comes in from the right
                        else -> slideInHorizontally(spatial) { it } togetherWith
                            (slideOutHorizontally(spatial) { -it } + fadeOut(ms.slowEffectsSpec()))
                    } using SizeTransform(clip = false)
                },
            ) { p ->
                CompositionLocalProvider(LocalNavShared provides this@SharedTransitionLayout, LocalNavPane provides this) {
                    if (p == Pane.CHAT) holder.SaveableStateProvider(Pane.CHAT) { ChatPane(a, ui, PaddingValues()) }
                    else Others(a, ui, p, holder)
                }
            }
        }
        if (ui.waitingSheet) WaitingSheet(a, ui)
    }
}

/** Today, Alarms, Views and Settings under the horizontal bar, which stays while they change under it. */
@Composable
private fun Others(a: MainActivity, ui: HomeState, pane: Pane, holder: androidx.compose.runtime.saveable.SaveableStateHolder) {
    val reduced = LocalReducedMotion.current
    val ms = MaterialTheme.motionScheme
    val floating = Prefs.floatingBar(a)
    val nav = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    // the page, clear of the bar: room for the floating toolbar over the content, or the docked bar's height
    val room = PaddingValues(bottom = nav + if (floating) FLOAT_ROOM else DOCK_ROOM)
    Box(Modifier.fillMaxSize()) {
        AnimatedContent(
            targetState = pane,
            transitionSpec = {
                if (reduced) EnterTransition.None togetherWith ExitTransition.None
                else (fadeIn(ms.defaultEffectsSpec()) + scaleIn(ms.fastSpatialSpec(), initialScale = 0.96f)) togetherWith
                    fadeOut(ms.fastEffectsSpec())
            },
            label = "pane",
        ) { p ->
            holder.SaveableStateProvider(p) {
                when (p) {
                    Pane.TODAY -> TodayPane(a, ui, room)
                    Pane.ALARMS -> AlarmsPane(a, ui, room)
                    Pane.VIEWS -> ViewsTab(a, ui, room)
                    else -> SettingsPane(a, ui, room)
                }
            }
        }
        KNav(a, ui, vertical = false, modifier = Modifier.align(Alignment.BottomCenter))
    }
}

/** How much room a page leaves at its end for the floating toolbar (its height plus the gap below it), or the docked bar. */
private val FLOAT_ROOM = 96.dp
private val DOCK_ROOM = 72.dp

/**
 * A transition that follows `target`, and that the predictive back gesture scrubs towards `back` while `enabled` (your
 * thumb moves it; let go and it finishes with `onBack`, or springs back if you cancel). Android 13 and older: a plain
 * back, then the move. The panes (to Chat) and Settings (to its grid) use it.
 */
@Composable
fun <T> rememberBackTransition(target: T, back: T, enabled: Boolean, label: String, onBack: () -> Unit): Transition<T> {
    val state = remember { SeekableTransitionState(target) }
    val reduced = LocalReducedMotion.current
    LaunchedEffect(target) { if (reduced) state.snapTo(target) else state.animateTo(target) }
    PredictiveBackHandler(enabled = enabled) { progress ->
        try {
            progress.collect { e -> if (!reduced) state.seekTo(e.progress, back) }
            onBack()
        } catch (e: CancellationException) {
            state.animateTo(state.currentState)
        }
    }
    return rememberTransition(state, label = label)
}

/** What's waiting for you (Inbox's content) in a sheet over any pane: WaitingBar on Chat, Today's Waiting tile. Drag it
 *  down, tap outside or go back to close it. */
@Composable
private fun WaitingSheet(a: MainActivity, ui: HomeState) {
    val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = false)
    ModalBottomSheet(onDismissRequest = { ui.waitingSheet = false }, sheetState = sheet) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 32.dp),
        ) {
            Text(waitingTitle(ui), style = MaterialTheme.typography.headlineSmallEmphasized, modifier = Modifier.padding(start = 4.dp, bottom = 4.dp))
            InboxContent(a, ui)
        }
    }
}

// ---------------------------------------------------------------------------------------------- the bento panes' kit

/**
 * A bento pane (Today, Alarms, Settings): a two-column grid of rounded tonal cards under a big title, pull to refresh with
 * the expressive loading indicator, clear of the bar (`room`) and of the status bar (a soft scrim over it, so cards
 * scrolling under the clock stay readable), at most 640dp wide.
 */
@Composable
fun PaneGrid(
    a: MainActivity,
    ui: HomeState,
    room: PaddingValues,
    state: LazyGridState = rememberLazyGridState(),
    refresh: Boolean = true,
    onScroll: ((Float) -> Unit)? = null,
    content: LazyGridScope.() -> Unit,
) {
    val pull = rememberPullToRefreshState()
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    if (onScroll != null) LaunchedEffect(state) {
        snapshotFlow { if (state.firstVisibleItemIndex == 0) state.firstVisibleItemScrollOffset.toFloat() else 2000f }.collect { onScroll(it) }
    }
    PullToRefreshBox(
        isRefreshing = ui.refreshing,
        onRefresh = { if (refresh) a.pull() },
        state = pull,
        modifier = Modifier.fillMaxSize(),
        indicator = {
            if (refresh) PullToRefreshDefaults.LoadingIndicator(
                state = pull, isRefreshing = ui.refreshing, modifier = Modifier.align(Alignment.TopCenter).statusBarsPadding(),
            )
        },
    ) {
        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            state = state,
            modifier = Modifier.align(Alignment.TopCenter).widthIn(max = 640.dp).fillMaxSize().imePadding(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = top + 8.dp, bottom = room.calculateBottomPadding() + 24.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            content = content,
        )
        Box(
            Modifier.fillMaxWidth().height(top + 8.dp).background(
                Brush.verticalGradient(listOf(MaterialTheme.colorScheme.background.copy(alpha = 0.85f), Color.Transparent)),
            ),
        )
    }
}

/** A grid item across both columns. */
fun LazyGridScope.wide(key: String, type: String = key, content: @Composable () -> Unit) =
    item(key = key, span = { GridItemSpan(maxLineSpan) }, contentType = type) { content() }

/** A pane's big title (and the line over it, e.g. the month), with what goes at its end. */
fun LazyGridScope.paneTitle(title: String, over: String? = null, actions: @Composable RowScope.() -> Unit = {}) =
    wide("title") {
        Row(Modifier.fillMaxWidth().padding(start = 4.dp, top = 12.dp, bottom = 4.dp), verticalAlignment = Alignment.Bottom) {
            Column(Modifier.weight(1f)) {
                if (over != null) Text(over, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    title,
                    style = if (over != null) MaterialTheme.typography.displayLargeEmphasized else MaterialTheme.typography.displayMediumEmphasized,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            actions()
        }
    }

/** A bento card: Material's extra-large rounded shape in a tonal colour; pressed, it sinks a little (a spring on its
 *  scale, in the draw phase). `onClick` null: not a button. */
@Composable
fun Tile(
    color: Color,
    content: Color,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    border: BorderStroke? = null,
    padding: Dp = 18.dp,
    body: @Composable ColumnScope.() -> Unit,
) {
    val src = remember { MutableInteractionSource() }
    val pressed by src.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.96f else 1f, MaterialTheme.motionScheme.fastSpatialSpec(), label = "press")
    val m = modifier.graphicsLayer { scaleX = scale; scaleY = scale }
    if (onClick != null) {
        Surface(onClick = onClick, shape = TILE, color = color, contentColor = content, border = border, interactionSource = src, modifier = m) {
            Column(Modifier.padding(padding), content = body)
        }
    } else {
        Surface(shape = TILE, color = color, contentColor = content, border = border, modifier = m) { Column(Modifier.padding(padding), content = body) }
    }
}

val TILE = RoundedCornerShape(28.dp)

/** A card's small heading: an icon and a word in capitals ("WAITING"). */
@Composable
fun TileLabel(text: String, icon: Int? = null, color: Color = Color.Unspecified) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        if (icon != null) {
            Icon(painterResource(icon), contentDescription = null, tint = color, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
        }
        Text(
            text.uppercase(),
            style = MaterialTheme.typography.labelLarge.copy(letterSpacing = 1.2.sp),
            color = color,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** A neutral card's colour: the surface container, a little translucent so the sky shows at its edges. */
@Composable
fun tileColor(): Color = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.94f)

// ------------------------------------------------------------------------------------------- the apricot palette

/** Look → Colours → Apricot and plum (0.8.10, the Rail design's palette): its colours are Theme.kt's Palettes.apricot. */
object Apricot {
    const val NAME = "apricot"
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
