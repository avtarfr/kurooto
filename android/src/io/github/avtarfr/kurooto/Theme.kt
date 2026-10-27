package io.github.avtarfr.kurooto

import android.content.Context
import android.os.Build
import android.provider.Settings
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialExpressiveTheme
import androidx.compose.material3.MotionScheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * The look of the Compose screens: Material 3 Expressive (a calmer take on its motion, emphasized type, large rounded
 * shapes), coloured by the palette chosen in Look (0.8.10): **Material You** (the default, as before: the wallpaper's
 * colours on Android 12+, Vivid or Calm), **Apricot** (apricot and plum on near-black, the Rail design) or **Kuro** (the
 * dashboard's olive). The default stays Material You so nobody's colours change on an update (the settings' rule: what
 * people already had doesn't change by itself); app-shell's `Prefs.palette` uses the same key and default. The palettes are [Palettes.all]; [Palettes.chosen] reads the choice and [Palettes.choose] sets it.
 * Besides Material's colour roles, a screen gets Kurooto's own through LocalKurooto: ok and bad (the checklist, "Sent."
 * and errors), hot (unread badges) and a few tonal pairs for shaped badges and tiles ([toneOf]); and whether it's light.
 * The sky behind the screens (Sky) takes its colours from the scheme.
 */
@Immutable
data class KColors(
    val ok: Color,
    val bad: Color,
    val light: Boolean,
    /** Unread counts and the like: the mockup's coral. */
    val hot: Color = bad,
    val onHot: Color = Color.White,
    /** Tonal pairs (container, content) for shaped badges and tiles, in order; empty: the scheme's three containers. */
    val tones: List<Pair<Color, Color>> = emptyList(),
)

/** One named palette: Material's colour scheme and Kurooto's own colours, light and dark. */
@Immutable
data class Palette(val name: String, val label: String, val light: ColorScheme, val dark: ColorScheme, val lightK: KColors, val darkK: KColors)

object Palettes {
    /** Material You: the wallpaper's colours (Android 12+; older phones: the Vivid scheme from Kurooto's olive, or Kuro when Calm). */
    const val YOU = "you"

    /** The Look's choice when nothing is chosen: Material You, as before 0.8.10. */
    const val DEFAULT = YOU

    /** The badges' and tiles' tonal pairs (the Rail mockup's settings tiles): bright containers with dark content, which
     *  read on the near-black and on the light cream alike. */
    private val RAIL_TONES = listOf(
        Color(0xFFFFB870) to Color(0xFF4A2800), // apricot
        Color(0xFFDCB8FF) to Color(0xFF2E0F47), // plum
        Color(0xFFB9D98C) to Color(0xFF1C3300), // leaf
        Color(0xFF9FD3FF) to Color(0xFF00344F), // sky
        Color(0xFFFFCF6B) to Color(0xFF3E2E00), // honey
        Color(0xFFFF9E85) to Color(0xFF4A1200), // coral
        Color(0xFFF6A8D8) to Color(0xFF4A1036), // rose
        Color(0xFFE0D4C8) to Color(0xFF3A3027), // sand
    )

    /** "apricot" (0.8.10, the Rail design): apricot and plum on near-black; light: the same hues on warm cream. The dark
     *  values are the mockup's (build-specs/0.8.10/mockups/rail.py), the light ones the same hues' tones (material colour
     *  utilities: primary 40, containers 90, on-containers 30, neutrals from the mockup's surface hue). */
    val apricot = Palette(
        name = "apricot",
        label = "Apricot",
        light = lightColorScheme(
            primary = Color(0xFF875212), onPrimary = Color(0xFFFFFFFF),
            primaryContainer = Color(0xFFFFDCBE), onPrimaryContainer = Color(0xFF693C00),
            inversePrimary = Color(0xFFFFB870),
            secondary = Color(0xFF6F518F), onSecondary = Color(0xFFFFFFFF),
            secondaryContainer = Color(0xFFEFDBFF), onSecondaryContainer = Color(0xFF573976),
            tertiary = Color(0xFF4C6627), onTertiary = Color(0xFFFFFFFF),
            tertiaryContainer = Color(0xFFCDEE9E), onTertiaryContainer = Color(0xFF354E11),
            background = Color(0xFFFFF8F4), onBackground = Color(0xFF201B15),
            surface = Color(0xFFFFF8F4), onSurface = Color(0xFF201B15),
            surfaceVariant = Color(0xFFF1E0CF), onSurfaceVariant = Color(0xFF504538),
            surfaceTint = Color(0xFF875212),
            inverseSurface = Color(0xFF362F29), inverseOnSurface = Color(0xFFFBEEE4),
            error = Color(0xFFBA1A1A), onError = Color(0xFFFFFFFF),
            errorContainer = Color(0xFFFFDAD6), onErrorContainer = Color(0xFF93000A),
            outline = Color(0xFF827567), outlineVariant = Color(0xFFD4C4B3),
            scrim = Color(0xFF000000),
            surfaceBright = Color(0xFFFFF8F4), surfaceDim = Color(0xFFE4D8CE),
            surfaceContainerLowest = Color(0xFFFFFFFF), surfaceContainerLow = Color(0xFFFEF1E7),
            surfaceContainer = Color(0xFFF8ECE2), surfaceContainerHigh = Color(0xFFF3E6DC),
            surfaceContainerHighest = Color(0xFFEDE0D6),
        ),
        dark = darkColorScheme(
            primary = Color(0xFFFFB870), onPrimary = Color(0xFF4A2800),
            primaryContainer = Color(0xFF6A4000), onPrimaryContainer = Color(0xFFFFDCBD),
            inversePrimary = Color(0xFF875212),
            secondary = Color(0xFFDCB8FF), onSecondary = Color(0xFF3F225E),
            secondaryContainer = Color(0xFF4C2A63), onSecondaryContainer = Color(0xFFF1DBFF),
            tertiary = Color(0xFFB9D98C), onTertiary = Color(0xFF203600),
            tertiaryContainer = Color(0xFF2E4A12), onTertiaryContainer = Color(0xFFD4F5A6),
            background = Color(0xFF14100C), onBackground = Color(0xFFF0E2D4),
            surface = Color(0xFF14100C), onSurface = Color(0xFFF0E2D4),
            surfaceVariant = Color(0xFF382F27), onSurfaceVariant = Color(0xFFC4B4A4),
            surfaceTint = Color(0xFFFFB870),
            inverseSurface = Color(0xFFF0E2D4), inverseOnSurface = Color(0xFF362F29),
            error = Color(0xFFFFB4AB), onError = Color(0xFF690005),
            errorContainer = Color(0xFF93000A), onErrorContainer = Color(0xFFFFDAD6),
            outline = Color(0xFF97897B), outlineVariant = Color(0xFF4D4338),
            scrim = Color(0xFF000000),
            surfaceBright = Color(0xFF3F3831), surfaceDim = Color(0xFF14100C),
            surfaceContainerLowest = Color(0xFF0E0B08), surfaceContainerLow = Color(0xFF1C1712),
            surfaceContainer = Color(0xFF231D17), surfaceContainerHigh = Color(0xFF2D261F),
            surfaceContainerHighest = Color(0xFF382F27),
        ),
        lightK = KColors(Color(0xFF4C6627), Color(0xFFBA1A1A), light = true, hot = Color(0xFFBF5938), onHot = Color.White, tones = RAIL_TONES),
        darkK = KColors(Color(0xFFB9D98C), Color(0xFFFFB4AB), light = false, hot = Color(0xFFFF8A65), onHot = Color(0xFF3A0D00), tones = RAIL_TONES),
    )

    /** "kuro": dark olive on warm paper, light sage on near-black (the dashboard's default). */
    val kuro = Palette(
        name = "kuro",
        label = "Kuro",
        light = lightColorScheme(
            primary = Color(0xFF3F5626), onPrimary = Color(0xFFF6F3EC),
            primaryContainer = Color(0xFFD3E4B4), onPrimaryContainer = Color(0xFF1C2A0E),
            inversePrimary = Color(0xFFA6C07A),
            secondary = Color(0xFF52624A), onSecondary = Color(0xFFF6F3EC),
            secondaryContainer = Color(0xFFE1E6D3), onSecondaryContainer = Color(0xFF2F3A26),
            tertiary = Color(0xFF3E6E66), onTertiary = Color(0xFFFFFFFF),
            tertiaryContainer = Color(0xFFCBE6DF), onTertiaryContainer = Color(0xFF0F2A26),
            background = Color(0xFFF4F2EC), onBackground = Color(0xFF2F3A26),
            surface = Color(0xFFF4F2EC), onSurface = Color(0xFF2F3A26),
            surfaceVariant = Color(0xFFE9E5DA), onSurfaceVariant = Color(0xFF52624A),
            surfaceTint = Color(0xFF3F5626),
            inverseSurface = Color(0xFF2F3A26), inverseOnSurface = Color(0xFFF4F2EC),
            error = Color(0xFFB23A26), onError = Color(0xFFFFFFFF),
            errorContainer = Color(0xFFF9DAD2), onErrorContainer = Color(0xFF410E05),
            outline = Color(0xFF7E8A74), outlineVariant = Color(0xFFCDCDBF),
            // the cards and list rows are white on the paper background, as on the web pages
            surfaceBright = Color(0xFFFFFFFF), surfaceDim = Color(0xFFE2DED2),
            surfaceContainerLowest = Color(0xFFFFFFFF), surfaceContainerLow = Color(0xFFFAF9F5),
            surfaceContainer = Color(0xFFFFFFFF), surfaceContainerHigh = Color(0xFFE9E5DA),
            surfaceContainerHighest = Color(0xFFE2DED2),
        ),
        dark = darkColorScheme(
            primary = Color(0xFFA6C07A), onPrimary = Color(0xFF1C2A0E),
            primaryContainer = Color(0xFF34481C), onPrimaryContainer = Color(0xFFD3E4B4),
            inversePrimary = Color(0xFF3F5626),
            secondary = Color(0xFF95A682), onSecondary = Color(0xFF1C2A0E),
            secondaryContainer = Color(0xFF2A3522), onSecondaryContainer = Color(0xFFDAD3C8),
            tertiary = Color(0xFF8DBDB3), onTertiary = Color(0xFF0F2A26),
            tertiaryContainer = Color(0xFF24433D), onTertiaryContainer = Color(0xFFCBE6DF),
            background = Color(0xFF0B0F0A), onBackground = Color(0xFFDAD3C8),
            surface = Color(0xFF0B0F0A), onSurface = Color(0xFFDAD3C8),
            surfaceVariant = Color(0xFF1F2A19), onSurfaceVariant = Color(0xFF95A682),
            surfaceTint = Color(0xFFA6C07A),
            inverseSurface = Color(0xFFDAD3C8), inverseOnSurface = Color(0xFF1A2016),
            error = Color(0xFFE8735A), onError = Color(0xFF3A0B02),
            errorContainer = Color(0xFF5C1A0C), onErrorContainer = Color(0xFFFFDAD2),
            outline = Color(0xFF5E6B52), outlineVariant = Color(0xFF2F3A28),
            surfaceBright = Color(0xFF2B3426), surfaceDim = Color(0xFF0B0F0A),
            surfaceContainerLowest = Color(0xFF070A06), surfaceContainerLow = Color(0xFF111610),
            surfaceContainer = Color(0xFF151B12), surfaceContainerHigh = Color(0xFF1F2A19),
            surfaceContainerHighest = Color(0xFF27321F),
        ),
        lightK = KColors(Color(0xFF2E6B3F), Color(0xFFB23A26), light = true),
        darkK = KColors(Color(0xFF8CCB98), Color(0xFFE8735A), light = false),
    )

    /** Every named palette by name. */
    val all: Map<String, Palette> = linkedMapOf(apricot.name to apricot, kuro.name to kuro)

    /** The Look's choices in order (name to label), for a Settings row: Material You, Apricot, Kuro. */
    val choices: List<Pair<String, String>> = listOf(YOU to "Material You", apricot.name to apricot.label, kuro.name to kuro.label)

    fun named(name: String?): Palette = all[name] ?: kuro

    /** The palette chosen in Look (`palette` in the app's settings): a name in [all], or [YOU]. */
    fun chosen(c: Context): String =
        try {
            Prefs.sp(c).getString(KEY, DEFAULT)?.takeIf { it == YOU || all.containsKey(it) } ?: DEFAULT
        } catch (e: Exception) {
            DEFAULT
        }

    fun choose(c: Context, name: String) {
        if (name == YOU || all.containsKey(name)) Prefs.sp(c).edit().putString(KEY, name).apply()
    }

    private const val KEY = "palette"
}

/** Material's expressive type scale, with its emphasized display and headline styles a step bolder (semibold, not
 *  medium: with the phone's own Roboto rather than Google Sans Flex, medium reads as regular at display sizes) and
 *  set a little tighter, as the Rail mockup's big titles are. */
private val TYPE = Typography().let { t ->
    fun SB(s: TextStyle, tight: Float) = s.copy(fontWeight = FontWeight.SemiBold, letterSpacing = tight.sp)
    t.copy(
        displayLargeEmphasized = SB(t.displayLargeEmphasized, -1f),
        displayMediumEmphasized = SB(t.displayMediumEmphasized, -0.75f),
        displaySmallEmphasized = SB(t.displaySmallEmphasized, -0.5f),
        headlineLargeEmphasized = SB(t.headlineLargeEmphasized, -0.25f),
        headlineMediumEmphasized = SB(t.headlineMediumEmphasized, -0.25f),
        headlineSmallEmphasized = SB(t.headlineSmallEmphasized, 0f),
    )
}

/** The shape scale (0.8.10): the Rail mockup's rounder corners. Rows and chips 12–16dp, cards 28dp (large, increased),
 *  sheets and big cards 32–36dp (extra large), the hero cards 48dp. */
private val SHAPES = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(32.dp),
    largeIncreased = RoundedCornerShape(28.dp),
    extraLargeIncreased = RoundedCornerShape(36.dp),
    extraExtraLarge = RoundedCornerShape(48.dp),
)

/** "Remove animations" as a motion scheme: every spec jumps to its end, so a screen that takes its motion from
 *  `MaterialTheme.motionScheme` needs no check of its own. */
private object StillMotion : MotionScheme {
    override fun <T> defaultSpatialSpec(): FiniteAnimationSpec<T> = snap()

    override fun <T> fastSpatialSpec(): FiniteAnimationSpec<T> = snap()

    override fun <T> slowSpatialSpec(): FiniteAnimationSpec<T> = snap()

    override fun <T> defaultEffectsSpec(): FiniteAnimationSpec<T> = snap()

    override fun <T> fastEffectsSpec(): FiniteAnimationSpec<T> = snap()

    override fun <T> slowEffectsSpec(): FiniteAnimationSpec<T> = snap()
}

/** Kurooto's motion: Expressive's roles (spatial and effects; fast, default, slow), but slower and settled, with
 *  almost no overshoot, so a pane glides in instead of snapping and bouncing (the stock timing felt rushed). */
private object CalmMotion : MotionScheme {
    override fun <T> defaultSpatialSpec(): FiniteAnimationSpec<T> = spring(0.92f, 200f)

    override fun <T> fastSpatialSpec(): FiniteAnimationSpec<T> = spring(0.88f, 420f)

    override fun <T> slowSpatialSpec(): FiniteAnimationSpec<T> = spring(0.95f, 110f)

    override fun <T> defaultEffectsSpec(): FiniteAnimationSpec<T> = spring(1f, 500f)

    override fun <T> fastEffectsSpec(): FiniteAnimationSpec<T> = spring(1f, 1000f)

    override fun <T> slowEffectsSpec(): FiniteAnimationSpec<T> = spring(1f, 250f)
}

val LocalKurooto = staticCompositionLocalOf { Palettes.apricot.darkK }

/** "Remove animations" (Settings → Accessibility): transitions jump instead of moving. */
fun reducedMotion(c: Context): Boolean =
    try {
        Settings.Global.getFloat(c.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    } catch (e: Exception) {
        false
    }

val LocalReducedMotion = staticCompositionLocalOf { false }

/** Look → Vivid colours (Prefs.vivid), read once per screen: rows and cards stained with the containers when on. */
val LocalVivid = staticCompositionLocalOf { true }

/**
 * Kurooto's theme for a Compose screen, light or dark as the system is (`forceDark`: always dark, the call and bedside
 * screens). `dynamic` (the default): the palette chosen in Look ([Palettes.chosen]); Material You there is the
 * wallpaper's scheme on Android 12+ (Vivid: a richer scheme in the wallpaper's own hue; Calm: Material You's own)
 * and, on older phones, the Vivid scheme from Kurooto's olive (Calm: Kuro), as before 0.8.10. `dynamic = false`: the
 * named `palette` itself (the dev builds' "palette" extra). Motion: Material's expressive springs, or none with "Remove animations".
 */
@Composable
fun KurootoTheme(palette: String = Palettes.DEFAULT, dynamic: Boolean = true, forceDark: Boolean = false, content: @Composable () -> Unit) {
    val c = LocalContext.current
    val dark = forceDark || isSystemInDarkTheme()
    val vivid = Prefs.vivid(c)
    val name = if (dynamic) Palettes.chosen(c) else palette
    val scheme: ColorScheme
    val k: KColors
    if (name == Palettes.YOU) {
        k = Palettes.kuro.let { if (dark) it.darkK else it.lightK }
        scheme = if (Build.VERSION.SDK_INT >= 31) {
            // vivid (0.7.5): a Content scheme from the wallpaper's colour (Kurooto's olive for a grey wallpaper)
            if (vivid) Vivid.scheme(Vivid.seed(dynamicLightColorScheme(c).primary), dark)
            else if (dark) dynamicDarkColorScheme(c) else dynamicLightColorScheme(c)
        } else if (vivid) {
            Vivid.scheme(Vivid.BRAND, dark) // Android 11 and older: no wallpaper colours, so Kurooto's olive
        } else {
            Palettes.kuro.let { if (dark) it.dark else it.light } // ... and Calm there: Kuro itself, as before 0.8.10
        }
    } else {
        val p = Palettes.named(name)
        k = if (dark) p.darkK else p.lightK
        scheme = if (dark) p.dark else p.light
    }
    val reduced = reducedMotion(c)
    CompositionLocalProvider(LocalKurooto provides k, LocalReducedMotion provides reduced, LocalVivid provides vivid) {
        MaterialExpressiveTheme(
            colorScheme = scheme,
            motionScheme = if (reduced) StillMotion else CalmMotion,
            shapes = SHAPES,
            typography = TYPE,
            content = content,
        )
    }
}
