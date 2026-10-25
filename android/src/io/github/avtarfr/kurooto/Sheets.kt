package io.github.avtarfr.kurooto

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * The small floating windows (0.7.6: Compose, Material 3 Expressive): a question to answer, Quick note, Share to Kurooto. A
 * rounded sheet floating over a dimmed screen (tap outside to close); the colours are the app's own (`KurootoTheme`, Vivid or
 * Calm). The activities use the `Kurooto.Sheet` window theme (translucent) and put their content in [sheet].
 */
abstract class SheetActivity : ComponentActivity() {
    protected val h = Handler(Looper.getMainLooper())

    override fun onCreate(b: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(b)
    }

    /** Draw the window: a floating [Sheet] with [content]; its close is `finish()`. */
    protected fun sheet(content: @Composable ColumnScope.() -> Unit) {
        setContent { KurootoTheme { Sheet(onClose = { finish() }, content = content) } }
    }
}

@Composable
fun Sheet(onClose: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    val none = remember { MutableInteractionSource() }
    Box(
        Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.45f))
            .clickable(interactionSource = none, indication = null, onClick = onClose)
            .windowInsetsPadding(WindowInsets.systemBars.union(WindowInsets.ime)).padding(16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = MaterialTheme.shapes.extraLarge,
            color = MaterialTheme.colorScheme.surfaceContainerHigh,
            tonalElevation = 6.dp,
            modifier = Modifier.widthIn(max = 460.dp).fillMaxWidth().clickable(interactionSource = none, indication = null, onClick = {}),
        ) {
            Column(
                Modifier.verticalScroll(rememberScrollState()).padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                content = content,
            )
        }
    }
}

@Composable
fun SheetTitle(text: String) = Text(text, style = MaterialTheme.typography.headlineSmallEmphasized, color = MaterialTheme.colorScheme.onSurface)

@Composable
fun SheetText(text: String) = Text(text, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface)

/** The main action: a filled, full-width expressive button. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun SheetButton(text: String, enabled: Boolean = true, onClick: () -> Unit) =
    Button(onClick, enabled = enabled, shapes = ButtonDefaults.shapes(), modifier = Modifier.fillMaxWidth()) { Text(text) }

/** A secondary action (a message's own buttons): tonal. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun SheetTonal(text: String, enabled: Boolean = true, onClick: () -> Unit) =
    FilledTonalButton(onClick, enabled = enabled, shapes = ButtonDefaults.shapes(), modifier = Modifier.fillMaxWidth()) { Text(text) }

/** The quiet action at the end (Later, Dismiss, Cancel). */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun ColumnScope.SheetFlat(text: String, enabled: Boolean = true, onClick: () -> Unit) =
    TextButton(onClick, enabled = enabled, shapes = ButtonDefaults.shapes(), modifier = Modifier.align(Alignment.End)) { Text(text) }

/**
 * A full-screen page (0.7.6): the app's sky behind, a big emphasized title, the content in floating cards, at most 640dp
 * wide, clear of the bars and the keyboard. For Places and Chat; the main screen's tabs have their own (Home.kt).
 */
abstract class PageActivity : ComponentActivity() {
    protected val h = Handler(Looper.getMainLooper())

    override fun onCreate(b: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(b)
    }

    protected fun page(title: String, subtitle: String? = null, content: @Composable ColumnScope.() -> Unit) {
        setContent { KurootoTheme { Page(this, title, subtitle, content) } }
    }
}

@Composable
fun Page(owner: androidx.lifecycle.LifecycleOwner, title: String, subtitle: String?, content: @Composable ColumnScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Sky(owner, strength = { 0.35f }, scroll = { 0f }, modifier = Modifier.fillMaxSize())
        Box(
            Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars.union(WindowInsets.ime)),
            contentAlignment = Alignment.TopCenter,
        ) {
            Column(
                Modifier.widthIn(max = 640.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(title, style = MaterialTheme.typography.displaySmallEmphasized, color = MaterialTheme.colorScheme.onBackground, modifier = Modifier.padding(top = 24.dp))
                if (subtitle != null) Text(subtitle, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                content()
            }
        }
    }
}
