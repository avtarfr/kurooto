package io.github.avtarfr.kurooto

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.PredictiveBackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animate
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.interaction.MutableInteractionSource
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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Velocity
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

/**
 * The small floating windows: a question to answer, Quick note, Share to Kurooto, pairing. 0.8.10 (the Rail design): a
 * sheet floating at the bottom of the screen, 12dp clear of its edges, with large rounded corners and a drag handle,
 * over a dimmed screen. It springs up from the bottom when it opens and slides down when it closes (the motion scheme's
 * spatial springs; it jumps with "Remove animations"); drag it down or fling it to close, tap outside, or Back (the
 * predictive back gesture shrinks it as you swipe). Every `finish()` of a [SheetActivity] plays the closing slide first.
 * The activities use the `Kurooto.Sheet` window theme (translucent) and put their content in [sheet].
 */
abstract class SheetActivity : ComponentActivity() {
    protected val h = Handler(Looper.getMainLooper())
    private var shown = false
    private var gone = false
    private var leaving by mutableStateOf(false)

    override fun onCreate(b: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(b)
        noWindowAnimations(this) // the sheet moves itself
    }

    /** Draw the window: a floating [Sheet] with [content]; its close is `finish()`. */
    protected fun sheet(content: @Composable ColumnScope.() -> Unit) {
        shown = true
        setContent { KurootoTheme { Sheet(leaving = leaving, onClose = { finish() }, onGone = { close() }, content = content) } }
    }

    /** Slide the sheet away, then close the window; straight away when nothing is drawn yet or the window isn't in front. */
    override fun finish() {
        if (gone) return
        if (!shown || !lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            close()
            return
        }
        if (leaving) return
        leaving = true
        h.postDelayed({ close() }, 900) // in case no frame comes to finish the slide
    }

    private fun close() {
        if (gone) return
        gone = true
        super.finish()
        noWindowAnimations(this)
    }
}

/** No window animation for opening or closing [a] (its content moves itself). */
@Suppress("DEPRECATION")
private fun noWindowAnimations(a: Activity) {
    if (Build.VERSION.SDK_INT >= 34) {
        a.overrideActivityTransition(Activity.OVERRIDE_TRANSITION_OPEN, 0, 0)
        a.overrideActivityTransition(Activity.OVERRIDE_TRANSITION_CLOSE, 0, 0)
    } else {
        a.overridePendingTransition(0, 0)
    }
}

/**
 * The floating sheet. `leaving` turns true when it should slide away; `onGone` runs when it has. Every moving part is
 * read in the draw phase (graphicsLayer, drawBehind): the slide, the drag, the back gesture's shrink and the dimming.
 */
@Composable
fun Sheet(leaving: Boolean = false, onClose: () -> Unit, onGone: () -> Unit = onClose, content: @Composable ColumnScope.() -> Unit) {
    val motion = MaterialTheme.motionScheme
    val density = LocalDensity.current
    val scope = rememberCoroutineScope()
    val shown = remember { Animatable(0f) } // 0: below the screen, 1: in place
    val drag = remember { mutableFloatStateOf(0f) } // px pulled down by the finger
    val back = remember { mutableFloatStateOf(0f) } // the back gesture's progress, 0..1
    var height by remember { mutableIntStateOf(0) }
    val margin = with(density) { 24.dp.toPx() }
    val dismissAt = with(density) { 120.dp.toPx() }

    LaunchedEffect(leaving) {
        if (!leaving) {
            shown.animateTo(1f, motion.defaultSpatialSpec())
        } else {
            shown.animateTo(0f, motion.fastSpatialSpec())
            onGone()
        }
    }

    suspend fun settle(velocity: Float) {
        if (drag.floatValue > dismissAt || velocity > 1800f) {
            onClose()
        } else {
            animate(drag.floatValue, 0f, velocity, motion.fastSpatialSpec()) { v, _ -> drag.floatValue = v }
        }
    }

    // the content's scroll hands on what it doesn't use: pulling down at its top drags the sheet
    val pull = remember {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
                if (available.y < 0 && drag.floatValue > 0f) {
                    val used = maxOf(available.y, -drag.floatValue)
                    drag.floatValue += used
                    return Offset(0f, used)
                }
                return Offset.Zero
            }

            override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset {
                if (source == NestedScrollSource.UserInput && available.y > 0f) {
                    drag.floatValue += available.y
                    return Offset(0f, available.y)
                }
                return Offset.Zero
            }

            override suspend fun onPreFling(available: Velocity): Velocity {
                if (drag.floatValue <= 0f) return Velocity.Zero
                settle(available.y)
                return available
            }
        }
    }

    PredictiveBackHandler(enabled = !leaving) { progress ->
        try {
            progress.collect { back.floatValue = it.progress }
            onClose()
        } catch (e: CancellationException) {
            scope.launch { animate(back.floatValue, 0f, 0f, motion.fastSpatialSpec()) { v, _ -> back.floatValue = v } }
            throw e
        }
    }

    val none = remember { MutableInteractionSource() }
    val scrim = MaterialTheme.colorScheme.scrim
    Box(
        Modifier.fillMaxSize()
            .drawBehind { drawRect(scrim, alpha = 0.5f * shown.value.coerceIn(0f, 1f) * (1f - 0.4f * back.floatValue)) }
            .clickable(interactionSource = none, indication = null, onClick = onClose),
    ) {
        Surface(
            shape = MaterialTheme.shapes.extraLargeIncreased,
            color = MaterialTheme.colorScheme.surfaceContainerHigh,
            contentColor = MaterialTheme.colorScheme.onSurface,
            shadowElevation = 12.dp,
            modifier = Modifier.align(Alignment.BottomCenter)
                .windowInsetsPadding(WindowInsets.systemBars.union(WindowInsets.ime))
                .padding(12.dp)
                .widthIn(max = 560.dp).fillMaxWidth()
                .onSizeChanged { height = it.height }
                .graphicsLayer {
                    val s = 1f - 0.08f * back.floatValue
                    scaleX = s
                    scaleY = s
                    transformOrigin = TransformOrigin(0.5f, 1f)
                    translationY = (1f - shown.value) * (height + margin) + drag.floatValue
                }
                .clickable(interactionSource = none, indication = null, onClick = {}),
        ) {
            Column {
                // the handle: drag the sheet by it (TalkBack: a button that closes it)
                Box(
                    Modifier.fillMaxWidth().height(28.dp)
                        .draggable(
                            orientation = Orientation.Vertical,
                            state = rememberDraggableState { d -> drag.floatValue = (drag.floatValue + d).coerceAtLeast(0f) },
                            onDragStopped = { v -> settle(v) },
                        )
                        .semantics {
                            contentDescription = "Close"
                            onClick {
                                onClose()
                                true
                            }
                        },
                    contentAlignment = Alignment.Center,
                ) {
                    Box(Modifier.size(width = 36.dp, height = 4.dp).background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f), CircleShape))
                }
                Column(
                    Modifier.nestedScroll(pull).verticalScroll(rememberScrollState()).padding(start = 24.dp, end = 24.dp, top = 4.dp, bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                    content = content,
                )
            }
        }
    }
}

/** A sheet's head: its mark (an [IconBadge] or a [ShapeBadge]), the title and a line under it. */
@Composable
fun SheetHeader(title: String, sub: String? = null, mark: (@Composable () -> Unit)? = null) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        if (mark != null) {
            mark()
            Spacer(Modifier.width(14.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.headlineSmallEmphasized, color = MaterialTheme.colorScheme.onSurface)
            if (!sub.isNullOrEmpty()) Text(sub, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun SheetTitle(text: String) = Text(text, style = MaterialTheme.typography.headlineSmallEmphasized, color = MaterialTheme.colorScheme.onSurface)

@Composable
fun SheetText(text: String) = Text(text, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface)

/** What Kurooto said, as the chat shows its messages: a bubble with a small corner at the bottom left. Selectable. */
@Composable
fun SheetBubble(text: String) {
    Surface(
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp, bottomEnd = 24.dp, bottomStart = 8.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHighest,
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        SelectionContainer {
            Text(text, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp))
        }
    }
}

/** The main action: a filled, full-width expressive button (56dp; it squares off as it's pressed). */
@Composable
fun SheetButton(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    val tall = ButtonDefaults.MediumContainerHeight
    Button(
        onClick,
        enabled = enabled,
        shapes = ButtonDefaults.shapes(),
        contentPadding = ButtonDefaults.contentPaddingFor(tall),
        modifier = Modifier.fillMaxWidth().heightIn(min = tall),
    ) { Text(text, style = ButtonDefaults.textStyleFor(tall)) }
}

/** A secondary action (a message's own buttons): tonal, full width. */
@Composable
fun SheetTonal(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    val tall = ButtonDefaults.MediumContainerHeight
    FilledTonalButton(
        onClick,
        enabled = enabled,
        shapes = ButtonDefaults.shapes(),
        contentPadding = ButtonDefaults.contentPaddingFor(tall),
        modifier = Modifier.fillMaxWidth().heightIn(min = tall),
    ) { Text(text, style = ButtonDefaults.textStyleFor(tall)) }
}

/** The quiet action at the end (Later, Dismiss, Cancel). */
@Composable
fun ColumnScope.SheetFlat(text: String, enabled: Boolean = true, onClick: () -> Unit) =
    TextButton(onClick, enabled = enabled, shapes = ButtonDefaults.shapes(), modifier = Modifier.align(Alignment.End)) { Text(text) }

/** A sheet's foot: the buttons on the right and how it went on the left (a [SaidLine]: a short one, "Sending…" or
 *  "Sent.", sits in the row so the sheet doesn't grow when it appears; a longer one gets the full width above). */
@Composable
fun SheetFoot(said: Said?, buttons: @Composable RowScope.() -> Unit) {
    val long = (said?.text?.length ?: 0) > 40
    Column(Modifier.fillMaxWidth()) {
        if (long) SaidLine(said, Modifier.padding(bottom = 8.dp))
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f).padding(end = 8.dp)) { if (!long) SaidLine(said, Modifier.padding(bottom = 8.dp)) }
            buttons()
        }
    }
}

/**
 * A full-screen page (Places): the app's sky behind, a round back button, a big emphasized title, the content as a lazy
 * list (stable keys, so rows that come and go move with the motion scheme), at most 640dp wide, clear of the bars and
 * the keyboard. Back (and the predictive back gesture: the manifest's `enableOnBackInvokedCallback`) closes it.
 */
abstract class PageActivity : ComponentActivity() {
    protected val h = Handler(Looper.getMainLooper())

    override fun onCreate(b: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(b)
    }

    protected fun page(title: String, subtitle: String? = null, content: LazyListScope.() -> Unit) {
        setContent { KurootoTheme { Page(this, title, subtitle, onBack = { onBackPressedDispatcher.onBackPressed() }, content = content) } }
    }
}

@Composable
fun Page(owner: androidx.lifecycle.LifecycleOwner, title: String, subtitle: String?, onBack: () -> Unit, content: LazyListScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background), contentAlignment = Alignment.TopCenter) {
        Sky(owner, strength = { 0.35f }, scroll = { 0f }, modifier = Modifier.fillMaxSize())
        val bars = WindowInsets.systemBars.union(WindowInsets.ime).asPaddingValues()
        LazyColumn(
            Modifier.widthIn(max = 640.dp).fillMaxSize(),
            contentPadding = PaddingValues(
                start = 16.dp,
                end = 16.dp,
                top = bars.calculateTopPadding() + 8.dp,
                bottom = bars.calculateBottomPadding() + 24.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item(key = "page-head", contentType = "head") {
                Column(Modifier.padding(bottom = 4.dp)) {
                    FilledTonalIconButton(onClick = onBack, shapes = IconButtonDefaults.shapes()) {
                        Icon(painterResource(R.drawable.ic_back), contentDescription = "Back")
                    }
                    Text(
                        title,
                        style = MaterialTheme.typography.displaySmallEmphasized,
                        color = MaterialTheme.colorScheme.onBackground,
                        modifier = Modifier.padding(top = 20.dp, start = 4.dp),
                    )
                    if (subtitle != null) {
                        Text(
                            subtitle,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 8.dp, start = 4.dp),
                        )
                    }
                }
            }
            content()
        }
    }
}
