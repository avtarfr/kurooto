package io.github.avtarfr.kurooto

import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.ListItemShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedListItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.ToggleButton
import androidx.compose.material3.ToggleButtonDefaults
import androidx.compose.material3.contentColorFor
import androidx.compose.material3.toShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
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
import androidx.compose.ui.unit.sp

/**
 * The Compose screens' building blocks (0.7.0), the Compose side of Ui.java, all from Material 3 Expressive: section
 * headings in emphasized type, segmented list groups (SegmentedListItem: rows in one rounded group with 2dp gaps,
 * larger corners at its ends, as Android 16's settings; a pressed row morphs its corners), toggle buttons for what's
 * on or off, MaterialShapes badges (a cookie, a burst) for the few places a shape says something, small print, status
 * lines and cards. A screen:
 *   Heading("Ringtones")
 *   Group(listOf(Item("Call ringtone", "phone default", onClick = { ... }), Item("Ring here too", checked = on, onClick = { ... })))
 *   Footnote("The alarm tone plays on the alarm stream ...")
 * And the Rail design's pieces (0.8.10): [toneOf] (a tonal pair for a shaped badge or tile), [IconBadge] (an icon in a
 * MaterialShapes polygon), [Overline] (a card's small label), [KField] (a rounded, filled text field) and [RoundAction]
 * (a round filled icon button that morphs as it's pressed: send, add).
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
    /** The settings guide's key for this row (SettingHelp, e.g. "app.vivid"): a long press opens its entry. */
    val help: String? = null,
)

/** Opens a setting's guide entry (Settings provides it; a long press on a row with `help` calls it). */
val LocalHelp = staticCompositionLocalOf<((String) -> Unit)?> { null }

/** A long press on a row with a guide entry opens it; a tap still does what the row does. */
@Composable
private fun Modifier.helpPress(key: String?): Modifier {
    val open = LocalHelp.current
    if (key == null || open == null) return this
    return this.pointerInput(key) { detectTapGestures(onLongPress = { open(key) }) }
}

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
        Surface(shape = shapes.shape, color = bg, contentColor = MaterialTheme.colorScheme.onSurface, modifier = Modifier.fillMaxWidth().helpPress(r.help)) {
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
        modifier = (if (r.checked == null) Modifier else Modifier.toggleState(r.checked)).helpPress(r.help),
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
    val vivid = LocalVivid.current
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
 *  the pairing help. `container` (0.8.10): a hero card in one of the scheme's colours (its content colour follows). */
@Composable
fun KCard(modifier: Modifier = Modifier, accent: Int = 0, container: Color = Color.Unspecified, content: @Composable ColumnScope.() -> Unit) {
    // (a translucent colour has no matching "on" colour, so the text's colour is set here)
    val bg = if (container == Color.Unspecified) rowColor(accent) else container
    val fg = if (container == Color.Unspecified) MaterialTheme.colorScheme.onSurface else contentColorFor(container)
    Surface(shape = MaterialTheme.shapes.extraLarge, color = bg, contentColor = fg, modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 20.dp)) { content() }
    }
}

/** The i-th tonal pair (container, content) for a shaped badge or a tile: the palette's own (Apricot: the Rail mockup's
 *  apricot, plum, leaf, sky...), or the scheme's primary, secondary and tertiary containers (Material You, Kuro). */
@Composable
fun toneOf(i: Int): Pair<Color, Color> {
    val tones = LocalKurooto.current.tones
    if (tones.isNotEmpty()) return tones[Math.floorMod(i, tones.size)]
    val cs = MaterialTheme.colorScheme
    return when (Math.floorMod(i, 3)) {
        0 -> cs.primaryContainer to cs.onPrimaryContainer
        1 -> cs.secondaryContainer to cs.onSecondaryContainer
        else -> cs.tertiaryContainer to cs.onTertiaryContainer
    }
}

/** An icon inside one of Material's expressive shapes, in the i-th tone ([toneOf]): a place, a shared file, a sheet's
 *  mark. `size` in dp; the icon is a little under half of it. */
@Composable
fun IconBadge(shape: RoundedPolygon, icon: Int, tone: Int, modifier: Modifier = Modifier, size: Int = 44) {
    val (bg, fg) = toneOf(tone)
    ShapeBadge(shape, bg, modifier, size) {
        Icon(painterResource(icon), contentDescription = null, tint = fg, modifier = Modifier.size((size * 0.48f).dp))
    }
}

/** A card's small label over its content ("SAVE WHERE YOU ARE", "WAITING FOR A PLACE"), with an optional icon. */
@Composable
fun Overline(text: String, modifier: Modifier = Modifier, icon: Int? = null, color: Color = Color.Unspecified) {
    val c = if (color == Color.Unspecified) MaterialTheme.colorScheme.onSurfaceVariant else color
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        if (icon != null) Icon(painterResource(icon), contentDescription = null, tint = c, modifier = Modifier.padding(end = 6.dp).size(16.dp))
        Text(text.uppercase(), color = c, style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold, letterSpacing = 0.8.sp))
    }
}

/** A text field in the Rail look: filled, fully rounded, no underline, a placeholder instead of a floating label, and
 *  room for a [RoundAction] at its end. */
@Composable
fun KField(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    singleLine: Boolean = false,
    minLines: Int = 1,
    maxLines: Int = if (singleLine) 1 else 8,
    container: Color = MaterialTheme.colorScheme.surfaceContainerHighest,
    keyboardOptions: KeyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
    keyboardActions: KeyboardActions = KeyboardActions.Default,
    trailing: (@Composable () -> Unit)? = null,
) {
    val cs = MaterialTheme.colorScheme
    TextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        enabled = enabled,
        singleLine = singleLine,
        minLines = minLines,
        maxLines = maxLines,
        placeholder = { Text(placeholder) },
        trailingIcon = trailing,
        shape = RoundedCornerShape(if (singleLine || maxLines == 1) 28.dp else 24.dp),
        keyboardOptions = keyboardOptions,
        keyboardActions = keyboardActions,
        colors = TextFieldDefaults.colors(
            focusedContainerColor = container,
            unfocusedContainerColor = container,
            disabledContainerColor = container.copy(alpha = 0.6f),
            focusedIndicatorColor = Color.Transparent,
            unfocusedIndicatorColor = Color.Transparent,
            disabledIndicatorColor = Color.Transparent,
            focusedTextColor = cs.onSurface,
            unfocusedTextColor = cs.onSurface,
            focusedPlaceholderColor = cs.onSurfaceVariant,
            unfocusedPlaceholderColor = cs.onSurfaceVariant,
        ),
    )
}

/** A round, filled icon button in the primary colour (it squares off a little as it's pressed): send, add. */
@Composable
fun RoundAction(icon: Int, description: String, enabled: Boolean = true, modifier: Modifier = Modifier, onClick: () -> Unit) {
    FilledIconButton(
        onClick = onClick,
        enabled = enabled,
        shapes = IconButtonDefaults.shapes(),
        modifier = modifier.padding(end = 4.dp).size(48.dp),
    ) { Icon(painterResource(icon), contentDescription = description, modifier = Modifier.size(22.dp)) }
}
