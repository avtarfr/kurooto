package io.github.avtarfr.kurooto

import android.content.Context
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialExpressiveTheme
import androidx.compose.material3.MotionScheme
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

/**
 * The look of the Compose screens (0.7.0): Material 3 Expressive (the expressive motion scheme, emphasized type),
 * coloured by Material You on Android 12+ (from the wallpaper, as before) and by a named palette otherwise. The palettes
 * are the web pages' (src/kurooto/web/static/style.css); "kuro" is the one there is now, with the same values as
 * the colors.xml files in res/values (and values-night), which the framework screens (Ui.java) still use. A new palette is one more entry in
 * Palettes.all; KurootoTheme(palette = "name") picks it.
 * Besides Material's colour roles, a screen gets Kurooto's own through LocalKurooto: ok and bad (the checklist,
 * "Sent." and errors, Kurooto's even with Material You) and whether it's light. The sky behind the screens (Sky)
 * takes its colours from the scheme.
 */
@Immutable
data class KColors(val ok: Color, val bad: Color, val light: Boolean)

/** One named palette: Material's colour scheme and Kurooto's own colours, light and dark. */
@Immutable
data class Palette(val name: String, val light: ColorScheme, val dark: ColorScheme, val lightK: KColors, val darkK: KColors)

object Palettes {
    /** "kuro": dark olive on warm paper, light sage on near-black (the dashboard's default). */
    val kuro = Palette(
        name = "kuro",
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

    /** Every palette by name; the first is the default. */
    val all: Map<String, Palette> = linkedMapOf(kuro.name to kuro)

    fun named(name: String?): Palette = all[name] ?: kuro
}

/** Material's expressive type scale, with its emphasized display and headline styles a step bolder (semibold, not
 *  medium): with the phone's own Roboto rather than Google Sans Flex, medium reads as regular at display sizes. */
private val TYPE = Typography().let { t ->
    fun SB(s: TextStyle) = s.copy(fontWeight = FontWeight.SemiBold)
    t.copy(
        displayLargeEmphasized = SB(t.displayLargeEmphasized),
        displayMediumEmphasized = SB(t.displayMediumEmphasized),
        displaySmallEmphasized = SB(t.displaySmallEmphasized),
        headlineLargeEmphasized = SB(t.headlineLargeEmphasized),
        headlineMediumEmphasized = SB(t.headlineMediumEmphasized),
        headlineSmallEmphasized = SB(t.headlineSmallEmphasized),
    )
}

val LocalKurooto = staticCompositionLocalOf { Palettes.kuro.lightK }

/** "Remove animations" (Settings → Accessibility): transitions jump instead of moving. */
fun reducedMotion(c: Context): Boolean =
    try {
        Settings.Global.getFloat(c.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    } catch (e: Exception) {
        false
    }

val LocalReducedMotion = staticCompositionLocalOf { false }

/** Kurooto's theme for a Compose screen: Material You on Android 12+ when dynamic, else the named palette; light or
 *  dark as the system is. */
@Composable
fun KurootoTheme(palette: String = "kuro", dynamic: Boolean = true, content: @Composable () -> Unit) {
    val c = LocalContext.current
    val dark = isSystemInDarkTheme()
    val p = Palettes.named(palette)
    val k = if (dark) p.darkK else p.lightK
    val vivid = Prefs.vivid(c)
    val (scheme, kk) = if (dynamic && Build.VERSION.SDK_INT >= 31) {
        val s = if (dark) dynamicDarkColorScheme(c) else dynamicLightColorScheme(c)
        // vivid (0.7.5): an Expressive scheme from the wallpaper's colour (Kurooto's olive for a grey wallpaper); Calm: Material You's own
        (if (vivid) Vivid.scheme(Vivid.seed(dynamicLightColorScheme(c).primary), dark) else s) to k
    } else if (dynamic && vivid) {
        Vivid.scheme(Vivid.BRAND, dark) to k // Android 11 and older: no wallpaper colours, so Kurooto's olive
    } else {
        (if (dark) p.dark else p.light) to k
    }
    CompositionLocalProvider(LocalKurooto provides kk, LocalReducedMotion provides reducedMotion(c)) {
        MaterialExpressiveTheme(colorScheme = scheme, motionScheme = MotionScheme.expressive(), typography = TYPE, content = content)
    }
}
