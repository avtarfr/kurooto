package io.github.avtarfr.kurooto

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.ListItemShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedListItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.ToggleButton
import androidx.compose.material3.ToggleButtonDefaults
import androidx.compose.material3.toShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalContext
import androidx.graphics.shapes.RoundedPolygon
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.toggleableState
import androidx.compose.ui.state.ToggleableState
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/**
 * The Compose screens' building blocks (0.7.0), the Compose side of Ui.java, all from Material 3 Expressive: section
 * headings in emphasized type, segmented list groups (SegmentedListItem: rows in one rounded group with 2dp gaps,
 * larger corners at its ends, as Android 16's settings; a pressed row morphs its corners), toggle buttons for what's
 * on or off, MaterialShapes badges (a cookie, a burst) for the few places a shape says something, small print, status
 * lines and cards. A screen:
 *   Heading("Ringtones")
 *   Group(listOf(Item("Call ringtone", "phone default", onClick = { ... }), Item("Ring here too", checked = on, onClick = { ... })))
 *   Footnote("The alarm tone plays on the alarm stream ...")
 */

/** One row of a Group: a title, a line under it, and what happens on a tap. With `checked` it's an on/off row (a
 *  toggle button at its end; a tap anywhere toggles); `extra` goes under the line (Done and +1 on a deadline). */
class Item(
    val title: String,
    val sub: String? = null,
    val onClick: (() -> Unit)? = null,
    val checked: Boolean? = null,
    val leading: (@Composable () -> Unit)? = null,
    val trailing: (@Composable () -> Unit)? = null,
    val extra: (@Composable () -> Unit)? = null,
    val titleColor: Color = Color.Unspecified,
    val subLines: Int = Int.MAX_VALUE,
)

/** A section's name over its group, in the accent colour, emphasized. */
@Composable
fun Heading(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.titleMediumEmphasized,
        color = MaterialTheme.colorScheme.primary,
        modifier = modifier.padding(start = 16.dp, end = 16.dp, top = 28.dp, bottom = 10.dp),
    )
}

/** The rows as one segmented group; nothing when there are none. */
@Composable
fun Group(rows: List<Item>, modifier: Modifier = Modifier) {
    if (rows.isEmpty()) return
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap)) {
        // small corners between rows, the large ones only at the group's ends
        val inner = ListItemDefaults.shapes(shape = RoundedCornerShape(4.dp))
        val single = ListItemDefaults.shapes(shape = MaterialTheme.shapes.large)
        rows.forEachIndexed { i, r -> SegRow(r, ListItemDefaults.segmentedShapes(i, rows.size, if (rows.size == 1) single else inner)) }
    }
}

@Composable
private fun SegRow(r: Item, shapes: ListItemShapes) {
    val bg = rowColor()
    val headline: @Composable () -> Unit = { Text(r.title, color = r.titleColor) }
    val supporting: (@Composable () -> Unit)? = if (r.sub == null && r.extra == null) null else {
        {
            Column(Modifier.animateContentSize(MaterialTheme.motionScheme.fastSpatialSpec())) {
                if (!r.sub.isNullOrEmpty()) Text(r.sub, maxLines = r.subLines, overflow = TextOverflow.Ellipsis)
                r.extra?.invoke()
            }
        }
    }
    val onClick = r.onClick
    if (onClick == null) {
        Surface(shape = shapes.shape, color = bg, contentColor = MaterialTheme.colorScheme.onSurface, modifier = Modifier.fillMaxWidth()) {
            ListItem(
                headlineContent = headline,
                supportingContent = supporting,
                leadingContent = r.leading,
                trailingContent = r.trailing,
                colors = ListItemDefaults.colors(containerColor = Color.Transparent),
            )
        }
        return
    }
    val trailing: (@Composable () -> Unit)? = if (r.checked == null) r.trailing else {
        {
            // the row says it's on or off (below), so the button is only for the eye and the finger
            ToggleButton(
                checked = r.checked,
                onCheckedChange = { onClick() },
                shapes = ToggleButtonDefaults.shapes(),
                modifier = Modifier.clearAndSetSemantics { },
            ) { Text(if (r.checked) "On" else "Off") }
        }
    }
    SegmentedListItem(
        onClick = onClick,
        shapes = shapes,
        colors = ListItemDefaults.segmentedColors(containerColor = bg),
        leadingContent = r.leading,
        supportingContent = supporting,
        trailingContent = trailing,
        modifier = if (r.checked == null) Modifier else Modifier.toggleState(r.checked),
        content = headline,
    )
}

/** Tells TalkBack an on/off row is a switch, and whether it's on. */
private fun Modifier.toggleState(on: Boolean): Modifier = semantics {
    role = Role.Switch
    toggleableState = if (on) ToggleableState.On else ToggleableState.Off
}

/** A row's or card's ground: with Vivid colours, the surface stained with the scheme's primary container (so rows read as
 *  coloured, not grey); otherwise the plain surface. A little translucent so the sky behind the screen shows through
 *  (opaque enough that text keeps its contrast). */
@Composable
fun rowColor(accent: Int = 0): Color {
    val cs = MaterialTheme.colorScheme
    val vivid = Prefs.vivid(LocalContext.current)
    val tint = when (accent % 3) { 0 -> cs.primaryContainer; 1 -> cs.secondaryContainer; else -> cs.tertiaryContainer }
    return (if (vivid) lerp(cs.surfaceContainer, tint, 0.55f) else cs.surfaceContainer).copy(alpha = 0.9f)
}

/** The arrow at the end of a row that opens another screen. */
@Composable
fun Chevron() {
    Icon(painterResource(R.drawable.ic_chevron), contentDescription = null, modifier = Modifier.size(24.dp))
}

/** Something inside one of Material's expressive shapes (MaterialShapes: a cookie, a burst, a clover...): the
 *  assistant's mark on Today, the checklist's state, the empty Inbox. `size` in dp. */
@Composable
fun ShapeBadge(shape: RoundedPolygon, color: Color, modifier: Modifier = Modifier, size: Int = 40, content: @Composable BoxScope.() -> Unit) {
    Box(
        modifier.size(size.dp).clip(shape.toShape()).background(color),
        contentAlignment = Alignment.Center,
        content = content,
    )
}

/** Small print under a group. */
@Composable
fun Footnote(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp),
    )
}

/** A line of supporting text. */
@Composable
fun Dim(text: String, modifier: Modifier = Modifier) {
    Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = modifier)
}

/** How something went: "Sending…" (dim), "Sent." (ok), an error (bad). */
class Said(val text: String, val tone: Int = DIM) {
    companion object {
        const val DIM = 0
        const val OK = 1
        const val BAD = 2
    }
}

@Composable
fun SaidLine(s: Said?, modifier: Modifier = Modifier) {
    if (s == null || s.text.isEmpty()) return
    val k = LocalKurooto.current
    val colour = when (s.tone) {
        Said.OK -> k.ok
        Said.BAD -> k.bad
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Text(s.text, style = MaterialTheme.typography.bodyMedium, color = colour, modifier = modifier.padding(top = 8.dp))
}

/** A card: a rounded container (Material's extra-large shape) with padding: the check-in and quiz cards, This phone,
 *  the pairing help. */
@Composable
fun KCard(modifier: Modifier = Modifier, accent: Int = 0, content: @Composable ColumnScope.() -> Unit) {
    // (a translucent colour has no matching "on" colour, so the text's colour is set here)
    Surface(shape = MaterialTheme.shapes.extraLarge, color = rowColor(accent), contentColor = MaterialTheme.colorScheme.onSurface, modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 20.dp)) { content() }
    }
}
