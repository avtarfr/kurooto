package io.github.avtarfr.kurooto

import androidx.compose.animation.AnimatedVisibilityScope
import androidx.compose.animation.BoundsTransform
import androidx.compose.animation.EnterExitState
import androidx.compose.animation.SharedTransitionScope
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.AnimationVector
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.TwoWayConverter
import androidx.compose.animation.core.VectorizedFiniteAnimationSpec
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.FloatingToolbarDefaults
import androidx.compose.material3.HorizontalFloatingToolbar
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp

/** The app's panes (0.8.10): it opens on Chat. HomeState.pane holds the one showing. */
enum class Pane(val label: String, val icon: Int) {
    CHAT("Chat", R.drawable.ic_nav_chat),
    TODAY("Today", R.drawable.ic_nav_today),
    ALARMS("Alarms", R.drawable.ic_nav_alarm),
    VIEWS("Views", R.drawable.ic_nav_views),
    SETTINGS("Settings", R.drawable.ic_nav_settings),
}

/**
 * The scopes the shell (Home.kt) hands down for the move between Chat and the other panes: its SharedTransitionLayout,
 * and the AnimatedVisibilityScope of the pane being drawn. KNav morphs between its two forms with them, and
 * [paneStagger] slides a row of Chat's rail out with them. Null outside the shell (another screen drawing KNav): then
 * nothing is shared and nothing moves.
 */
val LocalNavShared = staticCompositionLocalOf<SharedTransitionScope?> { null }
val LocalNavPane = compositionLocalOf<AnimatedVisibilityScope?> { null }

/**
 * The navigation between the panes (0.8.10). Every pane but Chat: a horizontal floating toolbar (Material 3 Expressive's,
 * vibrant colours) with a label under each icon, the open pane in a filled pill that slides to the one you tap; with
 * Look → Floating bar off, the same row docked to the bottom edge. Chat: the upright form, a capsule of the five icons at
 * the foot of its rail (`vertical`). Moving between Chat and another pane, the two forms morph into each other: the
 * capsule is `sharedBounds(key = "knav")` in both, each icon and the pill are shared elements, so the capsule stretches
 * sideways while the icons slide into a row and the labels fade in (and back). "Remove animations": nothing moves.
 * The Chat icon carries a badge: unread messages (HomeState.unread, set by the chat) plus what's waiting for you.
 */
@Composable
fun KNav(a: MainActivity, ui: HomeState, vertical: Boolean, modifier: Modifier = Modifier) {
    val reduced = LocalReducedMotion.current
    val st = if (reduced) null else LocalNavShared.current
    val av = if (reduced) null else LocalNavPane.current
    val spatial = MaterialTheme.motionScheme.defaultSpatialSpec<Rect>()
    val bounds = remember(spatial) { BoundsTransform { _, _ -> spatial } }
    val badge = ui.unread + (ui.waiting?.size ?: 0)
    val fadeInSpec = MaterialTheme.motionScheme.defaultEffectsSpec<Float>()
    val fadeOutSpec = MaterialTheme.motionScheme.slowEffectsSpec<Float>()
    // a part of the bar shared across the move (nothing outside the shell)
    val shared: @Composable Modifier.(String, Float) -> Modifier = { key, z ->
        val m = this
        if (st == null || av == null) m else with(st) {
            m.sharedElement(rememberSharedContentState(key), av, boundsTransform = bounds, zIndexInOverlay = z)
        }
    }
    // the capsule: one shared bounds, the two forms' contents cross-fading inside it (the leaving one more slowly, so
    // the colour under them never thins)
    val capsule: @Composable Modifier.() -> Modifier = {
        val m = this
        if (st == null || av == null) m else with(st) {
            m.sharedBounds(
                rememberSharedContentState("knav"), av,
                enter = fadeIn(fadeInSpec),
                exit = fadeOut(fadeOutSpec),
                boundsTransform = bounds,
                resizeMode = SharedTransitionScope.ResizeMode.RemeasureToBounds,
                zIndexInOverlay = 1f,
                clipInOverlayDuringTransition = OverlayClip(CircleShape),
            )
        }
    }
    if (vertical) RailNav(a, ui, badge, modifier, shared, capsule) else BarNav(a, ui, badge, modifier, shared, capsule)
}

/** Chat's form: the five icons stacked in a capsule (the rail's foot), Chat's icon in the pill. */
@Composable
private fun RailNav(
    a: MainActivity,
    ui: HomeState,
    badge: Int,
    modifier: Modifier,
    shared: @Composable Modifier.(String, Float) -> Modifier,
    capsule: @Composable Modifier.() -> Modifier,
) {
    val cs = MaterialTheme.colorScheme
    val vivid = Prefs.vivid(a)
    Column(
        modifier.capsule().clip(CircleShape).background(if (vivid) cs.primaryContainer else cs.surfaceContainerHigh)
            .padding(vertical = 6.dp).width(RAIL_W),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Pane.entries.forEach { p ->
            val on = p == Pane.CHAT // this form only shows on Chat (also while it leaves, when ui.pane is already the next)
            Box(Modifier.size(RAIL_W, 48.dp).navItem(p, on) { go(ui, p) }, contentAlignment = Alignment.Center) {
                if (on) Box(Modifier.shared("knav-pill", 2f).size(44.dp, 36.dp).clip(CircleShape).background(cs.primary))
                NavIcon(p, on, badge, Modifier.shared("knav-" + p.name, 3f), vivid)
            }
        }
    }
}

/** Every other pane's form: the floating toolbar (or the docked bar), a label under each icon, the pill sliding to
 *  the open pane with the motion scheme's quick spring. */
@Composable
private fun BarNav(
    a: MainActivity,
    ui: HomeState,
    badge: Int,
    modifier: Modifier,
    shared: @Composable Modifier.(String, Float) -> Modifier,
    capsule: @Composable Modifier.() -> Modifier,
) {
    val floating = Prefs.floatingBar(a)
    val cs = MaterialTheme.colorScheme
    val vivid = Prefs.vivid(a)
    val d = LocalDensity.current
    val screen = with(d) { LocalWindowInfo.current.containerSize.width.toDp() }
    val inner = if (floating) minOf(screen - 32.dp, 440.dp) - 8.dp else screen
    val itemW = inner / Pane.entries.size
    val index = ui.pane.ordinal.toFloat()
    // the pill's place, read in the placement phase only (Modifier.offset's lambda): no recomposition while it slides
    val pill = remember { Animatable(index) }
    val spec = MaterialTheme.motionScheme.fastSpatialSpec<Float>()
    val reduced = LocalReducedMotion.current
    LaunchedEffect(index) { if (reduced) pill.snapTo(index) else pill.animateTo(index, spec) }
    val pillW = 56.dp
    val row: @Composable () -> Unit = {
        Box(Modifier.width(inner)) {
            Box(
                Modifier
                    .offset { IntOffset(((itemW * pill.value) + (itemW - pillW) / 2).roundToPx(), 6.dp.roundToPx()) }
                    .shared("knav-pill", 2f)
                    .size(pillW, 32.dp)
                    .clip(CircleShape)
                    .background(if (floating) cs.primary else cs.secondaryContainer),
            )
            Row(Modifier.width(inner)) {
                Pane.entries.forEach { p ->
                    val on = p == ui.pane
                    Column(
                        Modifier.width(itemW).navItem(p, on) { go(ui, p) }.padding(vertical = 6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Box(Modifier.size(pillW, 32.dp), contentAlignment = Alignment.Center) {
                            NavIcon(p, on, badge, Modifier.shared("knav-" + p.name, 3f), vivid && floating, docked = !floating)
                        }
                        Spacer(Modifier.height(4.dp))
                        Text(
                            p.label,
                            style = MaterialTheme.typography.labelMedium,
                            color = if (!floating) cs.onSurfaceVariant else if (vivid) cs.onPrimaryContainer else cs.onSurface,
                            maxLines = 1,
                        )
                    }
                }
            }
        }
    }
    if (floating) {
        HorizontalFloatingToolbar(
            expanded = true,
            modifier = modifier.navigationBarsPadding().padding(bottom = 12.dp).capsule(),
            colors = if (vivid) FloatingToolbarDefaults.vibrantFloatingToolbarColors()
            else FloatingToolbarDefaults.standardFloatingToolbarColors(),
            contentPadding = PaddingValues(horizontal = 4.dp, vertical = 2.dp),
            content = { row() },
        )
    } else {
        // docked (Look → Floating bar off): the same row on the bottom edge, tonal and nearly opaque
        Surface(
            modifier = modifier.fillMaxWidth().capsule(),
            color = cs.surfaceContainer.copy(alpha = 0.97f),
            shape = RoundedCornerShape(0.dp),
        ) { Box(Modifier.navigationBarsPadding()) { row() } }
    }
}

/** One icon of the bar, with the Chat badge; tinted for the pill under it when it's the open pane. */
@Composable
private fun NavIcon(p: Pane, on: Boolean, badge: Int, modifier: Modifier, vivid: Boolean, docked: Boolean = false) {
    val cs = MaterialTheme.colorScheme
    val tint by animateColorAsState(
        when {
            on && docked -> cs.onSecondaryContainer
            on -> cs.onPrimary
            docked -> cs.onSurfaceVariant
            vivid -> cs.onPrimaryContainer
            else -> cs.onSurfaceVariant
        },
        MaterialTheme.motionScheme.fastEffectsSpec(),
        label = "navTint",
    )
    BadgedBox(
        badge = { if (p == Pane.CHAT && badge > 0) Badge { Text(if (badge > 99) "99+" else "$badge") } },
        modifier = modifier,
    ) { Icon(painterResource(p.icon), contentDescription = null, tint = tint) }
}

/** A bar item's tap target, read as a tab by TalkBack. */
private fun Modifier.navItem(p: Pane, on: Boolean, go: () -> Unit): Modifier =
    this.clip(CircleShape).clickable(onClick = go).semantics {
        role = Role.Tab
        selected = on
        contentDescription = p.label
    }

/** Open a pane; Settings tapped again goes back to its grid. */
private fun go(ui: HomeState, p: Pane) {
    if (p == ui.pane && p == Pane.SETTINGS) ui.settingsGroup = null
    ui.pane = p
}

/** The upright form's width (the rail's). */
val RAIL_W: Dp = 56.dp

/**
 * For Chat's rail (app-chat): row `index` (0 at the top) of the rail slides out to the left when you leave Chat, 20 ms
 * after the row above it, and comes back in the same order, on top of the shell sliding Chat's pane out. Only inside the
 * shell's pane move (it does nothing elsewhere, or with "Remove animations"): `Modifier.paneStagger(i)` on each avatar.
 */
fun Modifier.paneStagger(index: Int): Modifier = composed {
    val av = LocalNavPane.current
    if (av == null || LocalReducedMotion.current) return@composed this
    val spec = MaterialTheme.motionScheme.defaultSpatialSpec<Float>()
    // 0 shown, 1 gone: the row moves its own width and a little more, in the draw phase only
    val gone by av.transition.animateFloat(transitionSpec = { Delayed(spec, 20 * index) }, label = "stagger") {
        if (it == EnterExitState.Visible) 0f else 1f
    }
    graphicsLayer { translationX = -gone * (size.width + 24.dp.toPx()) }
}

/** A spec that waits `ms` before it starts (springs have no delay of their own): the stagger above. */
internal class Delayed<T>(private val inner: FiniteAnimationSpec<T>, private val ms: Int) : FiniteAnimationSpec<T> {
    override fun <V : AnimationVector> vectorize(converter: TwoWayConverter<T, V>): VectorizedFiniteAnimationSpec<V> =
        DelayedV(inner.vectorize(converter), ms * 1_000_000L)
}

private class DelayedV<V : AnimationVector>(private val inner: VectorizedFiniteAnimationSpec<V>, private val delay: Long) :
    VectorizedFiniteAnimationSpec<V> {
    override fun getValueFromNanos(playTimeNanos: Long, initialValue: V, targetValue: V, initialVelocity: V): V =
        if (playTimeNanos < delay) initialValue
        else inner.getValueFromNanos(playTimeNanos - delay, initialValue, targetValue, initialVelocity)

    override fun getVelocityFromNanos(playTimeNanos: Long, initialValue: V, targetValue: V, initialVelocity: V): V =
        if (playTimeNanos < delay) initialVelocity
        else inner.getVelocityFromNanos(playTimeNanos - delay, initialValue, targetValue, initialVelocity)

    override fun getDurationNanos(initialValue: V, targetValue: V, initialVelocity: V): Long =
        delay + inner.getDurationNanos(initialValue, targetValue, initialVelocity)
}
